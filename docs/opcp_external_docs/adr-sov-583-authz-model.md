---
id: core/adr-sov-583-authz-model
type: decision
diataxis: n/a
title: "ADR SOV-583 — Merge IAM / BL Design in cloudstore (authorization model)"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# ADR SOV-583 — Merge IAM / BL Design in cloudstore (authorization model)

> **Distilled from the Confluence ADR `[SOV-583] Merge IAM / BL Design in cloudstore`** (pageId 936727959, PDF export 2026-06-09). Cross-cutting **cloudstore-wide IAM/authorization** decision — affects every service (VM, S3/Object Storage, MKS, VCF, KMS) across all regions, and therefore CB, Object Storage, and Network Service alike.

| | |
|---|---|
| **ADR** | SOV-583 — Merge IAM / BL Design in cloudstore |
| **Create / Closed** | 30 Apr 2026 → **09 Jun 2026** |
| **Decision** | **Option 4 — Fine-grained unified authorization** |
| **Status** | ✅ **Decided — Jira SOV-583 = Done** (verified 2026-06-10). The Confluence page's status field still said "Proposed" at distill time (2026-06-09) — page-field lag, not an open decision. |
| **Deciders** | Nathan Malo · Charly Gregoire · Ibrahim Takouna · Pierre-Yves Aillet |
| **Attendees** | Charly Gregoire · Ibrahim Takouna · Thomas Wiebe · Damien Rannou · Carsten Dittmann · Nathan Malo |

---

## Context

The cloudstore exposes several **services** (vm, s3, mks, vcf, kms), each with its own API/backend/role-catalog, across multiple **regions**, for customers (accounts/realms) that organise workloads into **projects**. The model needs:

- a customer (account) holds multiple isolated **projects**; per-project roles (member/reader) **and** per-service roles (vcf, s3);
- heterogeneous services + regions — **not all services are OpenStack/Keystone-based**, not all regions offer the same services;
- a stable boundary for billing, quotas, resource ownership;
- Keycloak as the IAM engine — BL/UX must translate a Policy/Role assignment into Keycloak group/role structure.

**The two pre-existing models that had to be reconciled:**
- **Current cloudstore Keycloak** uses **client-role** assignment on a group (e.g. `vcf`) — the *service* decides access. = **service-access control**.
- **PaaS SNC** uses **group-attributes** to grant `(project, region)` scope (member/reader), via a Keycloak **client per (keystone, region)** + a mapper that aggregates `project-{region}` attributes into the JWT. = **resource-access control**.

→ Two tiers: **service access** (client-role: can the user use the service at all, + privilege admin/user) vs **resource access** (group-attribute: which project/region/scope + member/reader). Plus a leakage concern: if `vm` and `mks` share the same OpenStack project, a user granted via one service can see/manage resources of the other (as in OVH public cloud).

**Key model invariants chosen:** projects are **region-independent**; project **name unique per realm + identical across all regional Keystone domains**, but **UUID differs per region**; no two projects with same name/id in one domain.

## Options considered (group-count for P=100, R=3, S=5, Rs/k=2)

| Opt | Name | Idea | Groups/realm | Key trade-off |
|---|---|---|---|---|
| 1 | One-track (unified) | every service granted via project-region membership; even non-project services forced into project scope (pseudo-projects) | ~600 | simple grant, SNC-compatible · **no per-(project,service) granularity** |
| 2 | Two-track | `/projects/...` (project-scoped: vm,s3 via group-attr) + `/services/{svc}/` (non-project: vcf via client-role) | ~580 | clean scope split, vcf has a real home · still no per-(project,service) for project-scoped |
| 3 | Three-track (region separate) | service · project · region each independent dimension | ~213 (smallest) | cheap region mgmt + easy region audit · **loses per-(project,region) granularity** |
| **4** | **Fine-grained unified ✅** | **per-(project,region,service) granularity** via a new Keycloak mapper + a client per (service,region) | **~3,201 (largest)** | full granularity + structurally-isolated tokens · highest group count |

## Decision — Option 4: Fine-grained unified authorization

Based on a **new Keycloak mapper `OpcpProjectGrantsMapper`** (already a **working prototype**), using the standard Keycloak **client-role** mechanism:

- **Per-(project, region, service) granularity.** Projects are global (no region in the project itself); **regions live under projects**, **services live under regions**, **roles/teams under that**.
- **One Keycloak client per (service, region)**, naming `{service}-region-{region}` (S×R = 15 clients for 5×3). Each has its own mapper instance emitting a JWT with **only that (service, region)'s grants**. Client roles named `{service}.{role}` (e.g. `vm.member`).
- **Two-layer check in the mapper:** *Layer 1* — is the `(region, service)` active (group attr `enabled="true"`)? *Layer 2* — what roles does the user hold (group membership + `{service}.{role}` client-role)? A grant appears in the token **only when both layers permit**.
- Token keeps the **Keystone-shaped JSON `projects`** string + `roles` (supports OpenStack-based services *and* others like vcf). The client-role **replaces** the error-prone project-attribute JSON string for the project/role mapping.
- **Project auto-creation disabled** — BL creates the project in the target region(s) on grant.
- Role unification across services (a general writer/reader) is **still open** — for now the mapper keeps each service's existing roles.

**Group structure:**
```
projects/{project}/regions/{region}[enabled]/services/{service}[enabled](../../../../kb/deep-dives/business-logic-iam/quota,billing_tier)
                                            /teams/{team}  → assigned {service}.{role} client-roles
```

## Consequences

- **Pro:** per-(project,region,service) granularity preserved; cross-service/cross-region grants **structurally impossible at token issue** (each client mapper only sees its own scope — a `vm-region-par` token never carries s3 grants, even if the team holds both); soft-disable via `enabled="false"` is non-destructive; uniform role catalog possible; drops the error-prone project-attribute JSON; close to PaaS SNC structure; prototype already exists.
- **Con / open follow-ups:**
  - **Highest group count** (~3,201/realm) — mitigated by **lazy/on-demand** creation of project/region/service subtrees + clients.
  - ⚠️ **Cross-region/cross-service token reuse is NOT rejected at the consumer.** A valid `vm-region-par` token can be replayed against the wrong region's endpoint (e.g. keystone-GRA) because the consumer (Keystone) does not validate JWT **audience** or **region**. **Proposed fix: enforce Keystone region / JWT-audience validation.** → *open security follow-up.*
  - **Role unification across services (writer/reader)** still to be agreed.
  - Region audit is per-project (`/projects/*/regions/par/teams/*`), no single global region group (unlike Option 3).

## Implications for OPCP / the projects

- **All services adopt `{service}.{role}` client-roles** per (service, region): `vm.member`, `s3.objectstore_member`, etc.
- **Object Storage** — directly governs the multi-tenant Keystone/Keycloak federation discussed in the [2026-06-09 OS architecture brainstorm](../../misc/object-storage-on-cloud-store/meetings/2026-06-09-os-architecture-rook-vs-cephadm.md) (OSQ-02: dedicated Keystone + Apache-OIDC in the service-CP). S3 roles + the per-(service,region) client model land here.
- **Compute & Block** — the `vm.{role}` client-roles + project model align with the CB Keystone Controller (SOV-254) federation chain (Q-110/Q-111) and the LZM/panel region+project picker.
- **Network Service** — NS-exposed LB/L3 APIs authorise through the same model once user-facing.
- **BL/UX flow** (from the ADR): project creation (no region) → enable services per region → grant access per (project, service, region) → panel resource creation picks the `{service}-region-{region}` client.

## Source material

- Confluence `[SOV-583] Merge IAM / BL Design in cloudstore` (pageId 936727959) — PDF export 2026-06-09 (9 pp).
- Requirements: `OPCP - Projects & Resources management # Functional requirements` (Confluence).

## Cross-references

- [`summary.md`](../conceptions/business-logic-iam/summary.md) — Business Logic & IAM deep dive.
- [`../../../products/cloudstore/misc/object-storage-on-cloud-store/open-questions.md`](../../misc/object-storage-on-cloud-store/open-questions.md) — OSQ-02 (auth flow + SNC separation).
- [`../../projects/compute-block-on-cloud-store/architecture/business-logic-iam.md`](../../misc/compute-block-on-cloud-store/architecture/business-logic-iam.md) — CB-side BL/IAM (SNC CAIM reuse map).
- NSQ-027/028 — Charly Gregoire's public-connectivity middleware (same IAM/BL author cluster).
