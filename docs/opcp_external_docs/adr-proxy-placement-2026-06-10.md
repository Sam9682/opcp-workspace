---
id: compute-block-on-cloud-store/architecture-adr-proxy-placement-2026-06-10
type: decision
diataxis: n/a
title: "ADR — Proxy Placement for OPCP Service Packages"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# ADR — Proxy Placement for OPCP Service Packages

| | |
|---|---|
| **Date** | 2026-06-10 |
| **Deciders** | Marc Dittmann, Thomas Wiebe, Nathan, Ibrahim Takouna, Pierre-Yves, Alex Graf, Guillaume, Charley, Eddy Medina |
| **Consulted** | OPCP-Core proxy owners (Damien Rannou side) |
| **Status** | 🟡 PROPOSED — principles P1/P2/P3 agreed in session; A/B entrypoint fork deferred to follow-up session. **Thomas Wiebe + Nathan** assigned as authors for the final version once this draft is reviewed by Marc. |
| **Context** | Where do OPCP proxy groups live relative to the service control planes they protect? |
| **Decision** | P1 + P2 + P3 as binding placement principles; CB takes Groups 7+8 in OPCP Core as the immediate answer. A/B entrypoint fork open. |
| **Tickets** | SOV-715 · SOV-731 |
| **Open Qs feeding this** | Q-243 (proxy placement) · Q-244 (BM endpoint routing) · NSQ-010 · OSQ-21 |
| **Supersedes** | — |
| **Related** | ADR-0046 (K8s-per-group deployment model) · ADR-0053-S4 (dedicated OpenStack proxy group) |
| **Confluence draft** | [2026-06-12 — Proxy Placement ADR draft](https://confluence.ovhcloud.tools/x/yjz5OQ) |

---

## Context

**What ADR-0046 already fixed:** Each proxy group runs as its own Kubernetes cluster — 3 nodes, stateless pods, Cilium L2 + BGP HA, Redis-based token state, GitOps configuration. The *what* is settled. This ADR addresses the *where*: which control plane boundary the proxy groups sit in relative to the services they protect.

**Current architecture (6 proxy groups + ADR-0053-S4):**

```
 Internet / Tenant Network
         │
         ├──► Group 1: Global L2 CP Proxy   ──► Keycloak (master) · BL L2 · Panels
         ├──► Group 2: Global L3 CP Proxy   ──► Keycloak (tenant) · BL L3 · Panels
         ├──► Group 3: Regional L2 CP Proxy ──► OpenStack APIs (admin) · Horizon L2
         ├──► Group 4: Regional L3 CP Proxy ──► OpenStack APIs (user) · Horizon L3
         ├──► Group 5: L2 Data Plane Proxy  ──► S3 Admin / RGW L2
         └──► Group 6: L3 Data Plane Proxy  ──► S3 / RGW L3

 Internal only (ADR-0053-S4)
         └──► Group 7/8 (proposed): OPCP Core L2/L3 ──► OpenStack APIs directly
                                    (fixes Horizon bypass — tokens previously going
                                     browser → Glance without passing any proxy)
```

**What triggered this session:** As OPCP adds service packages (CB, NS, OS), each brings its own APIs and control plane. Every time the question came up — from CB's M3 scoping to NS and OS design — where the new proxy groups live was answered inconsistently. Q-243 has been open for months and its answer gates M3 sizing. A dedicated session was called to establish binding principles before any further per-service proxy design.

---

## Problem statement

Where should the proxy groups that protect an OPCP Service Package (CB, NS, OS, and future services) be deployed — inside the service's own control plane, or outside it?

**This ADR is NOT about:**
- Re-designing the proxy itself (token tracking, WAF rules, TLS model — ADR-0046 territory)
- Whether K8s, VMs, or Kata Containers are the right runtime (flagged for investigation, deferred)
- The single-entrypoint vs per-domain entrypoint question (Option C below — scheduled for a follow-up session)
- BM endpoint routing (Q-244 — explicitly not addressed in this session)

---

## Decision drivers

- **SNC qualification requires proxies to remain operational if the service CP they protect degrades.** A proxy on the same infrastructure as the service it guards fails with it.
- **Endpoint stability on SNC activation.** Customers may deploy without proxies first and activate SNC later. The external endpoint seen by the consumer must not change — otherwise every existing integration breaks.
- **Operational footprint.** Every proxy cluster is 3 nodes. Proliferating clusters per service compounds hardware cost and CVE patch surface (SNC SLA: 7–14 days from publication to prod).
- **Token-domain separation integrity.** Proxies enforce L2/L3 audience isolation via per-group Keystone-domain / Keycloak-realm allowlists. Domain-specific logic (OpenStack token tracking, S3 SSE-C enforcement, WAF rules per service) must stay associated with the right proxy context.
- **Alignment with the existing SNC proxy model.** Groups 1–6 already exist and are SNC-qualified. The OPCP convergence extends — does not contradict — this model.

**Out of scope:**
- Proxy runtime (K8s vs VM vs Kata/Firecracker) — under investigation by Thomas W.
- Single-entrypoint DSL design — requires a follow-up design session
- CloudStore L2/L3 entrypoint split — separate design track (Pierre-Yves)

---

## Proposed solutions

### Option A — Proxies co-located inside the service control plane

Each service package (CB, NS, OS) deploys its own proxy groups as part of its control plane. The `cbs-cp`, `nss-cp`, and `oss-cp` each run their own L2/L3 proxy clusters, configured and released with the service.

```
 Consumer (L2/L3)
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│  CB Service Package  (cbs-cp)                           │
│                                                         │
│  ┌──────────────────┐    ┌──────────────────────────┐   │
│  │  CB L2 Proxy     │    │  CB L3 Proxy             │   │
│  │  [K8s cluster]   │    │  [K8s cluster]           │   │
│  └────────┬─────────┘    └────────────┬─────────────┘   │
│           │                           │                 │
│           └────────────┬──────────────┘                 │
│                        ▼                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Compute API · Keystone · BL · Storage API       │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Pros:**
- Self-contained package — the service ships with everything it needs
- No cross-team dependency for proxy lifecycle management

**Cons:**
- **Violates the core security intent (eliminates this option).** Proxy inside the CP it protects provides no isolation — a CP-level incident takes the proxy down too.
- **Endpoint instability on SNC activation.** When a customer enables SNC on top of a proxy-free deployment, proxy VMs appearing inside `cbs-cp` would change the effective endpoint address. P2 cannot be held.
- **Multiplied CVE patch surface.** Proxy clusters per service × services = n-times the patch obligation.
- **Not aligned with SNC model.** Existing groups 1–6 live outside the backends they front. An inside-CP proxy creates a split the ANSSI audit would need to evaluate separately.

**Remaining questions:** None — eliminated by P1.

---

### Option B — Proxies in OPCP Core (Groups 7 + 8) ← current answer for CB

Proxy groups deployed in OPCP Core, outside and above the service packages. For CB, this means Groups 7 (L2) and 8 (L3), connected to ADR-0053-S4's dedicated OpenStack proxy slot. The groups always live in Core — never in the service CP.

```
 Consumer (L2/L3)
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│  OPCP Core                                                   │
│                                                              │
│  ┌──────────────────────┐    ┌──────────────────────────┐   │
│  │  Group 7 (L2)        │    │  Group 8 (L3)            │   │
│  │  OPCP Core Proxy     │    │  OPCP Core Proxy         │   │
│  │  [K8s cluster]       │    │  [K8s cluster]           │   │
│  └───────────┬──────────┘    └────────────┬─────────────┘   │
└──────────────┼────────────────────────────┼─────────────────┘
               │   (separate boundary)      │
               ▼                            ▼
┌──────────────────────────────────────────────────────────────┐
│  CB Service Package (cbs-cp)                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Compute API · Keystone · BL · Storage API           │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

The proxy boundary and the service CP boundary are **different network perimeters**. A compromise or outage on either side does not immediately propagate to the other.

**Pros:**
- P1 satisfied by design — proxy and service CP in different infrastructure units.
- Endpoint stability — Groups 7+8 can exist before the service is deployed. The external endpoint is fixed from day one. Activating SNC changes nothing visible to the consumer.
- Aligned with ADR-0053-S4 — the dedicated OpenStack proxy group is already in Core. Groups 7+8 are its natural extension.
- Fixes the Horizon bypass — Groups 7+8 sit directly in front of the OpenStack APIs. Nothing reaches them without passing through the proxy.
- No new cluster per service for the near term — CB's fix is 2 proxy VMs in Core.

**Cons:**
- Proxy lifecycle coupled to Core team — a CB-specific config change (e.g. new Keystone domain allowlist) requires coordination with OPCP Core.
- Scales with service count — as NS and OS join, group count grows. The 6-vs-2 collapse trade-off (Q-224) resurfaces at K8s-cluster granularity.
- Short-term CB fix = VMs, not K8s clusters — diverges from the ADR-0046 K8s target. Acceptable as a transitional state; needs a migration path.

**Remaining questions:**
- Naming: "OPCPCore" proxy group naming is a WIP.
- How does OS / NS get its proxy slot in Core when it needs one — new group per service, or reuse 7+8 with added domain config?

---

### Option C — Shared Proxy Package / Single Entrypoint (deferred)

One shared proxy set in front of all OPCP service control planes, routing traffic to each backend based on configurable per-service rules.

```
 Consumer (L2/L3)
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│  Shared Proxy Package (future — DSL not yet designed)        │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  L2 Proxy  ·  L3 Proxy                               │   │
│  │  [configurable domain-specific rules per service]     │   │
│  │                                                       │   │
│  │  CB config  │  OS config  │  NS config  │  ...        │   │
│  └──────┬──────┴──────┬──────┴──────┬──────┴────────────┘   │
└─────────┼─────────────┼─────────────┼──────────────────────┘
          ▼             ▼             ▼
       cbs-cp        oss-cp        nss-cp
```

**Pros:**
- Smaller cluster count — fewer K8s clusters to patch and maintain.
- Matches "OPCP as small as possible" — every control VM in a customer deployment counts.
- Natural fit for a "proxy-as-a-service" model (Gateway API operator proposal from Nathan / Guillaume / Thomas W.).

**Cons:**
- **Requires a configurable DSL that does not exist yet.** Today's proxies carry hard-coded domain-specific logic: OpenStack token tracking (custom KD module), S3 SSE-C header enforcement, per-service Keystone-domain allowlists, WAF rule sets. A shared proxy needs each consuming service to supply its config declaratively. That interface is not designed.
- Risk of coupling unrelated services — a config error for CB should not affect OS traffic.
- Deferred — not decided in this session. Scheduled for a follow-up session.

**Remaining questions:**
- What is the right interface for per-service proxy config — Gateway API CRDs? A proprietary DSL?
- Does the Caddy-based proxy-operator idea (Nathan) provide this without a new language?
- Does Option C conflict with or supersede ADR-0046's K8s-per-group model?

---

## Decision

**P1, P2, P3 are adopted as binding placement principles. CB takes Option B (Groups 7+8 in OPCP Core) as the current answer.**

Option A is eliminated by P1 — running a proxy inside the same control plane it protects defeats the security purpose. The session was unambiguous on this.

Option B is the answer for CB now: 2 proxy VMs in OPCP Core as a transitional fix, with the K8s cluster (ADR-0046 compliant) as the target state. This satisfies P1 and P2 without requiring new design work.

Option C stays on the table. It becomes the right answer as service count grows and per-service proxy group footprint becomes material — but requires the configurable DSL work first. A follow-up session is scheduled.

Proxy development moves out of CB M3/M4 scope entirely and becomes its own side-project (Thomas Wiebe lead). CB's remaining proxy work is limited to wiring Groups 7+8 in Core and aligning SOV-731 to the P2/P3 endpoint constraints.

### Binding principles

| # | Principle | Implication |
|---|---|---|
| **P1** | A proxy must not reside in the control plane it protects | Option A-type placements are out. Proxy and service CP must be in separate infrastructure units. |
| **P2** | Opt-in deployment, same logical slot always | The proxy endpoint is fixed from first deployment. Activating SNC must not change it. Endpoint changes on SNC activation should be avoided by design. |
| **P3** | Groups 7+8 (OPCP Core L2/L3) confirmed for CB | Connected to ADR-0053-S4. Closes the Horizon-bypass gap. Starting point: 2 proxy VMs in Core. |

---

## Consequences

- SOV-715 [MS3][cbs-cp/proxies] is no longer CB-owned work — proxy dev migrates to the side-project. CB M3 planning removes this block.
- SOV-731 re-scoped: validate that the M2 API endpoint shape is compatible with the Groups 7+8 insertion point without consumer-visible change.
- Q-243 partially closed: "inside the protected CP" is ruled out; per-domain (B) vs single-entrypoint (C) remains open, assigned to follow-up session.
- Q-244 (BM endpoint routing) not addressed — carry forward.
- OSQ-21, NSQ-010 not directly resolved — the single-entrypoint discussion (Option C) is the intersection point; revisit in follow-up.
- Thomas W. + Nathan assigned as ADR authors once Marc + Eddy write-up is reviewed.
- Pierre-Yves: design the L2/L3 CloudStore entrypoint split separately.

---

## References

- [Proxies deep-dive](../../../../opcp-core/architecture/conceptions/proxies/summary.md) — §3 group matrix · §4 ADR-0046 model · §5 ADR-0053-S4 · §7 token tracking
- [M3 Design Session notes — 2026-06-10](../meetings/2026-06-10-m3-proxy-session.md)
- [Eddy's official Confluence summary — pageId 972632952](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=972632952)
- [Confluence draft ADR](https://confluence.ovhcloud.tools/x/yjz5OQ)
- ADR-0046 (K8s-per-group model, PSPUSNC space) — fixes the *what*; this ADR fixes the *where*
- ADR-0053-S4 (dedicated OpenStack proxy group) — Groups 7+8 are its natural extension
- Source: Marc Dittmann, Thomas Wiebe, et al., M3 Design Session 2026-06-10
