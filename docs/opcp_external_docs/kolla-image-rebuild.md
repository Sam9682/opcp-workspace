---
id: core/kolla-image-rebuild
type: runbook
diataxis: how-to
title: "Kolla image rebuild (CVE + scheduled)"
owner: compute-team          # doc says owner TBD (compute or network lead) — provisional
status: draft                # held: unvalidated, blocked on expert qualification
publish_target: git
tags: [kolla, cve, openstack, images]
---

# Runbook — Kolla image rebuild (CVE + scheduled)

> **When to use:**
> - A CVE lands in a system package shipped inside one or more **Kolla-built OpenStack images** (`neutron-dhcp-agent`, `nova-libvirt`, `nova-novncproxy`, etc.). Example: SOV-728 / SOV-736 — dnsmasq CVE in `neutron-dhcp-agent`.
> - **Scheduled image hardening** ("satinisation" — package cleanup / smaller surface area).
> - Base image (Debian/Ubuntu) bump that requires re-layering all dependent images.
>
> **Owner of this runbook:** TBD — candidates are *Compute team lead* (for compute-side images) and *Network team lead* (for neutron-* / octavia-* images). When one team is overwhelmed the other can run the rebuild for them per the established cross-team practice (per SOV-736 chat 2026-05-13).
>
> **SLA reminder — SNC qualification:** CVE remediation has a documented deadline (typical 7-14 days from CVE publication to images redeployed in prod, depending on severity). Don't sit on a critical CVE.
>
> **Status:** DRAFT 2026-05-13 — concrete commands need verification against OPCP's actual CDS workflow + registry path. Mark TBC items resolved as you run this.
>
> **Doc-gardener note (2026-07-13):** **held in the git KB — not published to Confluence** until an expert (candidate: Damien Rannou / compute or network lead) runs it once, resolves the TBCs, and takes ownership. Colleague-facing Confluence runbooks must be validated first. Once qualified, this promotes to *03.01.05.01 Runbooks*.

---

## TL;DR (the 5-step skeleton)

```
1. Identify affected images        →  list of <image:tag> + the package version they need
2. Trigger the rebuild              →  CDS pipeline OR local kolla-build
3. Verify the rebuild               →  patched package version present in the new image
4. Roll out                         →  bump image reference in hieradata, Flux reconciles
5. Validate functionality           →  service-specific smoke test
```

---

## Background — what a Kolla image actually is

Each Kolla image is a Docker container that:
- starts from a **base image** (e.g. `kolla-base` on Rocky / Ubuntu / Debian),
- installs the OpenStack service via `pip` (sometimes from source, sometimes from PyPI),
- installs system packages via `apt-get install` / `dnf install` (this is where `dnsmasq`, `openssl`, `libvirt`, etc. land),
- gets pushed to an artefact registry — for OPCP this is **likely** the OVH artifact registry (`artifactory.ovhcloud.tools`) or the CloudStore Harbor (`9501yd0v.eu-west-par.container-registry.ovh.net`) — **verify which one your image set uses before proceeding**.

A **rebuild** for a CVE in a system package = re-run the Dockerfile so `apt-get install <pkg>` picks up the patched version from the upstream Debian/Ubuntu security repo. **No source change to OpenStack itself required.**

The OpenStack BMPod hosts then pull the new image tag and restart their containers.

---

## Step 1 — Identify affected images

### 1a. From the CVE advisory

Read the CVE advisory carefully:
- **What package is vulnerable?** (e.g. `dnsmasq`)
- **What versions are affected?** (e.g. `dnsmasq < 2.90`)
- **What's the fixed version in upstream Debian/Ubuntu security?** Check at <https://security-tracker.debian.org/tracker/CVE-XXXX-XXXX>.

### 1b. List Kolla images that ship the affected package

Two approaches:

**Approach A — grep the kolla repo Dockerfiles:**

```bash
cd <path-to-kolla-fork>
grep -rl "dnsmasq" docker/
# typical hits for dnsmasq:
#   docker/neutron/neutron-dhcp-agent/Dockerfile.j2
#   docker/nova/nova-novncproxy/Dockerfile.j2  (if applicable)
```

**Approach B — inspect a deployed image:**

```bash
# Pick a sample image from the current registry
docker run --rm <registry>/<image>:<current-tag> dpkg -l dnsmasq
# Look for the version in the output. If it's affected by the CVE → image needs a rebuild.
```

Repeat for each candidate image. Build the *affected-images* list before triggering anything — partial rebuilds cause integration headaches.

### 1c. Decide team ownership

- **Network team:** anything under `neutron-*`, `octavia-*`, `designate-*`.
- **Compute team:** anything under `nova-*`, `cinder-*`, `placement-*`.
- **Cross-cutting:** `keystone-*`, `glance-*`, `heat-*`, base images.

If a team is overwhelmed, the other team can run the rebuild on their behalf (precedent: SOV-736, 2026-05-13). **Document the cross-team takeover in the ticket** so blame doesn't land in the wrong place if rollout breaks something.

---

## Step 2 — Trigger the rebuild

### 2a. Via CDS (preferred — production path)

OPCP runs Kolla builds via CDS workflows. **Exact workflow location TBC** — look under the kolla-image repo's `.cds/workflows/`. Typical pattern:

```yaml
# .cds/workflows/build-kolla-images.yaml (likely)
name: build-kolla-images
parameters:
  images: "neutron-dhcp-agent,nova-novncproxy"   # comma-separated
  tag_suffix: "cve-2024-NNNN"
```

Trigger:
- CDS UI: pick the workflow, fill `images:` parameter with the affected list, kick off.
- Or via API: `cdsctl workflow run <project> <workflow> --param images=neutron-dhcp-agent`.

**Time budget:** 30-60 min per image, parallelisable. Plan for the full set to take 1-3 hours from trigger → registry.

### 2b. Local rebuild (development / emergency / debugging)

If CDS is unavailable or you need to test a Dockerfile change before pushing through CI:

```bash
# Prereq: kolla pip-installed locally + Docker / Podman running
pip install kolla
kolla-build neutron-dhcp-agent \
  --tag <new-tag> \
  --registry <registry-url> \
  --push
```

Beware: a local rebuild is **fine for testing** but for production CVE remediation **always go via CDS** so the audit trail is clean (who built it, with what inputs, when — needed for SNC compliance).

### 2c. Multi-image dependencies

Some images depend on others (e.g. `nova-compute` extends `nova-base`). Kolla handles this automatically — building `nova-compute` will rebuild `nova-base` if needed — but **verify all downstream consumers** are picked up:

```bash
kolla-build --print-tasks neutron-dhcp-agent
# Shows the dependency tree before kicking off.
```

---

## Step 3 — Verify the rebuild

### 3a. Confirm the image lands in the registry

```bash
# For Harbor:
curl -u sa-cs-team-<team>-read:<password> \
  "https://<registry>/api/v2.0/projects/<project>/repositories/<image-name>/artifacts/" \
  | jq '.[] | {tags, push_time}'
# Should show your new tag with a recent push_time.

# For artifactory:
curl -H "Authorization: Bearer <token>" \
  "https://artifactory.ovhcloud.tools/api/repositories/<repo>/<image>" \
  | jq '.children'
```

### 3b. Verify the patched package is actually in the image

```bash
docker pull <registry>/<image>:<new-tag>
docker run --rm <registry>/<image>:<new-tag> dpkg -l dnsmasq
# Expected output: dnsmasq <patched-version>
# If the version is still the vulnerable one → rebuild didn't pick up the upstream patch.
# Common cause: cached apt layer. Force a no-cache rebuild.
```

### 3c. (Optional) Image-size sanity check

CVE rebuilds shouldn't dramatically change image size. If your `neutron-dhcp-agent` image jumps from 500 MB to 2 GB, something is wrong:

```bash
docker images <registry>/<image>:<new-tag> --format "{{.Size}}"
# Compare against the previous tag's size.
```

---

## Step 4 — Roll out

### 4a. Update the image reference in hieradata

OPCP's image catalogue is **likely** declared in `fleet-infra-hieradata` (see the bundled `irobox/hieradata/fleet-infra/*_vars.yaml` in the iRobox clone — clone location outside this repo, listed in [`EXTERNAL-REPOS.md`](../../../../_workspace/EXTERNAL-REPOS.md)). The exact path differs per service:

```yaml
# Probable shape — verify against your actual hieradata
neutron_vars.yaml:
  neutron_dhcp_agent_image: "<registry>/<project>/neutron-dhcp-agent"
  neutron_dhcp_agent_tag:   "<new-tag>"             # ← bump this
```

Open a merge request against the hieradata repo with the tag bump. **Reviewers:** the team owning the image (network or compute). **CVE label:** add a `cve` label so reviewers know the urgency.

### 4b. Flux reconciles

Once the hieradata MR merges, Flux on the OPCP control plane reconciles the change:
- Updates the deployment manifests with the new tag.
- The OPCP Compute Controller / iRobox reconciler picks up the new tag.
- BMPod hosts pull the new image **on next pod restart** — **not automatically** for already-running pods.

### 4c. Rolling restart

For services that can restart in-place (most agent-style services like `neutron-dhcp-agent`):

```bash
# Per BM host, rolling — one at a time:
kubectl -n openstack rollout restart daemonset/neutron-dhcp-agent
# Or via the operator's per-node controls if available.
```

For `nova-compute` (running VMs): **plan a maintenance window** if you can't live-migrate VMs off the host first. The VMs themselves keep running during a `nova-compute` restart (libvirt doesn't reach into them) but **scheduling new VMs on that host won't work** until `nova-compute` comes back up.

---

## Step 5 — Validate functionality

Service-specific smoke tests after the rollout:

### `neutron-dhcp-agent`
- DHCP lease still works for a fresh VM:
  ```bash
  openstack server create --network <net> --image <img> --flavor <flv> test-vm
  openstack server show test-vm | grep addresses
  # Should show a private IP — proves DHCP responded.
  ```
- Container reports healthy: `kubectl -n openstack get pod -l app=neutron-dhcp-agent`.

### `nova-libvirt` / `nova-compute`
- Existing VMs still reachable (`ping`).
- A new VM can boot: `openstack server create …`.

### `octavia-*` (load balancer)
- Existing LBs still routing.
- Probably a small set of VIP-health-check requests.

### General check — patched package version on a live node
```bash
# Find a running pod of the rebuilt image:
kubectl -n openstack exec -it $(kubectl -n openstack get pod -l app=neutron-dhcp-agent -o name | head -1) -- dpkg -l dnsmasq
# Confirms the patched version is running in prod.
```

Sign off the CVE ticket only when this passes on **at least one BM host in each cluster** that ran the affected image.

---

## Common failures + fix recipes

| Symptom | Likely cause | Fix |
|---|---|---|
| Build fails with "Unable to fetch some archives" | Upstream Debian/Ubuntu mirror temporary issue | Retry; if persistent, swap mirror in Dockerfile.j2 |
| Rebuilt image still has the vulnerable package version | apt cache layer not invalidated | Rebuild with `--build-arg CACHEBUST=$(date +%s)` or `--no-cache` |
| Build size dramatically larger than previous tag | A removed-package list got dropped, OR a dev tool ended up in the image | Diff against previous image's package list (`dpkg -l`); check Dockerfile.j2 for accidental adds |
| Image won't pull on BM host: "no space left on device" | Registry quota or BM-local disk full | Free disk on the host OR rotate old images out of the local cache |
| Service restart but pods crashloop | The patched library has an ABI break with the service | Check `kubectl logs` for the actual error. Roll back the tag and investigate. May need an OpenStack patch alongside the system-package fix |
| Flux doesn't pick up the new tag | Hieradata MR didn't propagate, or Flux reconcile interval > expected | Force reconcile: `flux reconcile kustomization openstack -n flux-system` |
| `dnsmasq` patched but DHCP still failing | Unrelated — likely an OpenStack config issue, not the CVE fix | Restore the previous image to isolate; debug DHCP config separately |

---

## CVE compliance — SNC SLA reminder

SNC qualification has documented CVE remediation deadlines (per Damien Rannou, 2026-05-13 chat):

| CVE severity | Typical SLA from publication → images redeployed |
|---|---|
| Critical (CVSS ≥ 9.0) | 7 days |
| High (7.0–8.9) | 14 days |
| Medium (4.0–6.9) | 30 days |
| Low | next scheduled rebuild |

**Verify the exact numbers against the active SNC compliance framework** — these are typical, not authoritative for your environment.

The clock starts at *publication of the CVE upstream*, not at your awareness of it. **Audit trail matters** — log the timeline:
- CVE published: `<date>`
- Detected internally: `<date>`
- Rebuild triggered: `<date>`
- Rolled to prod: `<date>`
- Validated: `<date>`

Put these dates in the ticket comment when closing.

---

## Scheduled rebuilds — what's different

Same procedure, fewer urgency signals. Key differences:
- **Trigger** = scheduled CDS workflow (probably weekly or monthly), not a CVE alert.
- **Scope** = all images, not a targeted subset. Plan for 4-8 hours of build time.
- **Validation** = full integration test suite, not just the CVE-affected service.
- **No SLA pressure** — but does reset the CVE clock for *all* shipped packages, which earns 30 days of "we're current" margin against the SNC compliance framework.

This is also the natural place to land "satinisation" / hardening changes — fewer packages, smaller images, dropped dev tools — without the urgency of a CVE rebuild.

---

## 🚀 Potential accelerator — OSISM's image-build pipeline (investigation, 2026-05-13)

> **Status:** Research only — *not adopted*, *not on any roadmap yet*. Captured here because if executing this runbook gets painful (especially the CVE-response loop in *Step 2* + *CVE compliance* above), there's a concrete proven alternative to inherit from.
>
> **Owner of any decision:** the team running the OPCP Kolla pipeline (Damien Rannou, per the SOV-728 / SOV-736 chat thread on 2026-05-13).

### What it is

[`osism/container-images-kolla`](https://github.com/osism/container-images-kolla) — a public, Apache 2.0, actively maintained Kolla image-build pipeline from OSISM (the German OpenStack distribution shop). 706 commits, 49 release tags, multi-arch (arm64 + x86_64), publishes cosign-signed images to Quay.

### Why it might accelerate us — mapped to today's pain points in this runbook

| Today's pain | OSISM's solved equivalent |
|---|---|
| CVE rebuild (Step 2) is partly manual — Damien chased the dnsmasq fix himself per SOV-728/736 | `scripts/120-check-and-repush.sh` — automated re-push validation. Detects when a published image needs a fresh rebuild + re-publishes. |
| *"Satinisation of kolla"* (cleaning + hardening) lives in heads / informal practice | `patches/` + `overlays/` + `templates/$OPENSTACK_VERSION/template-overrides.j2` — explicit, versioned, reviewable. The same shape as our informal practice, but codified. |
| Multi-arch (M4+ may need arm64) — not solved today | Already in their flow: `kolla-build --base-arch $BASE_ARCH --platform linux/{amd64,arm64}`. |
| Supply-chain signing (SNC qualification eventually wants this) | `scripts/130-cosign.sh` — every published image cosign-signed at release time. |
| CI cadence "are we current on CVEs?" hard to answer | 49 release tags + their `120-check-and-repush` loop shows continuous tracking. |

### Their pipeline shape (the pattern worth knowing)

```
001-prepare.sh        → env setup
002-generate.sh       → render Dockerfiles from upstream Kolla templates + overrides
003-patch.sh          → apply patches/
004-build.sh          → invoke kolla-build with --template-override + --config-file
005-tag.sh            → tag built images
100-push.sh           → push to registry
110-release.sh        → cut release tags
120-check-and-repush  → re-validate published images, re-push if needed (CVE catch-up)
130-cosign.sh         → sign images
```

This is a structural pattern even if we don't adopt their specific code.

### Three options if this gets evaluated

**A — Fork + run in OVH CDS** *(recommended if SecNumCloud is in scope)*

- Inherit their script architecture + cosign signing.
- Build in OVH-owned CI (CDS), with OVH-controlled signing keys.
- Maintain a thin OVH-patch delta against the OSISM upstream.
- Audit trail: every binary built + signed in OVH-controlled CI. **SNC story stays clean.**
- One-time cost: porting Zuul + GHA workflows to CDS (engineer-month-ish); ongoing low.

**B — Consume their public Quay images + apply OVH patches as a layer**

- Faster (no CI to maintain).
- Audit trail is theirs — **probably blocks for SNC-graded environments**.
- Fine for non-SNC contexts (dev / test only).

**C — Reference-only**

- Borrow the patches / overlays / templates *pattern* for our existing pipeline. No external dependency.
- Misses the automation wins (`120-check-and-repush.sh`, multi-arch, cosign signing).

### Open question if Option A is on the table

Their `templates/` directory currently supports OpenStack **2024.1, 2024.2, 2025.1**. **Which version line is OPCP on?** Verify against `irobox/hieradata/*_vars.yaml` (in the iRobox clone — see [`EXTERNAL-REPOS.md`](../../../../_workspace/EXTERNAL-REPOS.md)). If we're on one of those, Option A is much cheaper.

### Source

- Repo: <https://github.com/osism/container-images-kolla> *(active, mature)*
- Misleading sibling repo to know about: `osism/container-image-kolla-ansible` *(singular "image") — that one packages the **deploy tool**, not the service images. Don't confuse them.*
- Quay: <https://quay.io/organization/osism>
- OSISM project: <https://www.osism.tech>

---

## Related

- **CVE source-of-truth:** <https://security-tracker.debian.org/> or <https://ubuntu.com/security/cves>.
- **OPCP image catalogue (probable location):** `irobox/hieradata/fleet-infra/*_vars.yaml` inside the iRobox clone — verify per service. See [`EXTERNAL-REPOS.md`](../../../../_workspace/EXTERNAL-REPOS.md) for the iRobox clone reference.
- **Companion runbook (project-specific):** [`Projects/Compute & Block on Cloud Store/runbooks/manual-keycloak-account-activation.md`](../../../cloudstore/misc/compute-block-on-cloud-store/runbooks/manual-keycloak-account-activation.md) — different topic, same operational style.
- **Upstream Kolla docs:** <https://docs.openstack.org/kolla/latest/admin/image-building.html>.

## Source

- Drafted 2026-05-13 from the SOV-728 / SOV-736 dnsmasq CVE chat (Damien Rannou + the compute team).
- TBC items in the doc need to be verified by the team running the procedure for the first time.
