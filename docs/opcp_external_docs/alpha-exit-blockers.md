---
id: object-storage-on-cloud-store/alpha-exit-blockers
type: reference
diataxis: explanation
title: "Alpha-exit blockers — Object Storage package (fact base, 2026-07-31)"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Alpha-exit blockers — Object Storage package

**Prepared by:** Jan Stuhlmann · **Date:** 2026-07-31
**For:** Eddy Medina (PO) · Vincent Casse (project owner) · Florent Thiery (product) — **and whoever else owns the beta / customer-readiness call**
**Assessed against:** [`cloudstore-service-object-storage`](https://stash.ovh.net/projects/CLOUDSTORE/repos/cloudstore-service-object-storage/browse) `origin/main` @ `0.2.0-alpha.18`, and the staging POC deployment [`f071496c`](https://cloudstore.staging.cloudstore.ovh/administration/services/object-storage/controllers/f071496c-b821-46c1-a791-6e0729793c05)

> **What this document is:** the **facts** about three lifecycle and validation gaps in the Object
> Storage package, each verified against the package source and named here with its evidence, its
> owner, and what would have to become true to close it.
>
> **What this document is not:** a decision. **The call on alpha / beta / customer readiness is not
> mine to make** — this is input for the people who own it. Where I give a read on the timeline it is
> labelled as my read, and it is separable from the facts it rests on.

---

## 1 · What is *not* in question

The POC works, and that is not what is being examined here:

- A **6-VM deployment stands up end-to-end** from the CloudStore UI: Ceph + RGW + Keystone + panel, S3 reachable.
- The **packaging chain works** — OCI build/publish, air-gapped vendoring, the copier template, `reschedule_copier`.
- The **Ceph layer is real**: 4 OSD-spec templates, CRUSH + pool device-class wiring, L2-admin / L3-user RGW zones, KMIP-OKMS SSE-S3 plumbing.

The gaps below are about **lifecycle and validation**, not about whether the thing runs.

---

## 2 · The three gaps

### 🔴 B1 — There is no update path. Any software update destroys all data.

**This is a dependency on the CloudStore team. It cannot be solved from our side.**

CloudStore appears not to support upgrading a deployed package in place, so the only route to a new
version is **delete + redeploy**. Deleting a deployment tears down the control plane → all resources
→ all disks → **all OSDs**. The one operation a storage service must never undergo is the only
mechanism available for shipping a patch.

**Verified in the package source:**

| Evidence | What it shows |
|---|---|
| `terraform/controlplane/modules/node/instance.tf:52` — `delete_on_termination = false # better keep the data` | ⚠️ **This comment reads as protection and is not.** It stops *Nova* cascading on **instance** deletion only. |
| `instance.tf:10` — volumes are `openstack_blockstorage_volume_v3` resources | The volumes are owned by the **deployment's own Terraform state**, so a destroy removes them regardless of the flag above. |
| `roles/ceph/tasks/upgrade.yaml:88` — `ceph orch upgrade start --image …` | **The Ceph side already works** — forward-only, version-compared, opt-in via the `upgrade-ceph` tag. |

The gap is therefore precisely located: **Ceph can upgrade itself; the platform has no way to
trigger a re-run of a deployment at a newer package version.** `prevent_destroy` is not the fix — it
makes `destroy` *error* rather than skip. Retention has to be deliberate platform behaviour, and the
under-specified half is the **retained → reattached path**: retention is worthless if a new
deployment cannot *adopt* the existing volumes.

**Tracked as:** [`SOV-2033`](SOV-2033) · mirror
[`SOV-2033-package-upgrade-disk-retention.md`](jira/SOV-2033-package-upgrade-disk-retention.md)
**Owner:** **Jan Stuhlmann** *(took assignment 2026-09-01)* — the *delivery* is still CloudStore-team work
(Stephan Hohn watching)
**Closed when:** a deployed package can be upgraded in place, **or** disks survive a delete/redeploy
*and* a new deployment can adopt them — demonstrated, not designed.

> **🆕 2026-09-01 — a CloudStore workstream now exists, and it splits B1 in two.** Created 2026-08-18,
> unreferenced here until today.
>
> - **The upgrade half has a home.** [`SOV-2205`](SOV-2205)
>   *Version upgrade for customer services* — UI version picker → `cloudstore-api` triggers an in-place
>   upgrade. Now linked as ***blocks*** SOV-2033. Its stated prerequisite is
>   [`SOV-2204`](SOV-2204) *Backup & restore*; the mechanism-level piece
>   is [`SOV-1801`](SOV-1801) (`csinstall` pre/post-upgrade jobs — what
>   would carry our `upgrade-ceph` tag).
> - **🔴 The retention half does not.** Neither epic covers disks surviving a deployment delete, the
>   retained → reattached path, or deleting retained volumes. **If SOV-2205 ships as scoped, deleting an OS
>   deployment still destroys every OSD.** This is the part of B1 that still needs an owner.
> - **🟡 Backup/restore is service-side — but its scope is undefined, and it is NOT simply B2.**
>   SOV-2204: *"backup/restore logic lives on the customer-service side (its own terraform plan/API), not as a
>   generic CloudStore mechanism — cloudstore-ui only triggers it and surfaces status."* So OS must implement
>   **some** backup/restore hook to consume the platform upgrade path. **What that hook has to cover is not
>   written anywhere** — it is exactly the job of `SOV-2207` (*"scope (what's backed up, RPO/RTO expectations,
>   limits)"*) and `SOV-2208` (packager guidelines), both unwritten and unassigned. ⚠️ **Do not assume it
>   equals B2** *(an earlier version of this note did — corrected 2026-09-01)*. Three separable things:
>   *(1)* the platform contract (trigger + status only); *(2)* the OS hook, scope TBD; *(3)* B2, control-plane
>   backup, which is a live data-loss risk **whether or not upgrade ever ships**. They probably intersect —
>   note that **losing the OKMS keys makes every object unrecoverable while all OSDs stay healthy**, so a
>   "Ceph-only" backup that skipped the control plane would not protect the S3 data — but the overlap is an
>   inference, not a documented dependency. **→ Ask the SOV-2204 authors what scope they intend before
>   planning against it.**
> - **Nothing is in progress.** Every ticket across both epics is `Backlog` and unassigned except
>   `SOV-2212` (product note, Florent Thiery). *"CloudStore has a plan"* is true; *"CloudStore is working on
>   it"* is not — don't let the existence of the epics read as progress in a steering conversation.

---

### 🔴 B2 — Nothing in the control plane is backed up. Keystone today, OKMS tomorrow.

The service control-plane **K3S cluster has no backup of any kind** — no etcd snapshot, no CNPG
backup, no restore procedure. The package source says so itself:

```
# terraform/controlplane/modules/k3s/manifests/20-cnpg-cluster.yaml.tpl:1
# keystone postgres; conn details in Secret ${cluster_name}-app. no backups (PoC)
```

**Two compounding facts:**

1. **Keystone's identity data is a single-instance Postgres.** `keystone_db_instances` defaults to
   `1` — its own description reads *"1 for the PoC; >=2 for HA"*. One CNPG cluster, one replica, no
   backup. Losing the K3S loses every S3 credential, project and role mapping with it.
2. **OKMS is planned onto this same unbacked-up cluster** ([`SOV-2034`](SOV-2034)).
   That turns an availability problem into a **permanent data-loss** one: **losing the OKMS keys
   makes all encrypted Ceph data unrecoverable.** The ciphertext survives; nothing can read it.

**This is a distinct gap from OSQ-22, which is the ≥3-node resilience gate.**
Three nodes protect against node failure. Neither protects against cluster loss, operator error, or
a delete/redeploy (B1) — **only a backup does.** Closing OSQ-22 would not close this. Recorded as
**OSQ-37**.

> **The mechanism already exists and is simply not wired:** CNPG supports scheduled backups to
> object storage natively. This is a configuration and restore-testing gap, not a build.

**Owner:** unassigned — needs one. Interlocks with **OSQ-21** (own-K3S vs shared Enabler cluster):
*where OKMS lives and who backs it up are the same question.*
**Closed when:** control-plane state is backed up **and a restore has been performed successfully** —
a backup that has never been restored is not a backup.

---

### 🔴 B3 — It has never run on real hardware, so nothing is performance-validated.

Everything to date runs on **VMs with 10 GB Cinder-volume OSDs** (`b3-8` flavors,
`volume_type=public_standard`). The M1 architecture calls for **≥4 bare-metal nodes with ≥5 data
drives**, 256 GB RAM and 25 GbE. No such hardware has been available, so:

- **No meaningful load or performance testing has been possible.** There are no throughput, latency
  or capacity numbers for this service — none. Any sizing statement made today is unvalidated.
- **The OSD spec cannot be validated where it matters.** `ceph_osd_spec_file` defaults to the loose
  take-every-disk `osd-test-single-spec.yml.j2`. Fine on a VM with one clean data disk; **wrong on
  real hardware** — no device-class control, so `replicated_ssd` matches zero OSDs and the RGW
  index/meta pools strand (OSQ-31 · [`SOV-2009`](SOV-2009)).
- **The package's own prerequisites contradict the architecture.** `prerequisites.description` states
  *"a VM is provisioned; no bare-metal pool required"* — the shipped description documents the POC
  shape, not the target ([`SOV-2019`](SOV-2019)).

The concern is not that bare metal will be slower. It is that **the entire storage layout — device
classes, CRUSH placement, pool sizing, encryption-at-rest — is exercised only in a shape it will
never ship in**, and `encrypted: true` must be set **before the first production OSD** because it is
immutable at create time.

**Blocked on:** hardware availability. **Owner:** unassigned. Recorded as **OSQ-38**.
**Closed when:** a ≥4-node bare-metal deployment reaches `HEALTH_OK` with the production OSD spec,
and a documented load test produces baseline numbers.

---

## 3 · What these facts bear on

Stated as consequences of the gaps above, for whoever makes the call:

| Question on the table | What the facts above say |
|---|---|
| Can a customer use it? | B1 and B2 both mean **data loss under ordinary operations** — not an edge case, the normal update path. |
| Can it go to production? | All three apply; B3 additionally means **no capacity or performance basis** for any sizing commitment. |
| Can a beta phase start in September? | B1 is not ours to resolve and has no committed date. B3 needs hardware that does not yet exist, plus a test cycle on top. **My read: not achievable on current evidence** — flagged as my assessment, not a decision. |
| Can internal POC work continue? | **Yes, unaffected.** None of this stops the current work. |

**Sequencing matters as much as the list:** these do not parallelise cleanly. B3 cannot start
without hardware. B1 is a dependency on another team with no committed date. **B1 is the critical
path**, and it is the one that cannot be staffed around from our side — which is why it is worth
escalating as a *dependency* rather than tracking as a task.

> ⚠️ **Sourcing gap on the September target.** No September beta date is recorded anywhere in this
> workspace. [`README.md`](README.md) still carries **≈ end-July 2026** (now passed, Jira confidence
> *Low*), and [`milestones.md`](milestones.md) defines **M2 as a "compliance-deferred beta"** with no
> date at all. The September target appears to come from outside the repo — **confirm the source and
> the exact commitment with Eddy Medina before this is used in a steering conversation.**

---

## 4 · What would have to become true

For the three gaps above to be closed — demonstrated rather than designed:

1. **A data-preserving update path exists and has been exercised.** Deploy → upgrade → data intact.
2. **Control-plane state is backed up and a restore has been performed.** Covers Keystone now and
   OKMS before any encryption goes live.
3. **A bare-metal deployment reaches `HEALTH_OK` with the production OSD spec**, with baseline load
   numbers recorded and `encrypted: true` set before the first production OSD.

Separately, the open security and lifecycle items still apply to any customer-facing use — public
Keystone ([`SOV-2024`](SOV-2024)), certificate issuance
([`SOV-2021`](SOV-2021)), hardened base images
([`SOV-2015`](SOV-2015)), air-gapped apt
([`SOV-2031`](SOV-2031)).

---

## 5 · Cross-references

- [`open-questions.md`](open-questions.md) — **OSQ-37** (control-plane backup) · **OSQ-38** (bare-metal + load validation) · OSQ-21 · OSQ-22 · OSQ-31
- [`handover-2026-08-jan-vacation.md`](handover-2026-08-jan-vacation.md) — operational cookbook + the 7 landmines
- [`milestones.md`](milestones.md) — M1–M4 scope · [`README.md`](README.md) — project dashboard
- Jira: [`SOV-2033`](SOV-2033) (B1) · [`SOV-2034`](SOV-2034) (B2 context) · [`SOV-2019`](SOV-2019) / [`SOV-2009`](SOV-2009) (B3)
