---
id: object-storage-on-cloud-store/overview
type: reference
diataxis: explanation
title: "Object Storage on CloudStore — Project Overview"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Object Storage on CloudStore — Project Overview

> **Shareable overview for a broad audience.** **A — what we want to build** · **B — how we plan it** · **C — relevant concepts.** Architecture, milestones and concepts only; no ownership, assignees, estimates, or ticket-level detail.

![Object Storage — the big picture](user-stories/visuals/os-big-pic-visual.png)

---

## A. What we want to build

S3-compatible **Object Storage** for OPCP, backed by **Ceph RADOS Gateway (RGW)**, delivered as a **CloudStore Service Package** — the second packaged product on OPCP Core after Compute & Block. Target feature scope = **parity with OVH Public Cloud Local Zones S3** (same technology underneath). → [Product Brief](Product Brief) · [LZ feature comparison](LZ feature comparison)

**Core idea:** package what the SNC Cloud Platform already runs for object storage into a self-contained CloudStore Service, and **automate what is still done manually in SNC** (the same pattern as Compute & Block).

**Architecture:**

- **The Package does everything.** An IT-Admin selects a pool of **≥4 empty bare-metal nodes**; the Package provisions the whole stack **through the OpenStack API** — networking (Neutron), host provisioning (Nova bare-metal flavor → Ironic), a golden image, then the **Ceph + RGW** cluster and its lifecycle (scale-in/out). RGW is **co-located on the Ceph nodes**, on a **dedicated** cluster. *OpenStack is used only internally to provision and manage the hosts — once installed, Object Storage runs **standalone**, not as an OpenStack service.*
- **Identity chain:** the Package ships its **own dedicated Keystone** that fronts RGW for S3 authentication, **federated up to the CloudStore Keycloak** — the same Keycloak↔Keystone federation Compute & Block uses:

  ```
  Ceph → RGW → Keystone (dedicated, in the Package) → Keycloak (CloudStore BL)
  ```

- **Credentials:** a middleware issues temporary session keys + permanent keys and **never exposes secret keys after creation** — the Landing-Zone "Access Keys" UI is its front-end. → [Object Storage middleware](architecture/objectstorage-middleware.md)
- **Business logic:** account activation, quotas, and usage/billing live in the shared Business Logic, not bespoke to the package.
- **L3 experience:** buckets (with versioning, lifecycle, static-website hosting), objects (drag-and-drop upload, HTTP-header config), and access keys. → [L3 UX](architecture/l3-ux-wireframes.md)

## B. How we plan it (milestones)

Four milestones, mirroring the Compute & Block cadence — *infra first, then customer value, then SecNumCloud compliance, then air-gap.*

| Milestone | Theme | Outcome |
|---|---|---|
| **M1** | Infra Deployment | Package turns ≥4 empty bare-metal nodes into a healthy, scalable Ceph + RGW cluster. |
| **M2** | Activation for Customer | Per-account activation; users create S3 credentials + buckets and manage objects, with quotas. Stands up the dedicated-Keystone → CloudStore-Keycloak identity chain. |
| **M3** | SNC Ready | SecNumCloud compliance — admin/user identity separation, S3 proxies, KMS / per-bucket encryption, audit + WAF. |
| **M4** | Air-gapped | Offline operation + clear customer responsibility for capacity monitoring and hardware ordering. |

*(As with Compute & Block, M2 is expected to be a compliance-deferred beta; the proxy + compliance layer concentrates in M3.)*

## C. Relevant concepts

- **CloudStore Service Package** — same contract as Compute & Block (`cloudstore.yaml` + controlplane/dataplane Terraform + OCI artifact). → [Service Contract & Packaging](../../architecture/conceptions/service-contract/summary.md)
- **Ceph + RGW** — the S3 backend; dedicated cluster with its own hardware spec (≥4 nodes, replication or erasure coding, an 80 % usage cap).
- **Keystone ↔ Keycloak federation** — reused from Compute & Block. → [Keycloak Federation & KeystoneDomain](../../../../generic/keycloak-federation/summary.md)
- **S3 credential model** — temporary session keys + permanent keys, secret shown once. → [Object Storage middleware](architecture/objectstorage-middleware.md)
- **SecNumCloud** — admin/user identity separation, S3 audience-separation proxies, per-bucket encryption (a later-milestone concern).

→ Deep dives: [CloudStore](../../architecture/conceptions/cloudstore/summary.md) · [Service Contract](../../architecture/conceptions/service-contract/summary.md) · [Proxies](../../../opcp-core/architecture/conceptions/proxies/summary.md)
→ Project KB: [Architecture index](architecture/README.md)
