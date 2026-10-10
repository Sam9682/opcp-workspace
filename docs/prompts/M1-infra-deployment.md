---
id: object-storage-on-cloud-store/user-stories-m1-infra-deployment
type: reference
diataxis: explanation
title: "Milestone 1 · 'Infra Deployment'"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Milestone 1 · "Infra Deployment"

> **User story:** *As an **IT-Admin**, I select a pool of **≥4 empty bare-metal nodes** and activate the Object Storage Service, so the Package provisions a **healthy, scalable Ceph + RGW cluster** for me — without me touching OpenStack, Ironic, or Ceph by hand.*
>
> **Reached at the end:** activating the Service stands up the **`oss-cp` control plane**, which drives the OpenStack API (Nova bare-metal flavor → Ironic, Neutron, golden image) to turn the empty nodes into Ceph hosts, deploys **Ceph + RGW (co-located on the nodes)**, and brings the cluster to `HEALTH_OK`. The cluster can be **scaled in/out**, and a **health + capacity view** is live. *No per-account activation, S3 credentials, proxies, or KMS yet — those are M2/M3.*
>
> **Why this milestone:** it's the hard infra-automation core and it forces the project's biggest architecture decision — **how `oss-cp` provisions + manages the hosts (OSQ-15)**. Done-test: `ceph -s` reports `HEALTH_OK` on a freshly-provisioned cluster, RGW answers, and `+1 node` scales the cluster cleanly.

---

## Visual

![M1 · Infra Deployment](visuals/os-m1-visual.png)

---

## Personas

| Tier | Persona | What they do in M1 |
|---|---|---|
| **L1** | **DC Operator** | Racks the bare-metal nodes; hands over **empty servers**. (Their only structural step — everything above is automated.) |
| **L2** | **IT-Admin** | Selects the BM pool + activates the Object Storage Service in CloudStore. |

---

## Sequence

1. **① L1** racks ≥4 empty BM nodes.
2. **② L2** activates the Service + selects the BM pool in CloudStore.
3. **③ `oss-cp` provisions** the hosts via the OpenStack API — Nova BM flavor → Ironic (host), Neutron (networks), golden image.
4. **④ `oss-cp` deploys Ceph + RGW** on the hosts (cephadm/ansible); pools per replication / EC 3:2.
5. **⑤ Cluster healthy** — `HEALTH_OK`; health + capacity view live; scale-in/out works.

---

## Components introduced (M1)

From the [`oss-cp` inventory](../architecture/oss-cp-components.md):

| Component | Role in M1 |
|---|---|
| **K8s control-plane substrate** (k3s on VMs) | the `oss-cp` brain |
| **CloudStore Package runner** (FluxCD + tofu-controller) | executes the controlplane TF |
| **Provisioning engine** ⭐ (**OSQ-15**) | empty BM → Ceph hosts via OpenStack API + day-2 lifecycle |
| **Ceph deploy tooling** (cephadm / SNC ansible role) | Ceph OSD/MON/MGR + RGW on the nodes |
| **Observability (basic)** | Ceph health + capacity % (warn 60/70, cap 80) |
| **Networking + base elements** | Neutron networks, DNS, secrets, GitOps TF source |

**Data plane (on the BM nodes):** Ceph OSD/MON/MGR + **RGW co-located** + health agent.

---

## What's built (layer by layer)

- **`oss-cp` (control plane):** k3s + the package runner + the provisioning engine + Ceph-deploy tooling + basic observability. This is the milestone where `oss-cp` first exists.
- **Ceph data plane:** the dedicated bare-metal Ceph cluster (≥4 nodes, RGW co-located), `HEALTH_OK`, scalable.
- **Landing Zone:** not yet — M1 has no end-user surface (an L2 cluster-health view is the only UI).

---

## Dependencies + open questions

- **OSQ-15 (the gating decision):** reuse the OPCP Infra **Storage Controller** (SOV-256, which already builds Ceph on BM) vs pure-TF + worker. **Day-2 lifecycle (scale/heal/replace) is the deciding factor** — settle this at the architecture session *before* M1 build starts.
- **OSQ-04 detail:** the exact Ceph-deploy mechanism (cephadm vs ansible).
- Reuse: [SNC Ceph + prometheus_agent ansible roles](https://stash.ovh.net/projects/SNC/repos/ansible-library/browse/roles/ceph); the [SNC hosts-storage TF](https://stash.ovh.net/projects/SNC/repos/terraform-modules/browse/hosts-storage).
