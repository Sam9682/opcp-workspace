---
id: object-storage-on-cloud-store/architecture-object-storage-package-survey-2026-06-10
type: deep-dive
diataxis: explanation
title: "`cloudstore-service-object-storage` — package survey (2026-06-10, re-surveyed 2026-07-29)"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# `cloudstore-service-object-storage` — package survey (2026-06-10)

> ⚠️ **The filename/date is the ORIGINAL survey. This is a living doc, refreshed by dated delta blocks at the
> top — newest first. Last re-survey: 2026-07-29 (`0.2.0-alpha.18`, 287 commits).** The numbered sections below
> are the **2026-06-10 baseline** and are substantially superseded; read the deltas first.

> **Repo-clone survey** of [`cloudstore-service-object-storage`](https://stash.ovh.net/projects/CLOUDSTORE/repos/cloudstore-service-object-storage/browse) (Stash, `ssh://git@stash.ovh.net:7999/cloudstore/cloudstore-service-object-storage.git`), release **v0.1.0-alpha.4** (2026-06-02). Purpose: establish **what the alpha already implements** so the OS project scopes against reality instead of re-planning what's built. Companion to the [2026-06-09 architecture brainstorm](../meetings/2026-06-09-os-architecture-rook-vs-cephadm.md) decisions.
>
> **TL;DR — it's a real, well-documented skeleton, not a product.** The CloudStore packaging contract (manifest + TF plumbing + OCI build chain) is fully in place; **zero Ceph / RGW / Keystone resources exist yet** — both Terraform planes are `TODO` stubs. Nothing contradicts our decisions; the repo simply stops where our decisions begin. One repo doc ([`docs/provisioning-approach.md`](#the-one-repo-authored-design-doc-docsprovisioning-approachmd)) is **stale vs the 2026-06-09 CephADM decision** and should be updated by the repo owners.

> **🔄🔄 2026-07-29 re-survey (`origin/main` @ `75497e8`, fetched 2026-07-29). The package is no longer a skeleton — treat everything below as historical baseline.**
>
> | Metric | 2026-06-10 | 2026-06-23 | **2026-07-29** |
> |---|---|---|---|
> | Release | `0.1.0-alpha.4` | `0.1.0-alpha.19` | **`0.2.0-alpha.18`** *(minor bump)* |
> | Commits | 14 | ~56 | **287** (239 since 06-23) |
> | Main committer | Zafar (8) + Boris (4) | Zafar | **Jan Stuhlmann (192 of the last 239)** + Zafar (47) |
> | Latest commit | — | — | **2026-07-28** |
> | Controlplane modules | none (stub) | k3s + CNPG + Keystone | **`ceph` · `k3s` · `node`** |
> | Dataplane modules | none (stub) | `keystone_federation` | **`keystone-federation` · `panel`** |
>
> **What's now real (was TODO/absent at the 06-10 baseline):**
> - **`modules/ceph` exists and is substantive** — `nodes.tf` + a vendored `ansible-library-copy/roles/ceph/` carrying the full cephadm role (mon/osd/mgr/rgw, `crush.yaml`, `rgw-pools.yaml`, `rgw.yaml` with the `ceph_object_storage` gate throughout). The SOV-687 irobox brick that was "READY (unmerged)" on 06-23 has landed here as a vendored copy.
> - **Ceph node roles are now split + sized:** `flavor_oob` · **`flavor_mon_nodes`** (converged mon/mgr/osd/rgw) · **`flavor_osd_nodes`** (dedicated osd-only), with `mon_node_count` / `osd_node_count` (commit `b4c3ffd`). ⚠️ **This supersedes the "single `flavor_name`" premise** — `flavor_name` still exists but now describes only the **k3s node**, not the Ceph hosts.
> - **`cloudstore.yaml docker_images` now includes Ceph:** `quay.io/ceph/ceph:v19.2.3` (also the default of the new `ceph_container_image` TF variable), plus `quay.io/prometheus/node-exporter:v1.7.0`, the middleware image, and the two panel images. ⚠️ **The 06-10/06-23 finding "no Ceph images → M4 air-gap gap" is CLOSED.**
> - **TLS / cert story rewritten:** LetsEncrypt dropped (doesn't work air-gapped) → the package accepts `ca_cert` + `ca_key` from outside and self-signs via the TF `tls` module; SSL now on Keystone, credentials-middleware, and RGW.
> - **Keystone exposure churn** — commits move it public → cluster-only+private → *public again* because the tf-runner needs to reach it, guarded only by `allowed_admin_cidr` which **cannot currently be tightened because the tf-runner IP is unknown**. Live security seam, relevant to `SOV-1530`.
>
> **⚠️ The OSD-spec default got worse, not better.** `ceph_osd_spec_file` now defaults to **`../templates/osd-test-single-spec.yml.j2`** — the *loose take-every-disk* spec — with the block-hybrid default commented out. At the 2026-07-16 OSQ-31 read the default was the block-hybrid spec, so **the shipped default is now the permissive one** — on real hardware it gives no device-class control (the `replicated_ssd` rule matches zero OSDs → RGW index/meta pools strand), offloads no `block.db`, and leaves data unencrypted. ⚠️ **Bounded by the empty-disk precondition:** cephadm only ever takes *empty* disks, so it cannot claim a disk already carrying an OS or data — [gap G3](ceph-rgw-osd-spec.md) is rated 🔴 on the stronger "eats the boot device" reading and **likely warrants re-rating** at the Boris + Jan review. Note also the 4 OSD templates are split across **two** directories: 3 under `modules/ceph/ansible-library-copy/roles/ceph/templates/`, and `osd-test-single-spec.yml.j2` alone under `modules/ceph/templates/` (hence the `../templates/` prefix in the default). → [`SOV-2009`](../jira/SOV-2009-role-flavor-osd-specs.md)
>
> **📦 Container base images — the full shipped set (answers OSQ-34 / [`SOV-2015`](SOV-2015) discovery step 1).** Verified 2026-07-29 from the package `cloudstore.yaml` plus the three build repos:
>
> | Component | Image (as shipped) | Base image | Registry class | Hardening state |
> |---|---|---|---|---|
> | **ceph** | `quay.io/ceph/ceph:v19.2.3` | upstream Ceph community build | public upstream (quay.io) | ❌ not hardened |
> | **k3s system** (8 images) | `docker.io/rancher/mirrored-{coredns,traefik,pause,busybox,metrics-server,local-path-provisioner,klipper-lb,klipper-helm}` | Rancher upstream mirrors | Docker Hub | ❌ upstream → **inherit `SOV-1798`/`SOV-1434`** |
> | **credential-middleware** | `…artifactory.ovhcloud.tools/object-storage-credentials-middleware:0.1.0-8.sha.gff215f6` | `node:22-alpine` via **`docker-hub-remote.artifactory.ovhcloud.tools`** | 🟡 OVH Artifactory Docker-Hub **remote proxy** | 🟡 not a hardened base, but **OVH-controlled path**; runs `USER node` ✅ + `dumb-init` ✅ — **best positioned of the three** |
> | **panel** (`regional-manager`) | `docker.45.12.50.116.nip.io/regional-manager:1ddcbd41` | `nginx:1.28.0-alpine3.21-with-openssl` via **`git.gridscale.it:5005`** | 🔴 **third-party Gridscale GitLab registry**, deployed from an **IP-based `nip.io` dev registry** | 🔴 not hardened · **no `USER` directive → runs as root** |
> | **panel auth helper** (`regional-manager-auth`) | `docker.45.12.50.116.nip.io/regional-manager-auth:52316b10` | `node:22-alpine-git-jq-curl` via **`git.gridscale.it:5005`** | 🔴 same third-party registry | 🔴 `USER node` ✅ but **git + jq + curl baked into the runtime image** — the opposite of hardening |
> | keystone | `public/keystone:2025.2.2` *(not in `docker_images`)* | irobox custom build (uwsgi) | central Harbor `public/` | ⚪ unknown — irobox-owned |
> | dataplane OIDC proxy | `public/apache-oidc-proxy:cds6426` *(not in `docker_images`)* | — | central Harbor `public/` | ⚪ unknown |
> | apache exporter | `public/apache-exporter:0.11.0` *(not in `docker_images`)* | — | central Harbor `public/` | ⚪ unknown |
> | node-exporter | `quay.io/prometheus/node-exporter:v1.7.0` | upstream | quay.io | ❌ not hardened |
> | *packager toolchain* | `docker/Dockerfile` | `debian:stable-slim` (Docker Hub, direct) | — | build-time only, **not shipped** |
>
> **Reading:** the two **panel images are the sharpest finding** — a third-party (Gridscale) GitLab registry as the base-image source, and an **IP-literal `nip.io` dev registry** as the deploy source. That is a supply-chain + non-production-registry problem *larger* than base-image hardening, and it must be resolved before SNC regardless of which hardened lineage is chosen. All three OS-built components are **Alpine**, so a distroless / Chainguard migration is technically plausible. Build repos: `objectstorage-middleware` · `ovh-opcp-frontend/deploy/regional-manager{,-auth}` — **panel + panel-auth are deployed by this package (dataplane `panel` module, separate namespaces) but built in the shared `ovh-opcp-frontend` repo**, so the ownership seam in OSQ-34 is real but narrower than "may be CloudStore-wide".
>
> ---
>
> **🔄 2026-06-23 delta (re-survey of the live repos).** The package has moved fast — and the irobox Ceph brick now exists:
> - **Package: `v0.1.0-alpha.4` → `v0.1.0-alpha.19`** (14 → ~56 commits). **Controlplane TF is no longer a bare stub** — it now stands up **k3s + CNPG + a dedicated Keystone** (active `feature<keystone>` work); **dataplane** has a **`keystone_federation` module** (Apache OIDC proxy + network policies + HTTP routes per account). **`cloudstore.yaml` `docker_images` is now populated** (~15 images: Keystone, CNPG, external-dns, k3s system) — **but still no Ceph images** (M4 air-gap gap) and **still no `ceph_*` module** (the Ceph cluster itself is the next phase).
> - **irobox Ceph+RGW reference is READY (unmerged):** `ansible/roles/ceph` on **`dev/shohn/SOV-687`** is complete — cephadm mon/osd/mgr/rgw, **full RGW↔Keystone wiring with the L2-admin / L3-user split (all 6 `rgw_keystone_*` params + api_version)**, **OKMS** via KMIP *or* Vault/OpenBao, **SSE-S3**, and `ceph_block_storage` / `ceph_object_storage` modes. **1 commit ahead of `release/3.1.x`, NOT yet merged** → wire into the package's future `ceph_cluster` module.
> - **Still stale:** the repo's own `docs/provisioning-approach.md` still says Ceph-deploy is **"OPEN"** (pre-dates the 2026-06-09 CephADM decision) — owner action for Zafar/Boris, outside our repo.
> - Treat the sections below as the 2026-06-10 baseline.

---

## 1 · What it is

| Fact | Value |
|---|---|
| Created | **2026-05-26** by **Zafar Akhtar**, from the copier template `cloudstore-service-template` **v0.6.2** (source: `https://github.com/OVH-Goldorack/cloudstore-service-template.git` — GitHub, *not* Stash) |
| Committers | **Zafar Akhtar** (8 commits, 05-26 → 06-02) + **Boris Behrens** (4 commits, 06-02) — exactly our Storage-Squad bring-up pair |
| History | 14 commits total. Substantive: template init → "init openstack structure" → README → `provisioning-approach.md` (05-27). The **alpha.1→alpha.4 releases (05-28/06-02) carry no feature content** — they are release-machinery / packaging-workflow tests (CHANGELOG entries are empty; one commit is literally `test`) |
| Shape | `cloudstore.yaml` manifest · `terraform/{controlplane,dataplane}/` (OpenTofu, stubs) · `cmd/tf-updater/` Go tool + prebuilt `bin/tf-updater` · `docker/Dockerfile` (packager toolchain) · `Makefile` + `.makefiles/` (OCI build/push/release) · `docs/` (template diátaxis docs + 1 repo-authored design doc) |
| CI | One CDS workflow: `terraform-docs` generation on PR. No test/deploy pipeline |

**Read on the release number:** `0.1.0-alpha.4` sounds like four iterations of product; in reality it is **one skeleton + four packaging-pipeline dry-runs**. The alphas validated the *path to the registry* (`make add_prerelease_version` → `make generate_package` → OCI push to the central CloudStore registry), which is genuinely useful — the delivery pipeline works before any product code exists.

## 2 · `cloudstore.yaml` distill

Manifest version **`v1alpha2`**, name **"Object-storage"**, *"S3-compatible Object Storage, backed by Ceph RADOS Gateway (RGW)"*. `docker_images: []` (nothing mirrored yet). The load-bearing parts:

```yaml
control:
  prerequisites:
    description: "Bare-metal nodes compatible with Ceph are required"
  target:
    baremetal:
      pools:
        - name: ceph-nodes
          tf_variable_name: node_uuids        # JSON array of Ironic node UUIDs
  inputs:        # all provided: true → injected by the platform
    openstack_auth_url / openstack_application_credential_id / ..._secret
    internal_dns_server / dns_tsig_key / dns_tsig_algorithm / dns_tsig_secret
  outputs:
    service_domain: {}
  permissions: {}                             # ← empty (no Keycloak groups/roles declared)

data:
  prerequisites:
    description: "An existing Object Storage controlplane deployment"
  inputs: {}                                  # account_name user-supplied; service_domain auto-wired
  outputs:
    s3_endpoint_url:
      format: url                             # rendered as a link in the CloudStore UI
  permissions: {}
```

Notable:

- **`target.baremetal.pools[ceph-nodes]`** = the manifest-level embodiment of OSQ-01 — the IT-Admin hands the package a pool of bare-metal node UUIDs.
- **OpenStack application credentials are platform-`provided`** — the package authenticates to OpenStack directly (the VCF way), no Infra-API hop.
- **`permissions: {}` in both planes.** The v1alpha2 schema supports Keycloak `groups`/`roles` per plane (VCF declares `vcf-admins`/`vcf-federation`); OS declares **nothing** yet — to reconcile with the [ADR SOV-583 Option-4](../../../architecture/adr/adr-sov-583-authz-model.md) `s3.{role}` client-role model.
- **No resilience/min-node schema anywhere** in the manifest or its v1alpha2 reference doc — the OSQ-22 OKMS gate has **no place to land** in the current manifest format (see §6).

## 3 · What the alpha implements

| Component | State | Evidence |
|---|---|---|
| CloudStore manifest (`cloudstore.yaml`) | ✅ **Implemented** (minimal) | v1alpha2, BM pool, provided inputs, `s3_endpoint_url` output |
| OCI packaging + release chain | ✅ **Implemented** (template) | `make generate_package` / `add_prerelease_version`; 4 alphas pushed to the central registry; `docker/Dockerfile` packager image (tofu 1.7.7, helm, flux, skopeo, sops…) |
| `tf-updater` Go tool | ✅ **Implemented** (template tooling, not OS-specific) | `cmd/tf-updater/main.go`: rewrites remote TF module sources + helm charts to local paths for **air-gapped / vendored** packaging |
| Controlplane TF plumbing | 🟡 **Stub** | Providers `openstack` (3.3.2, app-credential auth — wired!), `dns` (TSIG), `local`, `tls`. `main.tf` = locals only: `hosts = jsondecode(node_uuids)`, `service_domain`, a ready-made `openstack_env` export block for CLI-driven modules. **Zero resources.** |
| Dataplane TF plumbing | 🟡 **Stub** | Provider `local` only. `account_slug` local + passthrough output `s3_endpoint_url = "https://${service_domain}"`. **Zero resources.** |
| Ceph node provisioning (Glance image, Ironic/Nova launch) | ❌ **Absent** | `TODO` comments name future modules `ceph_image`, `ceph_hosts` (`count = length(local.hosts)`) |
| Ceph + RGW cluster bring-up | ❌ **Absent** | `TODO` module `ceph_cluster`; mechanism explicitly undecided in `docs/provisioning-approach.md` |
| Dedicated Keystone (+ Keycloak federation) | ❌ **Absent** | `TODO` module `keystone`; commented-out outputs `keystone_endpoint_url` / `keystone_admin_token` |
| Per-account activation (Keystone project, RGW user/quota) | ❌ **Absent** | Dataplane `TODO` comments only |
| Credential middleware (SNC SOV-514 reuse) | ❌ **Absent** (documented in README) | README auth-chain section; no code |
| Neutron networking setup | ❌ **Absent** | Not even a TODO module — only the README sentence |
| Service-CP K3S | ❌ **Absent — never mentioned** | `grep -ri k3s` = **0 hits** |
| OKMS / encryption | ❌ **Absent — never mentioned** | `grep -ri okms` = **0 hits** |
| Rook | ❌ Absent (good) | `grep -ri rook` = **0 hits** |
| SNC reuse bricks (`host-storage`, `OpenStack-instance-V2`, Ansible roles) | ❌ **Not referenced** | `provisioning-approach.md` even asks *"Is there an existing Ceph/cephadm Ansible role to reuse, or is it net-new?"* — the repo authors didn't know about Stephan's bricks when writing it |

### The one repo-authored design doc: `docs/provisioning-approach.md`

Written by Zafar 2026-05-27, **status "OPEN — decision needed"**. Frames the BM→cluster problem as **operator-reuse (CB-style) vs direct OpenStack (VCF-style) vs hybrid**, and deliberately keeps the skeleton provisioning-agnostic. Two **verified technical claims worth keeping**:

1. *"Even if we adopt the operator, the Ceph clustering step is still ours to build"* — the operator's unit of work is `1 Compute = 1 Job = 1 node`, **no cross-node coordination**; Ceph needs ordered mon-quorum → OSD → RGW bring-up.
2. *"The operator's API does not return node IPs to clients (verified — the `opcp-infra-api` Compute DTO omits `status.outputs`). **Peer addressing must be pre-assigned, not discovered.**"* — load-bearing for our network design regardless of path.

It concludes the problem is *"structurally like VCF, not like Compute & Block"* — i.e. it independently re-derives Marc's 2026-05-27 VCF-way call. Small internal inconsistency: the doc says the provisioning provider (`openstack` or `restapi`) "is added by whoever implements", but `providers.tf` **already wires the `openstack` provider with app-credential auth** — the skeleton de-facto leans direct-OpenStack.

## 4 · Alignment vs our decided state

**No contradictions.** The repo is *behind* our decisions (last commit 2026-06-02; the big decisions landed 2026-06-09), never *against* them.

| Decision / OSQ | Verdict | Detail |
|---|---|---|
| **OSQ-01** — package does everything (BM pool → full stack via OpenStack API) | ✅ **Matches (declared, not built)** | Manifest BM pool + provided OpenStack creds + README states it verbatim ("From a pool of empty bare-metal nodes, the package provisions the whole stack through the OpenStack API"). Implementation = TODO stubs. |
| **OSQ-04** — Nova bare-metal flavor → Ironic | ✅ **Matches (declared)** | `variable "flavor_name"`: *"Nova flavor name for the Ceph nodes (bare-metal flavor created in OpenStack)"*; README: "Nova bare-metal flavor → Ironic". No launch code yet. |
| **CephADM + Ansible, NO Rook (FINAL 2026-06-09)** | 🟠 **Untouched — repo doc STALE** | Zero Rook anywhere (consistent). But `provisioning-approach.md` still says the Ceph-deploy mechanism is **"OPEN — not yet decided"** with cephadm as one option among three. Pre-dates the decision (05-27 vs 06-09). **Repo doc needs updating** — flag to Zafar/Boris, else the repo re-litigates a closed question. |
| **VCF-way** ([ADR 2026-05-27](../decisions.md)) — direct OpenStack, no Infra-API | ✅ **Matches (de-facto)** | `openstack` provider already wired with platform-injected app credentials; the doc's analysis lands on "structurally like VCF". The operator-vs-direct framing as "open" is the same staleness as above (Marc decided 2026-05-27). |
| **OSQ-21** — own-K3S service-CP (planning lean, M3 session 2026-06-10) | ⚪ **Untouched** | K3S never mentioned. The TODO puts the `keystone` module inside the **controlplane TF** — compatible with either own-K3S or shared-Enabler outcome, but **the repo has no module slot for K3S bring-up** (the Boris+Zafar work item lives outside this repo today, in the irobox/SNC bricks). |
| **OSQ-02** — auth: dedicated Keystone, 1 KC/1 KS/1 Apache per realm, SOV-583 model | ✅ **Matches (declared)** | README auth chain: `Ceph → RGW → Keystone (dedicated, in the Package) → Keycloak (CloudStore L2)`; credential middleware "reused from SNC"; "SecNumCloud admin/user identity separation (M3) is realised within this Keystone-federation model". Zero implementation (dataplane provider = `local` only). `permissions: {}` not yet reconciled with SOV-583 client-roles. |
| **OSQ-16** — RGW co-located on Ceph nodes | ✅ **Matches (declared)** | README: "a dedicated Ceph + RGW cluster (RGW co-located on the Ceph nodes)". |
| **OSQ-22** — OKMS ≥3-node gate enforced in `cloudstore.yaml` | 🔴 **Untouched + schema gap** | OKMS never mentioned, *and* the **v1alpha2 manifest schema has no resilience/min-nodes construct** to express the gate. OSQ-22 likely needs a **platform-side manifest extension** (CloudStore team), not just an OS-repo edit. |
| **OSQ-10** — reuse SNC (middleware, bricks) | 🟡 **Partial** | Credential-middleware reuse is in the README; the **CephADM/`host-storage` TF + Ansible bricks are unknown to the repo** (it asks whether a reusable cephadm role exists). Wire-up = ours to do. |
| **OSQ-03** — BL owns activation/quota/usage | ✅ **Matches (declared)** | README: "Account activation, quotas, and usage/billing are expected to live in the **shared Business Logic** — not bespoke to this package." |

## 5 · Gaps — what the OS project still has to build

Everything product-shaped. In repo terms (the README's own "Next steps" list matches our plan almost 1:1):

1. **Controlplane modules** (`terraform/controlplane/modules/`): `ceph_image` (Glance golden image) · `ceph_hosts` (Ironic/Nova-BM launch, Neutron) · `ceph_cluster` (**CephADM + Ansible bring-up** — wire in the SNC `host-storage` / Ansible bricks, ⚠️ Stephan-Hohn bus-factor) · `keystone` (dedicated Keystone + Apache-OIDC federation to Keycloak L2, SOV-916).
2. **Service-CP hosting** — own-K3S bring-up (Boris + Zafar, pending OSQ-21 outcome): currently lives **nowhere** in the package; decide whether it becomes a controlplane module or stays a separate concern.
3. **Dataplane resources**: Keystone project + admin user per account · RGW user/quotas (`radosgw-admin` / dashboard API) · credential-middleware bootstrap (SOV-514 reuse) · optional per-account vhost DNS.
4. **`cloudstore.yaml` completion**: `permissions` groups/roles (reconcile with SOV-583), `docker_images` (Ceph container images must be mirrored for air-gapped cephadm — currently `[]`), eventual OKMS resilience gate (blocked on schema, §4/OSQ-22).
5. **TF → Ansible chaining** (OSQ-23) — nothing in the repo automates an Ansible handoff today.
6. **Doc refresh**: update `provisioning-approach.md` from "OPEN" to the decided state (CephADM + Ansible, direct OpenStack).

**Net effect for planning:** the alpha removes the *packaging/delivery* workstream from our scope (manifest contract, OCI build, registry sync, air-gapped vendoring tooling — all working), and confirms the team building it = the team in our ownership table. It removes **nothing** from the Ceph/Keystone/middleware engineering scope.

## 6 · New questions raised (list only — not yet filed as OSQs)

1. Does the **v1alpha2 `cloudstore.yaml` schema** support minimum-resilience/min-node declarations at all? OSQ-22 may require a **platform-side manifest-schema extension** — owner would be the CloudStore platform team, not the OS repo.
2. Who updates the **stale `docs/provisioning-approach.md`** (still "OPEN") to the decided CephADM-no-Rook + direct-OpenStack state? (Natural: Zafar/Boris, with the 2026-06-09 outcome.)
3. How do v1alpha2 **`permissions` realm groups/roles** map onto the **SOV-583 Option-4** per-(service, region) Keycloak clients + `s3.{role}` client-roles? (The manifest model may predate the ADR.)
4. **Where does the service-CP K3S provisioning live** — a controlplane module inside this package, or outside it? (OSQ-21 fallout; repo has no slot for it.)
5. `docker_images: []` — which **Ceph container images** must be declared/mirrored so cephadm works **air-gapped**? (cephadm pulls images at bootstrap; the registry-sync machinery exists, the list doesn't.)
6. The template lives at **GitHub `OVH-Goldorack/cloudstore-service-template` v0.6.2** — [`EXTERNAL-REPOS.md`](../../../../../_workspace/EXTERNAL-REPOS.md) records "no `cloudstore-service-template` on Stash"; worth recording the GitHub location + the copier-update flow (`make copier_update`) as the way template fixes reach this repo.
7. Repo-verified constraint to carry into network design: **the opcp-infra-api Compute DTO omits node IPs — peer addressing must be pre-assigned, not discovered** (moot on the direct-OpenStack path, but binding if the hybrid option ever resurfaces).

## 7 · Cross-links

- Project: [OS project CLAUDE.md](../CLAUDE.md) (§ "The Service-package repo EXISTS") · [decisions.md](../decisions.md) (2026-06-09 CephADM / own-K3S / OKMS-gate entries) · [open-questions.md](../open-questions.md) (OSQ-01/02/04/10/15/16/21/22/23)
- Meetings: [2026-06-09 architecture brainstorm](../meetings/2026-06-09-os-architecture-rook-vs-cephadm.md) · [2026-06-02 controllers & secrets alignment](../meetings/2026-06-02-controllers-secrets-alignment.md)
- Architecture siblings: [oss-cp components](oss-cp-components.md) · [objectstorage middleware (SOV-514)](objectstorage-middleware.md) · [architecture index](README.md)
- Reference: [`EXTERNAL-REPOS.md`](../../../../../_workspace/EXTERNAL-REPOS.md) (CloudStore-project inventory, repo row) · [Service Contract & Packaging deep-dive](../../../architecture/conceptions/service-contract/summary.md) · [ADR SOV-583 authz model](../../../architecture/adr/adr-sov-583-authz-model.md) · [opcp-infra-operator deep-dive](../../../../opcp-core/architecture/conceptions/opcp-infra-operator/summary.md) (per-node operator model the repo doc analyses)
- Upstream: [`cloudstore-service-object-storage` on Stash](https://stash.ovh.net/projects/CLOUDSTORE/repos/cloudstore-service-object-storage/browse) · template `https://github.com/OVH-Goldorack/cloudstore-service-template` (v0.6.2)
