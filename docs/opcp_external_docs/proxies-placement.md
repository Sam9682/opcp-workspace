---
id: compute-block-on-cloud-store/architecture-proxies-placement
type: deep-dive
diataxis: explanation
title: "Proxies placement — Decision #1 follow-up"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Proxies placement — Decision #1 follow-up

> ⚠️ **SUPERSEDED** by [`what-goes-where.md`](what-goes-where.md), [`Decision-2026-05-09b`](../decisions.md), and **SNC ADR 0046 *Proxies deployment* (ACCEPTED Feb 2026)** — which itself deprecates SNC ADR 0011 / 0030 / 0042.
>
> The architecture board's placement (visible on `drawings/2026-05-09_what-goes-where.png`) is: **all 6 SNC proxy groups + proxy-redis live in cbs-cp** (the vm-bs-service control plane), provisioned by the `cloudstore-vm-bs-service` CloudStore Service. *No* proxy lives in cs-cp directly.
>
> **2026-05-19 update — SNC ADR 0046 changes the deployment model.** The earlier "stateless proxy VMs provisioned via Terraform + golden image" pattern (the original `paas-snc-proxy-tf` shape) is replaced by **"one Kubernetes cluster per proxy group"**. The placement-in-cbs-cp decision still holds; the deployment substrate becomes K8s clusters rather than VMs. Q-217 → Q-224 + Q-242 → Q-244 in [`open-questions.md`](../open-questions.md) need re-baselining against the K8s-per-group model before the M3 Proxy Architecture Session.
>
> For the **full implementation breakdown** see [`Proxies Deep Dive`](../../../../opcp-core/architecture/conceptions/proxies/summary.md) — note: that doc is still framed against the VM model; banner there flags the same ADR 0046 transition.
>
> Full ADR cross-mapping with impact analysis: [`snc-adr-alignment-2026-05-19.md`](../plans/snc-adr-alignment-2026-05-19.md) (PM-private).
>
> The original draft below is kept for historical context only — it captures the reasoning we tried before the diagram landed.

---

> **Status:** **DRAFT** by Claude on 9 May 2026. First-pass guesses with reasoning, ready to be overwritten by architecture-board decisions. Format the table as you fill it in; remove this banner once decided.

## Context

**Decision #1 (May 9, 2026):** SNC's six proxy groups are brought into the OPCP / CloudStore architecture, **distributed**: some live as a CloudStore *Service* (marketplace, optional, per-customer), others as a CloudStore *Core Service* (always-on, baked into `cs-install`).

The mapping question is **per proxy group**:

- Is this proxy *always* needed for any OPCP install (→ Core Service), or is it conditional on what the customer is running (→ Service)?
- Where does its **token-attribution Redis** sit?
- How does it expose itself (Kubernetes Ingress through Traefik like other Core Services? VM-based like SNC today? Hybrid?)
- What's the failure-domain implication?

## SNC's six proxy groups recap

```
                 GLOBAL                       REGIONAL                   DATA PLANE
                 ──────                       ────────                   ──────────
   ┌───────────────────────────┐  ┌───────────────────────────┐  ┌─────────────────────────────┐
   │ Global L2 Proxy           │  │ Regional L2 Proxy         │  │ Data Plane L2 Proxy         │
   │  · admins → Business      │  │  · admins → OpenStack     │  │  · object storage admin →   │
   │    Logic API, Admin Panel,│  │    endpoints              │  │    RGW (L2) on port 7491    │
   │    Keycloak L2, Cloud     │  │  · admin SNC Panel        │  │                              │
   │    Panel, SNC Panel       │  │                           │  │                              │
   └───────────────────────────┘  └───────────────────────────┘  └─────────────────────────────┘
   ┌───────────────────────────┐  ┌───────────────────────────┐  ┌─────────────────────────────┐
   │ Global L3 Proxy           │  │ Regional L3 Proxy         │  │ Data Plane L3 Proxy         │
   │  · org admin → user mgmt, │  │  · end user → OpenStack   │  │  · end user → RGW (L3)      │
   │    sign-up, credentials,  │  │    endpoints, Cloud Panel │  │    on port 7490             │
   │    Keycloak L3            │  │                           │  │                              │
   └───────────────────────────┘  └───────────────────────────┘  └─────────────────────────────┘
                                       Redis (token attribution) lives in the PaaS-SNC control planes
                                       — global Redis for global proxies, regional Redis for regional ones
```

Full architectural detail in [`SNC Cloud Platform Deep Dive/summary.md` § 3.6](../../../../snc-cloud-platform/architecture/conceptions/snc-cloud-platform/summary.md).

## My first-pass guess (to be torn apart)

| # | Proxy group | Service or Core Service? | Why | Redis lives where? | Open question |
|---|---|---|---|---|---|
| 1 | **Global L2** | **Core Service** | Every OPCP install needs an admin path to its own CloudStore; sign-up / Keycloak L2 is intrinsic to running the platform at all. | CloudStore cluster (CNPG-like operator, replicated within the OPCP). | When does "Global" exist for a *single* OPCP at all? In single-OPCP world there's no global vs regional split — collapse to one until multi-AZ ships. |
| 2 | **Global L3** | **Core Service** | Same — sign-up, account creation, credential management is platform-intrinsic. Today's CloudStore API + Temporal already does this; the proxy is the network-level enforcer of "no L2 creds via L3 endpoint". | Same CloudStore cluster. | If the CloudStore API + `cloudstore.yaml`-permission model already enforces audience separation at the application layer, do we *also* need a proxy-level enforcement? Belt-and-braces or redundant? |
| 3 | **Regional L2** | **Service** (or "CloudStore-attached but conditional") | Only present when an OpenStack-backed service exists. Single-OPCP world doesn't have regions; multi-AZ ships this back into relevance. | Regional cluster Redis (CloudStore local Postgres? CNPG existing instance?). | Naming: "Regional" doesn't fit single-OPCP. Rename to something like "OpenStack-front" until multi-AZ. |
| 4 | **Regional L3** | **Service** | Comes with the VM Service (or any OpenStack-backed service). | Same as #3. | Same as #3. |
| 5 | **Data Plane L2** | **Service** (bundled with Object Storage Service) | Tightly coupled to the RGW / S3 product; not needed if Object Storage isn't installed. | Object Storage Service's own infra (could be in the Object Storage Service's namespace). | Out of V1 scope — defer to Object Storage track but document the contract now. |
| 6 | **Data Plane L3** | **Service** (bundled with Object Storage Service) | Same. | Same as #5. | Same as #5. |

### Net effect

- **Core Services**: Global L2 + Global L3 — sit in the CloudStore cluster, always-on, ship with `cs-install`.
- **Services**: Regional L2 + Regional L3 (bundled with VM/OpenStack Service); Data Plane L2 + Data Plane L3 (bundled with Object Storage Service).
- **Single-OPCP simplification**: in a non-multi-AZ install, Global and Regional collapse — there's only one "L2 proxy" and one "L3 proxy" until multi-AZ ships, at which point the regional ones reappear.

## Reasoning behind the split

Two principles drive the guess:

1. **Audience separation is a platform concern, capacity-front-ending is a service concern.** The Global L2/L3 proxies enforce *who can log in where* — that's intrinsic to running the platform regardless of which services are installed. The Regional and Data Plane proxies enforce *audience-correct routing into a specific backend* — they only exist when that backend exists.
2. **Don't make customers install proxies for services they don't use.** A customer who installs OPCP without Object Storage shouldn't have S3 RGW proxies running. Bundle proxy + backend so they ship together.

## Implementation-shape implications

If this guess holds:

- CloudStore *Core Service* implementations of Global L2/L3 proxies look like the existing core services (Helm chart + Terraform, packaged via `make generate_package`, but conceptually a Core Service). They run as Kubernetes pods (not VMs like today) with Traefik / Cilium for ingress and CNPG-or-Redis for token state.
- CloudStore *Services* implementations of Regional L2/L3 + Data Plane L2/L3 are bundled into the VM Service and the Object Storage Service respectively. The Service's `cloudstore.yaml` declares the proxy as part of the service.
- **VM-based proxies (today's SNC implementation) become Kubernetes-pod-based proxies.** This is itself a non-trivial migration. Existing single-instance limitations (today's SNC proxies are single-instance VMs) flip into k8s-native HA with multiple replicas + a shared Redis.

## Risks / red flags

- **Redis state migration** — today the proxies use external Redis in the PaaS-SNC control planes. If we move proxies into CloudStore, the Redis topology has to move too. CNPG vs a dedicated Redis-Operator vs reuse-Cloud-Store's-Postgres needs a call.
- **Belt-and-braces vs redundant** — if the CloudStore API + `cloudstore.yaml` permission model already enforces L2/L3 audience separation, the proxy might become redundant for the CloudStore path. SNC's audit may still demand the network-layer enforcement; **double-check with the SNC PU before consolidating**.
- **Name confusion** — "Global L2 proxy" inside a single-OPCP CloudStore install reads weird. Pick a name now ("CloudStore admin proxy" / "CloudStore user proxy"?) before code lands.
- **Failure domain coupling** — today the proxies are single-instance VMs (SPOF acknowledged in the deep dive). Moving them into the CloudStore cluster gives us k8s-native HA *for free*, which is a win — but it also couples their availability to the cluster's. Validate this is OK with the SNC PU.

## Decisions needed (route back to the architecture board)

For each row in the table above:
1. Is the Service / Core Service guess correct?
2. Where does Redis live?
3. What's the proxy's official name?
4. Who owns the package? (CloudStore team? OPCP Core team? SNC team?)

Plus the cross-cutting:
5. Do we collapse Global + Regional in single-OPCP installs, or keep both names from day one?
6. Do we keep proxy-level audience enforcement when application-level enforcement already exists? (SNC qualification angle.)
7. Where does Redis topology decision live — this doc, or its own ADR in `decisions.md`?
