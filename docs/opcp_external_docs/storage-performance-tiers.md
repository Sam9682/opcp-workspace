---
id: compute-block-on-cloud-store/architecture-storage-performance-tiers
type: deep-dive
diataxis: explanation
title: "Storage performance tiers — what SNC has today & what our Ceph can do"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Storage performance tiers — what SNC has today & what our Ceph can do

> **Finding by:** Boris Behrens, 2026-07-10 · **Source ticket:** SOV-1738 ([FDD #3] Storage performance tiers — do we have this in SNC?)
>
> **One-line answer:** SNC runs a **single** Ceph performance class today. Multiple **block-storage** tiers are achievable via **software QoS** (hypervisor IOPS limits), never via hardware — every cluster has one disk type. **Object storage** has no tiering path.

---

## 1. SNC today

- **One performance class on Ceph.** No storage performance tiers ship in SNC today, for either block or object storage.
- **One disk type per cluster.** From the hardware perspective there is a single drive class in each cluster → **no hardware-based storage classes** are possible.

## 2. Feasibility on our Ceph

| Storage kind | Can we tier it? | How | Notes |
|---|---|---|---|
| **Block** | ✅ Yes (software) | Limit IOPS at the **hypervisor** (QoS) → different volume classes | Matches [Decision 2026-05-09i](../decisions.md) — 3 Cinder volume types (Standard / High / Insane) as a QoS-enforced product contract, planned M4. |
| **Object** | ❌ No | — | Single class only. No hardware differentiation, and no per-object QoS lever equivalent to the hypervisor IOPS limit. |

## 3. Correction to Decision 2026-05-09i's hardware assumption

Decision 2026-05-09i (Cinder Volume Types) assumed the higher tiers *"likely need different drive specs (e.g. higher-grade NVMe)"* and left **"per-tier hardware target TBD"** as an M4 task.

**This finding resolves that TBD:** there is **no** per-tier hardware target. All clusters have a single disk type, so the three block-storage tiers are delivered **purely as software QoS** (published IOPS/BW limits enforced at the hypervisor), not by placing tiers on different NVMe grades. The three names + limits remain a product contract; the *implementation* is QoS-only.

## 4. Implications

- **FDD §2.1** claims IT Admins can "choose between three storage performance tiers." That maps to **block storage only** (software QoS, M4 per Decision 2026-05-09i). **Object storage is single-tier.** §2.1 should be scoped accordingly once the product decision (below) lands.
- **Product decision still open (AC#3 of SOV-1738, owner Marc / Florent):** how many tiers ship at GA — recommendation is **block = 3 QoS tiers (M4)**, **object = 1 tier**, no object path to more without new hardware.

## 5. Cross-references

- SOV-1738 — source FDD-feedback ticket (this finding answers AC#1 + AC#2).
- [`../decisions.md`](../decisions.md) — Decision 2026-05-09i (Cinder Volume Types: ship three at V1).
- [`cb-tech-spec.md`](cb-tech-spec.md) — block-storage tiers as a product contract (§Chapter-0 matrix + block-storage tiers detail).
