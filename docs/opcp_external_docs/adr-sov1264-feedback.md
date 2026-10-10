# Feedback on the NS↔CB packaging ADR (SOV-1264 / Carsten Dittmann)

> **From:** Marc Dittmann / OPCP-PM · **Date:** 2026-06-09 · **For:** Carsten Dittmann + the Tech Board.
> **Re:** [ADR — Network Service packaging: bundle into the VM Service (Option A) vs keep a separate CloudStore Service (Option B)](https://confluence.ovhcloud.tools/display/SOV/%5BSOV-1264%5D+Network+Service+packaging) (branch `adr/network-vm-service-bundling`, parent LVL2-22123). Tracked here as NSQ-029.
>
> The ADR is deliberately recommendation-free for the Tech Board. This note adds **evidence that landed after the ADR was written** (the as-built Octavia distillation, the SNC hardening matrix, the SOV-583 IAM decision, the Object-Storage decision) and a **recommendation under one explicit delivery premise** — it does not pre-empt the board.

## Delivery premise (the frame for this evaluation)

**CB ships first, in June, WITHOUT LB** — the API-only Beta (M1+M2), qualified as **parity** against the existing SNC compute product. **Network/LB is delivered later, as its own milestone track** (the workspace already runs this as a *separate* Network-Service project with its own M1–M4; NS-M2 cannot precede CB-M2). So the question is **not** "delay June or not" (Network isn't in June under either option) — it is **how we package the later LB delivery relative to the already-shipped, already-qualified CB product.**

This premise matters: it **removes Option A's headline pro** ("initial June package is not delayed") — that pro is moot, because the temporal separation exists regardless. What remains to weigh is the *coupling* each option creates for the later delivery.

## Evidence that landed after the ADR (changes the pro/con weights)

| # | New evidence (source) | Effect on the ADR |
|---|---|---|
| 1 | **Octavia is a self-contained stack** — own CloudNativePG+PgBouncer, own RabbitMQ operator, own mTLS PKI, own mgmt-VLAN (410), 8 own Cilium netpols, own DIB amphora-image + Docker-image pipeline ([octavia-implementation.md](octavia-implementation.md)). What it shares is **OPCP-Core** (Keystone/Barbican/Glance/Nova/Neutron), available regardless of packaging. | **Weakens A-pro "fewer components / shared infra reuse."** Octavia does not meaningfully ride on the *VM-Service* package's infra; it stands up its own. |
| 2 | **SNC qualification entanglement is now concrete:** the [hardening matrix C1–C20](octavia-implementation.md) has open GAPs (C16 real-image validation = *High*, C15 VIP-firewall inert on virtio, C17 rate-limiting, C20 SG-drift) **and** NSQ-025: NS-M3 = **first-ever** SNC qualification (threat-model + ANSSI + pen-test, multi-month), vs CB-M3 = fast parity. | **Strengthens A's #1 con — decisively.** Under A, CB's qualified, June-shipped product gets re-coupled to NS's slow first-qualification at the version boundary. "Feature-flag-disabled-in-SNC" = un-qualified L3/LB code (with known C15–C20 gaps) inside a qualified artifact → audit problem. |
| 3 | **Independent CVE / image cadence** — Octavia has its own amphora-image builds, downstream PostgreSQL patches, fleet ops (multiqueue failover). | **Strengthens A's "coupled blast radius" con.** An Octavia/amphora CVE would force a new version of the whole VM+Block service under A. |
| 4 | **SOV-583 IAM (Option 4) decided** — per-(project, region, service) authz: a Keycloak client `{service}-region-{region}` + roles `{service}.{role}` per service ([ADR SOV-583](../../../architecture/adr/adr-sov-583-authz-model.md)). | **Weakens A-pro "single toggle / coherent product."** The platform already enables + authorizes **per service per region**; a bundled service still carries multiple service identities. B is the more consistent fit. |
| 5 | **Object Storage just decided to ship as its own standalone service** (own service-CP; CephADM; [OS decisions.md](../../object-storage-on-cloud-store/decisions.md)). | **Strengthens B-pro "consistent platform pattern"** and A's own slippery-slope con ("why not also bundle Object Storage?"). NS-in-CB would be the lone exception. |
| 6 | **The FIP / public-IP path is already multi-system:** NSQ-009 decided Model A (CB-UI owns the FIP form field; NS-M2 commits a stable FIP-API subset), and NSQ-027/028 route public connectivity through **Charly's middleware** (2IIP / agora / BL / Edge-API). | **Weakens A-pro "no cross-service API-stabilization cost."** The FIP boundary exists and spans systems regardless of packaging; the contract is already being scoped under B. |
| 7 | **Runtime coupling is substrate-level, not service-level:** NSQ-026 — NS aggregate hosts are provisioned via the **existing `Compute`/`ComputePool` CRDs**; "amphorae are VMs" = a dependency on the **Nova substrate + operator**, satisfiable by API/CRD. | **Neutralizes A's "dependency ⇒ bundle" intuition** (matches the ADR's own "Dependency ≠ bundling" note). *Mild point FOR A:* the Octavia CP is K8s-native, so co-locating it in cbs-cp is technically easy — but "feasible" ≠ "beneficial." |

## Recommendation (under the stated premise) — **Option B: keep Network a separate CloudStore Service**

Because CB ships in June without LB and LB is a later milestone anyway, **Option B achieves the exact same temporal separation Option A's versioning would — but without re-coupling CB's already-qualified product to NS's slow, first-ever SNC qualification.** That re-coupling (evidence #2) is the load-bearing risk, and it is now concrete, not hypothetical. Option A's three headline pros (fewer components, single toggle, no cross-service contract) are each materially weaker against the as-built reality (#1, #4, #6), and its unique remaining benefit — one customer-product surface — is achievable under B as a UX/LZM concern (the ADR's own cross-cutting note #2; NSQ-009 already folds FIP into the VM-create form).

**When A could still win** (kept honest): if the board weights *one upgrade lane + one customer product object* above the qualification-decoupling, **and** accepts the flag-disabled-in-SNC audit posture. B's cost — the stable FIP-API-subset contract + deploy-ordering — is real but **bounded and already in motion** (NSQ-009; NS depends on CB-M2 regardless).

## Concrete asks for the Tech Board

1. **Decide B** (separate `cloudstore-network-service`) **— or**, if A, explicitly choose the SNC-sequencing model (whole-service-waits-for-NS-qualification **vs** flag-disabled-in-SNC) and own the audit answer for un-qualified L3/LB code in the qualified artifact.
2. **Lock the FIP-API subset contract** (the main B-cost) — fold into NSQ-009 / the M2 endpoint-alignment (SOV-731).
3. **Note the C15–C20 hardening punch-list** lands in **NS-M3** (NSQ-025), independent of CB-M3 — a key reason to keep the qualification tracks separate.

---

*This note is OPCP-PM's evidence-based position; the decision is the Tech Board's. Cross-ref: NSQ-029 · [octavia-implementation.md](octavia-implementation.md) · NSQ-025 · [ADR SOV-583](../../../architecture/adr/adr-sov-583-authz-model.md).*
