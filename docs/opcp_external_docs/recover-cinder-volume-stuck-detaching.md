---
id: generic/recover-cinder-volume-stuck-detaching
type: runbook
diataxis: how-to
title: "Recover a Cinder volume stuck in detaching (or attaching / reserved)"
owner: opcp-core-compute-block
status: draft
last_verified: 2026-08-06
next_review: 2026-11-06
publish_target: confluence
tags: [cinder, openstack, volume, detaching, attach-status, nova, minint, first-responder]
---

# Recover a Cinder volume stuck in detaching (or attaching / reserved)

> **When to use:** a Cinder volume is wedged in a transient attach state — most often **`detaching`** — and won't return to `available` or `in-use` on its own. Classic trigger: a user detaches a volume (or the volume's instance is **deleted mid-detach**), the Nova↔Cinder detach handshake never completes, and the volume is left in `detaching` forever — it can't be re-attached, moved, or deleted. The same recipe fixes a volume stuck in **`attaching`** or **`reserved`**.
>
> **Symptom, verbatim (FR-20260727-122917, minint, 2026-07-27):** *"all my volumes are currently stuck in detaching in minint … then the instance was deleted but volumes were still blocked in detaching, so cannot be used."*
>
> **Scope:** any OpenStack env we run (minint / demo). This resets **Cinder-side state only** — it does **not** clean up a real live attachment on a running instance. Only use it once you've confirmed the volume is not actually attached to a live VM (see Prerequisites).
>
> **Owner of this runbook:** opcp-core-compute-block — **TBD** confirm.
>
> **Status:** DRAFT — the `--detached` reset was **validated 2026-07-27** against FR-20260727-122917 (minint) and unblocked the volumes. Command/flag details for `--state` and the admin `attachment` cleanup are OpenStack-standard, marked `[inference]` where not exercised in that session.

---

## TL;DR (the skeleton)

```
1. Confirm the volume is really stuck (status = detaching/attaching/reserved) and NOT on a live VM
2. Reset the attach status:   openstack volume set --detached <volume_id>
3. Verify it flips to available (status + attachments empty)
4. SWEEP for siblings:        openstack volume list --all-projects --status detaching
5. Re-use it (re-attach / delete) as normal — or let the CSI consumer delete it itself
```

> **⚠️ Do not skip step 4.** Fixing only the reported volume is a demonstrated failure mode.
> On OFR-24 the reported volume was fixed, and a sweep afterwards found a **second** wedged volume
> on the same instance that nobody had reported and that had been stuck ~23 hours. Across the four
> occurrences to date, **4 volumes were wedged but only 3 were ever reported by a human** — so the
> reported volume is not a reliable indicator of blast radius.

> The one-liner that fixed FR-20260727-122917:
> ```bash
> openstack volume set --detached <volume_id>
> ```
> Repeat per volume — there is no bulk flag. **Note:** in that case the reporting user had **enough privilege to run it themselves** — the reset was **not** admin-only for them. Confirm your own role first (see Common failures).

## Background — what "stuck detaching" actually is

Attach / detach is a **two-party** operation: Nova (compute) and Cinder (block) each hold a piece of the state and exchange it over the volume **attachment** record. A normal detach is: Nova tears down the block device on the hypervisor → tells Cinder to delete the attachment → Cinder flips the volume `in-use → available`.

If that handshake is interrupted — the compute agent dies, the message is lost, or **the instance is deleted while a detach is in flight** — Cinder is left holding a half-torn-down attachment and parks the volume in the transient **`detaching`** state, waiting for a completion signal that never arrives. The volume is now unusable: you can't attach it (it's not `available`), and you often can't delete it either (it thinks it's still attached).

> **⚠️ Correction 2026-08-05 (from OFR-23, the second occurrence).** Don't assume a human deleted an
> instance. The second occurrence was a **Cinder CSI-provisioned Kubernetes PVC** — `volume show`
> reported `description: Created by OpenStack Cinder CSI driver`, properties
> `cinder.csi.openstack.org/cluster='kubernetes'` / `csi.storage.k8s.io/pvc/namespace='jupyterhub'`,
> on backend `cinder-volume-0@ceph01#ceph01`. There, **attach/detach is automated on pod
> rescheduling and no human touched an instance.** So the trigger set is wider than the
> instance-delete story: any interrupted detach does it, and CSI workloads generate detach churn
> continuously. `[verified from volume show; the precise interruption point was not captured]`
>
> Two open sub-hypotheses worth testing, both `[inference]`: (1) CSI reschedule loops hit the race
> far more often than human workflows, which would explain both occurrences landing in the same
> tenant; (2) `encrypted: True` volumes add a Barbican/OKMS key-teardown step to the detach path
> that may widen the race window — an unencrypted volume is the control.
>
> **Diagnostic worth running first:** `openstack volume show <id>` and check `description` /
> `properties` for `cinder.csi` markers. If present, this is a CSI-managed PVC — expect it to recur
> for that workload, and note it on the case rather than filing it as a one-off.

> **⚠️ Addendum 2026-08-06 (from OFR-24, a third occurrence that chronologically came first).**
> Four things that would have saved time:
>
> **1. There are two distinct shapes — record which one you saw.** The `attachments` list tells them apart, and they are not the same failure:
> - **Empty `attachments` + `status: detaching`** (OFR-23) — the attachment record was removed but the status transition never happened. Failure at the *tail* of the teardown.
> - **Populated `attachments` + `status: detaching`** (OFR-24) — the record is fully intact (`Status: attached`, no detach timestamp) while pointing at an instance that no longer exists. Failure *before* attachment removal.
>
> So the detach can break on either side of attachment removal. Note the shape on the case — the root-cause ticket (SOV-2118) needs it to locate the interruption point.
>
> **2. A delete that fails even with `--force` can still be this pattern.** OFR-24 arrived as a `?cascade=False&force=True` rejection whose error enumerates hard constraints — *"must not be migrating, attached, belong to a group, have snapshots, awaiting a transfer…"*. That reads like a snapshot or group problem, not a status problem, because Cinder does not say which condition tripped. Force bypasses status checks but not the attachment constraint. **Always run `volume show` before concluding it isn't this pattern.**
>
> **3. `--detached` alone is enough, even with a populated attachment record.** `[verified 2026-08-06]` On OFR-24 it cleared *both* the status and the attachment list in one step. The explicit `volume attachment delete` in Common-failures below was staged as a fallback and was **not needed** — it stays `[inference]`.
>
> **4. You usually do not need to delete the volume yourself.** If a CSI driver is the consumer it is already retrying `DELETE` on a fixed cycle (~16m40s on OFR-24) and will remove the volume on its next pass once the state is corrected. It never gives up — OFR-24 had accumulated roughly 80 failed attempts over 22 hours — but it also cannot correct the state itself. A long dwell time is normal: nothing alerts on this yet (SOV-2119), so a volume can sit wedged for a day before a human notices.

`openstack volume set --detached` tells Cinder, out of band, *"the attachment is gone — go back to `available`."* It is a **state correction**, not a real teardown: it fixes the *database* state on the assumption the *actual* device is already gone (which it is, when the instance was deleted). That assumption is the whole safety condition — verify it before you run the reset.

## Prerequisites

- [ ] `openstack` CLI authenticated against the affected env (correct `openrc` / cloud profile for **minint** or **demo**).
- [ ] The **volume ID(s)** stuck in `detaching` (from the user report, or list them — see Step 1).
- [ ] **Confirmation the volume is not attached to a live, running instance.** The safe cases: the instance was **deleted**, or `nova`/`virsh` shows no block device for this volume on any hypervisor. If a live VM still has the device, resetting Cinder state will desync Nova and Cinder — don't.

---

## Step 1 — Confirm it's really stuck (and not on a live VM)

```bash
# List volumes not in a clean state
openstack volume list --status detaching
openstack volume list --status attaching
openstack volume list --status reserved

# Inspect one — check status + the attachments list
openstack volume show <volume_id> -c id -c status -c attachments
```

**Expected (stuck):** `status = detaching` and `attachments` either empty or pointing at an **instance that no longer exists**. Cross-check the instance:

```bash
openstack server show <instance_id>   # expect: No server with a name or ID ...  (i.e. it was deleted)
```

If the referenced server **is still running and using the volume**, STOP — this runbook does not apply; investigate the live attachment instead.

## Step 2 — Reset the attach status

Per-volume (the verified fix):

```bash
openstack volume set --detached <volume_id>
```

For several volumes in the same tenant, loop:

```bash
for v in <vol_id_1> <vol_id_2> <vol_id_3>; do
  openstack volume set --detached "$v"
done
```

**Expected:** no error, no output. The command returns silently on success.

## Step 3 — Verify

```bash
openstack volume show <volume_id> -c status -c attachments
```

**Expected:** `status = available` and `attachments` empty (`[]`). The volume is now usable again.

## Step 4 — Sweep for siblings (do not skip)

The reported volume is rarely the only one. Before you close the case:

```bash
openstack volume list --all-projects --status detaching
openstack volume list --all-projects --status attaching
openstack volume list --all-projects --status reserved

# anything else orphaned on the same instance as the volume you just fixed:
openstack volume list --all-projects --long | grep -i <server_id>
```

> **Note:** `--name` is an **exact match**, not a glob — `--name 'ovh-managed-kubernetes-abc*'`
> silently matches nothing. To filter by name pattern use
> `openstack volume list --all-projects --long | grep -i <fragment>`.

Repeat Steps 2–3 for every volume found. There is no bulk reset flag.

**Why this matters:** on OFR-24, `cb74a7b1` was reported and fixed, then this sweep turned up
`5ec48d91` — same deleted instance, different device (`/dev/sdc` vs `/dev/sdd`), wedged ~23 hours,
never reported by anyone. It would still be wedged if the sweep hadn't been run.

Note the two volumes wedged **59 minutes apart**, so siblings are not necessarily one simultaneous
event — a sweep can surface orphans from quite different times.

## Verification (final smoke test)

Re-attach it to a fresh instance (or delete it) — the operation that was previously impossible now succeeds:

```bash
openstack server add volume <new_instance_id> <volume_id>
openstack volume show <volume_id> -c status   # -> in-use
```

**Expected:** volume reaches `in-use` bound to the new instance — proves the stuck state is fully cleared, not just cosmetically flipped.

## Common failures + fix recipes

| Symptom | Likely cause | Fix |
|---|---|---|
| `--detached` returns `Policy doesn't allow volume_extension:volume_admin_actions:reset_status` (or similar 403) | Your role can't run the reset in this env — attach-status reset is often admin-gated. *(In FR-20260727-122917 the user's own role sufficed — policy varies by env/tenant.)* | Get an operator with the right role to run it, or check the env's Cinder policy for who may reset attach status. |
| Volume flips back to `detaching` shortly after the reset | A **live attachment still exists** — the instance wasn't really gone, or a stale Cinder `attachment` record remains. | Re-check Step 1. If the instance is truly gone but an attachment record lingers, delete it directly (admin) `[inference — still never needed in practice]`: `openstack volume attachment list --volume <volume_id>` then `openstack volume attachment delete <attachment_id>`. **Note:** on OFR-24 a *populated* attachment record was cleared by plain `--detached`, so try that first and only reach for this if `attachments` is still non-empty afterwards. |
| `volume show` reports a populated `attachments` list and the delete keeps failing | The attachment points at a **deleted instance** — Cinder is holding an orphan. Confirm with `openstack server show <server_id>` from the attachment; *"No Server found"* is the tell. | Standard `--detached` reset (Step 2) clears it. `[verified 2026-08-06, OFR-24]` |
| `--detached` isn't accepted by the CLI | Older/newer client where the flag differs. `[inference]` | Use the explicit state reset: `openstack volume set --state available <volume_id>` (resets `status`; may need a separate `--attached/--detached` for `attach_status` depending on client version). |
| Volume also won't **delete** ("volume is busy" / still attached) | Same stuck attachment. | Run the `--detached` reset first (Step 2), confirm `available` (Step 3), then `openstack volume delete <volume_id>`. |

---

## References

- **First occurrence:** FR bot case **FR-20260727-122917** (minint, tenant `570045e843d14722b639777dc69eca45`, 2026-07-27) — volumes stuck `detaching` after instance deletion; unblocked with `openstack volume set --detached`.
- Recurring-issue tracking: [Root-Cause Backlog](../root-cause-backlog.md) — *"Cinder volume stuck in detaching after instance delete"*.
- Related OpenStack block context: [Compute & Block on CloudStore](../../products/cloudstore/misc/compute-block-on-cloud-store/README.md).
