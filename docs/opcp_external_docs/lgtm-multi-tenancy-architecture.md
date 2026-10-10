# LGTM Multi-Tenancy Architecture

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 956661706](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=956661706) (v9, last modified 2026-06-02; mirrored 2026-06-10). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

# ![](https://confluence.ovhcloud.tools/download/attachments/embedded-page/CPO/LGTM%20Multi-Tenancy%20Architecture/lgtm_v2.png?api=v2)

# Multi-Tenant LGTM Stack — How It Works

> **Scope.** One shared **LTM** (Loki / Tempo / Mimir) backend serves multiple **accounts** , each fully isolated. Everything runs in **one k3s cluster** — the control plane and the per-account data planes are just different namespaces (deploy scopes), **not** separate clusters.

## At a glance

  * Each **account** sends and views only its own metrics, logs, and traces.
  * Accounts never see each other's data; the support team sees only platform health (platform account), never account data.
  * **Tenant identity = the Keycloak realm a token comes from.** No separate tenant claim, no static realm list.
  * One enforcement pattern everywhere: a per-plane **Envoy** validates the realm JWT and stamps `X-Scope-OrgID`.



## Cluster layout (planes = namespaces)

Plane| Namespace| Deployed| Purpose  
---|---|---|---  
**Control plane**| `observability-<id>`| once| Shared LGTM backends + platform self-monitoring. In-cluster only.  
**Account data plane**| `<svc>-tenant-<account-id>`| per account| That account's own Grafana + Envoy.  
**Platform plane (support)**| `platform-support`| once| Grafana + Envoy.  
  
## Components

Component| Role  
---|---  
**Accounts (A, B, …)**|  Each has **users** (people opening dashboards) and **agents** (Alloy/OTel shipping telemetry). Each account is its own data-plane deploy (namespace `<svc>-tenant-<account-id>`) with its **own Grafana and own Envoy**.  
**Keycloak**|  One **L3 realm per account**. The realm a token comes from **is** the tenant identity.  
**Grafana**|  The dashboard UI. One per account (login via that account's L3 realm). **No shared Grafana.**  
**Envoy**|  The gatekeeper, **one per plane**. Validates JWTs against **exactly one realm** , strips any client-supplied `X-Scope-OrgID`, and stamps the correct value before forwarding. Account Envoys expose a **public TLS ingress** (remote agents) **plus** a ClusterIP (co-located workloads + local Grafana); the platform Envoy is **ClusterIP-only**.  
**LGTM backends**| **Mimir** (metrics, `:8080`), **Loki** (logs, `:3100`), **Tempo** (traces, `:3200` / `:4318`). ClusterIP only, no public ingress. Tenant isolation via `X-Scope-OrgID`; object-storage data separated per tenant.  
**Object store (MinIO)**|  Shared **S3-compatible** object store backing **all three** backends (Mimir blocks, Loki chunks, Tempo traces), separated by tenant-prefixed paths.  
**Alloy**|  Control-plane self-monitoring. Writes platform telemetry to the backends **directly** as the **`account-platform`** tenant, bypassing Envoy.  
**NetworkPolicy boundary**|  Only **Envoy pods** (any account namespace) **and the control-plane Alloy** may reach the backends. Nothing else has a network path to them.  
  
> **Naming.** Tenant IDs use the `account-*` scheme: `account-a`, `account-b`, and `account-platform` (the platform's own tenant). See _Naming changes applied_ below.

## Envoy path routing

Each Envoy serves a single gateway host and routes by path. **Every route validates the realm JWT and overwrites`X-Scope-OrgID`** with that Envoy's tenant.

Path| Backend  
---|---  
`/loki/…`| Loki  
`/api/v1/push`, `/prometheus/…`| Mimir  
`/v1/traces`, `/api/…`| Tempo  
  
## Workflows

### 1 · Account user views a dashboard (read path)

  1. The user opens their account's Grafana and signs in.
  2. Grafana redirects straight to that account's **L3 realm** in Keycloak (no broker hop); the user authenticates there.
  3. Keycloak issues a token from the `account-a` realm. No tenant claim is needed — the realm itself identifies the tenant.
  4. The user opens a dashboard; Grafana sends the query to its **local Envoy** , forwarding the user's token (`oauthPassThru`).
  5. Envoy validates the signature against that realm's public keys (JWKS), removes any `X-Scope-OrgID` already on the request, and injects `X-Scope-OrgID: account-a`.
  6. The backends return **only Account A's** data.



Grafana → Envoy and Envoy → backends are both in-cluster (ClusterIP).

### 2 · Account agent ships telemetry (write path)

  1. The agent authenticates against its account's **L3 realm** using a service account (`client_credentials` grant) and gets a token.
  2. The agent sends data to that account's **public TLS ingress** (its own Envoy gateway host, e.g. `gateway.account-a.example.com`).
  3. That Envoy's `jwt_authn` trusts **only** the `account-a` realm — a token from any other realm is rejected before it reaches a backend.
  4. Envoy strips any client `X-Scope-OrgID`, stamps `X-Scope-OrgID: account-a`, and routes by path.
  5. The backends write the data under tenant `account-a`.



Enforcement is the **realm binding** , not a hostname-to-vhost map on a shared gateway: each account's Envoy trusts exactly one realm, so an `account-a` token cannot be used against `account-b`'s gateway.

### 3 · Support engineer views platform telemetry (read path)

  1. The engineer opens the **platform Grafana** and signs in.
  2. Grafana redirects to Keycloak's **L3`platform` realm**; the engineer authenticates there.
  3. The engineer opens the "Platform" datasource; the query flows through the **platform Envoy** with the engineer's token, exactly as in Workflow 1.
  4. Envoy P validates against the `platform-account` realm and stamps `X-Scope-OrgID: account-platform`.
  5. The backends return **only platform telemetry** — LGTM's own logs, Keycloak logs, K8s events, ingress, Envoy itself. **No account data is reachable.**



### 4 · Platform telemetry is collected (write path)

Platform self-monitoring is gathered by the **control-plane Alloy** , which writes **directly** to the backends — logs → Loki, metrics → Mimir, traces → Tempo — with a fixed `X-Scope-OrgID: account-platform`. It does **not** go through Envoy and needs no realm token: the NetworkPolicy explicitly permits the control-plane Alloy (alongside Envoy pods) to reach the backends. This is how telemetry from the LGTM internals, Keycloak, ingress, and K8s lands under the `account-platform` tenant.

## Guarantees

Guarantee| How it's enforced  
---|---  
**Account isolation**|  Tenant identity is the realm, cryptographically signed by Keycloak; each account's Envoy stamps its own realm on every request; backends honour the header strictly.  
**No support backdoor**|  Support engineers reach only the `account-platform` tenant, by design. They cannot select or query an account tenant.  
**Write-path enforcement**|  An `account-a` token presented at `account-b`'s gateway is rejected, because each account's Envoy trusts only its own realm.  
**One enforcement point per tenant**|  Every read (Grafana queries) and write (agent telemetry) passes through an Envoy that validates the realm JWT and sets `X-Scope-OrgID`.  
**No network path around Envoy**|  Backends are ClusterIP-only with no public ingress; the NetworkPolicy lets only Envoy pods (any account namespace) and the control-plane Alloy reach them.  
**Cheap onboarding**|  Adding an account is one more data-plane deploy — one L3 realm, one Grafana, one Envoy. No shared realm list or shared gateway config to edit.  
  
* * *

  


  

