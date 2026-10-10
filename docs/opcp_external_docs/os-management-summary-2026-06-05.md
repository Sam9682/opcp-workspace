# OS — Management Summary 2026-06-05

> **Purpose:** Executive status update for Steerco / PU.OPCP Core leadership — **Object Storage on CloudStore**.
>
> **State:** 2026-06-05. **Baseline for delta:** 2026-05-29 CS Weekly + 2026-05-21 management-summary-log entry.
> **Owner:** Marc Dittmann (squad lead / driver) · **PO:** Eddy Medina. **Package owner:** Vincent Casse.

---

## 🎯 Headline

> *"Discovery just cleared its biggest blocker: Zafar Akhtar put forward the first concrete S3 architecture proposal (BM via Ironic → k3s → Rook + Ceph/RGW → per-Account Keystone↔Keycloak), which breaks the 'no shared direction nailed down' deadlock that had stalled the start. The open design space is now two crisp, parallelisable problems — **P1 Cluster orchestration (Rook vs cephadm)** and **P2 Auth flow & SNC admin/user separation (2-Keystone)** — both routed into a 1h expert brainstorm (Stephan + Boris + Nathan + Ibrahim). New reuse signal: SNC's current Ceph stack is well-written Ansible on the Ceph operator and may be usable largely out of the box. End-July target holds, but confidence stays **Low–Medium** — the schedule driver remains BL capacity (full until June)."*

---

## 1. Where we are

| Milestone | Status | Confidence on end-July target |
|---|---|---|
| **M1 — Install the Service** *(node provisioning + Ceph/RGW bring-up)* | 🟡 *Architecture proposal on the table; PoC stage starting (Hello World connectivity + Rook POC). Orchestration engine not yet frozen.* | 🟡 **Low–Medium** — gated by the P1 decision + PoC result |
| **M2 — Activate a customer** *(per-Account S3, compliance-deferred beta)* | ⚪ *IAM chain decided (Ceph→RGW→Keystone→Keycloak); SNC 2-Keystone separation = P2, open. Blocked on BL capacity.* | 🔴 **Low** — BL full until June (OSQ-03) |
| **M3 / M4** *(SNC-ready · air-gapped)* | Planning. Not in the near-term window. | n/a |

> **Stage framing:** OS is still **discovery → architecture**, one phase behind CB. This week moved it from "no agreed starting point" to "one proposal + two scoped problems + a brainstorm booked." That is the right kind of progress for this stage, but no implementation has been de-risked yet.

## 2. What changed this week — Delta to 2026-05-29

### ✅ Progress / new signal *(Teams thread 2026-06-03 → 2026-06-04, Object Storage channel)*

| Item | Stand 2026-05-29 | Stand 2026-06-05 |
|---|---|---|
| **Shared architecture direction** | ❌ *"no shared direction nailed down yet (how to start)"* — flagged as the thing stalling the start | 🟢 **First concrete proposal on the table** (Zafar) — see §3. Team now has a baseline to build on / argue against. |
| **Orchestration question** (OSQ-15 / OSQ-04) | 3-way open: cephadm / Ansible / Rook | 🟡 **Narrowed to 2** and reframed as **P1 — Rook vs cephadm**. Decision hinges on *"whether OPCP standardises on Kubernetes platform-wide"* (Zafar). |
| **SNC Ceph reuse** (OSQ-10) | "inventory what's manual in SNC" — open | 🟢 **Boris 2026-06-04:** SNC uses the **Ceph operator**, *"'just' very well written ansible (kudos to Stephan, wrote it last year)"* — **might be usable out of the box right now.** Concrete reuse base identified. |
| **Auth / SNC separation** (OSQ-02) | Topology meeting pending, unscheduled since 2026-05-18 | 🟡 **Reframed as P2** with the SNC target explicit: **two Keystones** (S3 users + S3 admins) → separate L3-customer / L2-admin proxies + RGW frontends. Folded into the brainstorm. |
| **Expert brainstorm** | — | 🟢 **Booked:** 1h session — **Stephan + Boris + Nathan + Ibrahim** (Marc's call; Vincent not needed at impl depth). **Eddy setting it up** ("On it, will set it up", 2026-06-04). |
| **PoC path** | 3 free `ceph-block-*` VMs found (paas-storage-block) | 🟡 Zafar adds: could **borrow the single-node `cloudstore` k3s** as a quick test bed to validate **Rook + multi-tenancy** even on one node. |

### 🟠 The two problems to land *(Zafar's framing, 2026-06-04 17:07)*

- **P1 — Cluster orchestration: Rook or cephadm?** *"Rook means running it on Kubernetes (k3s) — k8s-native but two systems to operate. cephadm runs Ceph directly on the hosts — no Kubernetes, smaller surface. Same S3 result either way; the decision hinges mainly on whether OPCP standardizes on Kubernetes platform-wide."*
  - **Lean (Stephan + Boris, 2026-06-04):** Rook — *"k8s is the management wrapper already known for creating and destroying resources … little to no experience how rook performs in larger environments, but think it will be fine."* Counter-pull (Zafar): *"I'm not seeing a real benefit to Rook for our case at the moment: it requires us to run a full Kubernetes cluster."* **→ unresolved; this is the live tradeoff.**
- **P2 — Authentication flow & SNC separation.** Per-Account Keycloak realms → **two Keystones** (one for S3 users, one for S3 admins) → separate customer (L3) and admin (L2) proxies + RGW frontends, so no credential can cross audiences. Covers key minting (Keycloak login → Keystone) and validation (RGW → Keystone). **This is the admin/user separation SNC requires** — and it directly extends OSQ-02.

### 🔴 Standing risks (unchanged this week)

- **BL capacity is still the schedule driver** (OSQ-03). Business Logic is full until June for SNC and is required for OS account-activation / quota / usage. End-July target depends on BL freeing up — escalation path is Marc → Vincent.
- **S3 proxy / network exposure unsolved** (OSQ-06) — and, as Marc noted in-thread, *"also not solved yet for Compute & Block."* Shared risk across both packaging projects; worth a joint decision rather than two parallel ones.
- **Architecture still unfrozen.** Neither P1 nor P2 is decided. The end-July line assumes the brainstorm lands a decision quickly and the Rook POC validates cleanly.

## 3. The proposal on the table — Zafar's first cut *(2026-06-03)*

A concrete, single-Keystone v1 shape (the SNC 2-Keystone split is the M3 target layered on top):

```
account-a / account-b          ← two customer Accounts
   ↓ (authenticate via own L3 realm)
realm-a / realm-b              ← per-Account Layer-3 Keycloak realm
   ↓ (federates)
Keystone — trusts L3 realms · mints + validates S3 keys · maps each key → its tenant
   ↓
Ceph + RGW — shared S3 endpoint   tenant-a buckets │ tenant-b buckets   (isolated, no cross-access)
   ↑ managed by
Rook — manages Ceph (MONs, OSDs, RGW as pods + lifecycle)
   ↑
k3s — Kubernetes (dedicated to the storage stack; no tenant workloads)  · "maybe depend on MKS service?"
   ↑
OpenStack (Ironic) — bare-metal nodes (~4, each with disks for Ceph)
```

**In Zafar's words:** *"each account = its own isolated RGW tenant … Keystone mints and validates the S3 access keys and maps each key to its tenant. So account-a and account-b authenticate independently and can never see each other's data."* Thomas Poehler's guard-rail: *"whatever architecture we design … we need to make sure we are SNC compliant."*

**Marc's framing of the job** (2026-06-03 15:30): reuse what SNC already has (it works); the *"only"* thing to solve is **packaging it as a standalone CloudStore Package** — our own small control-plane + an **owner/Keystone operator to connect to Cloud Store** + the **proxies** question (shared with CB) + bringing SNC's **manual L2 operations** (add a node / disk, etc.) into the Package, since Cloud Store users won't have the skills or access — the path to an **air-gapped-ready** version.

> Two open sub-questions surfaced by the proposal, worth tracking: **(a)** does k3s *"depend on the MKS service"*? and **(b)** is the single-node `cloudstore` k3s acceptable as the Rook/multi-tenancy PoC bed? Both feed OSQ-15 / OSQ-18.

## 4. Resource state — where attention is concentrated

| Person | Role this week | Signal |
|---|---|---|
| **Zafar Akhtar (EXT)** — SRE | Authored the architecture proposal; framed P1/P2 | Driving the design conversation; honest that he's *"not a Ceph expert"* — needs the experts in the room. |
| **Boris Behrens (EXT)** | Owns Rook discovery (took over from Stephan) | Surfaced the SNC-Ceph-operator reuse base; leans Rook for long-term manageability. |
| **Stephan Hohn (EXT)** | Ceph expert (off the OS workstream, consult-only) | Wrote the SNC Ceph Ansible — the reuse base. Needed in the brainstorm. Bandwidth split with CB SOV-256. |
| **Ibrahim Takouna (EXT)** | Keycloak / Keystone | Needed for P2 (2-Keystone). Already confirmed Keystone Controller is OS-compatible (6 RGW params). |
| **Nathan** | SNC reference | Named by Marc as an SNC S3 expert for the brainstorm. |
| **Eddy Medina** — PO | Coordination | Setting up the expert brainstorm + the SNC-manual-ops walkthrough. |
| **Vincent Casse** | Package owner | Per Marc, *"not that deep into the implementation details"* — not required in the technical brainstorm; stays the BL-capacity escalation point. |

## 5. Asks at Steerco / PU.OPCP Core Weekly

1. **Endorse the expert-brainstorm path** (Stephan + Boris + Nathan + Ibrahim, 1h) as the mechanism to land **P1 (Rook vs cephadm)** and **P2 (auth flow / SNC 2-Keystone)**. This is the gating decision for M1 — it should not drift.
2. **The Kubernetes-platform-wide question** is upstream of P1: *does OPCP standardise on k8s platform-wide?* If yes, Rook is the natural call; if undecided, that ambiguity blocks OS's orchestration decision. Needs a leadership steer.
3. **BL capacity (OSQ-03)** — when does Business Logic free up after June? This is the single biggest determinant of the end-July M2 date. Marc → Vincent.
4. **S3 proxies / network exposure (OSQ-06)** — unsolved for **both** OS and CB. Propose a **joint** proxy decision rather than two parallel efforts.

## 6. Looking ahead — next week's signal-to-watch

- **Expert brainstorm outcome** — does it land a P1 direction (Rook vs cephadm) and a P2 sketch (2-Keystone separation)? First real architecture-freeze signal.
- **Hello World** OpenStack connectivity test (Boris + Zafar) — unblocked since 2026-05-29; does it pass?
- **Rook POC** — on the borrowed single-node `cloudstore` k3s or the 3 `ceph-block-*` VMs; validates Rook + multi-tenancy.
- **BL capacity** signal as June starts — the end-July line moves with it.

---

## References

- [`tracking/weekly.md`](../tracking/weekly.md) · [`tracking/blockers.md`](../tracking/blockers.md) — live OS status + blockers.
- [`open-questions.md`](../open-questions.md) — OSQ table; this week touches **OSQ-15** (orchestration), **OSQ-04** (Ceph-deploy mechanism), **OSQ-02** (IAM / 2-Keystone), **OSQ-06** (proxies), **OSQ-10** (SNC reuse), **OSQ-18** (OpenStack test resources).
- [`README.md`](../README.md) — current direction + ownership.
- [`meetings/2026-05-28-zafar-onboarding.md`](../meetings/2026-05-28-zafar-onboarding.md) — Zafar onboarding (the prior session).
- [`../management-summary-log.md`](../../../../../_workspace/management-summary-log.md) — CB + OS weekly logbook (ABC frame).
- CB counterpart: [`../../compute-block-on-cloud-store/plans/cb-management-summary-2026-06-05.md`](../../compute-block-on-cloud-store/plans/cb-management-summary-2026-06-05.md).
