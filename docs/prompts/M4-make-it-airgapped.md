# Milestone 4 · "Make it Airgapped"

> **User story:** *As an **IT Admin** I want to manage my OPCP with Block & Compute air-gapped, so I have full visibility and control, from hardware management to mitigation of stuck VMs.*
>
> **Reached at the end:** the cluster is fully airgapped and operable. L1 Operator owns the substrate (rack new hardware, slot tier-specific NVMe drives). L2 has full **Cluster Lifecycle** controls (add / drain / upgrade / remove / smooth upgrade / downscale / replace / audit log) plus a dark *AIRGAPPED MODE* panel with the airgap guarantees. The OPCP Core operators expose lifecycle CRDs (`MaintenanceWindow`, `NodeDrain`, `RollingUpgrade`, `LiveMigrate`, `HostFailureWatch`). Auto-recovery is on by default — host failures evacuate VMs to surviving hosts within < 60 s RTO. End users pick the storage tier on create (Standard / High / **Insane**) and toggle auto-recovery from the Create Instance form.
>
> ↑ Index page: [`milestones.md`](../milestones.md).

---

## Visual

![M4 illustration](../../../../../products/cloudstore/misc/compute-block-on-cloud-store/user-stories/visuals/M4-illustration.png)

> *Polished cartoon illustration generated from the [image-gen prompt](visuals/M4-image-prompt.md). The structural composition reference is [`visuals/M4-layout.svg`](visuals/M4-layout.svg).*

---

## Personas (all three appear)

| Tier | Persona | What they do in M4 |
|---|---|---|
| **L1** | **Operator** | Finally enters the picture. Racks new high-tier hardware (e.g. a NVMe Insane node for the new top tier), slots it in. The substrate is theirs. |
| **L2** | **IT-Admin** | Wields the full Cluster Lifecycle admin UI: add / drain / upgrade / remove / smooth upgrade / downscale / replace / audit log. Configures auto-recovery defaults. Sees the airgap-mode guarantees. |
| **L3** | **End User** | Picks a storage tier (Standard / High / **Insane**) on the Create Instance form. Auto-recovery is default-on with a visible toggle and a `RTO < 60 s` indicator. |

---

## Sequence (matches the four step badges in the illustration)

1. **① L1 racks a new high-NVMe node** in the server rack — the substrate gains a new slot for the *Insane* tier.
2. **② L2 manages the cluster lifecycle** in the CloudStore admin UI — drains `cpt-02` for a firmware upgrade, has every other lifecycle control on display.
3. **③ Operators handle drain + auto-recovery** — `MaintenanceWindow` + `NodeDrain` + `RollingUpgrade` + `LiveMigrate` + `HostFailureWatch` CRDs do the work; on host failure, VMs are evacuated to a surviving host within < 60 s.
4. **④ L3 picks the Insane tier and turns Auto-recovery on** in the Create Instance form — both surface as first-class UI choices.

---

## What's in the picture (layer-by-layer)

- **LANDING ZONE (top)** — L3 + a richer Create Instance form (Name / Flavor row, Storage Tier row with three pills and **Insane** highlighted, yellow Auto-recovery row with HA shield + RTO, big blue CREATE button) + a running VM preview card with `⛨ Auto-rec` and `● Insane` badges + the airgapped-cluster outcome sticky.
- **CLOUD STORE (middle)** — L2 + the wide Cluster Lifecycle admin UI (top action row with all controls + 4 compute node cards with per-node drain / upgrade / remove buttons + 3 storage pool rows + auto-recovery policy pill) + the dark *⚡ AIRGAPPED MODE* panel with the five airgap guarantees (local Harbor / local OS + firmware / local audit / local IDP fallback / offline upgrades).
- **OPCP CORE (bottom)** — L1 Operator (hard hat + overalls) + the Server rack with the new st-Insane slot highlighted + the Compute + Storage Controllers with extended lifecycle CRDs (including `HostFailureWatch`) + the **Auto-recovery / live-migration mechanism** diagram (Host A failed × → green `evacuate · RTO < 60 s` arrow → Host B with `my-vm` running again) + the **3 Cinder Volume Tiers** card (Standard / High / **Insane** pools, with `vol-01 here`).
- **Cross-layer arrows**: ① rack → admin UI labelled `node appears in admin UI` (up); ② → ③ labelled `drain → live-migrate VMs` (down); ③ → ④ labelled `tiers + HA exposed in form` (up).

---

## Tasks (sub-themes from the Jira)

### 1. Lifecycle of Nodes + Cluster
- Add Node
- Maintenance Mode
- Remove Node
- (Implied: drain, replace, decommission, observability of node state — to detail)

### 2. Observability
- (Not detailed in the Jira yet — likely at minimum: integration with CloudStore's Prometheus + Loki, parity with SNC's LDP / Greylog story for SecNumCloud audit trail.)

### Operator implications (from the Apr 24 video)
- The current operator only handles **provisioning** (`create`), and a basic **update**. **Drain / decommission / live-migration in the destroy step** is *not yet implemented* — needs Block-Storage-Operator and probably new CRDs (e.g. `MaintenanceWindow`).
- A **dedicated agent on each compute node** that feeds back to the operator is *discussed but not implemented*.
- **Live migration** of customer VMs off a node before decommission — design needed; coupled to AMD-SEV-disabled choice.

### Added from Brief 01 (PM input — 2026-05-09)
- 🆕 **\[PB-1] Auto-recovery (vSphere HA equivalent)** — M4 owns the *whole* feature: host-failure detection, evacuation / restart of VMs onto a surviving host, threshold + RTO config, and the customer-visible on / off toggle on the create-instance form. Brief 01 makes this the VMware-migration deal-breaker (< 1 % of Gridscale customers turn `auto_recovery` off), so default-on. Pairs naturally with M4's add-node / drain / decommission lifecycle work.
- 🆕 **\[PB-10] Smooth upgrade of storage + VM hosts** — explicit IT Admin requirement from the brief. Belongs with the M4 lifecycle work; presupposes drain + live-migrate.
- 🆕 **\[PB-11 downscale] 🚩 Downscale of compute and Ceph clusters** — flagged at risk in the brief (red text). Needs explicit go / no-go from architecture board; if no-go for V1, document as deferred and surface the workaround.
- 🆕 **\[PB-5] Three Cinder Volume Types — Standard / High / Insane** — moved from M1 because the higher tiers ([Brief 02](../product-briefs.md#brief-02--block-storage-ceph-rbd-technical-brief): up to 7 500 IOPS / 300 MB/s) likely need different drive specs (e.g. higher-grade NVMe for the *Insane* pool) and ride on top of M4's add-node lifecycle. Tasks: define the three Cinder volume types, wire QoS limits via Ceph, document the per-tier hardware target, expose the type selector in the UI volume-create flow.

---

## Cross-references

- **Operator design (lifecycle CRDs):** [architecture/opcp-core-operator.md](../architecture/opcp-core-operator.md)
- **Where things go (cs-cp / oc-cp / cbs-cp):** [architecture/what-goes-where.md](../architecture/what-goes-where.md)
- **Decisions in play:** [Decision-2026-05-09g](../decisions.md) (auto-recovery — full feature lands in M4) · [Decision-2026-05-09i](../decisions.md) (3 Cinder Volume Tiers as product contract — land in M4 with the right hardware)
- **Gap rows folded in:** [PB-1](../product-briefs.md) auto-recovery · [PB-5](../product-briefs.md) 3 volume tiers · [PB-10](../product-briefs.md) smooth upgrade · [PB-11](../product-briefs.md) downscale (still flagged at risk in the brief)
- **Other milestones:** [M1](M1-install-the-service.md) · [M2](M2-start-a-vm.md) · [M3](M3-deploy-all-components.md)

> **Open question (Q-611):** the brief names auto-recovery as essential but doesn't pin a recovery-time target — the picture and prompts use *RTO < 60 s* as a placeholder. The actual SLA needs the PM + PCI PM sign-off before the M4 freeze.
