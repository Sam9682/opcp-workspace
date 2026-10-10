# Object Storage on CloudStore — Milestones

> Proposed 2026-05-21. Mirrors the proven Compute & Block cadence (Install → use → SNC parity → air-gapped) — a familiar shape for reviewers, and it sequences risk well: **infra first, then customer value, then compliance, then air-gap.** Each milestone has a dedicated walk-through subpage.

| Milestone | Theme | One-liner |
|---|---|---|
| **M1** | Infra Deployment | Package turns ≥4 empty bare-metal nodes into a healthy, scalable Ceph + RGW cluster. |
| **M2** | Activation for Customer | Per-account activation; users self-serve S3 credentials + buckets, with quotas (compliance-deferred beta). |
| **M3** | SNC Ready | SecNumCloud parity — admin/user separation, S3 proxies, encrypted buckets, audited access. |
| **M4** | Air-gapped | Offline operation; the IT-Admin owns lifecycle, capacity monitoring + hardware ordering. |

---

## Milestone 1 — "Infra Deployment"

![M1 · Infra Deployment](user-stories/visuals/os-m1-visual.png)

> **As an IT-Admin**, I select a pool of ≥4 empty bare-metal nodes and activate the Service, so the Package provisions a healthy Ceph + RGW cluster — via the OpenStack API, with no manual Ironic/Ceph work.

**Reached at the end:** `oss-cp` stands up and drives the OpenStack API (Nova bare-metal flavor → Ironic, Neutron, golden image) to build a dedicated Ceph + RGW cluster (`HEALTH_OK`), with scale-in/out and a health + capacity view.

→ [**Full M1 walk-through**](user-stories/M1-infra-deployment.md)

---

## Milestone 2 — "Activation for Customer" *(compliance-deferred beta)*

![M2 · Activation for Customer](user-stories/visuals/os-m2-visual.png)

> **As an IT-Admin**, I activate the App for an Account, so an end user can self-serve S3 credentials, account-segmented buckets, and objects via the Landing Zone.

**Reached at the end:** the identity chain (dedicated Keystone fronting RGW, federated to the CloudStore Keycloak) + the S3 credential middleware + BL-driven quotas are live; an end user creates a key (secret once), makes buckets, and uploads objects — endpoints direct, no proxies yet.

→ [**Full M2 walk-through**](user-stories/M2-activation-for-customer.md)

---

## Milestone 3 — "SNC Ready"

![M3 · SNC Ready](user-stories/visuals/os-m3-visual.png)

> **As the platform**, I enforce SecNumCloud requirements — admin/user audience separation, encrypted buckets, audited access — so the product is qualification-ready.

**Reached at the end:** S3 traffic flows through the SNC proxy stack (L2/L3 separation + WAF), the admin/user 2-Keystone split sits on the M2 chain, per-bucket encryption is keyed via OKMS, and access is audited to LDP/Wazuh.

→ [**Full M3 walk-through**](user-stories/M3-snc-ready.md)

---

## Milestone 4 — "Air-gapped"

![M4 · Air-gapped](user-stories/visuals/os-m4-visual.png)

> **As an IT-Admin**, I run and grow the Service entirely offline — and own capacity monitoring + hardware ordering — with the responsibility boundaries made explicit. *(Mostly an L2 milestone; the L3 end user is unaffected.)*

**Reached at the end:** the Service deploys + operates with zero external dependencies (local Harbor, OS/firmware mirrors, offline upgrades, local IdP fallback); the L2 IT-Admin owns the lifecycle + capacity + ordering, with the legal/SLA shift documented.

→ [**Full M4 walk-through**](user-stories/M4-air-gapped.md)

---

## Feature availability by milestone

> Side-by-side: which feature lands when. Cumulative — once a feature lands, it stays ✅ for all later milestones.
>
> **`✅`** = available · **`✅ basic` / `✅ full`** = present but enhanced in a later milestone · **`—`** = not available · **`🚩`** = at risk / pending decision.

| Feature | **M1**<br/>*Infra* | **M2**<br/>*Activation* | **M3**<br/>*SNC* | **M4**<br/>*Air-gapped* |
|---|:-:|:-:|:-:|:-:|
| **Infrastructure (Ceph data plane)** | | | | |
| Empty bare-metal → Ceph hosts via OpenStack (Nova BM flavor → Ironic) | ✅ | ✅ | ✅ | ✅ |
| Dedicated Ceph cluster + RGW (co-located on the nodes) | ✅ | ✅ | ✅ | ✅ |
| Replication / Erasure-Coding (3:2) pool options | ✅ | ✅ | ✅ | ✅ |
| Cluster scale in / out | ✅ | ✅ | ✅ | ✅ |
| Per-bucket encryption (OKMS / KMIP) | — | — | ✅ | ✅ |
| Offline scale-out from local artifacts | — | — | — | ✅ |
| **Control plane (oss-cp · L2)** | | | | |
| CloudStore Package runner (FluxCD + Terraform) | ✅ | ✅ | ✅ | ✅ |
| Provisioning engine (BM → Ceph + day-2 lifecycle) | ✅ | ✅ | ✅ | ✅ |
| Dedicated Keystone (fronts RGW for S3 auth) | — | ✅ | ✅ | ✅ |
| Keystone ↔ CloudStore-Keycloak federation | — | ✅ | ✅ | ✅ |
| S3 credential middleware (temp + permanent keys) | — | ✅ | ✅ | ✅ |
| Business Logic (account activation · quota · usage) | — | ✅ | ✅ | ✅ |
| S3 proxies (L2/L3 audience separation + WAF) | — | — | ✅ | ✅ |
| 2-Keystone admin/user split | — | — | ✅ | ✅ |
| Observability (cluster health + capacity %) | ✅ basic | ✅ basic | ✅ full | ✅ full |
| Audit feed → LDP / Wazuh | — | — | ✅ | ✅ |
| **End-user surface (L3)** | | | | |
| Create S3 access keys (secret shown once) | — | ✅ | ✅ | ✅ |
| Account-segmented buckets (create / manage) | — | ✅ | ✅ | ✅ |
| Object upload / download (drag-and-drop) | — | ✅ | ✅ | ✅ |
| Bucket versioning + lifecycle | — | ✅ | ✅ | ✅ |
| Static-website hosting per bucket | — | ✅ | ✅ | ✅ |
| Object HTTP-header config (Content-Type / Cache-Control / …) | — | ✅ | ✅ | ✅ |
| Per-account cost / usage view | — | ✅ | ✅ | ✅ |
| Encrypted buckets (visible to user) | — | — | ✅ | ✅ |
| S3 endpoints fronted by proxies | — | — *(direct in M2)* | ✅ | ✅ |
| **Admin / operations (L2)** | | | | |
| Per-account activation + quota | — | ✅ | ✅ | ✅ |
| Price-per-GB + feature-flag config | — | ✅ | ✅ | ✅ |
| Cross-account + cluster admin views | — | — | ✅ | ✅ |
| Cluster lifecycle (scale / upgrade / replace) | — | — | — | ✅ |
| Capacity monitoring + hardware ordering (customer-owned) | — | — | — | ✅ |
| **SNC / compliance** | | | | |
| Admin/user audience separation | — | — | ✅ | ✅ |
| Per-bucket encryption (OKMS) | — | — | ✅ | ✅ |
| Audit logging | — | — | ✅ | ✅ |
| WAF | — | — | ✅ | ✅ |
| **Air-gapped operations** | | | | |
| Local Harbor + OS / firmware mirrors | — | — | — | ✅ |
| Offline upgrades | — | — | — | ✅ |
| Local IdP fallback | — | — | — | ✅ |
| Legal / SLA responsibility shift documented | — | — | — | ✅ |

> **How to read this:** if you're "at" milestone N, you have everything ✅ in the M1 … MN columns. M2, for example, gives you a usable beta (buckets + credentials + quotas) but **not** the proxies, 2-Keystone split, or per-bucket encryption — those land in M3.

---

## Refinement worth a decision (mirrors CB)

In CB, **M2 was an API-only Beta** — proxies + full SNC compliance were deferred to M3, which de-risked the date. The same cut fits here: make **M2 "Activation" a compliance-deferred beta** (direct endpoints, no proxies, single-Keystone-acceptable), and let **M3 "SNC Ready"** bring the 2-Keystone split + proxies + KMS. That keeps M1+M2 a shippable beta and concentrates the compliance work in M3.

> **Open:** exact per-milestone scope cut (esp. what's in M2 beta vs M3 compliance) firms up once the architecture proposal + the "what's manual in SNC today" inventory exist. See [open-questions](open-questions.md) + the [`oss-cp` component inventory](architecture/oss-cp-components.md).
