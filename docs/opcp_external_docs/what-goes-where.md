---
id: compute-block-on-cloud-store/architecture-what-goes-where
type: deep-dive
diataxis: explanation
title: "What goes where — component placement"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# What goes where — component placement

> Source: [`drawings/2026-05-09_what-goes-where.png`](drawings/2026-05-09_what-goes-where.png) — the working "OPCP + CloudStore Placement of Components and ideas" diagram from the architecture board.

This is the canonical answer to the per-component question "in the converged OPCP + CloudStore world, where does this thing live?". It supersedes the earlier per-proxy guess in [`proxies-placement.md`](proxies-placement.md).

## The big picture

<img src="../../../../_docs/diagrams/what-goes-where-overview.svg" alt="SNC CP today → OPCP + CloudStore split — three planes with CloudStore Core Services / cloudstore-vm-bs-service / migrated paas-snc apps distinguished, and operators / OPCP Core platform / bare-metal nodes shown inside oc-cp" />

> Left = SNC Cloud Platform today (bespoke control planes). Right = the three-plane target with **cbs-cp** on top, **cs-cp** in the middle (split into CloudStore Core Services · the new VM-&-Block Service · migrated paas-snc global apps), and **oc-cp** at the bottom (operators · OPCP Core platform · bare-metal nodes). The colour tags next to each SNC component on the left point to the plane it lands on.

## Common GitOps approach (shared among all three planes)

Same building blocks, applied at every plane (cs-cp, cbs-cp, oc-cp):

- **fluxcd** — reconciler
- **k3s** — runtime
- **ansible** — host-level provisioning
- **terraform** — infra-level reconciliation (via `tofu-controller`)
- **(tofu, helm, ks, source) controllers** — Flux-CD ecosystem
- **oci repository** — distribution

This is what the CloudStore calls "CloudStore Core" + the OPCP team calls "iRobox + flux + tofu-controller". The same pattern, three deployments.

## The new CloudStore Service: `cloudstore-vm-bs-service`

This is the **single CloudStore Service** that this whole project ships. It bundles VM + Block. It has both planes per the standard CloudStore Service contract (`cloudstore.yaml`):

### Control plane (TF modules in the package)
- **Input from cloudstore:** node IDs (which BM nodes to use as compute / storage), cluster-provided creds, OIDC, DNS, …
- **What it does:**
  - Manages BM nodes via the **OPCP Infra API** (in oc-cp on the OPCP Controller)
  - Provisions the **vm-bs-service control plane (cbs-cp)** — a separate k3s + apps cluster
  - Provisions the **proxies** (regional + global, as VMs inside cbs-cp)
- **Output to cloudstore:** identifiers, status, endpoints

### Data plane (TF modules in the package)
- **Input from cloudstore:** account ID, cluster-provided creds, OIDC, DNS, …
- **What it does:** ensures the correct configuration for an Account so the End User can use the VM service (Keystone domain creation, federation, project mapping, app creds bootstrap, …)
- **Output to cloudstore:** identifiers, status

## Where each SNC component lands in the converged world

| SNC today | Lands in (target) | Notes |
|---|---|---|
| **Compute / OpenStack on BMPod** | `oc-cp` — **OPCP Core control plane** with Compute Controller / API | Operator already V0; demo'd Apr 24 |
| **Block storage Ceph cluster** | `oc-cp` — Storage Controller / API | **Operator NOT YET STARTED** — SOV-256 in Backlog |
| **Object storage Ceph cluster (RGW)** | Out of scope for this project (separate CloudStore Service track) | But same pattern |
| **Keystone Controller** | `oc-cp` — Keystone Controller / API | M2 work; called by the data plane of `cloudstore-vm-bs-service` |
| **PaaS-SNC global control plane (apps)** | `cs-cp` — alongside cloudstore-core-services | "without keycloak" because cs-cp already has Keycloak L2/L3 |
| **PaaS-SNC regional control plane (apps)** | `cbs-cp` — the new vm-bs-service control plane | One cbs-cp per VM-Service deployment |
| **6 SNC proxy groups (Global L2/L3, Regional L2/L3, Data Plane L2/L3)** | `cbs-cp` — all of them, as VMs | **Updates earlier guess.** No proxy lives in cs-cp. |
| **Proxy Redis (token attribution)** | `cbs-cp` (alongside the proxies) | Per the M2 graph: "Deploy proxy redis'" lives in the Extend ctrl plane block |
| **Business Logic API** | `cs-cp` (the `BL` box) | Now part of cloudstore-core stack |
| **CloudStore UI / Landing Zone Manager** | `cs-cp` | Already there |
| **Keycloak L2 (admin) + Keycloak L3 (per-account)** | `cs-cp` | Already there; used by both new Service and migrated SNC apps |
| **Keycloak L1 (infra-level)** | `oc-cp` | Already in OPCP Core |
| **Harbor** | `cs-cp` | Already there |
| **Wazuh / NTP / DNS / Log Archiver / LDP (Pod #0 stuff)** | **Out of scope for V1** (Decision-2026-05-09e: Pod #0 model deferred) | Re-visit when SNC V2 |

## OPCP Infra API call paths (from the diagram)

> Canonical reference for the operator design: [`opcp-core-operator.md`](opcp-core-operator.md). See also the [glossary entries for the four CRDs](../../../../../shared/glossary.md#operator-crds-the-k8s-native-api-to-opcp-core).

| Caller | Callee | Why |
|---|---|---|
| `cloudstore-vm-bs-service` control plane (TF) | **OPCP Infra API** in oc-cp (compute endpoints) | Provision Nova compute nodes from BM |
| `cloudstore-vm-bs-service` control plane (TF) | **OPCP Infra API** in oc-cp (storage endpoints) | Provision Ceph storage nodes from BM |
| `cloudstore-vm-bs-service` control plane (TF) | **OpenStack API** in oc-cp | Provision k3s VMs (for cbs-cp) and proxy VMs |
| `cloudstore-vm-bs-service` data plane (TF) | **OPCP Infra API** in oc-cp (keystone endpoints) | Create Keystone domain, federation, project per account |

## Implications

1. **The operators are the API layer to OPCP Core.** CloudStore Services don't talk to OpenStack directly except for VM provisioning (used to provision the proxies + control plane). All physical-node lifecycle goes through operators.
2. **There is no "Service-vs-Core-Service" split for proxies.** Every proxy lives in cbs-cp, which is provisioned by the CloudStore Service. The proxies are inside the Service's footprint.
3. **cbs-cp has to be small enough to bootstrap on the CloudStore's existing primitives.** It needs VMs (provisioned via OPCP Core OpenStack), k3s on those VMs (chicken/egg called out in M2 — "Is VM in CloudStore available to use for Ctrl Plane stuff"), Flux-CD, OCI artifacts pulled from Harbor.
4. **Keycloak is reused, not migrated.** SNC's Keycloak L2 + L3 instances disappear; cs-cp's Keycloak L2 + L3 (which are CloudStore Core Services today) take over. The migrated "apps of paas-snc global cp" land "without keycloak" specifically because cs-cp already has them.
5. **`cloudstore-vm-bs-service`'s control plane is essentially a manifest of "spin up cbs-cp with these N proxies, then call the operators with these node IDs"**. The data plane is a small TF that calls the keystone operator. Both fit the existing `cloudstore.yaml v1alpha2` contract — no schema bump needed (TBC).

## Open questions raised by this picture

- **The Common-GitOps red box at top-left** lists "fluxcd, k3s, ansible, terraform, controllers, oci repository" — *who builds this once, vs each plane re-implementing?* (CloudStore Core has it; OPCP Core has it; cbs-cp will need it. Sharing a base?)
- **Apps of paas-snc global cp "(without keycloak)"** — exactly which apps are these? (BL is shown explicitly; is everything else cosmetic UI / observability?)
- **Apps of paas-snc regional cp** — same question; need a list.
- **Where does "Provide VM images" live?** Shown on the M2 graph but not placed on the what-goes-where diagram. Likely Harbor + Glance.
- **The "external" arrows from cs-cp to cbs-cp ("ZOOM IN") and from cloudstore to vm-bs-service ("manages")** — which controller does the management? CloudStore API + Temporal? `tofu-controller` from cs-cp?
