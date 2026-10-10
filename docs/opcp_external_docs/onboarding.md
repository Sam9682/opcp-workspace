# OPCP Object Storage — Onboarding

> **Purpose:** get a newcomer up to speed on the OPCP Object Storage packaging effort — what it is, where we are, what's decided, what's still open. Paste into Confluence ("OPCP – Object Storage").
> **Status:** kickoff / discovery (May 2026). Target window ~July 2026.

---

## 1. What we're building

S3-compatible **Object Storage** for OPCP, backed by **Ceph RADOS Gateway (RGW)**, shipped as a **CloudStore Service Package** — the second packaged product on OPCP Core after **Compute & Block**.

A customer creates buckets and manages objects through the S3 API and the Landing-Zone UI; the platform stands up and manages the underlying Ceph cluster. Target feature scope = **parity with OVH Public Cloud Local Zones S3** (same technology underneath).

## 2. The core idea (how it relates to SNC)

Same play as Compute & Block: **package what SNC already runs into a CloudStore Service, and automate the steps that are still manual in SNC.** We are not reinventing object storage — we're productising and automating it.

From a pool of **empty bare-metal nodes**, the Package provisions the whole stack **through the OpenStack API**: networking, host provisioning (Nova bare-metal flavor → Ironic), a golden image, then the Ceph + RGW cluster (RGW co-located on the Ceph nodes, a **dedicated** cluster) and its lifecycle (scale-in/out). On top of that sits per-account activation, S3 credentials, buckets, and quotas.

> **Scope note:** OpenStack is used **only internally to provision and manage the hosts**. Once installed, Object Storage runs **standalone — it is not an OpenStack service** (S3 via RGW, not Swift).

## 3. How it fits together

```
   IT-Admin ── activates the Service ──►  Package provisions the cluster
                                          (empty BM ──OpenStack API──► Ceph + RGW)
   IT-Admin ── activates per Account ──►  account gets quotas + access
        │
   Landing-Zone user ──► creates S3 credentials (via the credential middleware)
                         ──► buckets + objects (S3 API / UI), direct to Ceph S3
```

- **Identity chain:** the Package ships its **own dedicated Keystone** that fronts the Ceph RGW for S3 authentication, and that Keystone **federates up to the CloudStore Keycloak** — the **same Keycloak↔Keystone federation Compute & Block uses** (via the Keystone operator):

```
Ceph → RGW → Keystone (dedicated, in the Package) → Keycloak (CloudStore BL)
```

- **Credentials:** on top of that Keystone, a middleware issues temporary session keys + permanent keys, and **never exposes secret keys after creation** — the Landing-Zone "Access Keys" UI is its front-end. (Reuse of the SNC object-storage middleware; the secret is shown exactly once.)
- **SecNumCloud:** the admin/user identity separation (the SNC model) is realised within this Keystone-federation model (M3).
- **Business Logic:** account activation, quotas, and usage/billing are expected to live in the shared Business Logic — not bespoke to this package.

## 4. Where we are

| Area | State |
|---|---|
| Product brief + scope | ✅ in hand (Ceph RGW, ≥4-node clusters, replication or erasure coding, HW spec, capacity model) |
| L3 (Landing-Zone) UX | ✅ wireframes in hand (buckets, objects + HTTP headers, access keys, static-website, jobs panel) |
| Credential middleware | ✅ design known (SNC reuse) |
| Provisioning approach | 🟡 direction set (Package provisions via OpenStack); engine choice open |
| Architecture proposal | ⚪ pending the HLD + the SNC reuse inventory |
| Access-control detail | 🟡 model chosen (two-Keystone); deployment detail open |
| Milestones / estimate | 🟡 milestone shape proposed; estimate pending architecture |

## 5. Milestones (proposed)

Four milestones, mirroring the Compute & Block cadence — *infra first, then customer value, then SecNumCloud compliance, then air-gap.* As with CB, **M2 is a compliance-deferred beta**; the proxy + full-compliance layer concentrates in M3.

### M1 — Infra Deployment

![M1 · Infra Deployment](user-stories/visuals/os-m1-visual.png)

The IT-Admin selects a pool of **≥4 empty bare-metal nodes** and activates the Service; the Package provisions everything via the OpenStack API (Nova bare-metal flavor → Ironic, Neutron, golden image) and brings up a healthy, scalable **Ceph + RGW cluster** (RGW co-located on the nodes), with a health + capacity view.

### M2 — Activation for Customer *(beta)*

![M2 · Activation for Customer](user-stories/visuals/os-m2-visual.png)

Per-Account activation: a Landing-Zone user **creates S3 credentials** (secret shown once) + **account-segmented buckets** and manages objects, with **per-account quotas** (BL-driven). Identity chain live: dedicated Keystone fronting RGW, federated to the CloudStore Keycloak. Endpoints direct — no proxies yet.

### M3 — SNC Ready

![M3 · SNC Ready](user-stories/visuals/os-m3-visual.png)

SecNumCloud parity: the **S3 proxies** (L2/L3 audience separation + WAF), the **admin/user 2-Keystone split**, **per-bucket encryption** via the external OKMS (KMIP), and **audited** access (LDP / Wazuh).

### M4 — Air-gapped

![M4 · Air-gapped](user-stories/visuals/os-m4-visual.png)

Offline operation — local Harbor + OS/firmware mirrors, offline upgrades, local IdP fallback. **Mostly an L2 milestone:** the IT-Admin owns the lifecycle + capacity monitoring + hardware ordering (with the legal/SLA shift documented); the L3 end user is unaffected.

## 6. Biggest open questions

1. **Provisioning engine** — Package-owned Terraform vs reuse of the OPCP Core provisioning operator (day-2 lifecycle is the deciding factor).
2. **Access-control deployment** — how the two-Keystone model + the credential middleware are packaged + deployed (the topology itself is decided).
3. **Business-Logic capacity** — when the BL team can take the activation/quota/usage work (the schedule driver).
4. **Network exposure** — public vs private S3 endpoints; customer control over reach + access.
5. **KMS scope** — per-bucket encryption via the external OVH OKMS (KMIP), V1 vs later.
6. **SNC reuse inventory** — what's reused as-is vs which manual SNC steps must be automated.
7. **Air-gapped responsibility** — the legal / SLA wording for capacity monitoring + hardware ordering when disconnected.

*(Decided since kickoff: the Package does everything via the OpenStack API; RGW co-located on the Ceph nodes; a dedicated Ceph cluster (separate from Block); the dedicated-Keystone → CloudStore-Keycloak identity chain with a two-Keystone admin/user split; BL owns activation/quota/usage; Local-Zone S3 feature parity.)*

## 7. References

- **[Product Brief — OPCP Object Storage](https://confluence.ovhcloud.tools/display/CPO/OPCP+-+Object+Storage)** · **HLD** (GSSNC-411).
- **SNC object-storage middleware** — S3 credential proxy (ADR 0045 / SOV-514).
- **SNC Cloud Platform Object Storage** product note (the reuse base).
- **LZ feature comparison** — [OVH Public Cloud Local Zones S3 limitations (KB0065306)](https://help.ovhcloud.com/csm/en-public-cloud-storage-s3-local-zone-limitations?id=kb_article_view&sysparm_article=KB0065306) + compliancy matrix (KB0047478).
- **Related products:** Compute & Block packaging (LVL2-18373) · Cloud Store v1 GA (LVL2-20870) · Cloud Store Observability (LVL2-18370).
