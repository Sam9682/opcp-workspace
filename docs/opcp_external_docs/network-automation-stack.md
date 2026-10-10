---
id: core/network-automation-stack
type: deep-dive
diataxis: explanation
title: "OPCP Network Automation Stack — Neutron, ML2, NOG, Ragnarok & Arista"
owner: sov-copilot
status: approved
publish_target: git
product: opcp-core
---

# OPCP Network Automation Stack — Neutron, ML2, NOG, Ragnarok & Arista

> **Audience:** engineers and PMs who need to understand how Neutron, the ML2 OVH driver, NOG, Ragnarok, and Arista switches interact — what role each plays, which interfaces they use, and where the state-drift problem comes from.
>
> **Related:** [OPCP Core deep-dive](opcp-core/summary.md) · [OPCP Core Tech Spec v2026-06](opcp-core/tech-spec-v2026-06.md) · [Glossary](../../../../shared/glossary.md) · [Root Cause Collection — SOV-1751](../../../../.claude/skills/opcp-root-cause-collection/references/epic-details.md)

---

## 1. The actors — who is who

| Component | What it is | Where it runs | Since |
|-----------|-----------|---------------|-------|
| **Neutron** | OpenStack's networking API — virtual networks, ports, trunks, VLANs, routers. The abstraction layer that tenants and OpenStack services (Nova, Ironic, Octavia) talk to. | Controller node (`oc-cp`) as a K8s pod | upstream OpenStack (GOR downstream fork, branch `2025.2`) |
| **ML2 OVH Driver** | Neutron "Mechanism Driver" — OVH-built plugin that bridges Neutron's abstract network model to the physical switch world. Translates Neutron port/trunk/VLAN operations into NOG API calls. | Controller node (`oc-cp`), loaded as Neutron plugin | ~2018, in-house |
| **NOG** | OVH-built network automation — "the brain of the network." Receives events from ML2 driver, applies them to switches via on-switch agents. Also handles ZTP (zero-touch provisioning) for switch bootstrap. | Controller node (`oc-cp`) + small agent on **each Arista switch** | 2018 (originally for OVHcloud Connect) |
| **Ragnarok** | Switch **state machine** — newer component that tracks expected vs. actual switch state and detects drift. Runs as a K8s service with its own API server. Designed as the eventual replacement for direct NOG API calls. | Controller node (`oc-cp`) — K8s Service (`ragnarok-api-server`, `ragnarok-bootstrap`) | newer (post-2020), partially deployed |
| **Netbox** | CMDB / DCIM — inventory of every rack, switch, port, cable, MAC, IP. Generates each switch's startup config for ZTP. | Controller node (`oc-cp`) | upstream (self-hosted) |
| **Arista ToR** | Physical top-of-rack switches (**Arista DCS-7050CX3-32S**). Run a small NOG agent that listens for changes and applies them. Features: MLAG, LACP, VXLAN, BGP EVPN, MTU 9000. | Physical hardware, 2× per rack (A+B for HA) | hardware |
| **Cisco IPMI switch** | Out-of-band management switch (**Cisco C9200-48T**). Separate from the data-plane Arista stack. | Physical hardware, 1× per rack | hardware |

---

## 2. The communication chain — event flow

### 2.1 Happy path: "A VM is deployed — how does the switch get configured?"

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────┐    ┌───────────────────┐
│  Tenant API │    │   Neutron API    │    │ ML2 OVH     │    │     NOG API       │
│  (Horizon/  │───▶│  (port/trunk/    │───▶│ Driver      │───▶│  (REST API on     │
│   Nova/     │    │   VLAN create/   │    │ (Neutron    │    │   controller,     │
│   Ironic)   │    │   update/delete) │    │  plugin)    │    │   port 8082 or    │
└─────────────┘    └──────────────────┘    └─────────────┘    │   similar)       │
                                                                └────────┬──────────┘
                                                                         │
                                              ┌──────────────────────────▼───────────────────┐
                                              │          NOG Agent (on-switch)               │
                                              │    Small process running on each Arista      │
                                              │    Listens for changes from NOG controller    │
                                              │    Applies config directly via Arista eAPI    │
                                              │    or CLI on the switch                       │
                                              └──────────────────────────┬───────────────────┘
                                                                         │
                                                                         ▼
                                              ┌──────────────────────────────────────────────┐
                                              │       Arista ToR Switch (DCS-7050CX3-32S)    │
                                              │    VLAN, trunk, LACP, BGP config applied     │
                                              │    ToR A + ToR B (HA pair, MLAG)              │
                                              └──────────────────────────────────────────────┘
```

**Step by step:**

1. **Tenant or OpenStack service** (Nova, Ironic, Octavia) calls the **Neutron API** to create/update/delete a port, trunk, or network.
2. **Neutron** processes the request in its database and invokes its **ML2 plugin** — the mechanism driver layer.
3. **ML2 OVH Driver** (OVH's custom mechanism driver) receives the Neutron event and translates it into a **NOG API call** (REST HTTP). Example: *"Neutron port X deleted on VLAN Y → tell NOG to remove VLAN Y from the trunk on switch port Z"*.
4. **NOG API** (running on the controller) receives the request and pushes the change to the **NOG agent** on the relevant Arista switch.
5. **NOG agent** (running on the switch itself) applies the configuration change directly on the Arista switch using the switch's native management interface.
6. **Arista ToR** now has the updated config — VLAN added/removed, trunk modified, LACP interface configured.

### 2.2 ZTP — switch bootstrap (how a new switch joins)

```
   Physical switch powers on
            │
            ▼
   1. DHCP/PXE boot (VLAN 200 — provisioning)
            │
            ▼
   2. Pulls firmware from controller
            │
            ▼
   3. Controller provides config (generated by Netbox — knows topology)
            │
            ▼
   4. NOG agent installed on switch → starts running
            │
            ▼
   5. NOG agent receives live updates from NOG controller
            │
            ▼
   6. Switch is READY — part of the fabric
```

**Key:** Netbox is the source of truth for *what* the switch should look like (its startup config). NOG is the source of truth for *ongoing changes* (port/trunk/VLAN lifecycle events). The NOG agent is the *execution arm* on each switch.

### 2.3 Ragnarok — drift detection (the safety net that doesn't fully work yet)

```
┌─────────────────────────────────────────────────────────────────┐
│                      RAGNAROK (state machine)                    │
│                                                                 │
│  Expected State          Actual State (from switches)          │
│  (from Neutron/Netbox)   (via switch polling / agent reports)   │
│         │                          │                            │
│         └──────────┬───────────────┘                            │
│                    ▼                                             │
│             Drift Detection                                      │
│          (expected ≠ actual → alert)                           │
│                    │                                             │
│                    ▼                                             │
│             Drift Report (alert / dashboard)                    │
└─────────────────────────────────────────────────────────────────┘
```

Ragnarok is supposed to:
- Know the **expected state** (what VLANs/trunks/ports *should* be on each switch, derived from Neutron + Netbox)
- Query the **actual state** on each Arista switch (via its on-switch agent or polling)
- **Detect drift** — flag when expected ≠ actual
- Eventually: **auto-reconcile** (push corrections back to the switch)

**Current status (as of 2026-07):**
- ❌ Not all ToRs are enrolled (e.g. pod4.rbx missing)
- ❌ Spine switches not enrolled
- ❌ False positives due to output format differences (e.g. VLAN concatenation)
- ❌ No auto-reconciliation yet — drift is detected but not fixed
- ❌ Uses legacy EOS serialization (planned migration to OpenConfig & gNMI — SOV-60)

---

## 3. Communication interfaces — the protocol stack

| From → To | Interface / Protocol | What flows | Notes |
|-----------|----------------------|-----------|-------|
| **Tenant/Nova/Ironic** → **Neutron** | OpenStack REST API (`/v2.0/networks`, `/ports`, `/trunks`) | Create/update/delete networks, ports, trunks, floating IPs | Standard OpenStack API |
| **Neutron** → **ML2 OVH Driver** | Neutron ML2 mechanism driver API (Python plugin callbacks) | Port create/update/delete, trunk create/update/delete, network create/update/delete | In-process Python calls inside Neutron |
| **ML2 OVH Driver** → **NOG API** | REST HTTP (NOG's own API) | Translated switch operations: "add VLAN X to port Y", "remove trunk Z", "configure LACP on port A+B" | 🟡 **UNDER INVESTIGATION** — see [Root cause investigation status](#root-cause-investigation-status) |
| **NOG API** → **NOG Agent (on switch)** | Internal NOG protocol (push-based, long-lived connection or polling) | Switch config deltas: "apply this VLAN config change" | NOG agent listens for updates from NOG controller |
| **NOG Agent** → **Arista switch** | Arista eAPI (JSON/HTTP) or CLI | Direct switch config changes (interface, VLAN, trunk, LACP, BGP) | eAPI is Arista's RESTful API for programmatic config |
| **Ragnarok** → **Arista switch** | Legacy EOS serialization (today) → OpenConfig & gNMI (planned, SOV-60) | State polling / drift detection queries | gNMI = gRPC Network Management Interface; OpenConfig = vendor-neutral YANG models |
| **Netbox** → **Switch (ZTP)** | DHCP/PXE + generated config files | Startup configuration for each switch based on topology position | Netbox generates per-switch configs; switch pulls at boot |
| **Ragnarok API** → **K8s** | K8s Service (`ragnarok-api-server`, LoadBalancerClass: `io.cilium/l2-announcer`) + HTTPRoute via Traefik Gateway | Bootstrap and management of Ragnarok itself | Exposed via Gateway API HTTPRoute; bootstrap listener on HTTP (chicken-and-egg with TLS) |

---

## 4. Where the state-drift problem comes from

### The core issue: UNDER INVESTIGATION — root causes still being validated

> **Previous narrative corrected (2026-07-08):** The previous version of this section stated "ML2 → NOG is a fire-and-forget pipeline with no feedback loop." After colleague feedback and a code investigation (Neutron, Ironic, Nova GOR forks + Jira SOV-286/473/1293), this was found to be partially incorrect. The more likely root cause is at the Neutron/Ironic lifecycle level (driver not called for some baremetal operations), not at the ML2 driver level (driver dropping events). See the [Root cause investigation status](#root-cause-investigation-status) section at the end of this page for validated findings vs. hypotheses.

```
Baremetal port lifecycle — what the code actually shows
        │
        ├──▶ CREATE: Neutron calls ML2 driver → NOG → switch ✅
        │    (locks here are useful — prevent double-creation during parallel Terraform calls)
        │
        ├──▶ UPDATE (unbind) [VALIDATED IN CODE]:
        │    Ironic calls update_port during tear_down (NOT delete_port)
        │    → ML2 driver receives update_port_postcommit
        │    → HYPOTHESIS: if driver only cleans up NOG on delete_port_postcommit,
        │      the unbind is missed → stale switch config
        │
        ├──▶ DELETE [VALIDATED IN CODE]:
        │    Nova calls delete_port — but only for Nova-created ports
        │    For Ironic-created / pre-existing ports: Nova only unbinds (update_port)
        │    → These ports may never get a delete_port event
        │    → HYPOTHESIS: NOG config dangles forever for these ports
        │
        ├──▶ NOT CALLED [VALIDATED IN JIRA, SOV-473]:
        │    Neutron does not always call the ML2 driver for some lifecycle events
        │    → event never reaches NOG → drift
        │
        └──▶ TIMEOUT / ERROR [HYPOTHESIS — needs log extraction]:
             NOG doesn't respond →
             HYPOTHESIS: ML2 driver catches error silently and returns success →
             Neutron has no opportunity to retry → stale config
```

**VALIDATED findings:**
- Neutron does not always call the ML2 driver for update/delete operations on baremetal ports. Ironic calls `update_port` (unbind) during tear_down, NOT `delete_port`. (Ironic: `conductor/manager.py` `_do_node_tear_down`)
- Nova calls `delete_port` for Nova-created ports, but only unbinds (`update_port`) for Ironic-created / pre-existing ports — these may never get a `delete_port` event. (Nova: `network/neutron.py`)
- Ironic powers off the node and cleans up the ramdisk BEFORE unbinding ports. (Ironic: `conductor/manager.py`)
- Neutron has DB-level retry and port binding retry (`MAX_BIND_TRIES=10`), but does NOT retry on `MechanismDriverError`. (Neutron: `plugin.py`, `managers.py`)
- There is no reconciliation loop in NOG — it processes events one at a time and forgets. (Already known)
- Ragnarok should catch it, but it's incompletely deployed. (Already known)

**HYPOTHESES (not yet validated — need log extraction or driver source review):**
- The ML2 OVH driver may only clean up NOG config on `delete_port_postcommit`, missing `update_port_postcommit` events. (Driver source `networking-ovh-goldorack` v0.3.39 not available for review)
- The ML2 OVH driver may swallow exceptions and return success to Neutron, bypassing Neutron's retry mechanisms. (Needs driver source or log extraction)
- Lock conflicts are mainly a creation-sequence concern (parallel Terraform API calls), not a systemic issue during update/delete. (Supported by SOV-286, but not yet confirmed in driver code)
- The "Neutron retries up to 10×" claim from colleague feedback was NOT found in code for mechanism driver lifecycle calls. `MAX_BIND_TRIES=10` is for port binding, not for create/update/delete retry.

### The three-layer failure pattern (DRAFT — under revision)

```
Layer 1: Neutron / Ironic   ─── [VALIDATED] does NOT always call ML2 driver for baremetal update/delete
           │                  (Ironic: update_port unbind, not delete_port; Nova: delete_port only for Nova-created ports)
           │
Layer 2: ML2 OVH Driver     ─── [HYPOTHESIS] no internal retry; may swallow exceptions;
           │                            may only handle delete_port_postcommit (not update_port)
           │                  (driver source networking-ovh-goldorack not available for review)
           │
Layer 3: NOG API + Agent    ─── [VALIDATED] no reconciliation loop (processes events, forgets them)
           │
Layer 4: Ragnarok           ─── [VALIDATED] incomplete (not all switches enrolled, false positives)
                                 ↑ should catch drift but can't be trusted yet

NOTE: Root causes are under investigation. Log extraction needed to validate hypotheses in Layer 2.
```

**Every hotfix ticket in SOV-1751 is a symptom of one of these layers:**
- SOV-1293, SOV-473, SOV-286, SOV-468 → Layer 1/2 (driver not called / may miss events)
- SOV-1378, SOV-653 → Layer 3 (NOG misconfiguration / bootstrap issues)
- SOV-1213 → Layer 4 (Ragnarok incomplete)

---

## 5. The long-term vision — ML2 rewrite (SOV-110)

```
    TODAY                                    FUTURE (SOV-110)
                                          
Neutron API                            Neutron API
    │                                       │
    ▼                                       ▼
ML2 OVH Driver                         ML2 Driver (REWRITTEN)
    │                                       │
    │ direct NOG API calls                  │ talks to Ragnarok state machine
    │ (under investigation)                 │ (state-machine guarantees)
    ▼                                       ▼
NOG API                                Ragnarok State Machine
    │                                       │
    ▼                                       │ auto-reconciles drift
NOG Agent on switch                        ▼
    │                              NOG Agent on switch (or gNMI)
    ▼                                       ▼
Arista switch                          Arista switch

    NO RECONCILIATION                    CONTINUOUS RECONCILIATION
    events may not reach driver         state-machine driven
    drift accumulates silently           drift detected + corrected
```

**What changes:**
1. ML2 driver no longer talks to NOG directly — it talks to **Ragnarok**
2. Ragnarok owns the **expected state** and **reconciles** against actual switch state
3. If an event is lost, Ragnarok's next reconciliation cycle catches it
4. NOG (or its successor) becomes the **execution arm** that Ragnarok drives

**Prerequisites:**
- SOV-1213 (Ragnarok drift detection must be reliable — all switches enrolled, false positives fixed)
- SOV-60 (Ragnarok agents migrated to OpenConfig & gNMI — replacing legacy serialization)
- SOV-1746 (nog-cli dump in opcp-diag — diagnosis tooling to verify state)

---

## 6. The network fabric — physical topology

```
                    ┌─────────────────────────────────┐
                    │        External connectivity     │
                    └────────────┬────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │     Edge Switch A + B (HA)       │
                    │     (Arista DCS-7050CX3-32S)     │
                    └────────────┬────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │     Spine Switch A + B          │
                    │     (Arista DCS-7050CX3-32S)    │
                    └──┬─────────┬──────────┬─────────┘
                       │         │          │
              ┌────────▼──┐ ┌───▼──────┐ ┌─▼──────────┐
              │  ToR A+B   │ │ ToR A+B  │ │ ToR A+B    │
              │  Rack 1    │ │ Rack 2  │ │ Rack 3     │
              │  (Arista)  │ │(Arista) │ │ (Arista)   │
              └──────┬─────┘ └────┬────┘ └─────┬──────┘
                     │            │             │
              ┌──────▼──┐  ┌─────▼──┐  ┌───────▼──┐
              │Controller│  │BM nodes│  │ BM nodes │
              │  nodes   │  │(compute│  │(compute) │
              │(3× HA)  │  │+ Cisco │  │          │
              │         │  │IPMI)   │  │          │
              └─────────┘  └────────┘  └──────────┘
```

- **ToR A + B** = two Arista switches per rack in MLAG (Multi-Chassis Link Aggregation) for HA
- **Spine switches** connect all ToRs — VXLAN + BGP EVPN preserves VLANs across racks
- **Fabric** = the whole network of ToRs + spines
- **Inter-rack traffic** uses VxLAN tunneling + BGP EVPN for automatic network configuration
- **MTU 9000** end-to-end (jumbo frames mandatory)

### VLAN map (data-plane networks)

| VLAN | Name | Purpose |
|------|------|---------|
| 199 | Discovery | New / unseen machines |
| 200 | Provisioning | Bare-metal PXE boot (also called "Admin" in recordings) |
| 128 | In-band management | Controller in-band management path |
| 198 | Inter-controller K8s | K8s node-to-node traffic across 3 controllers |
| 666 | Garage | Unallocated / shut-down baremetal |
| 20 | Management | Controllers managing ToR switches |
| 4 | IPMI | Out-of-band management |

---

## 7. Summary — role of each component in one line

| Component | One-line role |
|-----------|--------------|
| **Neutron** | OpenStack's network API — abstract networks, ports, trunks. Tenants say *what* they want. |
| **ML2 OVH Driver** | The translator — turns Neutron's abstract operations into physical switch commands. **Under investigation — may not be the primary loss point.** |
| **NOG** | The network brain — receives translated commands and pushes them to switches. Has no memory of past events. |
| **NOG Agent** | The on-switch execution arm — runs on each Arista, applies config changes. |
| **Ragnarok** | The state machine — should detect and fix drift. Currently the unreliable safety net. |
| **Netbox** | The inventory — knows every rack, switch, port. Generates ZTP startup configs. |
| **Arista ToR** | The physical switches — where the VLANs, trunks, LACP, BGP actually live. |
| **Cisco IPMI** | Out-of-band management switch — separate from the data plane. |

---

## Root cause investigation status

### 2026-07-08 — Colleague feedback + code investigation

After a colleague reviewed this page, the feedback was investigated against source code (Neutron GOR fork: `neutron/plugins/ml2/plugin.py`, `managers.py`; Ironic: `ironic/conductor/manager.py`, `ironic/common/neutron.py`, `ironic/drivers/modules/network/common.py`; Nova: `nova/network/neutron.py`) and Jira tickets (SOV-286, SOV-473, SOV-1293).

**The previous narrative ("ML2 driver is lossy — drops events, lock conflicts, no retry") was partially incorrect.** The investigation revealed that the root cause is more likely at the Neutron/Ironic lifecycle level (driver not called for some operations) than at the ML2 driver level (driver dropping events).

#### Validated findings (confirmed in code)

1. Ironic calls `update_port` (unbind) during baremetal tear_down, NOT `delete_port`. The ML2 driver receives `update_port_postcommit`, not `delete_port_postcommit`. (Ironic: `conductor/manager.py` `_do_node_tear_down` → `remove_vifs_from_node` → `vif_detach` → `unbind_neutron_port` → `update_port`)
2. Nova calls `delete_port` for Nova-created ports, but only `update_port` (unbind) for Ironic-created / pre-existing ports. These ports may never get a `delete_port` event. (Nova: `network/neutron.py` `deallocate_for_instance`)
3. Ironic powers off the node and cleans up the ramdisk BEFORE unbinding ports. The switch config is already stale by the time the unbind reaches the ML2 driver.
4. Neutron has DB-level retry (`retry_if_session_inactive`) and port binding retry (`MAX_BIND_TRIES=10`), but does NOT retry on `MechanismDriverError`. (Neutron: `plugin.py`, `managers.py` `_call_on_drivers`)
5. Per SOV-473: "Neutron does not seem to propagate every port deletion event" — confirms the issue is at the Neutron level, not the ML2 driver level.
6. Per SOV-286: lock conflicts "only occur when ports are managed by Terraform" — supports that locks are a creation-sequence concern, not a systemic lifecycle issue.

#### Hypotheses (NOT yet validated — need log extraction or driver source review)

1. **HYPOTHESIS:** The ML2 OVH driver may only clean up NOG config on `delete_port_postcommit`, missing `update_port_postcommit` events. If so, the baremetal unbind never triggers NOG cleanup. (Driver source `networking-ovh-goldorack` v0.3.39 not available for review.)
2. **HYPOTHESIS:** The ML2 OVH driver may swallow exceptions and return success to Neutron, bypassing Neutron's retry mechanisms. (Needs driver source or log extraction.)
3. **HYPOTHESIS:** The "Neutron retries up to 10×" claim from colleague feedback refers to a mechanism other than `MAX_BIND_TRIES` — possibly behavior in the ML2 OVH driver itself. Not found in Neutron code for mechanism driver lifecycle calls.
4. **DRAFT IDEA:** Lock conflicts are mainly a creation-sequence concern (parallel Terraform API calls), not a systemic issue during update/delete. Supported by SOV-286 but not yet confirmed in driver code.

### 2026-09-01 — Driver source reviewed + contract test harness: hypotheses resolved

The driver source (`networking_ovh_goldorack`) **has since been reviewed in depth** (Alexander Graf's hardening workspace, 2026-08), and a contract test harness now reproduces the lifecycle bugs against a real Neutron ML2 plugin + real NOG in docker (stash [`gor/network-ovh-ml2-testenv`](https://stash.ovh.net/projects/GOR/repos/network-ovh-ml2-testenv/browse), 26 scenarios). The verified symptom→cause catalog, per-bug fix-PR status, and triage heuristics live in **[Network provisioning — known bugs & failure modes](../../procedures/troubleshooting/network-provisioning-known-bugs.md)**. Resolution of the hypotheses above:

1. **Refined.** The driver DOES handle `update_port_postcommit`, but specific unbind shapes fall through it: shelve-offload / plain unbind (host cleared, profile emptied) hits the "no context.host, ignoring request" branch and leaks the VLAN (W7, fix PR #53); live-migration activate and rollback leak source/target VLANs (fix PRs #49/#50). So "cleanup missed on unbind" is real, but per-code-path, not a blanket delete-vs-update gap.
2. **VALIDATED.** NOG calls are synchronous post-commit fire-and-forget; failures are variously raised, logged-and-`None`'d, or silently returned (three coexisting policies), and NOG refusals were logged at DEBUG — Neutron never sees most failures. PR #54 makes every non-200 NOG answer a WARNING.
3. **VALIDATED (negative).** No retry exists in the driver either — a single TCP timeout was permanent loss until PR #48 added retry/timeouts.
4. **VALIDATED, and worse.** The driver's file locks are pod-local (`lock_path` per pod) while BOTH the neutron-api and neutron-rpc pods load and execute the driver — no cross-pod mutual exclusion at all, beyond the Terraform-parallelism case.

The log-extraction action item below is largely superseded by the harness (the questions it lists are answered in the known-bugs doc); it remains useful only for confirming prod-specific frequencies.

#### Action item (DRAFT — to be scheduled)

Extract logs during a baremetal decommissioning cycle to validate the hypotheses above:
1. Enable debug logging on the Neutron ML2 plugin and the ML2 OVH driver (`networking_ovh_goldorack` logger)
2. Capture NOG API logs (request/response) during the same period
3. Capture Ironic conductor logs for the tear_down flow
4. Correlate timestamps between Neutron, ML2 driver, NOG, and Ironic to trace the exact event flow
5. Use `nog-cli dump` (SOV-1746) and `opcp-diag` to capture switch state before and after the lifecycle event

Questions to resolve:
- Which Neutron lifecycle events trigger ML2 driver callbacks?
- Which events are missing (not propagated to the ML2 driver)?
- Does the ML2 OVH driver raise exceptions on NOG API failures, or swallow them?
- When is `delete_port` actually called, relative to Ironic metadata cleanup?
- Does the ML2 OVH driver handle `update_port_postcommit` for NOG cleanup, or only `delete_port_postcommit`?
