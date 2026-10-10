# Milestone 2 · "Start a VM" *(API-only Beta)*

> **User story:** *As an **IT Admin**, I enable the Compute & Block App for my Accounts (End Users), so my End Users can start deploying VMs with Volumes via the OpenStack API — **directly**, with manual Keycloak setup per the M2 runbook.*
>
> **Reached at the end (API-only Beta):** an Account has the service enabled (via a **manual Keycloak runbook** + a **manual `kubectl apply` of a `KeystoneDomain` CR** per Account — see [`runbooks/manual-keycloak-account-activation.md`](../runbooks/manual-keycloak-account-activation.md)). End Users in that Account can launch VMs with attached volumes via the **OpenStack API** (CLI / SDK / `python-openstackclient` / Terraform `openstack` provider), reaching the OpenStack endpoints **directly** (no SNC proxy stack in front in M2). VNC console available; a basic pre-loaded Glance image catalogue is in place. *(The first-party **CloudStore VM App UI**, volume snapshots, full PCI image sync, Horizon basic, **6 SNC proxy groups**, and **Business Logic automation** all land in M3; auto-recovery / HA lands in M4.)*
>
> **Scope decision 2026-05-13 — Phase 1 = API-only Beta:**
> - **No proxies in M2.** Endpoints exposed directly; full SNC stack moves to M3. Beta consumers accept endpoint-URL change risk. New design task: [`jira/SOV-731-design-proxyless-api-exposure.md`](../jira/SOV-731-design-proxyless-api-exposure.md).
> - **No Business Logic automation in M2.** Keycloak L3 realm/client/role/group setup is **manual** per the runbook. BL automation slips to M3. New estimation ticket: [`jira/NEW-M3-bl-estimation.md`](../jira/NEW-M3-bl-estimation.md).
> - **SOV-254 stays in M2** but is **triggered manually** via `kubectl apply` per the runbook. New Task under SOV-254 owns the runbook delivery: [`jira/SOV-735-task-manual-runbook.md`](../jira/SOV-735-task-manual-runbook.md) — assignee Ibrahim Takouna (EXT).
> - **Horizon best-effort moves to M3** (depends on the proxy stack).
> - `CLOUD-587` / `CLOUD-589` / `CLOUD-600` / `CLOUD-616` re-target from M2 → M3.
>
> **Why this milestone (Beta):** validates that the **Keystone Controller** (`SOV-254`) works end-to-end, that a customer Account can be provisioned via the manual runbook, and that End Users can use direct OpenStack endpoints to manage their workloads. Concrete done-test: an Account Admin/User in an enabled Account **can create and `ping` a VM** via the OpenStack API after Ibrahim runs the manual runbook for them. This is the proof that the new CloudStore-packaged path can actually serve a tenant — *before* the SNC proxy + BL stack layers go on top in M3.
>
> ↑ Index page: [`milestones.md`](../milestones.md).

---

## Visual

![M2 illustration](../../../../../products/cloudstore/misc/compute-block-on-cloud-store/user-stories/visuals/M2-illustration.png)

> *Polished cartoon illustration generated from the [image-gen prompt](visuals/M2-image-prompt.md). The structural composition reference is [`visuals/M2-layout.svg`](visuals/M2-layout.svg).*

---

## Personas

| Tier | Persona | What they do in M2 |
|---|---|---|
| **L2** | **IT-Admin** | Enables the *Compute & Block* service for an account in the CloudStore admin UI. |
| **L3** | **End User** | Uses the **OpenStack API** (CLI, SDK, or `openstackclient`) — or the **Horizon UI** if it shipped — to create an instance with an attached volume and get a running VM (no auto-recovery — that's M4; no first-party CloudStore VM App UI yet — that's M3). |

> *(L1 Operator does not act in M2 — their substrate work is M1's prerequisite, and the lifecycle work is M4.)*

---

## Sequence (matches the four step badges in the illustration)

1. **① L2 enables** the *Compute & Block* service for an account in the CloudStore admin UI.
2. **② Keystone Controller configures** the realm + domain + IdP federation for that account in OPCP Core.
3. **③ L3 creates** an instance via the OpenStack API (`openstack server create ...`) — or via Horizon if it shipped.
4. **④ VM runs** on a Compute node, with `vol-01` attached via Cinder/Ceph RBD, surfaced through the cbs-cp proxies.

---

## What's in the picture (layer-by-layer)

- **LANDING ZONE (top)** — L3 with an `openstack server create ...` CLI session + `openstack server list` output showing `my-vm · b3-8 · Active · vol-01 (100 GB)` + a VNC console window opened via `openstack console url show`. **Optional Horizon** browser tile to the right with a "best-effort · maybe M2, otherwise M3" tag. *(The first-party CloudStore VM App UI is M3 — not in this picture; snapshots also M3.)*
- **CLOUD STORE (middle)** — L2 + admin UI with the *Compute & Block* per-account toggle ON + the `cbs-cp` Service control plane (already running, pre-existed before M2 — proxies, Horizon host, Manager UI, DNS, TLS, first-party VM App + LZM integration).
- **OPCP CORE (bottom)** — Keystone Controller (Realm + Domain + IdP federation + group mapping + project / users / appcreds + Keystone ingress) + Glance images (basic pre-loaded subset — full sync from OVHCloud PCI catalogue lands in M3) + Compute node with `my-vm` running and `vol-01 (100 GB)` attached via Cinder · Ceph RBD.

---

## Tasks (from the M2 draft graph)

### IAM & Account flow (centre)
- **Create Account in cloudstore** → **Setup IAM & ACLs** which fans out to:
  - **Create Keycloak Realm**
  - **Configure admin privileges for account admin on realm / domain**
  - **(red ring around the next group)** *"does this happen always when creating an account? or only if Compute & Block or other openstack-based services is active?"*
    - **Implement Keystone Controller & API**
      - **Create Keystone Domain & Federation & IdP**
      - **Setup Keystone Ingress (apache deployment & mod_openid)**

### L3 user enablement (left)
- **Allow L3 user(s) to use OpenStack APIs** ⚠️ UX note
  - **Create Keystone project (via federation: group & attr mapping)**
  - **Create user**
  - **Assign user to group**
  - **Create appcreds for user**

### Networking (right)
- **Setup IP pools** → **Setup "desired" networking in OPCP core (public? private?)**

### Provide VM images
- **Provide basic VM images** (right side, bottom) — M2 ships a small pre-loaded subset of base images bundled with the service (enough to boot a stock Linux VM end-to-end). The full **\[PB-2] populate / sync local Glance from OVHCloud PCI images** flow — selectable list in a config file, systemd-timer sync, inherited CVE-driven image lifecycle, image-team ownership — moves to **M3**.

### Control plane k3s
- 🔵 **Implement k3s provisioner (ansible playbooks?)** — note: *"Is VM in CloudStore available (to use for Ctrl Plane stuff)"* (open question)
- 🔵 **Implement terraform modules / plan to provision vm resources for the svc control plane (k3s)**
- 🔴 *"Do we need separation of global and regional ctrl plane?"* — open question for M2

### Extend ctrl plane (red circle)
- **Extend ctrl plane** → fans out to:
  - **Deploy proxies** ← **Configure proxies (for certs & domains)** + **Manage DNS records**
  - **Deploy proxy redis'**
  - *(further task, partially cut off)* — **Manage TLS certificates**

### Added from Brief 01 (PM input — 2026-05-09)
- 🟡 **Horizon UI — best-effort surface** — if the Horizon host (already part of the `cbs-cp` proxy + manager stack) can be exposed cheaply behind the regional proxies with Keystone-federated SSO, ship it in M2. If it needs non-trivial work (separate ingress, auth-flow design, polish), defer to M3 alongside the first-party VM App UI.

> **PB-6 CloudStore VM App UI — first cut** moved to **M3** *(decided 2026-05-12)* — M2 ships an OpenStack-API-only surface (plus optional Horizon). The first-party VM App UI (create-instance form, filterable list, instance detail with VNC console + controls) now lands in M3 alongside the polished Landing Zone Manager work.
> **PB-2 Glance sync from OVHCloud PCI** moved to **M3** — M2 ships only a small pre-loaded base-image set.
> **PB-4 Volume snapshot UI actions** (`create / clone / rollback / delete`) moved to **M3** (operator-side Ceph CoW work folds into the M3 SNC-parity wave).
> **PB-1 Auto-recovery** moved to **M4** (lifecycle / failure handling pairs with the host-failure detection and node lifecycle work). M2 ships VMs *without* auto-recovery surfaced; the on / off toggle on the create-instance form lands when M4 brings the operator side online.

---

## Architecture-board TLDRs (notes block, bottom-right of M2 graph)

**For it is like that:**

**ActivateService / Install Service / Deploy VM CTRL-Plane**
- Use the already existing VM Feature from Openstack/OPCP and use VMs to Provision VM CTRL-Planes with Proxies, Managers, Horizon etc.
- Use Compute Controller to get Compute Nodes "ready for VM" (base installing, Openstack Nova installing & configuration.)
- Use Storage Controller to get an in cinder configured CEPTH Cluster. ⇒ Openstack is able to provision Block Storage on Customer Projekts

> **TLDR:** *VM-CTRL-Plane ready, Openstack Ready with Compute and Block Storage*

**Activate Service for Organisation / Deploy Data-Plane (Terraform Module)**
- Create Keystone Domain, Configure L3-KeyCloak Realm of Organisation, Configure Proxys, Managers etc.

> **TLDR:** *(continues below the visible crop — likely "Allow Organisations to use Openstack(only configurations needed)")*

---

## IT-Admin "enable Compute & Block for an Account" end-to-end flow

> Refined 2026-05-12 in the Keystone Controller workshop ([meeting notes](../meetings/2026-05-12-keystone-workshop.md)). The IT-Admin action has **two halves** — an OPCP-side chain that the Keystone Controller drives, and a CloudStore side that the Business Logic team owns.

### Half 1 — OPCP Core side (Keystone Controller, 6 resources per `KeystoneDomain` apply)

cs-cp's per-Account TF posts a `KeystoneDomain` CR (via OPCP Infra API once Q-112 is closed, or directly via `kubernetes_manifest` per Q-112 Option B). The Keystone Controller reconciles all 6 resources below in a single `terraform apply` from its iRobox-sourced TF module (M2 target: a new `keystone-federation` sub-module — see Q-114):

1. **Keystone domain** — one per Account, name = Account slug. Today's `keystone` TF module covers this.
2. **Identity Provider (IdP)** in Keystone — points at the Cloud-Store-side Keycloak as OIDC issuer.
3. **Federation mapping** in Keystone — translates Keycloak groups → Keystone roles + projects.
4. **Apache pod with `mod_openidc`** — sits next to Keystone in OPCP-Core's K8s control plane, performs OIDC redirect, forwards `HTTP_OIDC_*` headers. Created via Terraform Kubernetes provider.
5. **HTTPRoute** (Gateway API; Ingress patch in legacy flow) — adds a path-prefix match routing the federation redirect URL to the Apache pod. *"It's more easy than before, because we use a gateway API instead of Ingress" — Ibrahim, workshop.*
6. **NetworkPolicy** — allows the Apache↔Keystone OIDC handshake (Cilium-side policy on OPCP Core's K8s).

**Observability note:** the Prometheus probe for the federation **stays in the TF module**, NOT in the Keystone Controller's reconcile loop (decision 2026-05-12 — see [`decisions.md`](../decisions.md)). The operator binary stays Prometheus-free; observability is consumer customisation.

### Half 2 — CloudStore side (Keycloak + BL)

The Keystone Controller's job ends at *"Account is federated with OpenStack Keystone."* For the user to actually log in and provision VMs, the **CloudStore side** still needs:

- **Assign projects + group mapping** for the user in Keycloak (Account-level realm)
- **Hand out credentials** so the user can authenticate to Keystone via the federation path

**Ownership:** the CloudStore **Business Logic (BL) team** owns this. `CLOUD-587` (Merge IAM/BL Implementation) is the 8-week M2 blocker that delivers it.

**If BL is not ready by M2** (likely — `CLOUD-587` is unassigned as of 2026-05-12), Ibrahim's plan: *"We will do it manually. We go to Keycloak, set up the project-group mapping, and give the credentials to the customer."* I.e. an admin opens the CloudStore Keycloak admin UI for the affected realm and sets the mapping by hand.

**Open:** Q-113 — *who* does the manual Keycloak step if BL isn't ready (CloudStore Packagers? OPCP Core team? Customer support?). Has tooling implications (CLI vs UI walk-through). Tracked in [`../open-questions.md`](../open-questions.md).

### Sequence (extends the four step badges in the illustration)

The 4-step badge sequence from the illustration above stays correct at a high level; this section shows **what step ② expands into** under the hood (Keystone Controller side) + adds CloudStore-side workhand-off:

1. **① L2 IT-Admin enables** the *Compute & Block* service for an Account in the CloudStore admin UI.
2. **② CloudStore-side** (CLOUD-587 / BL or manual):
   - Keycloak realm + group mapping configured for the Account
   - Per-user credentials handed out
3. **② OPCP-side** (`SOV-254` Keystone Controller + `KeystoneDomain` CR):
   - Domain → IdP → mapping → Apache pod → HTTPRoute → NetworkPolicy (all 6 above)
4. **③ L3 End User** logs in via Keystone federation, authenticates against Keycloak, gets a Keystone token, creates an instance via the OpenStack API.
5. **④ VM runs** on a Compute node with `vol-01` attached, surfaced through the cbs-cp proxies.

> **Naming note (workshop output):** the meeting used "Keystone Operator" / "keystone-op" for what we call the **Keystone Controller** (a reconciler inside the unified OPCP Infra Operator binary). When reading meeting artefacts, mentally map "operator" = binary, "operator/op" prefix on Keystone = Keystone Controller.

---

## M2-specific open questions (also tracked in [`open-questions.md`](../open-questions.md))

- *"Do we need separation of global and regional ctrl plane?"* (red circle on the graph) — **Q-101**
- *"Is VM in CloudStore available (to use for Ctrl Plane stuff)"* — **Q-102**, ✅ closed 2026-05-12 (use OPCP-Compute hypervisor VMs)
- *"Does Implement Keystone Controller & API happen always when creating an account, or only if Compute & Block or other openstack-based services is active?"* — **Q-103**
- *"Do we even need proxies for non-snc?"* — **Q-104**
- *"If we consider M2 (definitely not yet, ...based APIs & Manc..."* — partial annotation — **Q-105**
- **Q-110** — Keystone Controller owner (`SOV-254` still unassigned; refined 2026-05-12 with the 6-step list)
- **Q-112** — Extend OPCP Infra API for `KeystoneDomain` (or use `kubernetes_manifest` directly from cs-cp's TF)?
- **Q-113** *(new 2026-05-12)* — Who does manual Keycloak project-group mapping if BL isn't ready?
- **Q-114** *(new 2026-05-12)* — Who refactors the `keystone-post-setup` TF module to extract `keystone-federation` (precondition for `SOV-254` reconcile-loop work)?

---

## M2 preconditions — `LVL2-22779` (CloudStore Packagers team, sibling LVL2)

> Added 2026-05-12 PM. `LVL2-22779` *"OPCP - CloudStore control plane preparation [Q4FY26]"* is the **CloudStore Packagers team's parent epic** for all CloudStore-side preparation our M2 work depends on. It's a sibling LVL2 (parent `LVL2-19101 CloudStore 1.0`), owned by **Thomas Poehler (EXT)**, reported by Pierre-Yves Aillet. Start 16/Mar/26 · End 14/Jun/26 · 33 weeks · Wish-delivery 04/Sep/26.
>
> **We cannot fold this tree into our `LVL2-18373` hierarchy** (different team, different parent). We track it as a precondition via Jira `depends on` link from `SOV-257`.

The three children of `LVL2-22779` (all "Need Work" today, all originally children of `CLOUD-579`):

| Key | Title | Assignee | Estimate | What it blocks for M2 |
|---|---|---|---|---|
| `SOV-16` | [Cloudstore Packaging] Separate CloudStore L2 and L3 endpoints | **Ibrahim Takouna (EXT)** | 5 wk / 24 MD | The Account/IAM flow + per-Account proxy work needs to know **where L2 endpoints live vs L3** (today they share an IP). Cilium-managed LoadBalancer + dedicated networks + 2 ingress controllers (or Gateway API). ADR: `confluence /0037+-+Openstack+endpoints+separation`. iRobox PR `#489`. |
| `SOV-17` | [Cloudstore Packaging] Make artefacts available to services | **Unassigned** | 6 wk | The service-Package install pipeline needs to deliver **glance images + docker images + packages** from CloudStore to where OPCP-Core and CloudStore controllers can consume them. M1 also benefits. Confluence ref: `Service+Metapackage`. |
| `SOV-18` | [Cloudstore Packaging] Dedicate one compute node to deploy control plane VMs | **Unassigned** | 3 wk | **The cs-cp + cbs-cp on OPCP-Compute hypervisor VMs scope** — covered in the [2026-05-12 decisions log entry](../decisions.md) and `jira/gaps/SOV-18-update-2026-05-12.md`. Closes Q-002 + Q-102. |

**LVL2-22779 has a "needs more design" flag** — Vincent Casse 2026-02-11: *"This work need more design to define what we use on business logic team and CloudStore team."* The precondition isn't just "these three Epics close" — there's also a design gap on CloudStore + BL team boundaries (tracked via Q-111 in [`open-questions.md`](../open-questions.md)).

**Action on the LVL2-18373 side:**
- `SOV-257` (M2 milestone Epic) gets a Jira `depends on` link to `LVL2-22779` (and individually to `SOV-16`, `SOV-17`, `SOV-18` if we want fine-grained tracking).
- `[MS2][cbs-cp / proxies] Development` (work-block Epic, to file under LVL2-18373) acknowledges these as dependencies.
- `[MS2][CloudStore] Development` (`SOV-680`) explicitly notes SOV-16 + SOV-17 as L2/L3-endpoint + artefact-delivery preconditions.

---

## Cross-references

- **Where things go (cs-cp / oc-cp / cbs-cp):** [architecture/what-goes-where.md](../architecture/what-goes-where.md)
- **Decisions in play:** [Decision-2026-05-09e](../decisions.md) (use existing OPCP Nova to bootstrap cbs-cp) *([Decision-2026-05-09g](../decisions.md) — auto-recovery — applies to M4, not M2.)*
- **Sibling LVL2 (M2 precondition):** `LVL2-22779` + children `SOV-16` / `SOV-17` / `SOV-18` (CloudStore Packagers team; see "M2 preconditions" section above).
- **Gap rows folded in:** *(none — PB-2 Glance sync · PB-4 snapshot UI · PB-6 VM App UI all moved to M3; M2's UI surface is OpenStack API + optional Horizon)*
- **Other milestones:** [M1](M1-install-the-service.md) · [M3](M3-deploy-all-components.md) · [M4](M4-make-it-airgapped.md)
