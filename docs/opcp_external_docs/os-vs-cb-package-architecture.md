---
id: object-storage-on-cloud-store/architecture-os-vs-cb-package
type: deep-dive
diataxis: explanation
title: "OS vs CB package architecture — what the two packages do differently, and what OS can borrow"
owner: sov-copilot
status: draft
publish_target: git
product: cloudstore
tags: [object-storage, compute-block, architecture, comparison, provisioning]
---

# OS vs CB package architecture

> **Why this exists.** The two CloudStore service packages are built on opposite provisioning
> interfaces, and that difference gets re-derived in every design conversation because no side-by-side
> existed. §1–3 are the comparison; **§4–5 are the practical half** — what Object Storage can adopt
> from Compute & Block *without* revisiting the interface decision.
>
> **Sources.** OS: [`handover-2026-08-jan-vacation.md`](../handover-2026-08-jan-vacation.md) ·
> [`SOV-2031`](SOV-2031) role inventory · project
> [`CLAUDE.md`](../CLAUDE.md). CB: [`cb-tech-spec.md`](../../compute-block-on-cloud-store/architecture/cb-tech-spec.md) ·
> [`what-goes-where.md`](../../compute-block-on-cloud-store/architecture/what-goes-where.md) ·
> [`cb-service-package-survey-2026-06-25.md`](../../compute-block-on-cloud-store/architecture/cb-service-package-survey-2026-06-25.md) ·
> [`handover-sov-687-storage-minint.md`](../../compute-block-on-cloud-store/handover-sov-687-storage-minint.md).
>
> ⚠️ **Dating.** The CB package survey is from **2026-06-25** (`main` @ `0.1.0-alpha.7`); the operator
> and irobox facts are from the **2026-08** minint runs. The CB *package* branch state has not been
> re-verified since June.

---

## 1. The one-line difference

**OS talks to the OpenStack API directly. CB is forbidden from doing so for bare metal** — it calls
the OPCP Infra API and lets the Infra Operator provision.

Neither is drift; both are recorded decisions.

> **The criterion, stated (Jan Stuhlmann, 2026-08-28):** *use the **OPCP Infra API** when what the
> package provisions has to be **integrated into the OPCP Core OpenStack**; use the **OpenStack API
> directly** when it does not.*
>
> - **CB** → Infra API, because the compute the package provides must be **set up as a hypervisor on
>   the OPCP Core OpenStack** (the operator's Phase-2 *Nova join*, §1 diagram).
> - **OS** → direct, because the Ceph/RGW cluster is **standalone and end-user-facing**; nothing of
>   it registers into Core OpenStack (OSQ-11).
>
> **So the two opposite paths are both valid** — that is the point of this section. The "privileges"
> reasoning recorded below is downstream of this: CB needs elevated OpenStack + network privileges
> *because* it has to join Core, not as an independent reason. **Revisit trigger:** if OS ever
> becomes OPCP-internal too — e.g. **backup S3 for Cinder** — the Infra API could become the right
> call. Open, undecided: **OSQ-39**.

| | Decision | Reasoning as recorded |
|---|---|---|
| **OS** | **[ADR 2026-05-27](../decisions.md)** (Marc, Webex) — *"the VCF way, not Infra-API"*; the boundary was set by OSQ-01, 2026-05-21 | OS needs no special privileges, unlike CB. The operator binary could be reused *inside* the package. |

> ⚠️ **Citation corrected 2026-08-25.** This was previously cited as *OSQ-15*. That is wrong — OSQ-15
> asks *"Rook vs ceph-operator"* and closed on **CephADM + Ansible**. The VCF-way note was filed under
> it only because it made the then-live *"Option C (Rook + VCF)"* look natural; Option C was
> superseded and the citation outlived its context. There is now an
> [ADR](../decisions.md) — cite that.
| **CB** | **2026-05-09d/e** — Infra API, not cross-cluster CRs | *"CloudStore Services do not touch physical nodes directly."* The only direct OpenStack use is VM provisioning (cbs-cp k3s VMs, later proxy hosts). |

```
OBJECT STORAGE                          COMPUTE & BLOCK
──────────────                          ───────────────
cloudstore.yaml                         cloudstore.yaml
   │ tofu apply                            │ tofu apply
   ▼                                       ▼
OpenStack API  ◄── the package         OPCP Infra API   (REST, mastercard/restapi provider)
   │               does it all             │
   │                                       ▼
   ▼                                  Compute/ComputePool · Storage/StoragePool  CRs
6 VMs                                      │
 1  k3s          service control plane     ▼
 1  oob          jumphost + tinyproxy  OPCP Infra Operator  (oc-cp)
                 + HAProxy + CORS          │  reconcile → provisioner-apply-{name} Job
 3  converged    mon + rgw + osd           │   Phase 1  Terraform → Ironic          ~20 min
 1  osd-only                               │   Phase 2  Ansible: DEBIAN12-CIS       ~40 min
                                           │            + k3s + resource agent
 + vendored ansible-library-copy            ▼            + Nova join
   runs cephadm bootstrap              bare-metal nodes   (1:1:1  CR ↔ job ↔ node)

                                       separately, direct OpenStack API — VMs only for
                                       cbs-cp k3s VMs and (M3) proxy hosts
```

## 2. Side by side

| | **Object Storage** | **Compute & Block** |
|---|---|---|
| **BM provisioning interface** | OpenStack API, package-owned | OPCP Infra API → CRs → operator |
| **Who runs Ironic** | the package | the operator's provisioner job |
| **Who runs Ansible** | the package — the binary is **shipped inside it** *(after the Ansible MR was rejected on "pure HCL" grounds, 2026-07-10)* | the operator, Phase 2, roles from irobox |
| **Node shape** | 6 VMs today; target ≥4 BM with ≥5 drives | min **3 compute + 5 storage** hosts *(the minint demo used 2+2)* |
| **Per-node input** | the full TF variable set | `node_uuid` — *"the only per-host input"* |
| **OS hardening** | ❓ see §5.2 | `DEBIAN12-CIS` + supporting roles, Phase 2, ~40 min |
| **Health signal** | Prometheus agent · Ceph itself | resource agent heartbeat → CRD `Healthy` condition |
| **Own control plane** | ✅ 1 k3s VM, package-provisioned, running | **cbs-cp** — *designed, not built*. M1 ships TF-only |
| **Egress / OOB node** | ✅ jumphost + tinyproxy + HAProxy + CORS | ❌ none. Nodes get apt/DNS from `compute_node_ansible_vars` + hieradata |
| **Status surface to CloudStore** | panel iframe (working) | **none** — *"a black box, no feedback channel"* (Q-246); M2's iframe is unbuilt |
| **Destroy protection** | ❌ none — see §5.4 | ✅ `preventDestroy` on the CR, enforced by the operator |

## 3. What CB inherits that OS owns

Everything in the operator's Phase 1 + Phase 2 is **free to CB and package-owned for OS**: Ironic
provisioning, CIS hardening, node lifecycle, retries and structured status, destroy hooks,
`preventDestroy`, the health heartbeat.

That is the real price of the 2026-05-27 decision, and it is worth stating plainly because it is not
what the decision was argued on. It was argued on **privileges** — OS does not need the elevated
access CB needs — which is itself downstream of the root criterion in §1: **CB's nodes have to join
the OPCP Core OpenStack as hypervisors and OS's do not.** The cost that came with the choice is
**lifecycle ownership**, and that cost is where most of the OS package's current open items sit.

**None of that is an argument for switching OS to the Infra API.** The interface follows from what
the package's output *is*, not from what the package would like to inherit; the escape hatch the ADR
named — reuse the operator binary **inside** the package — is the route to those capabilities without
reopening the interface. The one thing that *would* reopen it is a scope change (OS becoming
OPCP-internal, e.g. backup S3 for Cinder) — **OSQ-39**.

> This is not an argument to revisit that decision. It is an argument for being deliberate about which of
> the operator's *behaviours* OS reimplements, rather than discovering each one as a gap.

## 4. Low-hanging fruit — portable without touching the API-surface decision

The useful distinction throughout: **an Ansible role is portable; a delivery chain is not.** CB's
`compute_node_ansible_vars` → hieradata → CDS render → CR `var.ansible_vars` chain depends on the
operator and cannot come along. The *roles* that chain feeds can.

### 4.1 ✅ apt + DNS — mostly already there, one change to make

**Answer to "could I easily also have `compute_node_ansible_vars` + hieradata?" — no, and OS does not
need it.** That chain exists to get variables *into* a node the package never touches. OS runs Ansible
on its own nodes directly, so the delivery problem does not exist.

OS already has the structural counterpart. `modules/ceph/playbooks/ceph.yml` invokes
**`ceph_system_prep`**, whose task files line up with CB's `roles/system-prepare` almost one to one:

| CB `roles/system-prepare` | OS `ceph_system_prep` |
|---|---|
| `setup_dns` | `system_prepare.yml` *(`systemd-resolved`)* |
| `setup_apt` | `ceph_repo.yml` |
| `setup_packages` | `system_prepare.yml`, `chrony.yml` |
| — | `oob_tinyproxy.yml`, `configure_registry_mirror` *(OS-specific)* |

**So the borrowable thing is not the mechanism — it is the apt source itself.** CB now points apt
**straight at the Artifactory remote** (irobox `eb5f0905`) rather than at `download.ceph.com`:

```
deb [signed-by=/usr/share/keyrings/ceph.gpg] https://<rt-host>/artifactory/apt-ceph-debian-tentacle bookworm main
```

Three things that buys OS, all currently open work:

- **`SOV-2031`** — removes the third-party repo *and* the network-fetched GPG key in one change.
  Artifactory proxies ceph.com's signed repo rather than re-signing, so the Ceph release key ships as
  its own keyring.
- **`SOV-2020` / OSQ-30 R1** — the tinyproxy egress responsibility shrinks, because the largest
  reason for egress was apt.
- ⚠️ **A live hazard, independent of the above:** `ceph_apt_repository_key` names a **suite**, and
  upstream keeps only the current patch release in it. **20.2.3 has been withdrawn** from
  `download.ceph.com/debian-tentacle`. A pinned image version can therefore silently diverge from what
  apt installs — this already bit CB (see [`SOV-2193`](SOV-2193)).

⚠️ **Do not aggregate remotes into a virtual repository.** The jfrog maintainer's guidance is explicit
— dependency-confusion risk; *"use the remote repository's dedicated URL directly."* Two CB PRs were
declined on this. `apt-ceph-debian-tentacle` already exists and is already readable by the node
credential (group `artifactory_edges_airgap`), so no Artifactory change is needed for the apt half.

**Effort:** small — one task file, one variable. **Verify first:** that `ceph_repo.yml` is the only
place the Ceph repo is defined in the vendored copy.

### 4.2 ❓ Host hardening — first find out whether anyone owns it

CB settled this on **2026-05-12**: *no SNC golden-image reuse; the iRobox Ansible roles
(`DEBIAN12-CIS` plus supporting hardening, `system-prepare`, `ovh-tools`, `wazuh_agent`) are the
canonical path*, applied in Phase 2, with the ~40 min accepted as install-budget scope rather than
optimised away. That path is portable in principle — OS already runs Ansible; the roles would need
vendoring, and the cost is ~40 min per node.

**But porting the role is step two.** Step one is a correction:

> 🔴 **The OSQ-34 row asserts that *host/VM* golden images are "already covered", citing
> [`SOV-855`](SOV-855) *"Debian CIS-hardened, matching SNC
> baseline"* and [`SOV-859`](SOV-859) *"hardened Debian 12 VMs"*.
> **Neither ticket is about golden images.** In Jira, `SOV-855` is **`[MS1][Provisioning Engine]
> Development`** (Boris — BM node → Ceph host via Nova/Ironic/Neutron, scale in/out, node replace) and
> `SOV-859` is **`[MS3][S3 Proxies] Development`** (Caddy + Coraza WAF, L2/L3 audience separation).
> Verified 2026-08-25.

If those references are wrong, then OSQ-34's framing — *"host images are covered, only **container**
base images are uncovered"* — is wrong too, and **OS host hardening is owned nowhere**. That is a
materially different gap from the one the row describes, and it matters for SNC qualification.

⚠️ Two innocent explanations before treating it as a finding: the descriptions may have changed since
2026-07-29, or the intended keys may have been different ones. **Confirm with Eddy or Boris rather
than filing.**

### 4.3 ❌ Health signal — not portable, and OS is not the one behind

CB's resource agent PATCHes `/computes/:name/heartbeat` on the **operator's internal REST API**. OS
has no such endpoint and no operator, so the agent cannot come across as-is, and building an OS
equivalent would mean inventing the receiving end too.

**Recommend not porting this.** The underlying need is already met from two directions: the package
ships a `prometheus_agent`, and Ceph reports its own health authoritatively (`ceph -s`,
`ceph orch host ls`) far better than a per-node heartbeat would.

On the *status-to-CloudStore* axis OS is in fact **ahead** — the panel iframe works today, while CB's
equivalent is Q-246's unbuilt M2 sketch. Worth knowing before borrowing in the wrong direction.

### 4.4 Summary

| Candidate | Portable? | Effort | Where it lands |
|---|---|---|---|
| **apt source → Artifactory remote** | ✅ role already exists | **small** | `SOV-2031` · `SOV-2020` R1 |
| **Registry-mirror / air-gap path** | ✅ already in `ceph_system_prep` | — | already done |
| **Host CIS hardening** | ✅ in principle | medium *(+40 min/node)* | **first: fix the OSQ-34 reference** |
| **Health heartbeat** | ❌ needs the operator | — | don't port — Prometheus + Ceph cover it |
| **Destroy protection** | ❌ structurally | — | §5 |

## 5. Destroy protection — the hard one

**The question:** CB's protection lives on a CR held by a reconciler that **outlives the thing being
deleted**. Every OS resource is owned by the deployment's own Terraform state, which goes away with
the deployment. There is no component on the OS side that survives the delete.

That is the whole problem in one sentence, and it means **no direct port exists.** What follows is an
honest options list rather than a recommendation.

| # | Option | Assessment |
|---|---|---|
| 1 | `lifecycle.prevent_destroy` on the volumes | ❌ **Known bad, twice over.** It makes `destroy` *error*, not skip, and it blocks in-place **replacement** as well as deletion — which is what made CB's MAC-drift case unrecoverable. CB deliberately moved *away* from this to the CR field. |
| 2 | **Take the volumes out of the deployment's TF state** | 🟢 **The only lever fully inside OS's control.** Two shapes: **(a)** create the volumes outside the package and *adopt* them via `data` sources, so a destroy never owns them; **(b)** `removed` blocks / `state rm` before the destroy. ⚠️ (a) dents the "the package does everything" principle (OSQ-01) and needs someone else to create them; (b) needs a deliberate pre-delete step, i.e. a **platform trigger** — the same missing piece as `SOV-2033`. |
| 3 | **Snapshot before delete** | 🟡 Not retention, but it bounds the loss. Does nothing for the upgrade path. Reasonable interim mitigation, not a fix. |
| 4 | **The target BM shape shrinks the problem** | 🟡 On bare metal the OSD disks are physical, not `openstack_blockstorage_volume_v3`, so the TF-owns-your-data shape is **partly an artifact of the VM POC**. ⚠️ It does not vanish: releasing an Ironic node triggers a clean that wipes disks. The failure mode moves rather than disappearing. |
| 5 | **`SOV-2033` — CloudStore-side retention + re-adoption** | 🔴 Still the real answer, and still not ours. The under-specified piece remains the **retained → reattached path**: retention is worthless if a new deployment cannot adopt the volumes. |

### 5.1 The piece that already has a ticket

**[`SOV-855`](SOV-855) `[MS1][Provisioning Engine] Development`
(Boris, Backlog) is the natural home for the OS-side half** — its *Done means* already reads:

> - Scale-out: new node joins cluster automatically
> - Scale-in: node drains, cluster rebalances
> - **Node replace: failed node replaced without data loss**

That is the OS counterpart to Stephan's
[storage-node deprovisioning spec](../../compute-block-on-cloud-store/architecture/storage-node-deprovision-spec.md),
and *"without data loss"* is the retention requirement stated in different words. Worth treating
`SOV-2033` as the **CloudStore-side dependency** and `SOV-855` as the **OS-side design**, rather than
carrying both on one ticket that nobody owns.

### 5.2 Two Ceph-layer findings to check against the vendored role

From Stephan's spec, verified against irobox `dev/shohn/SOV-256-storage-node-ansible` — **not yet
checked against `ansible-library-copy`**:

1. **`pools.yaml` creates pools with no `size` argument** ⇒ they inherit replica 3. On 3 hosts with a
   host-level failure domain, removing a host leaves every PG **permanently** undersized. The OS POC
   is exactly that shape (3 converged mons).
2. **`pool_flags.yaml` sets `nodelete` and `nosizechange` on every pool and never clears them.**
   `nodelete` refuses pool deletion ⇒ **teardown is blocked**; `nosizechange` refuses the size
   reduction that would make a 3-node shrink possible.

If the roles share ancestry, (2) is a **second, independent blocker inside `SOV-2033`** — distinct
from the "delete destroys everything" one, and arguably its opposite: the delete may not complete at
all. **A role diff is the cheapest way to find out.**

## 6. Cross-references

- [`alpha-exit-blockers.md`](../alpha-exit-blockers.md) — B1 is the destroy/upgrade gap in §5
- [`open-questions.md`](../open-questions.md) — OSQ-30 · OSQ-34 *(see the §4.2 correction)* · OSQ-37 · OSQ-38
- [`storage-node-deprovision-spec.md`](../../compute-block-on-cloud-store/architecture/storage-node-deprovision-spec.md) — the CB drain/destroy spec §5 draws on
- [`cb-tech-spec.md`](../../compute-block-on-cloud-store/architecture/cb-tech-spec.md) — the three control planes, the Infra API call paths
- [`SOV-2193`](SOV-2193) — the apt findings in §4.1 · [`SOV-2031`](SOV-2031) · [`SOV-2033`](SOV-2033) · [`SOV-855`](SOV-855)
- [`shared/glossary.md`](../../../../../shared/glossary.md) — CR/CRD · reconcile · `preventDestroy` · Ceph vocabulary
