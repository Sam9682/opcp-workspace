# L3 & Load Balancer — Primer (subfeatures, technology, complexity levels)

> **Audience:** Everyone working on or co-deciding for the Network Service project — PM, architect, squad engineer, or newcomer who has read [`intro.md`](../intro.md) and wants to go deeper into the *technical anatomy* of what we're building. Explains what L3 actually consists of in OpenStack, which subfeatures LB + Gateway expose, where the real complexity sits, and why OVN is the quality answer to Damien's question *"do you want a real, scalable L3 experience?"*
> **Companion:** [Release cut Beta/GA/OVN](../plans/release-cut-beta-ga-ovn-2026-06-11.md) (the planning view) · [octavia-implementation.md](octavia-implementation.md) (as-built) · [intro.md](../intro.md) (use cases).

---

## 1. L3 in OpenStack — what it actually is

**East-west vs. north-south.** Tenant VMs talking to each other over their private Neutron networks is *east-west* traffic — it stays at L2, handled by OVS, and we already have it. **L3 is the north-south direction:** traffic going *out* to the internet or *in* from outside onto a VM or a load balancer VIP. Without L3, everything stays locked inside private networks — which is exactly what Damien meant when he said *"Octavia is a private-to-private LB"*: without L3 infrastructure, the load balancer can only balance between private networks and is unreachable from the internet.

**The four building blocks that make up L3:**

| Building block | What it does | Analogy |
|---|---|---|
| **External / provider network** | the Neutron network that physically leads outside (public IPs live here) | the street in front of the house |
| **Router (= our "Gateway", NSQ-004)** | virtual router connecting tenant networks to the external net | the house connection |
| **SNAT** | many private IPs → one public IP for **outbound** traffic ("VMs want to pull updates") | shared outbound mailbox |
| **Floating IP (DNAT)** | **one** public IP mapped 1:1 onto **one** private IP/port — this is how a VM **or an LB VIP** becomes reachable from outside | doorbell sign with its own number |

All four are delivered by the `neutron-l3-agent` — in our case a DaemonSet on the L3-services-aggregate hosts.

**Why the OVS implementation has a scaling problem.** The `neutron-l3-agent` builds one **Linux network namespace per router** on a network node. The important consequence: **all north-south traffic belonging to one router flows through that single node.** A heavy tenant can saturate that node, and adding more network nodes only helps if routers are spread across them — an individual router's traffic cannot be distributed. This is what Damien means by "scaling (BP and req/s) will be a problem": not that the system falls over immediately, but that the architecture creates a centralized chokepoint on the kernel network path for each router.

**Our SNC particularity (NSQ-027).** SNC today delivers customer IP ranges via **routing** (provider VLAN + BGP), not NAT — which is why there is currently no FIP/router Terraform code in the existing codebase at all. The NS project adds the NAT/FIP path on top of that substrate; public-IP orchestration for NS is expected to run through Charly Gregoire's middleware (NSQ-028).

## 2. L3 complexity levels (Damien's "depends what you want to achieve")

L3 in OpenStack is not a single feature — it is a progression of capability levels, each with its own implementation effort, risk profile, and architectural consequences. Damien's question *"do you want a real, scalable L3 experience?"* is specifically the choice between levels 1–2 (workable but architecturally centralized) and level 4 (the right answer architecturally, but a different stack entirely):

| Level | What | Effort/risk | Where we stand |
|---|---|---|---|
| **0 — no L3** | provider networks only, everything routed/private | — | today's SNC state |
| **1 — simple L3 (OVS)** | L3 agent + router + SNAT + FIP, centralized on network nodes | small — **substrate exists** (router plugin active, agent hardened); only the **tenant API surface** is new | **= the Beta path.** Known limits: centralized throughput, HA see below |
| **2 — HA router (VRRP)** | router namespace on 2+ nodes, keepalived failover | medium — standard feature, but **untested in our setup** (Damien) | GA-1 block (related to G1) |
| **3 — DVR** | Distributed Virtual Router: east-west + FIP traffic directly on the compute nodes | high — many edge cases, SNAT stays centralized anyway; widely considered a maintenance nightmare | **skip** — OVN solves exactly this, better |
| **4 — OVN (+ DPDK)** | entirely different control/data plane: routing as **distributed OVS flows on every node**, no L3 agent/namespace, NAT in the flow path, BGP via ovn-bgp-agent; DPDK = userspace datapath for "real" packet rates | large — migration of the whole network backend; **POC exists** (Damien) | = the **"real, scalable L3 experience"** → post-GA release |

**The core of Damien's OVN argument:** levels 1–2 scale *organizationally* — you add more network nodes and spread routers across them — but not *architecturally*: each individual router remains a centralized, single-node kernel path. OVN replaces that model entirely: routing and NAT are distributed across all nodes as flow rules, so throughput scales with the fabric rather than with a single namespace. Add DPDK and you get real packet rates in the datapath too. The price is a new stack (ovn-controller replacing the assorted L3-agent pieces) and a **migration story for existing tenants** — the hidden complexity block O3 in the release cut, and the reason OVN is post-GA rather than the immediate path.

## 3. Load balancer (Octavia) — the subfeature tree

Octavia's feature surface is broader than a typical LB product because it operates at both L4 (TCP/UDP) and L7 (HTTP). The full taxonomy of what a Load Balancer *is* in Octavia:

```
Load Balancer (has 1 VIP — private; public only via Floating IP!)
├── Listener (port + protocol: TCP/UDP/SCTP/HTTP/HTTPS/TERMINATED_HTTPS)
│   ├── TLS termination (certificate from Barbican)
│   ├── L7 policies (URL switching, host-header, cookie routing)  ← HTTP(S) only
│   └── Connection limit (guidance ≈2000, benchmark)
├── Pool (algorithm: round-robin / least-conn / source-IP / cookie persistence)
│   ├── Member (backend IP:port, weight)
│   └── Health Monitor (HTTP(S)/TCP/PING/TLS-HELLO → member ONLINE/ERROR)
├── Flavor (S/M/L = 1/2/4 vCPU — locked taxonomy, NSQ-002)
├── Topology: SINGLE (1 amphora) | ACTIVE_STANDBY (2 amphorae, VRRP — UNTESTED in our setup)
└── Quotas (LBs/listeners/pools/members per project — Octavia-native)
```

**Day-2 / operational subfeatures** are the GA-1 substance that makes Octavia production-worthy rather than just a working demo: automatic failover on heartbeat loss (plus manual failover trigger), a spare-amphora pool for fast replacement, certificate rotation, amphora image refresh and CVE patching pipeline ([NSQ-007](../open-questions.md)), tenant metrics (the `stats_prometheus` driver is merged but exposure to customers is still missing), and access/flow logging (adds ~20% CPU overhead, can be disabled per tenant).

**The dependency chain that explains why L3 is part of Beta scope.**

The VIP of an Octavia LB is always a *private* IP on a Neutron subnet. For the LB to be reachable from the internet, a Floating IP must be associated with that VIP — and Floating IPs require a router connected to an external provider network. The full chain:

```
publicly reachable LB = Octavia LB (✅ ready)
                      + Floating IP on the VIP      ← L3!
                      + external network + router    ← L3!
```

There is no way to offer a useful, internet-facing load balancer without all three elements. This is why minimal L3 (OVS level 1) is included in Beta scope (release-cut B3) rather than deferred to GA — without it the load balancer only serves internal traffic between private networks, which covers a much narrower set of customer workloads.

## 4. The OVN special case for the LB: the OVN provider

When OVN lands as the network backend (post-GA), it opens up a second way to implement load balancing. Instead of amphora VMs running HAProxy, Octavia can use the **OVN provider**: L4 load balancing implemented directly as OVN flow rules — **no amphorae**, no VM overhead, instant provisioning, scales with the fabric. The tradeoff is clear: **L4 only** — no L7 routing, no TLS termination, no cookie insert. Everything above TCP/UDP still requires amphorae.

This is not an either/or choice. A realistic picture after the post-GA OVN release: **OVN provider for simple TCP/UDP LBs, amphorae for L7/TLS** — both running in parallel under the same Octavia API surface. That evaluation is tracked as release-cut O4.

### 4.1 Mechanics — how the OVN provider actually implements a LB

The driver (`ovn-octavia-provider`, PyPI package — **not vendored in our octavia fork**, confirmed via `doc/source/admin/providers/ovn.rst` pointing at the upstream project) plugs into Octavia at the provider layer only. The API/DB layer (LB/listener/pool/member objects, quotas) is unchanged — provider selection just swaps which driver provisions the dataplane, and for `ovn` that path skips Nova, the worker process, health-manager, and housekeeping entirely. No amphora is ever created.

**NB DB write.** The driver writes directly to the OVN Northbound DB's `Load_Balancer` table via ovsdbapp. OVN's LB primitive is a flat map — `vips: {VIP:port → [backend_ip:port, ...]}` per protocol (tcp/udp/sctp) — not Octavia's listener→pool→member object graph. The driver's job is collapsing that richer model into this flat one. The `Load_Balancer` row is attached to the Logical_Switch/Logical_Router of the VIP's network (`ls.load_balancer` / `lr.load_balancer` columns), which is what scopes which chassis need the resulting flows.

**Compile chain (same NB→SB→OVS pipeline as [OVN/OVSDB architecture](ovn-ovsdb-architecture.md), applied to LB instead of routing).** `ovn-northd` compiles the NB `Load_Balancer` row into SB logical flows using the `ct_lb`/`ct_lb_mark` OVS action — a conntrack-based DNAT-and-select primitive, the same mechanism OVN uses for L3 NAT. `ovn-controller` on **every chassis** (direct SB DB monitor, no separate per-node LB agent) programs local OVS flows from that. Backend selection and connection persistence happen locally on the hypervisor nearest the client — this is Level 4's distributed property (primer §2) applied specifically to load balancing: no amphora VM, no network-node chokepoint. **Caveat: this "distributed" property is east-west only — see §4.2 for what changes once the VIP is public.** `[Inference]`

**Health checks exist but keyed to backend location, not client location.** `Load_Balancer_Health_Check` (NB) → `ovn-northd` emits one SB `Service_Monitor` row **per member**; the chassis hosting *that member's* logical port runs the actual TCP/ICMP probe and reports status back, and `ovn-northd` recomputes the `ct_lb` backend set to drop failed members. So it's distributed, but per-member-host, not per-client-host — and weaker than Octavia amphora's HTTP(S)/TLS-HELLO monitors either way. `[Inference]`

**Why L4-only is structural, not a missing feature.** `ct_lb` is a conntrack DNAT primitive baked into the OVS flow pipeline — it has no place to hold a TLS session (that needs a process with the cert in memory, which is exactly what haproxy-on-amphora provides) and no way to inspect payload for L7 URL/header routing or cookie insertion. Nothing above L4 can become OVN-native without a fundamentally different mechanism.

**Provider coexistence is structural too.** Provider is chosen per-LB via the `--provider` flag at the Octavia API — `ovn` and `amphora` LBs run side by side under the same API/project, confirming the O4 "not either/or" framing at the mechanism level.

**Consequences for NS scoping once OVN lands (post-GA, NSQ-030):**
- OVN-provider LBs need **zero amphora-aggregate capacity** — no S/M/L flavor, no `ovh.network` aggregate sizing, none of the CPU-pinning-off flavor work in [octavia-implementation.md §12](octavia-implementation.md). Different capacity/billing model than amphora LBs.
- ACTIVE_STANDBY/VRRP HA (currently untested, GA-1 block) is moot for OVN LBs — every chassis programs identical flows from SB DB, so HA is inherent to the model rather than a bolt-on feature to validate.
- No effect on M1–M4 scope today — this only activates once the OVN network backend actually lands.

### 4.2 What changes for a *public* LB (VIP + FIP) — the fabric-scaling claim is east-west only

§4.1's "distributed, no chokepoint" pitch holds for **east-west** traffic (VM → VIP inside the fabric — `ct_lb` runs on the source VM's own chassis). **North-south is different**, and worth being precise about before this reaches a Steerco. `[Inference — general OVN mechanics, not verified against the driver source; the driver package (`ovn-octavia-provider`) is not vendored locally]`

**Public LB traffic collapses to the gateway chassis.** External traffic can only enter the OVN fabric through the router's distributed gateway port, which is pinned to a single **gateway chassis** (or an HA chassis group with BFD failover — HA, not horizontal scale). FIP-DNAT and the VIP's `ct_lb` both execute *there*. So for a public LB, "load balancing happens on the hypervisor running the L3 router" is correct — that hypervisor is the active gateway chassis, and it's a centralized N-S point, same as SNAT is today (primer §2, Level 1–2). **OVN does not remove this chokepoint for public LBs** — it removes it for east-west only.

**Gateway chassis selection — two layers, don't conflate them:**
1. **Pool eligibility (capability-gated, not random):** a chassis only qualifies as gateway-capable if it has physical bridge-mapping connectivity to the external/provider network (`ovn-bridge-mappings`) and is flagged `enable-chassis-as-gw`. A pure compute node with no provider uplink cannot host the gateway port.
2. **Pick within the pool (per-router, scheduler-driven):** Neutron's OVN driver schedules the gateway chassis **per router**, writing a priority-ordered list into the router's gateway port — highest-priority-available is active, BFD failover walks down the list on death.

Net effect: **load is distributed across routers** (many routers spread across the gateway pool), **not within one router** — an individual router/LB's N-S throughput ceiling is still one active chassis at a time. This is architecturally the same property OVS's `neutron-l3-agent` scheduler already has today (spread routers across network nodes) — not an OVN-specific win. OVN's own distributed-FIP feature (the DVR-style bypass that lets a regular VM's own floating IP skip the gateway chassis) does **not** cleanly extend to LB VIPs — a VIP has no single bound port to distribute to.

**How traffic physically finds the (possibly just-failed-over) gateway chassis: BGP.** This isn't hypothetical — it's exactly how the *current* OVS setup already works, per the verified [minint egress-debugging runbook](../runbooks/minint-egress-debugging.md): the Neutron BGP dynamic-routing agent (**`neutron-bgp-dragent`** — distinct from and not to be confused with `ovn-bgp-agent` below), running as `bird` (proto `neutron_minint`, AS65003i) on the L3 node, announces each FIP as a `/32` to the border router `routerbgp`. The OVN-world equivalent of this same job is **`ovn-bgp-agent`** — it would run on the gateway chassis and announce the VIP/FIP `/32` (or the router's external block) from wherever the *active* gateway chassis currently is. On BFD failover to the next chassis, the **new** chassis's BGP speaker starts announcing the same `/32`, the old one withdraws — that's what makes the fabric actually follow the internal failover, not just an internal flow-table change nobody outside the box knows about. `[Inference for the OVN/ovn-bgp-agent half; the neutron-bgp-dragent/minint half is verified — see NSQ-027]`

**Open risk, not yet documented anywhere else in this project — added to [NSQ-027](../open-questions.md) 2026-07-13:** gateway failover is two-speed, chained. OVN-internal BFD detection (chassis↔chassis) is sub-second, but the **BGP session to the upstream router** only reacts on its own terms — either its (often slow-by-default) Hold Timer expiring, or a *separate* BFD-for-BGP session between the BGP speaker and its peer, if one is configured. Until that second stage clears, the upstream may still hold a route to the now-dead chassis — a black-hole window, not just a slow-failover window. Same question applies to today's OVS+`neutron-bgp-dragent`+`routerbgp` path, not just the future OVN one — nobody has confirmed whether that BGP session uses BFD or default hold-timers.

## 5. What this means for your conversations (cheat sheet)

- **"Is L3 hard?"** → Level 1 (OVS simple): no — substrate is there, what's new is the tenant API (FIP/router CRUD) + public-IP wiring. Level 4 (OVN): a project of its own with infra, DPDK and migration parts.
- **"Why not OVN right away?"** → Beta time pressure + the POC is not validated yet; OVS-simple unblocks customers/MKS immediately, OVN matures in parallel (Damien's R&D track; OVN is a **post-GA feature** per Marc 2026-06-11).
- **"What is the risk of the two-step path?"** → the **OVS→OVN migration** under running tenants (O3) — whoever uses Beta on OVS has to be moved later. This must be priced into the post-GA planning, otherwise the OVN release becomes a stranding risk for Beta customers.
- **"HA?"** → built (ACTIVE_STANDBY/VRRP), **never tested** — validation is a GA-1 block, not a Beta blocker (Beta can document SINGLE).
- **"How do we judge performance?"** → benchmark gives us the *as-is*; the *target* must come from Products (**NSQ-031**) — throughput/req/s/connections per flavor.
