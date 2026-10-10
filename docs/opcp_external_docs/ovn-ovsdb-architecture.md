# OVN / OVSDB Architecture

> **What this is:** Technical reference for OVN's control-plane architecture and the OVSDB database protocol that underlies it. Relevant for NS because OVN is the post-GA network backend (NSQ-030), and OVSDB is why the "pure DB-reaction" event model works without a message broker.
>
> **Companion docs:** [L3 & LB Primer](l3-and-lb-primer.md) (OVS vs OVN levels) · [Component survey 2026-07-08](component-survey-2026-07-08.md) · [Open questions NSQ-030](../open-questions.md).

---

## 1. What OVSDB is

OVSDB (Open vSwitch Database, RFC 7047) is a purpose-built database protocol created by the OVS project — **not** a REST API, not Postgres, not a general-purpose RDBMS.

Key properties:

- **Transport:** JSON-RPC over TCP or Unix socket (typically TCP port 6641/6642 for OVN)
- **Schema-driven:** the server declares typed tables + columns; clients validate against the schema
- **Long-lived connections:** clients connect once and keep the connection open
- **Server-push change notifications:** the `monitor` operation lets a client subscribe to tables; the server pushes diffs automatically whenever the data changes — no polling

The server process is `ovsdb-server`, which hosts one or more OVSDB schemas. OVN runs two distinct OVSDB instances:

| Instance | Port | Who writes | Who reads |
|---|---|---|---|
| **NB-DB** (Northbound) | 6641 | `neutron-server`, `ovn-nbctl` CLI | `ovn-northd` |
| **SB-DB** (Southbound) | 6642 | `ovn-northd` | `ovn-controller` (one per hypervisor host) |

---

## 2. OVN component architecture

```
neutron-server ──► NB-DB (6641)
                        │
                   ovn-northd
                   (logical → physical compiler)
                        │
                   SB-DB (6642)
                        │ OVSDB monitor (persistent TCP/SSL)
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
 ovn-controller   ovn-controller   ovn-controller
 (hypervisor-1)   (hypervisor-2)   (hypervisor-3)
       │                │                │
  ovsdb-server     ovsdb-server     ovsdb-server   ← local OVS instance (loopback)
  ovs-vswitchd     ovs-vswitchd     ovs-vswitchd
  openvswitch.ko   openvswitch.ko   openvswitch.ko
```

**What ovn-northd does:** compiles the logical network model (NB-DB: logical switches, routers, ACLs, NAT rules) into physical flow rules (SB-DB: `Logical_Flow`, `Port_Binding`, `MAC_Binding`, `Chassis` tables). Runs continuously, re-compiles on every NB-DB change.

**What ovn-controller does:** on each hypervisor, reads SB-DB flows and translates them into OpenFlow rules pushed to the local `ovs-vswitchd`. Also handles tunnel setup (Geneve) to other hypervisors.

---

## 3. OVSDB monitor — the "pure DB-reaction" mechanism

The reason OVN needs no RabbitMQ or central event bus:

```json
// 1. ovn-controller connects and sends a monitor request:
{
  "method": "monitor",
  "params": ["OVN_Southbound", null, {
    "Logical_Flow":  [{"columns": ["table_id","priority","match","actions"]}],
    "Port_Binding":  [{"columns": ["logical_port","chassis","mac","ip"]}],
    "MAC_Binding":   [{"columns": ["logical_port","ip","mac"]}]
  }],
  "id": 1
}

// 2. SB-DB responds with current full state (initial dump):
{ "result": { "Logical_Flow": { "uuid-1": {"new": {...}}, ... } }, "id": 1 }

// 3. When ovn-northd writes new flows to SB-DB,
//    SB-DB pushes diffs to ALL connected ovn-controllers immediately:
{
  "method": "update",
  "params": [null, {
    "Logical_Flow": {
      "uuid-new": {"new": {"priority": 50, "match": "ip4.dst==10.0.0.6", ...}}
    }
  }]
}
```

`ovn-controller` receives the `update`, translates the new Logical Flows into OpenFlow rules, and writes them to the local OVS via its own local OVSDB connection (loopback). The whole chain — NB-DB write → ovn-northd recompile → SB-DB write → monitor push → OpenFlow update — completes in milliseconds with no intermediate broker.

---

## 4. HA — Raft consensus built into OVSDB

Since OVN 2.9, NB-DB and SB-DB both support **multi-server Raft consensus** natively (no external ZooKeeper/etcd needed).

```
NB-DB Node-1 (Leader) ←──Raft──► NB-DB Node-2 ←──Raft──► NB-DB Node-3
        ▲
  neutron writes here
  ovn-northd reads here
```

- Writes go to the Leader; followers replicate
- Leader failure triggers Raft election (typically < 1s)
- Reads can be served by any node (consistency level configurable)
- Typical deployment: 3-node (1 leader + 2 followers), same hosts as the OpenStack control plane

---

## 5. Scaling ceiling — the SB-DB connection bottleneck

Every `ovn-controller` (one per hypervisor) holds a persistent TCP connection to the SB-DB. At large scale (500+ hypervisors) this is the known bottleneck:

- 500 open connections to SB-DB
- Large initial dumps when a new hypervisor joins
- `ovn-northd` recompile time grows with logical topology size

Mitigation options: `ovn-sb-ctl` relay nodes (proxy between ovn-controllers and SB-DB), incremental processing in ovn-northd (upstream feature). Relevant for NS post-GA scale planning (NSQ-030 / NSQ-031 performance targets).

---

## 6. OVN vs Neutron+RabbitMQ — comparison

| Aspect | Neutron + OVS L3-agent | OVN |
|---|---|---|
| **State store** | MySQL (neutron DB) + RabbitMQ (events) | OVSDB (both in one) |
| **Change notification** | RabbitMQ topic exchange → N agents | OVSDB `monitor` push → N controllers |
| **L3 / routing** | One Linux network namespace per router on a network node — centralized chokepoint | Distributed: routing as OpenFlow rules on every hypervisor |
| **NAT** | Kernel netfilter in the router namespace | Flow-based NAT in the OVS datapath |
| **Consistency** | Eventual (RabbitMQ delivery + agent processing latency) | Stronger — OVSDB write is atomic; monitor push follows immediately |
| **Debugging** | "When did agent X get the event?" — hard to answer | `ovn-sbctl show`, `ovn-trace` — exact state visible at any time |
| **Extra components** | RabbitMQ cluster required | None — OVSDB is self-contained |
| **Scale limit** | Individual router = single node bottleneck | Per-hypervisor distributed; bottleneck shifts to SB-DB connection count |

---

## 7. Geneve tunneling

OVN's preferred tunnel protocol is **Geneve** (Generic Network Virtualization Encapsulation) rather than VXLAN:

- Geneve header is flexible: carries a tunnel ID + arbitrary TLV metadata
- OVN uses the metadata to encode the logical port and logical datapath — enables flow decisions without a full IP lookup at the destination
- VXLAN has a fixed 24-bit VNI with no metadata extension — OVN can use it but loses the metadata optimization

In the OPCP substrate: Geneve tunnels form between hypervisor hosts for east-west VM-to-VM traffic. The tunnel endpoint is managed by `ovs-vswitchd`; `ovn-controller` programs the tunnel configuration via its local OVSDB connection.

---

## 8. DPDK integration (post-GA)

DPDK (Data Plane Development Kit) replaces the kernel OVS datapath with a userspace NIC driver:

- NIC packets go directly to a DPDK-polling userspace process — kernel bypass
- `ovs-vswitchd` runs in DPDK mode; OpenFlow rules still applied but at userspace speeds
- Combined with OVN: flow compilation stays the same; the datapath that executes the flows moves to DPDK
- Relevant for NSQ-030/031: DPDK is what makes "real packet rates" possible for the OVN post-GA track

DPDK is independent of OVN adoption — OVN can run with or without DPDK. The NS post-GA release plan couples them because OVN is the prerequisite for the distributed datapath that makes DPDK worthwhile at the router/NAT level.

---

## See also

- [L3 & LB Primer §2](l3-and-lb-primer.md#2-l3-complexity-levels-damiens-depends-what-you-want-to-achieve) — OVN as Level 4 in the complexity ladder
- [L3 & LB Primer §4](l3-and-lb-primer.md#4-the-ovn-special-case-for-the-lb-the-ovn-provider) — OVN provider for L4 LBaaS without amphorae
- [L3 & LB Primer §4.1](l3-and-lb-primer.md#41-mechanics--how-the-ovn-provider-actually-implements-a-lb) — NB DB `Load_Balancer` table → `ovn-northd` → `ct_lb` SB flows → `ovn-controller` per chassis
- [L3 & LB Primer §4.2](l3-and-lb-primer.md#42-what-changes-for-a-public-lb-vip--fip--the-fabric-scaling-claim-is-east-west-only) — public LB collapses to the gateway chassis; BGP (`ovn-bgp-agent`) makes the fabric follow gateway-chassis failover
- [NSQ-030](../open-questions.md) — OVN post-GA track: POC infra, DPDK, migration story
- [NSQ-031](../open-questions.md) — performance specs from Products (OVN POC validation yardstick)
- [Component survey 2026-07-08](component-survey-2026-07-08.md) — what OVN/OVS code exists in irobox/neutron repos today
