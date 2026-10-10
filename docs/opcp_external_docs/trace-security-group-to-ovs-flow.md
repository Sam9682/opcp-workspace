---
id: generic/trace-security-group-to-ovs-flow
type: runbook
diataxis: how-to
title: "Trace a Neutron security-group rule to its OVS flow (native OVS firewall)"
owner: opcp-core-networking
status: draft
last_verified: 2026-07-22
next_review: 2026-10-22
publish_target: confluence
tags: [neutron, openvswitch, ovs, security-group, firewall, conntrack, debugging]
---

# Trace a Neutron security-group rule to its OVS flow (native OVS firewall)

> **When to use:** you have a Neutron **security-group rule** (e.g. `tcp/80 ingress`) and want to see **where it is actually implemented in the dataplane** — the concrete OpenFlow flow on `br-int` on the compute node — to confirm it is installed, whether it matches, and how much traffic it carries. Also for the inverse: a flow is dropping/allowing traffic and you want to map it back to the SG rule that produced it.
>
> **Scope:** compute nodes using the **native OVS firewall driver** (`firewall_driver = openvswitch`), i.e. conntrack-based flows in `br-int` — **not** the legacy `iptables_hybrid` driver (there the rules live in `iptables` on `qbr…`/`tap…`, not in OVS). Check which you have in [step 4](#4-confirm-native-ovs-firewall-not-iptables_hybrid).
>
> **Environment caveat:** UUIDs / IPs / ofport numbers below are from a live SNC trace (`paas-snc-srv4`, VM `server`, port `3ca16729…`, 2026-07-22). Confirm the live values on your node — don't hard-code them.
>
> **Status:** DRAFT — the SG→flow trace was **validated live 2026-07-22** (SG rule `ca66b181` tcp/80 ingress → `table=82` flow on `br-int`, counters incrementing). Table numbers other than 82/72 are from Neutron docs, marked `[inference]` below.

---

## Background — how a SG rule becomes an OVS flow

Neutron does **not** store "security groups" anywhere in OVS. A security group lives in the Neutron API; the OVS agent **renders** its rules into OpenFlow flows on `br-int` on each node hosting a port that uses the group. So there is no "grep by SG name" — you correlate **SG rule → port → ofport/MAC → flow**.

The native OVS firewall is **conntrack-based**. Its flows sit in a fixed set of tables on `br-int`:

| Table | Role | Seen live 2026-07-22 |
|---|---|---|
| 72 | **RULES_EGRESS** — egress SG rules | inference |
| 82 | **RULES_INGRESS** — ingress SG rules | ✅ verified |
| 71 / 81 | BASE_EGRESS / BASE_INGRESS (conntrack setup, zone assignment) | inference |
| 73 | ACCEPT_OR_INGRESS | inference |
| 91 / 92 | ACCEPTED_EGRESS / ACCEPTED_INGRESS tracking | 94 seen in an earlier dump |
| 93 | DROPPED_TRAFFIC | inference |
| 94 | ACCEPTED_EGRESS_TRAFFIC_NORMAL | ✅ seen |

Each flow identifies its port and conntrack context via registers (verified live):

- **`reg5` = the port's ofport** — e.g. `reg5=0x20` = ofport 32. Ingress rules match the destination port on `reg5`.
- **`reg6` = the conntrack zone** — used as `ct(commit,zone=NXM_NX_REG6[0..15])`.
- Flows are keyed on **`ct_state`**: `+new-est` (a new connection — gets `ct(commit)` + forwarded) vs `+est-rel-rpl` (already-known / reply traffic — fast-accepted without re-commit).

When one SG rule covers many remote IPs/ports, the agent uses **`conjunction`** flows: match-halves emit `conjunction(<id>,1/2 or 2/2)`, and a separate `conj_id=<id>` flow carries the action. The `tp_dst=<port>` match still appears on a match-half, so grepping by port still finds it.

---

## TL;DR (the skeleton)

```
1. Server → port:   openstack port list | grep <fixed-ip>      → port UUID, MAC
2. Port → SG:       openstack port show <port>                 → security_group_ids, binding_host_id, driver
3. SG → rules:      openstack security group rule list <sg>    → the rule you care about (e.g. tcp/80 ingress)
4. Confirm driver:  port show → bound_drivers=openvswitch, ovs_hybrid_plug=False  (else it's iptables — stop)
5. On the node:     find the OVS pod (neutron-ovs / ovs-vswitchd), get the tap ofport
6. Flow:            ovs-ofctl --names dump-flows br-int table=82 | grep -w <tap> | grep tp_dst=80
7. Read it:         ct_state, reg5 (ofport), action (ct commit / output / resubmit), n_packets
```

---

## Prerequisites

- [ ] OpenStack CLI authenticated to the region as **admin** (`openstack …`).
- [ ] SSH / kubectl access to the compute node hosting the port (`binding_host_id` from step 2).
- [ ] Shell **inside the OVS pod** on that node — on the k3s-based platform this is the **`neutron-ovs`** pod, **`ovs-vswitchd`** container (this is where the `ovs-vsctl` / `ovs-ofctl` / `ovs-appctl` / `ovs-dpctl` tools are installed):
  ```bash
  kubectl -n <ns> get pods -o wide | grep neutron-ovs        # find it on the target node
  kubectl -n <ns> exec -it <neutron-ovs-pod> -c ovs-vswitchd -- bash
  ```

---

## Steps

### 1 — Server → port (by fixed IP)

```bash
openstack server show <server>                 # → addresses (priv=10.0.0.200), host
openstack port list | grep 10.0.0.200
# → port UUID 3ca16729-dab7-… , MAC fa:16:3e:52:05:ec
```

### 2 — Port → security group + binding

```bash
openstack port show <port-uuid>
```
Read off:
- `security_group_ids` → the SG (`81fe202f-…`)
- `binding_host_id` → the compute node (`paas-snc-srv4`)
- `mac_address` → `fa:16:3e:52:05:ec`
- `binding_vif_details` → `bound_drivers.0='openvswitch'`, `bridge_name='br-int'`, `ovs_hybrid_plug='False'`, `port_filter='True'` (see step 4).

### 3 — SG → the rule you care about

```bash
openstack security group rule list <sg-uuid>
# e.g. ca66b181-…  tcp  IPv4  0.0.0.0/0  80:80  ingress   → the tcp/80 rule
```

### 4 — Confirm native OVS firewall (not iptables_hybrid)

From step 2's `binding_vif_details`: **`ovs_hybrid_plug='False'` + `bound_drivers.0='openvswitch'`** ⇒ native OVS firewall — rules are OVS flows, continue. (Or check `firewall_driver` in `openvswitch_agent.ini` on the node.)
If `ovs_hybrid_plug='True'` (hybrid) ⇒ SG rules live in **iptables** on the `qbr…` linux bridge, not in OVS — this runbook does not apply; use `iptables -S | grep neutron`.

### 5 — On the node: tap interface + ofport

The tap interface name is **`tap` + the first 11 characters of the port UUID**: port `3ca16729-dab7-…` → **`tap3ca16729-da`**. Verify rather than trust:

```bash
ovs-vsctl --columns=name find interface external_ids:iface-id=<full-port-uuid>
ovs-vsctl get interface tap3ca16729-da ofport         # e.g. 32   (-1 ⇒ no OpenFlow port)
```

### 6 — Find the flow (the whole point)

```bash
ovs-ofctl --names dump-flows br-int table=82 | grep -w tap3ca16729-da | grep tp_dst=80
```

Live result:
```
table=82, n_packets=84, priority=77,ct_state=+est-rel-rpl,tcp,reg5=0x20,tp_dst=80 actions=output:"tap3ca16729-da"
table=82, n_packets=19, priority=77,ct_state=+new-est,tcp,reg5=0x20,tp_dst=80 actions=ct(commit,zone=NXM_NX_REG6[0..15]),output:"tap3ca16729-da",resubmit(,92)
```

Two flows for one SG rule:
- **`ct_state=+new-est`** — a **new** inbound connection to :80. This is the SG rule doing its job: commit to conntrack (zone from `reg6`), forward to the VM, `resubmit(,92)` (accepted-ingress tracking).
- **`ct_state=+est-rel-rpl`** — already-established / reply traffic. Fast-accepted, no re-commit.

All rules for this port (any table): grep by MAC or ofport instead of `tp_dst`:
```bash
ovs-ofctl --names dump-flows br-int table=82 | grep -w tap3ca16729-da   # all ingress SG rules
ovs-ofctl --names dump-flows br-int table=72 | grep -w tap3ca16729-da   # all egress SG rules
```

---

## Verification

- The `tp_dst=80` flow(s) exist in `table=82` → rule is installed.
- **`n_packets` on the `+new-est` flow increments** when you hit the port from outside → the rule is matching real traffic. Watch it live:
  ```bash
  watch -n1 "ovs-ofctl --names dump-flows br-int table=82 | grep -w tap3ca16729-da | grep tp_dst=80"
  ```
- Cross-check what conntrack currently holds for the VM:
  ```bash
  ovs-appctl dpctl/dump-conntrack | grep 10.0.0.200
  ```

---

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `ovs-ofctl dump-flows … \| grep tapXXXX` returns **nothing**, but the tap name **is** visible when you run the command without a pipe | `ovs-ofctl` prints **port names only when stdout is a TTY**; piped/redirected it prints **ofport numbers** (`output:32`), so a grep for the tap name matches nothing. Silent — no error. | Force names: **`ovs-ofctl --names dump-flows br-int …`**. (Or grep the ofport number / MAC instead.) |
| `ovs-vsctl get interface <tap> ofport` returns `-1` | Interface has no OpenFlow port on `br-int` (wrong bridge, or internal port) | Confirm the port is on `br-int` (`ovs-vsctl show`); the VM tap for a native-firewall port binds directly to `br-int`. |
| No flows found for the port at all, `ovs_hybrid_plug='True'` | Legacy **iptables_hybrid** firewall — rules aren't in OVS | `iptables -S \| grep neutron` on the node; this runbook doesn't apply. |
| Rule spans many CIDRs/ports and the `tp_dst` match looks incomplete | Agent used **conjunction** flows — match is split across `conjunction(id,1/2)` + `conjunction(id,2/2)` with the action on `conj_id=<id>` | Grep the `conj_id` to find the action half; both halves belong to the same SG rule. |
| `ovs-*ctl: command not found` on the node | Tools live inside the OVS pod, not on the host | `kubectl exec` into the **`neutron-ovs`** pod, **`ovs-vswitchd`** container (see Prerequisites). |

---

## Owner

OPCP Core networking. Validate the inference-marked table numbers against the next real trace before removing DRAFT.

## See also

- [OVS/OVN architecture primer](../../products/cloudstore/misc/network-service-lb-l3-gateways/architecture/ovn-ovsdb-architecture.md)
- [minint egress / Floating-IP debugging](../../products/cloudstore/misc/network-service-lb-l3-gateways/runbooks/minint-egress-debugging.md) — the L3/NAT side of the dataplane
- [Glossary](../../shared/glossary.md)
