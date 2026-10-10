---
id: compute-block-on-cloud-store/architecture-storage-controller-onboarding
type: deep-dive
diataxis: explanation
title: "Storage Controller — Onboarding Briefing"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Storage Controller — Onboarding Briefing

> **Audience:** Stephan Hohn (EXT) — lead of the Storage Controller buildout (SOV-256) — and anyone joining the Storage workstream.
>
> **Purpose:** hand over what the Compute workstream has already learned so the Storage Controller starts from solid ground, not from scratch. Includes a path for spec-first development with [OpenSpec](https://github.com/Fission-AI/OpenSpec) if the team chooses to adopt it.
>
> **Status:** prepared 2026-05-26 by Marc + Claude as a forwardable briefing. Cross-check against the live `opcp-infra-operator` repo before committing to anything below — claims here are accurate to mid-May 2026.

---

## 1. TL;DR

- The **OPCP Infra Operator** binary already exists with a generic framework (`internal/controller/base/`) explicitly designed so Storage + Keystone Controllers are **additions, not rewrites**.
- The Compute Controller is shipped and battle-tested; its design choices are codified as ~20 markdown specs in `opcp-infra-operator/specs/001-020/` — **read these first as your spec vocabulary**.
- The Storage Controller (`StoragePool` + `Storage` CRDs) is a **mirror** of Compute, plus a small set of Ceph-specific concerns the Compute precedent does *not* cover (bootstrap-vs-join, destroy-safety, Ceph-daemon-health → `Healthy` mapping).
- If you want to do **spec-first / OpenSpec** here: the Compute team already did it informally (their `specs/` folder); OpenSpec would just be a formalisation. Six initial Storage specs are listed in §6 below.

---

## 2. What's already done — re-use this, don't re-derive

The Compute workstream has spent months landing the following framework + invariants. They generalise to Storage by construction.

### 2.1 The shared framework (`internal/controller/base/`)

This is the single biggest reason your scope is small. The base framework provides:

| Capability | Provided by base | What you need to add for Storage |
|---|---|---|
| Provisioner-Job lifecycle (apply / destroy) | `base/` | Storage-specific Terraform + Ansible content |
| Drift detection (spec hash + source-revision tracking) | `base/` | — |
| Resource Agent heartbeat plumbing | `base/` + `internal/api/server.go` | Storage-specific Resource Agent payload |
| Pool aggregation pattern | `base/pool/` | `StoragePool` CRD wiring it up |
| Per-resource reconcile loop | `base/resource/` | `Storage` CRD wiring it up |
| K8s Secret as TF-state storage | `base/` | — |
| `BreakTheGlass` + `PreventDestroy` + `SuspendReconciliation` flags | base + CRD shape | Surface them on `Storage` CRD with sensible defaults (see §4) |
| Validating admission webhook scaffolding | `internal/webhook/` | Storage-specific validation rules (e.g. min Storage-nodes per Pool for quorum) |
| Prometheus metrics | `internal/metrics/` | — |

**Concrete next-step:** stand up `internal/controller/storage/` + `internal/controller/storagepool/` mirroring `internal/controller/compute/` + `internal/controller/computepool/`. Wire the framework, then iterate on the Terraform/Ansible content.

### 2.2 The invariants

These hold across all sibling Controllers — Storage must honour them too:

- **1:1:1** — one CR ↔ one Provisioner Job ↔ one target node. No parallel jobs per CR. Operator enforces, replacing TF-native locking. *(For Ceph, "target" is one OSD-host; cluster-level bootstrap is a higher-order concern — see §5.3.)*
- **`Vars` is opaque** — the CRD schema knows nothing about domain-specific fields; the TF module interprets them. Resist the temptation to type-narrow Storage-specific fields into the CRD — keep the symmetry with Compute.
- **3 independent conditions** — `Ready` (provisioning success) · `Synced` (spec freshness) · `Healthy` (runtime liveness via Resource Agent). Don't merge them. Map Ceph-daemon health → `Healthy` only; OSD-up-count belongs in `status.lastSignal` payload, not in a fourth condition.
- **Two REST surfaces — disambiguate religiously** — see §3 below; this is the single most-confused topic in our docs.

### 2.3 The 20 specs in the repo — your best spec-first vocabulary

Read `opcp-infra-operator/specs/001-020/` in order. They cover: architecture overview · custom-resource spec · provisioner architecture · variable injection · status-update API · resource agent · heartbeat detection · break-glass debug · single-namespace mode · OpenStack secrets mount · etc.

**These are the Compute team's lived spec-driven dev.** If you go OpenSpec route, your six Storage specs (§6) sit alongside these.

### 2.4 The 20 in-repo docs

`opcp-infra-operator/docs/` is the canonical contract source — stays current with the code. When in doubt, the repo wins over any wiki page:

| Topic | Doc |
|---|---|
| Overall architecture + diagrams | `docs/architecture.md` |
| Full CRD reference (Spec/Status fields, defaults, examples) | `docs/api-reference.md` |
| External integration (customer-facing OPCP Infra API design) | `docs/external-integration.md` |
| Heartbeat / Resource Agent | `docs/heartbeat.md` |
| OpenStack credentials handling | `docs/openstack-credentials.md` |
| Terraform module conventions | `docs/terraform-module.md` |
| Variable injection (pool/CR/Secret merge order) | `docs/variables.md` |
| Troubleshooting | `docs/troubleshooting.md` |

---

## 3. Verwechslungsfalle Nr. 1 — two REST surfaces

The repo has **two distinct REST APIs**. Don't conflate them.

| | **Internal callback API** | **OPCP Infra API (external)** |
|---|---|---|
| **Lives in** | Operator binary (`internal/api/server.go`, Gin) | Separate service outside this repo (per `docs/external-integration.md`) |
| **Listens on** | `:8082` (`--api-bind-address`) | Public ingress |
| **Who calls it** | Operator's own Provisioner Jobs + Resource Agents on baremetal | External: `cloudstore-vm-bs-service` TF · Temporal · dashboards · CI/CD |
| **Auth** | K8s SA tokens (protected routes); unauthenticated heartbeat + healthz | Basic auth M1; OIDC planned |
| **Storage-relevant routes** | `PATCH /storages/:name/heartbeat` (planned) · `PATCH /storages/:name/status` (planned) · `GET /api/v1/storage/:name/context` (planned) | CRUD against `Storage` / `StoragePool` — customer-facing CRDs abstraction |

**Mental rule:** *"the operator talks to itself"* → internal `:8082`. *"anybody outside K8s talks to OPCP infra"* → external API. When older docs say *"the OPCP Infra API"* without qualifying, they almost always mean **external**.

Canonical external reference: [OPCP Infra API Swagger](https://rtstatic.ovhcloud.tools/gor/publiccloud/opcp-infra-api/latest/opcp-infra-api-reference.html).

---

## 4. The Storage CRDs — proposed shape (Compute mirror)

```go
// api/v1alpha1/storage_types.go (proposed, mirrors Compute)
type StorageSpec struct {
    PoolRef               string                           // required
    SuspendReconciliation bool
    Vars                  map[string]apiextensionsv1.JSON  // opaque — TF module interprets
    SecretVarRefs         []string                         // ceph keyring refs, etc.
    PreventDestroy        bool                             // RECOMMEND default true for Storage (data!)
    BreakTheGlass         bool
}

type StoragePoolSpec struct {
    SourceRef        FluxSourceRef    // GitRepository / Bucket / OCIRepository
    WorkingDirectory string
    Vars             map[string]apiextensionsv1.JSON  // shared pool defaults
}
```

**Key Storage-specific decisions to make explicit:**

- **`PreventDestroy` default — Storage > Compute.** Ceph-node destroy = data loss. Recommend defaulting to `true` for `Storage` CRs (Compute defaults to `false`). Decision needs an ADR row.
- **Ceph-specific `Vars` keys** — minimum: `failure_domain`, `replication_factor`, `osd_role` (mon/osd/mgr/mds), `crush_root`. Add as you discover via TF-module work. **Keep them out of the CRD schema** — keep symmetry with Compute.
- **Conditions** — same three (`Ready`, `Synced`, `Healthy`). Resource Agent reports Ceph-daemon-liveness; `status.lastSignal` payload carries OSD-up-count + nearfull warnings.

---

## 5. What Compute *didn't* solve — Storage-specific spec work

These are the genuine net-new design questions where Compute precedent stops helping.

### 5.1 Destroy-safety for data-bearing nodes

Compute has `PreventDestroy` for "don't tear down infrastructure on CR delete." Storage needs more:

- **OSD drain before destroy** — `terraform destroy` on a Storage-node must wait for `ceph osd out <osd-id>` + rebalance completion. Doing it naively = data unavailability.
- **Cluster-quorum check** — destroying a MON node when only 3 MONs exist breaks the cluster. Reconciler must refuse.
- **Decommission-vs-replace distinction** — replacing a failed disk (keep OSD-id) is different from removing a node (forget OSD-id). CRD/spec needs to express which one we mean.

This is a **dedicated spec** worth writing before the destroy code.

### 5.2 Bootstrap-vs-join

Compute is stateless: every Compute-node is identical-in-role. Ceph is not:

- **First Storage-node in a Pool** must bootstrap the cluster (`ceph-mon-bootstrap`, generate keyrings, create CRUSH map).
- **Second-Nth Storage-node** joins an existing cluster (fetch bootstrap keys from a Secret, register OSDs, no-op on MON-creation).

**Decision points:** does the reconciler infer "I'm first" by checking `len(StoragePool.status.readyResources) == 0`? Or does the operator carry an explicit `bootstrapped: true/false` flag in `StoragePool.status`? Recommend latter — explicit > implicit for cluster lifecycle.

### 5.3 Ceph-cluster topology — what's a "Pool"?

A `StoragePool` in the operator's vocabulary maps to *what* in Ceph terms? Options:

- **One CephCluster per `StoragePool`** — simplest, one TF-module per pool. Recommend default.
- **One CephCluster across multiple `StoragePool`s** (cross-AZ, cross-fault-domain) — more flexible but adds a higher-order coordination resource the framework doesn't have.

Pick early; this constrains the TF-module shape.

### 5.4 Storage Resource Agent — what does Healthy mean?

Compute Resource Agent reports "k3s + Nova process up, heartbeat OK." Storage needs:

- **Per-daemon health** — MON quorum, OSD up/in/safe-to-stop, MGR active.
- **Cluster-level health** — Ceph HEALTH_OK / HEALTH_WARN / HEALTH_ERR.
- **Rebalance state** — degraded PG count, misplaced objects.

`Healthy` condition = bool. So the agent's job is to map this rich state → "yes/no." Recommend: `Healthy=true` iff `ceph health` is HEALTH_OK *for this node's role*. Everything else lives in `status.lastSignal.payload` for ops dashboards.

### 5.5 Cross-Reconciler contract (Storage ↔ Compute ↔ Block-Service)

How does `cloudstore-vm-bs-service` consume Storage? Two open questions:

- **Q-228** — Vendor Terraform inline or extract `cloudstore-vm-bs-service` to an external TF module? *(Blocks SOV-680 design start.)*
- **Q-229** — Can `cloudstore.yaml` inputs reference external K8s Secrets directly (for SOV-683 minint credentials)? *(Blocks SOV-674 design.)*

Both impact Storage's spec because they decide *where Storage credentials live* and *who hands them to the TF module*. Track these in [`open-questions.md`](../open-questions.md).

---

## 6. Spec-first / OpenSpec-shape — the six initial specs

If you adopt [OpenSpec](https://github.com/Fission-AI/OpenSpec) (or just spec-first markdown the way the Compute team did): write these six in order, **before** writing controller code.

| # | Spec | Why this order |
|---|---|---|
| **S1** | **`Storage` + `StoragePool` CRD shape** — mirror of Compute, plus Ceph-specific opaque `Vars` keys | Foundation everything else references |
| **S2** | **Ceph-cluster topology** — One-CephCluster-per-Pool vs Many — §5.3 | Constrains S3 + S4 + the TF module |
| **S3** | **Bootstrap-vs-join semantics** — §5.2 | Reconciler logic depends on this |
| **S4** | **Resource-Agent payload + `Healthy` mapping** — §5.4 | Drives operator-side `Healthy` evaluator + agent code |
| **S5** | **Destroy-safety + OSD drain** — §5.1 | Hardest correctness story; do it before the destroy path goes live |
| **S6** | **Cross-Reconciler contract** — closes Q-228 + Q-229 — §5.5 | Unblocks SOV-680 / SOV-674 |

For OpenSpec specifically, propose-change → review-delta → apply on each of these gives you a clean audit trail per design decision. For *just* spec-first-markdown, place these under `opcp-infra-operator/specs/021-026/` continuing the Compute team's numbering.

---

## 7. Open questions Storage spec work needs to resolve

From [`open-questions.md`](../open-questions.md):

| Q | Question | Why Storage-relevant |
|---|---|---|
| **Q-228** | Vendor TF inline or extract external module for `cloudstore-vm-bs-service`? | Determines TF-module ownership boundary — does Storage TF live with Storage or with the Block-Service? |
| **Q-229** | Can `cloudstore.yaml` reference external K8s Secrets directly? | Determines how Storage credentials reach the TF module |
| **Q-234** | When does the missing provisioner TF module land? | E2E-test gates for SOV-256 depend on this |
| *(new)* | OSD drain mechanism — operator-managed or external runbook for V1? | Spec-S5 forcing function |
| *(new)* | Test-hardware E2E timing — biggest project risk per STATE.md | Slot-coordination with Boris Behrens + Camille (HPE Gen11) |

---

## 8. Reading list — first 4 hours

In strict order:

1. [`kb/deep-dives/opcp-infra-operator/summary.md`](../../../../opcp-core/architecture/conceptions/opcp-infra-operator/summary.md) — the whole Operator in one read (~30 min)
2. [`kb/deep-dives/compute-operator/summary.md`](../../../../opcp-core/architecture/conceptions/compute-operator/summary.md) — Compute lifecycle + recipes (~30 min)
3. [`opcp-core-operator.md`](opcp-core-operator.md) (this repo, project-side) — how Operator + cs-cp + cbs-cp glue together (~20 min)
4. [`code-survey-2026-05-11.md`](code-survey-2026-05-11.md) — where Compute-team's docs diverged from code-truth — same fall-traps for Storage (~20 min)
5. `opcp-infra-operator` repo — clone, then read `docs/architecture.md` + `docs/api-reference.md` + `docs/external-integration.md` + `docs/heartbeat.md` (~1 h)
6. `opcp-infra-operator/specs/001-020/` — skim the spec list, deep-read the 5 most-relevant to data-bearing nodes (provisioner architecture · status-update API · resource agent · heartbeat detection · break-glass) (~1 h)
7. [OPCP Infra API Swagger](https://rtstatic.ovhcloud.tools/gor/publiccloud/opcp-infra-api/latest/opcp-infra-api-reference.html) — external API surface, scan for where `Storage` will slot in (~20 min)

---

## 9. References

- **Operator deep-dive (component-level):** [`kb/deep-dives/opcp-infra-operator/summary.md`](../../../../opcp-core/architecture/conceptions/opcp-infra-operator/summary.md)
- **Compute Controller deep-dive (domain-level):** [`kb/deep-dives/compute-operator/summary.md`](../../../../opcp-core/architecture/conceptions/compute-operator/summary.md)
- **Operator design — project-side:** [`opcp-core-operator.md`](opcp-core-operator.md)
- **Code-vs-docs survey 2026-05-11:** [`code-survey-2026-05-11.md`](code-survey-2026-05-11.md)
- **External REST contract:** [OPCP Infra API Swagger](https://rtstatic.ovhcloud.tools/gor/publiccloud/opcp-infra-api/latest/opcp-infra-api-reference.html)
- **OpenSpec tooling:** [github.com/Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) — spec-first markdown workflow for LLM-assisted dev
- **Storage tracking ticket:** [SOV-256](SOV-256)
- **Cross-reconciler open questions:** [`../../../../products/cloudstore/misc/compute-block-on-cloud-store/open-questions.md`](../open-questions.md)
