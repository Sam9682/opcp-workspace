---
id: object-storage-on-cloud-store/architecture-oss-cp-components
type: deep-dive
diataxis: explanation
title: "oss-cp — Component Inventory (what the Object Storage Service Control Plane needs)"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# oss-cp — Component Inventory (what the Object Storage Service Control Plane needs)

> **Purpose:** detect the components + base elements the **Object Storage Service Control Plane (`oss-cp`)** needs — the equivalent of CB's `cbs-cp`. Feeds the milestone pages ([M1](../user-stories/M1-infra-deployment.md)–[M4](../user-stories/M4-air-gapped.md)).
>
> **Two planes:** the **`oss-cp` control plane** (the brain — runs as the Service control plane, like `cbs-cp`) and the **Ceph data plane** (the bare-metal storage nodes). *Decided:* RGW is **co-located on the Ceph nodes** (OSQ-16); OpenStack is used **only internally to provision the hosts** — once installed, OS runs **standalone** (OSQ-11).

---

## 1. The two planes at a glance

```
  ┌──────────────────────── oss-cp (Service Control Plane — the brain) ─────────────────────────┐
  │  CloudStore Package runner (FluxCD + tofu-controller)                                         │
  │  Provisioning engine (OSQ-15: reuse OPCP Infra/Storage Controller  OR  pure-TF + worker)      │
  │  Dedicated Keystone (fronts RGW for S3 auth) ── federated ──► CloudStore Keycloak (BL)        │
  │  S3 credential middleware (SOV-514 reuse)                                                      │
  │  Business-Logic adapters (activation · quota · usage)                                          │
  │  Observability (Prometheus + Grafana: health + capacity %)                                     │
  │  (M3) S3 proxies · OKMS/KMIP client · audit feed                                               │
  └───────────────────────────────────────────────│──────────────────────────────────────────────┘
                                OpenStack API (Nova BM flavor → Ironic, Neutron) — provision/manage hosts only
                                                   ▼
  ┌──────────────────────── Ceph data plane (dedicated bare-metal nodes, ≥4) ───────────────────┐
  │  Ceph OSD / MON / MGR   +   RGW (co-located)   +   resource/health agent                      │
  └──────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 2. `oss-cp` control-plane components

| # | Component | What it does | Source / reuse | First needed |
|---|---|---|---|---|
| 1 | **K8s control-plane substrate** (k3s on VMs) | Hosts the package controlplane + the components below — same shape as `cbs-cp`. | OPCP Compute VMs (Nova) | M1 |
| 2 | **CloudStore Package runner** | FluxCD `Kustomization` → `Terraform` CR → tf-runner; executes the controlplane/dataplane TF. | CloudStore platform (exists) | M1 |
| 3 | **Provisioning engine** ⭐ | Turns empty BM → Ceph hosts via the OpenStack API (Nova BM flavor → Ironic, Neutron, golden image) + day-2 lifecycle (scale/heal/replace). | **OSQ-15 open:** reuse OPCP Infra/Storage Controller *vs* pure-TF + worker. | M1 |
| 4 | **Ceph deploy tooling** | Bring up Ceph (OSD/MON/MGR) + RGW on the provisioned hosts; pool config (replication / EC 3:2). | ✅ **2026-06-23: reference ready in irobox `ansible/roles/ceph` (`dev/shohn/SOV-687`, unmerged)** — cephadm mon/osd/mgr/rgw, RGW↔Keystone (L2/L3 split, all 6 `rgw_keystone_*`), OKMS (KMIP/Vault), SSE-S3, block+object modes. Wire into the package's future `ceph_cluster` module. *(Supersedes the generic "SNC ansible role" pointer.)* | M1 |
| 5 | **Dedicated Keystone** | Fronts RGW for S3 / EC2 authentication; the user-facing identity. | new (in-package) — ⬆️ **2026-06-23: active** in the package controlplane (k3s + CNPG + Keystone deployed; `feature<keystone>` from alpha.5+) | M2 |
| 6 | **Keystone↔Keycloak federation** | Federates the dedicated Keystone up to the CloudStore Keycloak (BL). | **Reuse CB's** Keystone-operator / [KeystoneDomain federation](../../../../../generic/keycloak-federation/summary.md) — ⬆️ **2026-06-23: a `keystone_federation` dataplane module (Apache OIDC proxy + netpol + HTTPRoutes) is live in the package** | M2 |
| 7 | **S3 credential middleware** | ⚠️ **As built (Jan, 2026-08-26)** — a thin **proxy for access-key CRUD onto Keystone**, **no database of its own**: it strips the secret Keystone returns on read (secret visible only at creation), and issues + **scheduled-cleans** the panel's temporary access keys, which are **ordinary keys with no special prefix**. *(This diverges from the SNC design in [`objectstorage-middleware.md`](objectstorage-middleware.md), which has a metadata DB and a `TMP_OVH_` prefix.)* | **Reuse SNC SOV-514** — see [middleware doc](objectstorage-middleware.md) | M2 |
| 8 | **Business-Logic adapters** | Account activation, quotas-per-account, usage/consumption reporting. | shared **BL** (CAIM-style) — OSQ-03 | M2 |
| 9 | **Observability** | Prometheus + Grafana: Ceph health + capacity % (warn 60/70, cap 80) + predictive alerts. | reuse [SNC prometheus_agent role](https://stash.ovh.net/projects/SNC/repos/ansible-library/browse/roles/prometheus_agent) | M1 (basic) → M3 (full) |
| 10 | **S3 proxies** | SecNumCloud L2/L3 audience separation + `reserved-ovh-internal-` prefix + WAF. | **Reuse SNC proxies** (K8s-per-group, [ADR 0046](../../../../opcp-core/architecture/conceptions/proxies/summary.md)) | M3 |
| 11 | **OKMS / KMIP client** | Per-bucket encryption keys via the external OVH **OKMS** (KMIP). | **consume** [OKMS](https://docs.ovhcloud.com/de/guides/manage-and-operate/kms/architecture-overview) (KMS Team owns; not ours) | M3 |
| 12 | **Audit feed** | Ship audit logs to LDP / Wazuh (SecNumCloud). | reuse SNC pattern | M3 |

## 3. Ceph data-plane components (on the bare-metal nodes — *not* in oss-cp)

| Component | Note |
|---|---|
| **Ceph OSD / MON / MGR** | ≥4 nodes (1 reserved); 3× replication *or* EC 3:2 (EC needs ≥6). Dedicated cluster (separate from Block's Ceph). |
| **RGW (RADOS Gateway)** | Co-located on the Ceph nodes (OSQ-16). The S3 endpoint; authenticates against the dedicated Keystone. |
| **Resource / health agent** | Reports node + cluster health back to oss-cp observability (heartbeat pattern, à la the OPCP resource-agent). |

## 4. Base elements / cross-cutting

| Element | Note | Milestone |
|---|---|---|
| **Networking** | Neutron-provisioned networks; **private connectivity** VM→S3; S3 endpoint exposure public/private (**OSQ-06**). | M1 / M2 |
| **DNS + TLS** | S3 endpoint DNS + certs (frontend + backend trust). | M2 |
| **Secrets** | OpenStack app-creds (auto-injected via `cloudstore.yaml`), Keystone/Keycloak client secrets, OKMS creds. | M1+ |
| **GitOps TF-module source** | The package's TF modules (own fork vs iRobox — the "two lifecycles, one operator" pattern). | M1 |
| **Artifact registry** | Harbor for images/charts; **local mirror** for air-gap. | M1 → M4 |
| **Capacity model** | 80 % usable cap, EC/replication math, scale-out rules (from the Product Brief). | M1 |

## 5. Reuse map (CB / SNC → OS)

| Need | Reused from |
|---|---|
| Package contract + runner | CloudStore platform / CB pattern |
| Provisioning + day-2 lifecycle | *(if OSQ-15 = reuse)* OPCP Infra **Storage Controller** (SOV-256) |
| Keystone↔Keycloak federation | CB Keystone operator / KeystoneDomain |
| S3 credential middleware | SNC **SOV-514** |
| Ceph + prometheus roles | SNC ansible-library |
| S3 proxies | SNC proxies (ADR 0046) |
| KMS | OVH **OKMS** (external) |

> **The principle (OSQ-10):** package what SNC already runs + automate the manual. Most of `oss-cp` is *integration + automation* of existing SNC/CB pieces, not greenfield. The one genuinely-new decision is the **provisioning engine (OSQ-15)**.

## 6. Cross-references
- [Project overview](../overview.md) · [Milestones M1–M4](../../compute-block-on-cloud-store/user-stories/README.md) · [Open questions](../open-questions.md)
- [Object Storage middleware](objectstorage-middleware.md) · [L3 UX](l3-ux-wireframes.md)
