---
id: compute-block-on-cloud-store/architecture-cb-service-package-survey-2026-06-25
type: deep-dive
diataxis: explanation
title: "CB Service Package — code survey vs. Alex's walkthrough (2026-06-25)"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# CB Service Package — code survey vs. Alex's walkthrough (2026-06-25)

> **Repo:** [`cloudstore-service-compute-and-block`](https://stash.ovh.net/projects/GOR/repos/cloudstore-service-compute-and-block/browse) (GOR) · cloned 2026-06-25 (`main` @ `68cd7ed`, `0.1.0-alpha.7`).
> **Purpose:** verify the repository against what Alexander Graf demonstrated in the [Package Walk-Through session](../meetings/2026-06-25-cb-package-walkthrough.md). **Verdict: the repo matches the call closely — and the M2 branch is more detailed than the demo.**
> **Distillation recipe:** repo-clone survey (see [root CLAUDE.md](../../../../../CLAUDE.md)).

---

## 1. What it is

The **CloudStore Service Package** for **Compute & Block** — the `cloudstore-vm-bs-service` equivalent the CB project ships. Built from the CloudStore service-packager template (copier; `.copier-answers.yml` present). Two layers exist as **two branches**, exactly as Alex described ("two service versions… alpha 7 is the M1 thing, everything dev is M2"):

| Branch | Version | = Alex's term | Shape |
|---|---|---|---|
| **`main`** | `0.1.0-alpha.7` | **"Alpha 7" / M1** | **Terraform-only.** `tofu apply` calls `opcp-infra-api` directly via the `mastercard/restapi` provider. |
| **`feat/m2-controlplane-sketch`** | (dev) | **"M2" / dev** | **Container/control-plane.** TF deploys a long-lived Go controller pod that talks to the operator API and serves a status **iframe**. **Explicitly a sketch.** |

## 2. Top-level structure (`main`)

```
cloudstore.yaml                 ← service spec (v1alpha2, name "Compute-and-block")
terraform/controlplane/         ← main.tf + modules/opcp_pool/  (provisions compute+storage pools via opcp-infra-api)
terraform/dataplane/            ← per-Account (App) layer
docker/Dockerfile               ← packager image
cmd/tf-updater/ + bin/          ← Go TF-version updater tooling
docs/                           ← service-packager how-tos/reference (tutorials, ref_cloudstore_yaml.md, …)
Makefile + .makefiles/          ← packager.mk, harbor_api.mk, terraform.mk, docker.mk … (release → Harbor)
.cds/workflows/                 ← CDS CI
```

## 3. Claim-by-claim verification (call ↔ code)

| Alex said (transcript) | Code confirms | Where |
|---|---|---|
| "Alpha 7 is the M1 thing, just doing Terraform" | `main` is `0.1.0-alpha.7`; `terraform/controlplane` calls the API via `mastercard/restapi`. | `terraform/controlplane/main.tf`, CHANGELOG |
| "FS7 creates a pool and assigns the nodes to the pool using REST API of infra operator" | `modules/opcp_pool` + commits *"provision compute nodes via opcp-infra-api"* / *"provision storage nodes, extract opcp_pool module"*. | `terraform/controlplane/modules/opcp_pool/`, git log |
| "two nodes for compute … the other two for storage" | `control.target.baremetal.pools`: `compute` (`compute_node_uuids`) + `storage` (`storage_node_uuids`). | `cloudstore.yaml` |
| "min 3 nodes (compute) and 5 hosts (block)" is the real prereq (demo used 2+2 = test) | `control.prerequisites.description: "A minimum of 3 nodes (compute) and 5 hosts (block)"`. | `cloudstore.yaml` |
| "you need to configure this token and you get it by asking Ibrahim … or a Kubernetes secret … I don't like that I need to specify this, it should be automatic" | `opcp_api_url` / `opcp_api_key` inputs are **`{}`** (not `provided: true`) → must be supplied by the deployer; all the OIDC/OpenStack/DNS inputs **are** `provided: true`. The asymmetry is the friction. | `cloudstore.yaml` `control.inputs` |
| "when the Terraform was done, it will output something … rendered" | `control.outputs`: `debug`, `identity`, `runtime`, `compute_pool`, `compute_nodes` (yaml), `storage_pool`, `storage_nodes` (yaml). | `cloudstore.yaml` |
| "that design relies on Terraform being always successful. If not, it's a black box … no feedback channel" | M2 design doc says it verbatim: *"API failures bubble up as plan/apply errors with no UI-visible diagnostics beyond the raw apply log."* | `docs/m2-design.md` (M2 branch) |
| "the dev version … use that container and talk to the API and I told Claude to write everything coming back … show in iframe" | M2 branch adds `cmd/compute-and-block-controlplane/` with `apiclient/` (API client), `reconciler/`, **`statusserver/` + `templates/status.html`** (the iframe), `statuswriter/` (writes return-codes/errors to a ConfigMap). | M2 branch `cmd/…` |
| "I will deploy version 21 today or tomorrow … but Kubernetes does not find the images of that service … image pull fails, so it doesn't start up" | M2 design: container image build + Harbor push is **Phase A.3 (TBD)**; `go.mod` "not updated", code = "structural placeholders with TODO". So the image isn't in Harbor yet → `ImagePullBackOff`. **Consistent.** | `docs/m2-design.md` §"Phase A.3" |
| "Claude … noted everything here so it knows what we did" (CloudMD) | `CLAUDE.md` (538 lines) added on the M2 branch. | M2 branch `CLAUDE.md` |
| "racy … you can use the same nodes for compute and storage … already filed a bug" | M2 design ports this as **B.3 cross-pool UUID uniqueness check** (`setintersection(compute, storage)` → fail). On `main` it's only a `terraform_data.pool_uniqueness` precondition. | `docs/m2-design.md` §B.3 |
| "release … pushes it to this harbor registry … to access you need GoPass … synced to all OPCP locations … local rewrite to fetch from that mirror" | `.makefiles/harbor_api.mk` + `packager.mk`; air-gap mirror rewrite is the packager design. Harbor: `9501yd0v.eu-west-par.container-registry.ovh.net`. | `.makefiles/`, [env-access doc](../../../../opcp-core/environments/env-access-onboarding.md) |

## 4. The M2 control-plane design (more than the demo showed)

`docs/m2-design.md` (M2 branch, 207 lines) is a full architecture sketch — **read it before any M2 work**. Headlines:

- **Shift:** M1 runs business logic *inside* `tofu apply`; M2 makes TF a thin layer that only mutates K8s objects (Deployment, Service, ConfigMap, RBAC, HTTPRoute), and a **long-lived Go reconcile loop** does the operator-API calls with retries + structured logging + a status surface.
- **Status surface (3 formats, all "always on"):** status ConfigMap (`yaml`) · `safe-to-delete` URL (`url`) · **status iframe** (`html`, auto-refresh 10 s) embedded in the CloudStore "Results" tab.
- **Deletion safety (defense in depth):** every created Compute/Storage gets `preventDestroy=true`; a `/readyz/safe-to-delete` endpoint (stub returns `{"safe":true}`) for a *planned* CloudStore "ask the service before deleting" gate; a pre-stop teardown Job that refuses to drain locked resources.
- **Roadmap Phases A→E:** A = create-path parity with M1 · B = full lifecycle (update/delete) parity · C = useful status iframe · D = informers/workqueue (reaction in seconds) · E = TLS/metrics/tests/leader-election + real safe-to-delete predicate.
- **Status:** explicitly **"a sketch — nothing wired against a real operator, Go code is TODO placeholders, go.mod not updated."** The architecture is the deliverable, not a running binary.

## 5. How it maps to our use case + open questions raised

| Finding | Lands in |
|---|---|
| The **no-feedback-channel black box** is the headline product risk for M1/Beta — operators can't see why a deploy hangs. M2's iframe is the answer but is unbuilt (image not in Harbor). | Q-246 · [meeting note](../meetings/2026-06-25-cb-package-walkthrough.md) |
| `opcp_api_key` is a manual input, not `provided:true` — the "systems are not connected." Should be auto-injected like the OIDC/OpenStack creds. | Q-247 |
| FluxCD / advanced-config defaults must be shipped as defaults (the "ticket Zoom opened yesterday"). | Q-248 (ties to SOV-1307) |
| **Platform-provided iframe hosting** (gateway/hostname/OIDC for the status surface) — CloudStore should own the pattern; today every service author supplies `status_gateway_*`. | Q-249 (parked in m2-design.md) |
| **CloudStore "safe-to-delete" contract** — exact predicate (Nova instances on our hypervisors / Cinder volumes on our OSDs?) is undefined; M2 stubs `{"safe":true}`. | Q-250 (parked in m2-design.md) |

## 6. Cross-references

- Walkthrough session notes → [`meetings/2026-06-25-cb-package-walkthrough.md`](../meetings/2026-06-25-cb-package-walkthrough.md)
- Environment access (how to reach the CloudStore UI + K3S + Harbor + OPCP API) → [`kb/runbooks/env-access-onboarding.md`](../../../../opcp-core/environments/env-access-onboarding.md)
- The CB service-package skeleton design → [`cloudstore-vm-bs-service-skeleton.md`](cloudstore-vm-bs-service-skeleton.md)
- Upstream M2 design doc → `cloudstore-service-compute-and-block` branch `feat/m2-controlplane-sketch` → `docs/m2-design.md`
- The OS package equivalent (same template, parallel state) → [`object-storage-package-survey-2026-06-10.md`](../../object-storage-on-cloud-store/architecture/object-storage-package-survey-2026-06-10.md)
- Repo inventory → [`EXTERNAL-REPOS.md`](../../../../../_workspace/EXTERNAL-REPOS.md)
