# Deprecated: LGTM Multi-Tenancy Architecture

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 956275232](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=956275232) (v6, last modified 2026-06-01; mirrored 2026-06-10). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

latest version: [LGTM Multi-Tenancy Architecture](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=956661706)

# How the multi-tenant LGTM stack works

The platform lets multiple customers each send and view their own observability data (metrics, logs, traces) through a single shared LGTM stack. Customers never see each other's data, and the support team can see the platform's own health without seeing customer data.

## The pieces

  * **Customers (A, B, …)** — each has users (people opening dashboards) and agents (Alloy/OTel shipping telemetry).
  * **Keycloak** — one realm per customer, plus an `operators` realm for support, plus an `sso` broker realm that Grafana talks to.
  * **Grafana** — the dashboard UI. Logs everyone in via OIDC against the broker realm.
  * **Envoy** — the gatekeeper. Validates every JWT and stamps the correct `X-Scope-OrgID` header before forwarding to LGTM.
  * **LGTM stack** — Mimir (metrics), Loki (logs), Tempo (traces). Uses `X-Scope-OrgID` to keep tenants isolated.
  * **Object storage** — shared, with data separated by tenant prefix.



## Workflow 1 — A customer user views a dashboard

  1. The user opens Grafana and signs in.
  2. Grafana redirects to Keycloak's `sso` broker realm. The user is routed to their customer's identity provider and authenticates there.
  3. Keycloak issues a token containing `tenant: customer-a` (stamped by an identity-provider mapper based on which realm they came through).
  4. The user opens a dashboard; Grafana sends the query to Envoy and forwards the user's token alongside it.
  5. Envoy validates the token's signature against Keycloak's public keys, reads the `tenant` claim, removes any `X-Scope-OrgID` the request already carried, and injects `X-Scope-OrgID: customer-a`.
  6. LGTM returns only Customer A's data.



## Workflow 2 — A customer agent ships telemetry

  1. The agent authenticates against its customer's Keycloak realm using a service account (`client_credentials` grant) and gets a token.
  2. The agent sends data to a customer-specific endpoint, e.g. `customer-a.lgtm.example.com`.
  3. Envoy's virtual host for that hostname only accepts tokens from the `customer-a` realm. A token from any other realm is rejected.
  4. Envoy hardcodes `X-Scope-OrgID: customer-a` for that hostname — the hostname _is_ the tenant — and forwards to LGTM.
  5. LGTM writes the data under tenant `customer-a` in object storage.



## Workflow 3 — A support engineer views platform telemetry

  1. The engineer opens Grafana and signs in.
  2. Grafana redirects to the broker realm; the engineer authenticates via the `operators` identity provider.
  3. Their token carries `tenant: _platform`.
  4. They open the "Platform" datasource. Queries flow through Envoy exactly as in Workflow 1, but with `X-Scope-OrgID: _platform`.
  5. LGTM returns only platform telemetry — LGTM's own logs, Keycloak logs, K8s events, ingress, Envoy itself. **No customer data is reachable.**



## Workflow 4 — Platform agents ship platform telemetry

Same as Workflow 2, but the agent uses a service account in the `operators` realm and writes as the `_platform` tenant. This is how we collect telemetry from LGTM internals, Keycloak, ingress, K8s, etc.

## Workflow 5 — Break-glass (Keycloak is down) - **Not yet decided**

If Keycloak is unreachable, normal OIDC login won't work. The local Grafana admin account remains available as a fallback. It can only see the `_platform` datasource, which authenticates to Envoy with a static bearer token mapped to the `_platform` tenant. Same blast radius as a regular support session — no "see everything" power.

## Guarantees this gives us

  * **Customer isolation.** A customer cannot reach another customer's data. The tenant identity is cryptographically signed by Keycloak; Envoy enforces it on every request; LGTM honours the header strictly.
  * **No support backdoor.** Support engineers only have access to the `_platform` tenant. They cannot query customer data, by design.
  * **Routing-layer enforcement on writes.** A token from `customer-a` presented at `customer-b.lgtm.example.com` is rejected before it ever reaches LGTM, because the hostname requires the matching realm.
  * **One enforcement point.** Envoy validates both the read path (queries from Grafana) and the write path (telemetry from agents). There is no way to bypass it without bypassing the network.



  


![](https://confluence.ovhcloud.tools/download/attachments/embedded-page/CPO/Deprecated:%20LGTM%20Multi-Tenancy%20Architecture/lgtm-multitenancy-envoy.drawio.png?api=v2)
