---
id: object-storage-on-cloud-store/user-stories-m3-snc-ready
type: reference
diataxis: explanation
title: "Milestone 3 · 'SNC Ready'"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Milestone 3 · "SNC Ready"

> **User story:** *As the **platform**, I enforce SecNumCloud requirements on the Object Storage Service — admin/user audience separation, encrypted buckets, and audited access — so the product is qualification-ready.*
>
> **Reached at the end:** the M2 beta is hardened to **SecNumCloud parity**: S3 traffic flows through the **SNC proxy stack** (L2/L3 audience separation + `reserved-ovh-internal-` prefix rules + WAF), the **admin/user identity separation** (SNC 2-Keystone model) sits on top of the M2 Keystone chain, **per-bucket encryption** is keyed via **OKMS (OVH KMIP)**, and access is **audited** to LDP/Wazuh. *(This is where the "no proxies / single-Keystone" beta shortcuts taken in M2 are paid back.)*
>
> **Why this milestone:** SecNumCloud compliance is the end-state requirement (OSQ-09 feature parity + the SNC reuse principle). Done-test: an audit-style review passes — no L2 token works on an L3 endpoint, buckets are encrypted, and access is fully logged.

---

## Visual

![M3 · SNC Ready](visuals/os-m3-visual.png)

---

## Personas

| Tier | Persona | What they do in M3 |
|---|---|---|
| **L1/L2** | **Operator / IT-Admin** | Admin S3 + admin views go through the **admin** identity + proxy path. |
| **L3** | **End user** | Same self-service as M2, but now via the **L3 proxy** path with encrypted buckets. |

---

## Components introduced (M3)

| Component | Role in M3 |
|---|---|
| **S3 proxies** | SecNumCloud L2/L3 audience separation + `reserved-ovh-internal-` prefix + WAF — **reuse SNC proxies** (K8s-per-group, [ADR 0046](../../../../opcp-core/architecture/conceptions/proxies/summary.md)) |
| **Admin/user identity separation** | the SNC **2-Keystone** model layered on the M2 Keystone↔Keycloak chain |
| **OKMS / KMIP client** | per-bucket encryption keys via the external OVH [OKMS](https://docs.ovhcloud.com/de/guides/manage-and-operate/kms/architecture-overview) (KMS Team owns; we consume) |
| **Audit feed** | ship access/audit logs to LDP / Wazuh |
| **Full observability** | the complete metrics + predictive-capacity stack |

---

## What's built (layer by layer)

- **`oss-cp`:** the S3 proxy groups + the OKMS/KMIP client + the audit feed + the admin/user Keystone split join the control plane.
- **Ceph data plane:** unchanged; now fronted by proxies and serving encrypted buckets.
- **Landing Zone:** L3 unchanged; new **admin views** for L2 (cluster + cross-account).

---

## Dependencies + open questions

- Depends on **M2** (working identity chain + buckets) and the **SNC reuse inventory** (OSQ-10) — what proxy/Keystone assets come straight from SNC.
- **OSQ-07** — exact per-bucket KMS mapping (ADR 0048 S3 KMS unsealing) + V1-vs-later cut.
- **OSQ-06** — final public/private exposure model with proxies in front.
- The **access-control clarification meeting** (Florent/Vincent/Ibrahim) feeds the 2-Keystone deploy detail.
