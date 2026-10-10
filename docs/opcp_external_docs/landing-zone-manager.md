---
id: core/landing-zone-manager
type: reference
diataxis: explanation
title: "Landing Zone Manager — the end-user portal (L3)"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Landing Zone Manager — the end-user portal (L3)

> **The pitch:** *"Your cloud, on demand."* Landing Zone Manager (LZM) is the **end-user portal** of the OnPrem Cloud Platform — the self-service web UI through which a developer, data scientist, or business team actually *uses* the cloud services that the IT-Admin enabled for their Account.
>
> **Source:** [ovhcloud.com/fr/hosted-private-cloud/onprem-cloud-platform/landing-zone-manager](https://www.ovhcloud.com/fr/hosted-private-cloud/onprem-cloud-platform/landing-zone-manager/) — public product positioning.

![Landing Zone Manager — the end-user portal (L3): the End-User personas above (Developer · Data Scientist · DevOps · Business · Internal Tools), the End User's interaction surfaces (Portal · Horizon · APIs+SDKs · Visibility/governance), self-service actions in a Landing Zone (VMs · Volumes · K8s · Buckets · DBs · Invite/RBAC), per-Account tenancy primitives (Keystone domain · federation · Keycloak L3 · project · creds · quotas · audit), the LZ lifecycle + federated identity flow, with L2 Cloud Store and L1 OPCP Core compressed below](../../shared/illustrations/illiu%20-%20l3.png)

---

## Basics

### What Landing Zone Manager is, in one paragraph

Landing Zone Manager is the **face of OPCP for the End User**. It's a self-service portal where a developer logs in, sees the services their Account has access to (VMs, volumes, K8s clusters, object buckets, databases, AI endpoints, …), and provisions them inside an isolated **Landing Zone** that already has the right network, identity, quotas, and audit context wired up. There is no ticket queue, no request-and-wait — provisioning is one form, one click, immediate.

### What is a "Landing Zone"?

A Landing Zone is a **pre-paved, governed environment** carved out for a team or project inside the customer's OPCP. It comes with:

- **Identity** — federated to the customer's IdP via Keycloak L3
- **Network** — its own VPC / subnets / routing isolated from other Landing Zones
- **Quotas** — compute, storage, network limits set by the IT-Admin
- **Policies** — what the team can deploy, where, with which tags
- **Audit slice** — every action recorded into the team's own audit trail

The team operates *inside* the Landing Zone with full self-service. The IT-Admin operates *on* the Landing Zone — defining what is and isn't allowed there.

### Who uses it

The **L3 End User** persona — see [Concepts → L1 / L2 / L3 model](../../shared/l1-l2-l3-model.md). A developer, data scientist, business-app team, internal-tool builder. They typically have no platform expertise — they want a VM, a database, a bucket, a K8s namespace, and they want it now.

### How LZM relates to the rest

```
   ┌──────────────────────────────────────────────────────┐
   │  END USER (L3)  ──>  Landing Zone Manager portal     │  ← this page
   │                          │                           │
   │                          ▼                           │
   │                 OpenStack / K8s / S3 APIs            │
   │                 (per-Account, isolated)              │
   └──────────────────────────────────────────────────────┘
                                │
   ┌─── (services made available by IT-Admin via) ────────┐
   │           CLOUD STORE  (L2 service catalogue)        │
   └──────────────────────────────────────────────────────┘
                                │
   ┌─── (running on) ─────────────────────────────────────┐
   │                  OPCP CORE (L1 substrate)            │
   └──────────────────────────────────────────────────────┘
```

LZM is **always present** as a Cloud Store Core Service — every OPCP deployment includes it.

---

## Features

### Self-service, on demand

- **Provision a VM** — pick a flavor, image, network, volume — created in seconds
- **Attach a volume** — Standard / High / Insane tiers (where the service is enabled)
- **Spin up a Kubernetes cluster** — or a namespace inside a shared one, depending on the service the IT-Admin enabled
- **Create an object bucket** — S3-compatible, with credentials immediately available
- **Request a managed database** — Postgres, MySQL, etc., per the catalogue
- **Deploy an AI endpoint** — when GPU + AI services are enabled

### Multiple consumption paths

The portal is the default surface, but it's **not the only one**. End Users can drive the same Landing Zone via:

- **Web UI** (LZM itself) — the obvious entry point
- **OpenStack Horizon** — for users who already live in Horizon
- **OpenStack API / CLI / SDKs** — for IaC tooling (Terraform, Pulumi, …)
- **Kubernetes API** — for K8s-native workflows
- **S3 API** — for object workflows

All paths terminate at the same per-Account isolation; choosing one doesn't get you a different cloud.

### RBAC + per-Account governance

- **Roles within a Landing Zone** — owner, editor, viewer, operator, billing, etc.
- **Federated identity** — sign in with the customer's existing IdP (SAML / OIDC) via Keycloak L3
- **Quota enforcement** — visible to the End User; predictable failures, not silent throttling
- **Tag policies** — IT-Admin can require certain tags (cost-centre, environment, owner) and the portal enforces them at create time

### Multi-tenant isolation

Each Account gets its own Keystone domain, network space, identity realm, audit log, and quotas. **Cross-Account leakage is structurally prevented** at the platform layer, not policy-enforced at the UI layer.

### Visibility for the user

- **Resource inventory** — every VM, volume, bucket, cluster the team owns, in one view
- **Usage + quota** — current consumption vs limits
- **Cost / chargeback hooks** — where the customer wires in their accounting system
- **Per-resource activity log** — who did what, when

### Catalogue tiles match enabled services

The set of tiles the End User sees is **derived from what the IT-Admin enabled for their Account** through Cloud Store. Enable Compute → "VMs" appears. Enable Object Storage → "Buckets" appears. Disable a service → the tile disappears, with no broken links.

---

## Solutions

The four problem areas LZM is positioned against:

### 1. "Our developers wait days for a VM"

The traditional ticket-driven on-prem provisioning model dies here. Self-service portal + per-Account isolation + pre-set quotas means the developer self-serves in seconds, the IT team is no longer a bottleneck, and governance is enforced at the platform layer instead of by manual review.

### 2. "We need governance without slowing teams down"

Quotas, RBAC, tag policies, network isolation, audit are configured *once per Landing Zone* by the IT-Admin and then automatically enforced for every End-User action. The team gets self-service; the platform team gets guardrails. **Governance lives in the platform, not in tickets.**

### 3. "We need multiple teams on shared hardware without them stepping on each other"

Per-Account Keystone domains, network spaces, quotas, and audit slices give every team a slice of the platform that *feels* like its own private cloud, while the underlying hardware is shared and the platform team operates one OPCP, not N forks.

### 4. "We need an interface our non-platform people can actually use"

The LZM UI is built for End Users, not platform engineers. Tiles for the things they want, forms with sensible defaults, immediate feedback. Power users can drop into Horizon or the APIs at any time — but the portal works without them.

---

## Processes

How a Landing Zone moves through its lifecycle, from creation to daily use.

```
   ── L2 PHASE (IT-Admin) ───────────────────────────────────────────────
   │  1. Create Landing Zone for team X                                 │
   │  2. Enable services (Compute, Object, K8s, …) for the Account      │
   │  3. Set quotas, RBAC, tag policies, network plan                   │
   │  4. Federate the team's IdP (SAML/OIDC) via Keycloak L3            │
   │  5. Hand the URL + first-admin invite to the team owner            │
   ───────────────────────────────────────────────────────────────────────
                                  │
                                  ▼
   ── L3 PHASE (End User) ───────────────────────────────────────────────
   │  6. Team owner logs in, invites colleagues, assigns roles          │
   │  7. End Users provision resources via portal / API / Horizon       │
   │  8. Tagging + quota enforced live; audit captured automatically    │
   │  9. Team consumes the platform like any public cloud               │
   ───────────────────────────────────────────────────────────────────────
                                  │
                                  ▼
   ── ONGOING ──────────────────────────────────────────────────────────
   │  Adjust quotas · add/remove services · rotate access · archive    │
   │  the Landing Zone when the team disbands                          │
   ───────────────────────────────────────────────────────────────────────
```

### The four operational loops

1. **Landing Zone creation**
   IT-Admin in Cloud Store: "new Landing Zone for team X" → underlying data-plane modules of the relevant Cloud Store services run → Keystone domain + federation + initial project + quotas materialise → LZM tile becomes accessible to the team's identity.

2. **End-User self-service**
   End User logs in → sees the catalogue tiles their Account has → provisions VM / volume / bucket / cluster → gets working credentials + endpoints → uses them. **No human in the loop on the IT side.**

3. **Governance + audit**
   Every action is captured into the Account's audit trail. Quotas + tag policies are enforced at create-time. The IT-Admin can answer "who created what, in which Landing Zone, when, with which tags" from the platform's audit interface — without walking the team's logs.

4. **Lifecycle changes**
   Team grows → IT-Admin raises quotas. Team needs a new service → IT-Admin enables it on the Account, the new tile appears for the team. Team disbands → IT-Admin archives the Landing Zone, resources are reclaimed, audit history is preserved per retention policy.

### What LZM does NOT do

- It does not provision bare metal — that's [OPCP Core](../opcp-core/README.md).
- It does not install or upgrade services — that's [Cloud Store](README.md), driven by the IT-Admin.
- It does not bypass quotas or governance — guardrails set by the IT-Admin are enforced for every End-User action.

---

## Where to go next

- **OPCP Core** — the L1 substrate underneath everything → [`opcp-core.md`](../opcp-core/README.md)
- **Cloud Store** — the L2 catalogue that LZM exposes to End Users → [`cloud-store.md`](README.md)
- **OPCP umbrella product** — back to the three-layer overview → [`opcp-overview.md`](../opcp-core/overview.md)
- **L1 / L2 / L3 model** — the persona model that the portal embodies → [Concepts → L1 / L2 / L3 model](../../shared/l1-l2-l3-model.md)
