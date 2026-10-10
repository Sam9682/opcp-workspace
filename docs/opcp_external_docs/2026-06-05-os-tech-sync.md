# Object Storage — Tech Sync (W23, 2026-06-05)

> **Source:** Confluence page [OS-MN-W23 — 2026-06-05 Object Storage Technical Sync](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=963465261) (SOV space).
> **Type:** weekly OS technical sync (distinct from the deeper architecture brainstorm scheduled for Tue 2026-06-09 15:00).

---

## Attendees

Marc Dittmann · Boris Behrens · Zafar Akhtar · Jan Stühlman · Eddy Medina.

## Purpose

> *"Get unblocked on Object Storage. Align on the architecture approach, clear up confusion around Rook vs what's running today, and find a way to start testing."*

## Key clarifications (the architecture lock-in this week)

### Rook ≠ Ceph orchestrator

- **What runs today** in Gridscale + Local Zones = **Ceph orchestrator** (YAML-based rules, **no Kubernetes**).
- **What Stephan built for Block Storage** = a **Kubernetes controller** that uses CRDs and **runs Ansible playbooks from the Ionic repo**.
- That Ansible stack is **reusable for Object Storage almost as-is** — important reuse signal.

### The Block ↔ Object Storage delta is just RGW

The only difference between Block and Object Storage is the **RADOS gateway** — the S3 frontend that talks to Keystone and federates against Keycloak. **That's where the complexity sits**, and that's where Rook earns its place.

### Why Rook fits here

- Rook can manage the **RADOS gateway config via Kubernetes CRDs** instead of Ansible.
- A **small K3S cluster** will live in the OS service control plane anyway → that same cluster can host Rook → no extra overhead.

## Decisions made

| # | Decision | Implication |
|---|---|---|
| 1 | **K3S confirmed in the OS control plane** — same cluster hosts Rook. | Closes part of P1 from the Eddy weekly: K3S is on the table; Rook can live there. |
| 2 | **Rook manages the RADOS gateway via Kubernetes CRDs** — replaces or complements Ansible for the RGW layer. | Re-frames OSQ-15: Rook isn't replacing Ansible *everywhere*, it's owning the RGW CRD layer (Ansible from Ionic stays underneath for the rest). |
| 3 | **Object Storage Ansible playbooks from the Ionic repo are reusable** — almost identical to Block / SNC. | Re-frames OSQ-04 (Ceph-deploy mechanism) — the Ansible base is already there. |
| 4 | **Testing approach agreed** — spin up VMs (OVH or Gridscale) → attach disks → deploy K3S → test Keystone / Keycloak + RGW auth flow. | If the auth flow validates, that confirms both the auth approach AND K3S as the Rook base in one pass. |
| 5 | **Existing SNC Gridscale environment** has Keystone already running — candidate for reuse. | Conditional on VPN / DNS connectivity validation first. |

## Resources & timeline

- **No bare metal in minint right now** — too busy across projects.
- **4 bare metal nodes arrive Monday 2026-06-08** — potentially 1 allocated to Object Storage *depending on Block Storage needs*. Allocation decision still open.
- **Short-term alternative:** VMs on OVH or Gridscale, ~8–10 GB RAM, a few disks attached — enough to start.
- **Boris availability:** one week available, then back until CW27.

## Action items

| Owner | What | Due | Affects |
|---|---|---|---|
| **Marc** | Confirm VM aggregate availability + resource options. | **ASAP** | unblocks Boris + Zafar's CW24 test setup |
| **Boris + Zafar** | Spin up VMs, get K3S running, start Keystone / Keycloak + RGW auth flow test. | CW24 | SOV-855 Provisioning Engine · SOV-916 RGW Federation against Keycloak |
| **Boris + Zafar** | Check node availability with Guillaume Monday 2026-06-08. | Mon 2026-06-08 | SOV-672 Identify HW nodes for Ceph dev env |
| **Stephan + Boris + Nathan + Ibrahim + Zafar + Marc** | Follow-up architecture brainstorm — close the two remaining open Qs. | **Tue 2026-06-09 15:00** | OSQ-15 + the SNC admin/user identity separation question |

## Still open (for the Tuesday brainstorm)

1. **Rook scope is unclear** — does Rook replace Ansible entirely, or only the RADOS gateway layer? Boris needs hands-on time to figure this out. Affects [SOV-864 (OSQ-15 Provisioning Engine — Rook vs pure TF)](SOV-864).
2. **Circular dependency** — Managed Kubernetes depends on Object Storage, which Zafar's Observability project *also* depends on. **Needs product input to resolve.**
3. **VPN / DNS connectivity** — needs validation before reusing the Gridscale SNC environment for testing.

## Implications for the workspace state

- **OS management summary [`plans/os-management-summary-2026-06-05.md`](../plans/os-management-summary-2026-06-05.md)** — was written before this sync; the P1 framing ("Rook vs cephadm" still open) is partially out-of-date. Rook's role is now clearer (RGW CRD layer, on K3S, with Ansible underneath). The Tuesday brainstorm still needs to close "how far does Rook go" + the SNC identity separation. Eddy weekly already references the Tuesday session.
- **OS open-questions** — OSQ-15 (Rook vs pure TF) gets refined rather than closed; OSQ-04 (Ceph deploy mechanism) effectively resolved via Ansible-from-Ionic reuse signal. Worth a small update.

## Cross-references

- Sibling artefact same week: [`2026-06-05-architecture-thread.md`](2026-06-05-architecture-thread.md) — Teams-channel architecture thread, complementary content.
- Prior alignment meeting: [`2026-06-02-controllers-secrets-alignment.md`](2026-06-02-controllers-secrets-alignment.md) — where Dedicated Keystone per service was locked in.
- Source-of-truth: [`plans/os-management-summary-2026-06-05.md`](../plans/os-management-summary-2026-06-05.md).
- Weekly update (paste-ready for Eddy): [`tracking/weekly-status-2026-06-05.md`](../tracking/weekly-status-2026-06-05.md).
