# Milestone 3 · "Deploy all components"

> **User story:** *As **OVH** I want to be able to use OPCP + CloudStore in the SNC Cloud Platform, so the same level of features + security like Proxies is reached.*
>
> **Reached at the end:** the SNC platform components are now in place — all 6 SNC proxy groups live in cbs-cp, the Landing Zone Manager has graduated to a polished OVH-cloud-style product UI, Cinder backups push to a customer-configurable external S3, the observability stack (Prometheus / Grafana / Loki + LDP audit + Wazuh) is scraping every cluster, and L2 has cross-account admin views (list / migrate / hardware utilisation). Power users can jump to Horizon for advanced flows. **Volume snapshots** (create / clone / rollback / delete) and the **full Glance sync from the OVHCloud PCI image catalogue** also land here (moved from M2 to consolidate operator-side Ceph CoW work + image-team ownership into the SNC-parity wave).
>
> **Goal:** bring all the additional components (Proxies, Manager UI, Observability, etc.) in place to **sync back to the SNC Cloud Platform compatibility**.
>
> **State at end of M3:** *customer workload runs full-stack, but maybe still need to do things manually.*
>
> ↑ Index page: [`milestones.md`](../milestones.md).

---

## Visual

![M3 illustration](../../../../../products/cloudstore/misc/compute-block-on-cloud-store/user-stories/visuals/M3-illustration.png)

> *Polished cartoon illustration generated from the [image-gen prompt](visuals/M3-image-prompt.md). The structural composition reference is [`visuals/M3-layout.svg`](visuals/M3-layout.svg).*

---

## Personas

| Tier | Persona | What they do in M3 |
|---|---|---|
| **L2** | **IT-Admin** | Configures backup destination (S3), uses cross-account admin views, can migrate any VM. |
| **L3** | **End User** | Now sees a polished OVH-cloud-style Landing Zone Manager (sidebar nav, stat cards, recent activity, CPU sparkline) and can jump to Horizon for power-user flows like editing security groups. |

> *(L1 Operator does not act in M3 — M3 is about deploying additional components on top of an already-running platform. L1 appears in M4 for cluster lifecycle.)*

---

## Sequence (matches the four step badges in the illustration)

1. **① L2 sets up backup** in the CloudStore admin UI (S3 destination, daily schedule, all-accounts scope).
2. **② Cinder Backup pushes** volume snapshots and VM image exports to the configured external S3 endpoint.
3. **③ All 6 SNC proxy groups go live** in cbs-cp (Global / Regional / Data-Plane × L2 / L3, plus proxy-redis), with TLS, Keystone token-audience attribution, tenant isolation, and audit feeds to LDP / Wazuh — *SNC parity reached*.
4. **④ L3 uses the polished Landing Zone Manager** — full nav sidebar, multiple stat cards, recent-activity feed, CPU sparkline, and a *Horizon ↗* power-user link.

---

## What's in the picture (layer-by-layer)

- **LANDING ZONE (top)** — L3 + the OVH-styled LZM with header bar, sidebar nav, 5 stat cards (Compute · Storage · Backups · Accounts · Platform Health), Recent activity panel, and a CPU usage 24 h sparkline.
- **CLOUD STORE (middle)** — L2 + the admin Backup-config UI + the Cross-account VM list with per-VM `migrate` buttons + the SNC-parity outcome sticky.
- **OPCP CORE (bottom)** — Cinder Backup → External S3 cloud + Observability stack (Prometheus · Grafana · Loki · LDP · Wazuh) + the **6 SNC Proxy Groups** card (the visual showpiece, 3 × 2 grid + proxy-redis side-pill + security footer) + a *FROM M1 + M2 (still healthy)* compressed container.
- **Cross-layer arrows**: ① → ② labelled `backup destination set` (down), ③ → ④ labelled `proxies surface APIs + UI` (up — visually conveying that the proxies make the polished LZM possible).

---

## Tasks — implied work (not yet broken down)

- Bring **all six SNC proxy groups** into the Cloud-Store-packaged service (per the May 9 architecture). Per the [`what-goes-where`](../architecture/what-goes-where.md) diagram, all proxies live in **cbs-cp** (the vm-bs-service control plane).
- Bring the **regional + global manager UI** equivalents — the SNC Panel functionality.
- Bring **Observability** (Prometheus / Grafana / Loki / LDP / Wazuh etc. — TBD which fit here vs Pod #0 deferred work).
- Bring **all the apps of paas-snc global cp** (without keycloak — that's reused) into cs-cp.
- Bring **all the apps of paas-snc regional cp** into cbs-cp.
- Migrate runbook steps that today require manual interaction (panels, proxies, control plane, paas-snc storage, paas-snc block storage, paas-snc object storage, business logic) — see [`architecture/snc-deployment-flow.md`](../architecture/snc-deployment-flow.md).

### Added from Brief 01 (PM input — 2026-05-09)
- 🆕 **\[PB-2] Glance sync from OVHCloud PCI images** *(moved here from M2 on 2026-05-11)* — populate / sync local Glance from OVHCloud PCI images: selectable list in a config file, runnable via systemd timer or equivalent, inheriting OVHCloud's CVE-driven image lifecycle. Likely owners (per brief stakeholders): the **image team** (PCI SRE + bare-metal SRE). Define the sync tool + config schema + cadence as part of this task. M2 ships only a small pre-loaded base-image set; this task brings the full catalogue.
- 🆕 **\[PB-4] Volume snapshot UI actions** *(moved here from M2 on 2026-05-11)* — `create / clone / rollback / delete` per Brief 01. Drives "Trigger snapshot" button on the volume detail page (Figma) + "Create new volume from snapshot" flow. Operator-side Ceph CoW (Brief 02) is the prerequisite — landing it in M3 lets the Ceph work consolidate with the broader SNC-parity wave.
- 🆕 **\[PB-6] CloudStore VM App UI** *(moved here from M2 on 2026-05-12)* — Figma `https://www.figma.com/design/x3kCSfzWPKwKta6DjAFRwI/OPCP-Flow?node-id=8066-11730`. **Both** the first cut (create-instance form, filterable list, instance detail with VNC console + controls) AND the polished sidebar / stat cards / sparkline polish now land here. M2 ships only the OpenStack API surface (plus optional Horizon); the first-party VM App UI is M3.
- 🆕 **\[PB-3] Volume backup → customer-configurable S3** — full export / copy of a volume, restorable to *another* Ceph cluster (e.g. cluster lost after upgrade). Push target is an S3 location the customer configures.
  - 🚩 **Veeam path** — Brief 01 lists *"and / or by using industry standards like Veeam"* as at-risk. Confirm whether Veeam is in V1 scope or a follow-up.
- 🆕 **\[PB-7] Horizon access for power users** — required for advanced flows like editing security groups (VM firewalls). Brief explicitly names this. Define how it's exposed (separate ingress? off the LZM header?).
- 🆕 **\[PB-8] IT Admin views** — list all VMs (link to account) + free CPU/RAM + scaling action; list all volumes (link to account) + storage capacity + scaling action; **Account view** (all VMs of an account); list all hardware nodes (VM + storage) with utilization (raw CPU / mem / disk + key metrics) + a global view; *"allow accounts to use a specific service"* action via UI.
- 🆕 **\[PB-9 partial] Migrate VM to another node** as an admin action — exposed from the IT Admin VM list. The full lifecycle (drain / decommission / live-migration during destroy) lives in M4; here we just need the manual one-shot.
- 🆕 **\[PB-11 upscale] Upscale of compute and Ceph clusters** from the IT Admin UI (initial deploy is M1; this is the +1-node-at-a-time path).

### Note from the project curator (6 May Jira comment)
> *"We maybe should check, for Milestone 3 / 4, what topics from [SOV-462] should be moved into the Compute Milestones, so we can close SOV-462. For me only the really critical stuff we want to do before the CloudStore merge needs to stay and maybe prioritized."*

→ A scope-rationalisation pass against SOV-462 is itself an M3 prerequisite. Track as Q-203.

---

## Cross-references

- **Where things go (cs-cp / oc-cp / cbs-cp):** [architecture/what-goes-where.md](../architecture/what-goes-where.md)
- **Per-proxy placement:** [Decision-2026-05-09b](../decisions.md) — all 6 proxies live in cbs-cp
- **SNC deployment flow (manual-step inventory):** [architecture/snc-deployment-flow.md](../architecture/snc-deployment-flow.md)
- **Gap rows folded in:** [PB-2](../product-briefs.md) Glance sync *(moved from M2)* · [PB-3](../product-briefs.md) backup → S3 · [PB-4](../product-briefs.md) snapshot UI *(moved from M2)* · [PB-6](../product-briefs.md) CloudStore VM App UI *(moved from M2)* · [PB-7](../product-briefs.md) Horizon for power users · [PB-8](../product-briefs.md) IT Admin views · [PB-9 partial](../product-briefs.md) migrate VM action · [PB-11 upscale](../product-briefs.md)
- **Other milestones:** [M1](M1-install-the-service.md) · [M2](M2-start-a-vm.md) · [M4](M4-make-it-airgapped.md)

> *(Auto-recovery [PB-1] and the 3 Cinder volume tiers [PB-5] are M4 — see [Decision-2026-05-09g](../decisions.md) and [Decision-2026-05-09i](../decisions.md).)*
