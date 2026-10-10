---
id: core/network-provisioning-known-bugs
type: troubleshooting
diataxis: reference
title: "Network provisioning (ML2 / NOG / ToR) — known bugs & failure modes"
owner: sov-copilot
status: published
last_verified: 2026-09-02
publish_target: git
tags: [neutron, ml2, nog, arista, network, troubleshooting, state-drift]
---

# Network provisioning (ML2 / NOG / ToR) — known bugs & failure modes

> Symptom→cause catalog of **verified** bugs in the Neutron→device chain
> (`networking_ovh_goldorack` ML2 driver → NOG → on-ToR `NogTaskMgr` agent → Arista eAPI).
> Distilled 2026-09-01 from Alexander Graf's hardening workspace (driver + NOG source
> review, live cluster verification, and a 26-scenario contract test harness —
> stash [`gor/network-ovh-ml2-testenv`](https://stash.ovh.net/projects/GOR/repos/network-ovh-ml2-testenv/browse)).
> Everything below is **code- or harness-verified**, not hypothesis — this supersedes the
> "driver source not available for review" caveat in
> [network-automation-stack.md](../../architecture/conceptions/network-automation-stack.md#root-cause-investigation-status).
>
> **Live status of fixes** (PRs land, statuses move): the fix-branch table in the
> workspace `README.md` (`~/Work/git/ovh/networking/` on agraf's machine) and the open
> PRs on stash [`gor/network-ovh-ml2`](https://stash.ovh.net/projects/GOR/repos/network-ovh-ml2/pull-requests).
> Statuses below are as of **2026-08-26**.

## Architecture in one line — why failures are silent

The ML2 driver fires **synchronous, post-commit, fire-and-forget** REST calls at NOG:
no retry (pre-PR#48), no reconciliation loop, no local Neutron→NOG mapping table.
NOG renders CLI into a `tasks` table; the on-ToR `NogTaskMgr` EOS-SDK agent polls
(~5 s per VRF) and applies via eAPI over the local unix socket. NOG is write-only and
blind to the device — nothing reads state back. **The system's failure mode is silent
divergence, not crashing**: absorbed failures surface weeks later as dangling VLANs,
orphan EVPNs, and unexplained port wedges. This is the code-level confirmation of the
drift problem tracked in [SOV-1751 — NOG State Drift](../../../../generic/root-cause-collection/nog-state-drift-SOV-1751.md).

> **Fix recipe:** when this residue strands a node in `clean failed` (trunk-mode
> drift, orphan aggregate, or leaked layer), the per-signature nog-cli cleanup is
> codified in [baremetal-clean-failed-nog-residue](../runbooks/baremetal-clean-failed-nog-residue.md)
> (validated 2026-09-04, demo).

## ML2 driver — symptom → cause

| Symptom | Cause | ID | Status (2026-08-26) |
|---|---|---|---|
| VLAN stays on **source** bond after live migration | `_unset_vlan` missed at migration activate | — | Fix: ml2 [PR #49](https://stash.ovh.net/projects/GOR/repos/network-ovh-ml2/pull-requests/49) |
| VLAN leaks on **target** when live migration is rolled back | Nova clears `migrating_to` + deletes the inactive target binding — no driver hook fires | — | Fix: [PR #50](https://stash.ovh.net/projects/GOR/repos/network-ovh-ml2/pull-requests/50) |
| VLAN leaks on **shelve offload** (no migration involved) | Nova's unbind (host cleared, profile emptied) falls through to "no context.host, ignoring request" | W7 | Fix: [PR #53](https://stash.ovh.net/projects/GOR/repos/network-ovh-ml2/pull-requests/53) |
| Node **deprovision fails** — leftover VLAN blocks untrunk/delete of the driver-created bond; NOG 400s mode changes on interfaces carrying layers | Leaked layers from the bugs above; NOG *correctly* refuses interface deletion. The `recursive_deletion` config flag was loaded but never consulted (dead code) | W3 | Fix (flag-gated cleanup sweep): [PR #48](https://stash.ovh.net/projects/GOR/repos/network-ovh-ml2/pull-requests/48) |
| Detached trunk **subport un-attachable forever** (`PortInUse: already has an attached device`) | `_unbind_subports` left `device_id` on the subport | W6 | Fix: [PR #52](https://stash.ovh.net/projects/GOR/repos/network-ovh-ml2/pull-requests/52) |
| Baremetal parent port **loses its pre-set binding profile at trunk create** (why Ironic must re-stamp it at deploy) | Trunk-create sets trunk status from the parent (DOWN pre-deploy) → `trunk_update` → any non-ACTIVE status runs `_delete_trunk` → unbinds the never-bound parent | W8 | 🔴 **Unfixed**, harness-red |
| `openstack port set --disable` on a deployed LACP baremetal port is a **silent no-op** — fencing does nothing | `_set_interface_status` skips port-channels; member physicals never shut | W9 | 🔴 **Unfixed**, harness-red |
| Portgroup with members on **two different ToRs half-configures** instead of refusing — port ends BOUND with an orphan aggregate stranded on the 2nd ToR | Same-node check is dead code on the LACP path; NOG's refusal of the foreign member is only logged | W10 | 🔴 **Unfixed**, harness-red |
| Trunk subport on the **same network as its baremetal parent** → `MacAddressInUse`, port `binding_failed` (hit on prod minint 2026-08-20) | Trunk driver copies the parent's MAC onto the subport, which collides on the parent's network | — | Documented restriction, **unsupported by design**; long-term cure = W12 declarative trunk-driver redesign |
| Orphan **port-channel left on ToR after a failed bind**; 403 on deploy | No cleanup on bind failure | — | Fix: [PR #51](https://stash.ovh.net/projects/GOR/repos/network-ovh-ml2/pull-requests/51) |
| Driver failures **invisible in prod logs** | `logging.conf` caps the `networking_ovh_goldorack` logger at INFO while the driver logs at DEBUG (irobox one-liner: `log_levels.nog = "DEBUG"`) | W1 | Post-[PR #54](https://stash.ovh.net/projects/GOR/repos/network-ovh-ml2/pull-requests/54): every non-200 NOG answer logs one WARNING with verb/path/status |
| Sporadic races on VLAN set/unset and port-channel create | Neutron api + rpc pods **both** run the driver; oslo file locks are pod-local — no cross-pod mutual exclusion | W2 | Stopgap: shared hostPath volume (single-node); durable: NOG-side atomicity |

## NOG / task pipeline / on-ToR agent — symptom → cause

| Symptom | Cause | Status |
|---|---|---|
| Task stuck in `doing` forever | Agent dead on that device (its stale-`doing` self-heal only runs while alive), or a wedged eAPI daemon — the executor's unix-socket transport has **no timeout** | Open (mitigation: `socket.setdefaulttimeout`) |
| Content-bearing tasks (`show vlan`, `show running-config`) **always fail `ovhError` and block the device queue**, while config tasks work | **The 4094-byte bug**: pyclient `put_object` sends `lastreturn` as URL query params; gunicorn's request-line limit (4094) answers HTML 400; the client's unconditional `.json()` explodes. Empty results fit the URL — that's why provisioning worked and only diagnostics failed | Root-caused 2026-08-12 on drannou; fix = form body (`data=`), push blocked on `sol/nog-pyclient` write access |
| Rejected CLI command reported as **success** — NOG (and Neutron) see a rejected config as completed | On-ToR executor maps eAPI `AppError` to task status `done`, error only in `last_return`. eAPI stops at the first failing command (bench-verified) | Open (should be `customerError`/`ovhError`) |
| **Partial config** applied on the device | No atomicity: commands stream line-by-line; if line 7 of 12 fails, 1–6 stay committed, 8–12 are lost | Open (planned: Arista `configure session` wrapping) |
| Agent polling loop **silently dies** | `running` doubled as loop flag and config-fetch target; a `None` return terminated polling | Fixed: nog-agent-repo [PR #5](https://stash.ovh.net/projects/GOR/repos/nog-agent-repo/pull-requests/5) |
| `config_load` bootstrap **silently drops rejected lines** and reports success | Executor deleted from the list it was indexing; retried until convergence, omissions logged only to `/tmp/cfg_load` on the ToR | Fixed on PR #5 (lossy-success question still with the team) |
| Anything on the mgmt network can **read or flip any device's tasks** | Tasks API has no auth and no per-domain authorization (`# No auth` in the on-switch client) | Open — top device-path security item |
| Drift is detected on-device but **never reported** | Agent's `check_config()` diffs running-config vs NOG intent every ~15 rounds — results stay in `/tmp/ref_diff_*` / `last_diff_*` on the ToR | Open — remaining work is reporting, not detection |
| Orphan tasks pointing at deleted nodes | `Todo.domain` is a free-form hostname string, no FK to `Node` | Open |

## Triage heuristics

- **Establish what actually serves the endpoint before diagnosing any port.** A broken
  port is not automatically the outage. From a host that can reach it:
  `curl -ksv` the URL (note the connecting IP), or per candidate IP
  `curl -k --resolve <fqdn>:443:<ip> <url>` — a 404 + `TRAEFIK DEFAULT CERT` on a
  bare-IP request means an ingress that routes by Host/SNI, so test *with* the
  hostname. Verified lesson from
  SOV-2415: the CloudStore UI on minint
  is served via the node's **adminnet** port; the conspicuously broken public port was
  a **dormant** defect, and the real outage was the node itself not booted (see the
  SED row in the [root-cause backlog](../../../../generic/root-cause-backlog.md)).
- **Port `DOWN` + `binding_vif_type: unbound` + empty `binding_profile` on a baremetal
  node** = the VIF was never mapped to a physical port at the Ironic/ML2 layer. Check
  `openstack baremetal port list --node <X> --long` / `port group list` — attach needs
  a **free port-like object** (a NIC or portgroup without a `tenant_vif_port_id`); a
  deploy spec with more networks than portgroups can never fully attach. Check
  `openstack server event list <instance>`: two `attach_interface` events milliseconds
  apart = parallel Terraform, a known silent-half-failure trigger (SOV-286 family). A
  port that kept its `fa:16:3e:*` virtual MAC (vs the node's real NIC MACs) never
  completed Ironic's VIF attach — the MAC rewrite to the physical MAC is the marker of
  a completed attach. Power operations (`stop`/`start`/`reboot`) never re-drive
  binding; repair = `server remove port` + `add port` (or trunk subport when no
  physical is free). Same family as W8/W10. Live example: SOV-2415 —
  `cloudstore-minint-0` public port unbound since day 0 (2026-03-13), found 2026-09-02
  ([local mirror](../../misc/first-responder/jira/SOV-2415-cloudstore-ui-minint-url.md)).
- **Who did what:** `openstack server event show <instance> <req-id>` yields the
  `user_id` per action; `openstack user show <id>` resolves it. The `ironic` service
  user as actor = automation (e.g. the unlock flow's own start), not a human.
  `rescue`/`unrescue` events in `server event list` are the SED unlock choreography
  made visible.
- **Neutron says fine, wire says nothing** → check NOG layers + rendered tasks
  (`nog-cli`), then the ToR agent log; remember drift diffs sit in `/tmp` on the
  switch. Never start by restarting services — this stack fails by *diverging*,
  not by crashing.
- **A device's whole task queue is blocked** → look for one `ovhError` task whose
  command produces output (the 4094-byte bug) before suspecting the device.
- Most rows above are **reproducible in the harness**
  (`gor/network-ovh-ml2-testenv`, 26 scenarios, `./run.sh`) — a red scenario at an
  unexpected step is a finding, not noise.

## Cross-references

- [SOV-1751 — NOG State Drift (root-cause epic)](../../../../generic/root-cause-collection/nog-state-drift-SOV-1751.md) —
  the tracking epic this catalog gives code-level ground truth for (SOV-1293/473/286/472 map onto the leak + unbind rows above).
- [Network automation stack](../../architecture/conceptions/network-automation-stack.md) —
  architecture + investigation history; its Layer-2 "hypotheses" are resolved by this page.
- [Root-cause backlog](../../../../generic/root-cause-backlog.md) — recurring-symptom register;
  new occurrences of these patterns belong there.
- [Baremetal / Ironic triage](baremetal-ironic-triage.md) — node-side counterpart of this page.
