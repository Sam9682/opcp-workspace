---
id: core/baremetal-clean-failed-nog-residue
type: runbook
diataxis: how-to
title: "Baremetal node stuck in clean failed — NOG residue cleanup"
owner: opcp-core-network
status: published
last_verified: 2026-09-04
next_review: 2026-12-04
publish_target: confluence
tags: [ironic, baremetal, neutron, ml2, nog, cleaning, tor]
---

# Baremetal node stuck in `clean failed` — NOG residue cleanup

> **When to use:** a baremetal node lands in **`clean failed` on every cleaning
> attempt** (often after a failed deploy), while Ironic / Neutron / NOG all look
> green. Typical trigger: a deploy died at `switch_to_tenant_network`
> (`binding_failed`, e.g. the customer put a trunk subport on the parent's
> network) and its network teardown never ran — the leftover NOG state then
> blocks all subsequent cleans. Not for cleans failing *inside* a clean step
> (disk erase errors → see [triage & common failures](../troubleshooting/baremetal-ironic-triage.md)).
>
> **Owner of this runbook:** opcp-core-network (Alexander Graf until handover).
>
> **Status:** validated 2026-09-04 on demo — all three signatures fixed on live
> nodes, cleaning succeeded.

## TL;DR

```
1. openstack baremetal node history list/get <node>   # which failure shape?
2. openstack baremetal port list --node <uuid> --long # ToR + port names, pxe_enabled port
3. nog-cli interfaces show ...                        # match signature A / B / C below
4. Fix via nog-cli (as nog_admin):
   A  trunk-mode drift      → interfaces set --switchmode access
   B  leftover aggregate    → interfaces delete (aggregate id)
   C  leftover layer (VLAN) → layers delete
5. openstack baremetal node manage <node> && ... provide <node>
6. Verify: dnsmasq sees DHCPDISCOVER from the pxe port → node reaches available
```

## Background

The ML2 `ovh` driver programs ToR switchports through NOG **fire-and-forget**:
no reconciliation ever reads state back, so when a deploy's teardown is skipped
(driver exception, `binding_failed`, aborted deploy) the residue stays in NOG's
DB forever and every later render is wrong — while every task still reports
`done` / "everything fine".

Cleaning is where this bites, for two reasons:

- **Cleaning binds each baremetal port individually** (no LACP), so a leftover
  aggregate makes NOG refuse `_set_vlan` on the member ports — the clean dies at
  *prepare* ("Failed to create neutron ports").
- **Only the `pxe_enabled` Ironic port** gets a fixed IP + iPXE boot options on
  the cleaning network (even with `add_all_ports = true`), so drift on that one
  switchport side is fatal — the clean dies at *ramdisk timeout*.

A ToR MLAG pair is **one NOG node** (two `interface` rows per port name,
`peer_node` A/B). `interface id`s shown by the driver logs and by `nog-cli` are
NOG DB ids, unambiguous across the pair.

## Prerequisites

- [ ] Operator shell on the environment's pod-host — see
      [env access / onboarding](../../environments/env-access-onboarding.md).
      The `openstack` and `nog-cli` aliases are predefined on interactive shells.
- [ ] NOG **admin** credentials (writes need `nog_admin`, not the default
      operator user):

  ```bash
  NOG_ADMIN_PASSWORD=$(kubectl get secret nog-secret -n nog -o json | jq -r '.data."secrets.yml"' \
    | base64 -d | awk '/user_id: "nog_admin"/{f=1} f && /secret_password:/{gsub(/"/,"",$2); print $2; exit}')
  ```

- [ ] The node name / UUID, and the cleaning network's VLAN id:
      `openstack network show <cleaning_network> -c provider:segmentation_id`
      (demo: `adminnet` = VLAN 200; parking VLAN on torn-down ports is 666).

---

## Step 1 — identify the failure shape

`last_error` on the node is often **null** even in `clean failed` — use the
history:

```bash
openstack baremetal node history list <node>          # newest events last
openstack baremetal node history get <node> <event-uuid>
```

Two shapes, different signatures downstream:

| History says | Meaning | Go to |
|---|---|---|
| `Timeout reached while cleaning … Failed on step {}` (+ `agent_last_heartbeat` in `driver_internal_info` is old) | Ramdisk never PXE-booted — the cleaning VLAN never became effective on the pxe port | Signature **A** |
| `Failed to prepare node … Failed to create neutron ports for node's ports […]` | NOG refused the port binding — clean died before power-on | Signature **B** or **C** |

For shape 2, the *reason* for the refusal is in the ironic-conductor log
(`Could not create neutron port … ForbiddenException: 403 … Cant configure
interface: _set_vlan: can't set vlan <V> on interface id <N>`) and, with the
NOG interface id `<N>`, in the neutron-server log
(`Mechanism driver 'ovh' failed in update_port_postcommit`):

```bash
kubectl logs -n ironic deploy/ironic-conductor --since=6h | grep "Could not create neutron port"
```

Check for the same failed-deploy trigger in the history: a
`Deploy step deploy.switch_to_tenant_network failed … binding_failed` ERROR
shortly before the first clean failure confirms the residue hypothesis.

## Step 2 — map the node's ports to NOG interfaces

```bash
openstack baremetal port list --node <node-uuid> --long -f json   # MACs, ToR, port names, pxe_enabled
openstack baremetal port group list --node <node> --long          # LACP portgroup? (relevant for B)
nog-cli interfaces list --node <tor-hostname> --details --vlan    # or, with the id from Step 1:
nog-cli interfaces show --node <tor-hostname> <interface-id> --vlan
```

Note which Ironic port has `pxe_enabled=true` and which ToR side it lands on.
(Read-only SQL against the `nog-db` postgres is fine for diagnosis when joins
help; **all writes go through nog-cli — never SQL.**)

## Step 3 — match the signature and fix

### A — trunk-mode drift on the pxe port (ramdisk timeout)

**Signature:** the NOG interface row for the node's `pxe_enabled` switchport
shows `switch_mode trunk` with `vlan []` (healthy torn-down ports are
`access` + parking VLAN). Task history for the port shows
`switchport trunk allowed vlan add <V>` at clean start instead of
`switchport access vlan <V>` — untagged PXE DHCP can never reach the cleaning
VLAN, yet every task reports done.

```bash
nog-cli --api_user nog_admin --api_password "${NOG_ADMIN_PASSWORD}" \
  interfaces set --node <tor-hostname> --interface <id> --switchmode access
```

Returns `message ok` + a `task_id` — the API updates the DB **and** pushes
`switchport mode access` to the ToR. Fix every drifted side (check both A and B
rows of each port name), not just the pxe port.

The API refuses with *"interface already in use"* if layers still exist —
that's signature C on the same interface; remove the layer first.

### B — leftover LACP aggregate (clean-prepare failure, node has a portgroup)

**Signature:** the refused interface (`_set_vlan … on interface id <N>`) is a
physical with `aggr_id`/`fk_aggregate_id` set; the aggregate
(descr `baremetal node aggregate`) carries **zero layers** — pure residue of
the failed LACP deploy. NOG *correctly* refuses VLANs on aggregate members, and
cleaning binds ports individually, so the node can never clean.

```bash
nog-cli interfaces show --node <tor-hostname> <aggr-id> --vlan   # expect vlan []
nog-cli --api_user nog_admin --api_password "${NOG_ADMIN_PASSWORD}" \
  interfaces delete --interface <aggr-id> --node <tor-hostname>
```

If the aggregate still carries layers, delete those first (signature C), then
the aggregate. The Ironic portgroup stays untouched — the next LACP deploy
recreates the NOG aggregate properly.

### C — leftover layer: leaked tenant VLAN or stale parking VLAN (clean-prepare failure)

**Signature:** the refused interface is `access` mode but already carries a
layer — either a **tenant VLAN that was never unset** (leak) or the **parking
VLAN** that the preceding `_unset_vlan` failed to remove. An access interface
takes exactly one untagged VLAN, so NOG refuses the cleaning VLAN.

```bash
nog-cli evpns list --details | grep <vlan-id>                    # find the evpn
nog-cli layers list --evpn <evpn-id> --node <node-id> --details  # find the layer on the interface
nog-cli --api_user nog_admin --api_password "${NOG_ADMIN_PASSWORD}" \
  layers delete --layer <layer-id> --node <node-id> --evpn <evpn-id>
```

## Step 4 — re-run cleaning

```bash
openstack baremetal node manage <node>
openstack baremetal node provide <node>     # → cleaning → available (wipes disks)
```

---

## Verification

```bash
# per fix: the pushed device task completed
nog-cli tasks show <task_id>                                   # status: done

# the render is correct now — pxe port gets "switchport access vlan <V>"
nog-cli tasks list --status done --hostname <tor-hostname> | tail -8

# definitive PXE signal ~2-3 min after power-on: DISCOVER/OFFER/ACK for the pxe MAC
kubectl exec -n neutron <dhcp-agent-pod> -c dhcp-agent -- \
  sh -c 'timeout 600 tail -f /var/log/neutron/dnsmasq/dnsmasq.log | grep -a <pxe-mac>'

# end state (secure-erase takes a while on big disks)
openstack baremetal node show <node> --fields provision_state last_error -f value
```

**Expected:** `cleaning` → `available`, `last_error` empty.

## Common failures + fix recipes

| Symptom | Likely cause | Fix |
|---|---|---|
| `interfaces set --switchmode` → *"interface already in use"* | Layers still attached | Signature C first (delete the layer), then retry |
| `interfaces delete` on the aggregate refused | Aggregate still carries layers | Delete its layers first (NOG refuses by design) |
| Fix task stuck in `todo`/`doing` | On-ToR NogTaskMgr agent dead or eAPI wedged on that switch | Different problem — see [network provisioning known bugs](../troubleshooting/network-provisioning-known-bugs.md) (task pipeline section) |
| Mode fixed, clean still times out, dnsmasq sees **no** DHCPDISCOVER | Another drifted side, or the device port disagrees with NOG (mode was never task-managed historically) | Re-check *all* interface rows of the node's port names (A **and** B sides); compare device state |
| dnsmasq sees DISCOVER but no OFFER | Wrong network / DHCP agent issue, not NOG | Check the cleaning port's `fixed_ips` + boot options in the dhcp-agent log |
| Clean fails *inside* a step (e.g. disk erase I/O errors) | Not a network problem | [Baremetal / Ironic triage](../troubleshooting/baremetal-ironic-triage.md), firmware note in [node recovery](baremetal-node-recovery.md) |

## Related

- [Network provisioning (ML2 / NOG / ToR) — known bugs & failure modes](../troubleshooting/network-provisioning-known-bugs.md) — the failure-mode catalog behind this runbook (teardown gaps W3/W8/W10, fire-and-forget architecture)
- [Baremetal node recovery / re-enrollment](baremetal-node-recovery.md) — when the node itself needs re-enrollment
- [Baremetal / Ironic — triage & common failures](../troubleshooting/baremetal-ironic-triage.md)
- [Root-cause backlog](../../../../generic/root-cause-backlog.md) — pattern row "failed deploy teardown leaves NOG residue"
- [NOG State Drift epic SOV-1751](../../../../generic/root-cause-collection/nog-state-drift-SOV-1751.md)

## Source / changelog

- Drafted 2026-09-04 from a live demo debugging session: signature A on a node
  with 9 consecutive clean timeouts since 2026-05-28 (trunk drift on the pxe
  port after a failed trunk deploy), signature B on a portgroup node locked
  since 2026-08-20 (customer trunk-subport-on-parent-network misconfig →
  `binding_failed` → orphan aggregate), signature C observed on two further
  nodes the same day. All fixes executed via nog-cli and verified: cleaning
  succeeded, nodes returned to `available`.
