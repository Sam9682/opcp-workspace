---
id: core/irobox-contributing
type: deep-dive
diataxis: how-to
title: "Contributing to Irobox — branching, releases & deploying to environments"
owner: sov-copilot
status: approved
publish_target: git          # distillation of two SOV-Confluence pages — Confluence stays source of truth
product: opcp-core
---

# Contributing to Irobox — branching, releases & deploying to environments

> **What this is:** the developer workflow for getting an Irobox / configuration change into an environment — branching + release model, and the contribution/promotion flow (dev envs vs. prod envs `demo`/`nuc0`).
>
> **Source of truth = Confluence (SOV space).** This page is a distillation for Copilot context — check the originals before acting:
>
> - [Branching model and release management](https://confluence.ovhcloud.tools/display/SOV/Branching+model+and+release+management) *(mirrored v1, fetched 2026-07-20)*
> - [Contributing to Irobox and deploy it on environment](https://confluence.ovhcloud.tools/display/SOV/Contributing+to+Irobox+and+deploy+it+on+environment) *(mirrored v5, fetched 2026-07-20)*
> - [Prod-cli](https://confluence.ovhcloud.tools/display/SOV/Prod-cli) *(mirrored v2, fetched 2026-07-20 — install/config + usage walkthrough)*
>
> ⚠️ **Scope: BM POD SNC.** The Irobox-versioning + hieradata mechanism here applies to **BM POD SNC** environments (Baremetal Pod / SNC Cloud Platform), where OVH operates the whole stack. **OPCP Managed** and **OPCP Unmanaged** follow other configuration mechanisms — not covered here.

---

## 1. Branching + release model (X.Y.Z)

- **Major (X)** — released for breaking changes (e.g. HA).
- **Minor (Y)** — released **every month** (every 2 sprints); rhythm flexible but worth keeping.
- **Patch (Z)** — any time, under backport rules:

| Maintained versions | latest | 2nd most recent | 3rd … |
| --- | --- | --- | --- |
| **Major** | all fixes backported (if no minor since) | security + major bug fixes | unmaintained |
| **Minor** | all fixes backported | unmaintained | unmaintained |

**Which rack runs what** *(as of 2026-03-02 — verify current mapping)*:

| Rack | Rule | Version then |
| --- | --- | --- |
| MinInt | next **major** | 3.0.0 |
| Demo1 | next **minor** | 2.1.0 |
| Demo2 | next **patch** | 2.0.5 |

**In git:** versions are **tags** (immutable). Each major/minor gets a `release/X.Y.X` branch cut from stable, worked + tested, then tagged (`vX.Y.0`) and merged back to `master` (fast-forward). Patches iterate on the release branch with a new tag each. Commits to backport get a **label on the PR**; on conflicts, cut a `backport/X.Y.X` branch, cherry-pick, PR it into the release branch (strongly advised — forces peer review), then tag the patch release.

---

## 2. The three repos + how a change flows

| Repository | Role | Remote |
| --- | --- | --- |
| `irobox` | Control-plane base template (code, cluster templates, Terraform modules). Versioned by **tag**. | `ssh://git@stash.ovh.net:7999/gor/irobox.git` |
| `fleet-infra-hieradata` | Per-env Hiera/YAML values + **`iroboxVersion` mapping** — **the source you edit**. | `ssh://git@stash.ovh.net:7999/gor/fleet-infra-hieradata.git` |
| `fleet-infra-generated` | **Generated** output — rendered manifests Flux applies to the clusters. **Never edit by hand.** | `ssh://git@stash.ovh.net:7999/gor/fleet-infra-generated.git` |

```
irobox (templates, by tag)   fleet-infra-hieradata (per-env values ← you edit)
            └────────────┬────────────┘
                 fleet-infra-cli   renders / generates
                         ▼
              fleet-infra-generated   (never hand-edited)
                         ▼
                       Flux   reconciles onto the cluster
```

Each environment pins **which Irobox version it uses** via `iroboxVersion` in `fleet-infra-build-config.yaml` — accepts a **tag** (`3.0.5`), a **branch** (`release/3.1.x`, `master`), or a **commit hash** (point an env at a branch to test untagged code; tag stays recommended for prod). Hieradata is organized by stage: `hieradata/dev/gor-<login>.yaml` · `hieradata/prod/gor-demo.yaml`, `gor-nuc0.yaml`, … + per-stage `common.yaml`.

---

## 3. Dev environments (`minint`, personal `gor-<login>`, …)

Classic git workflow + **local build** — no `prod-cli` involved:

1. Branch from `main` on `fleet-infra-hieradata`, edit your env's yaml.
2. **PR → review → merge.**
3. Build: `fleet-infra-cli build [--env <name>]` (or `--raw` to use the current irobox working tree instead of a tagged version).

**Prerequisites (once):** git (`pull.rebase=true`) · `sops` + `age` (encrypted secrets) · `~/.hieradata-fic-artifactory-creds.txt` (Artifactory token) · `bastion-wrapper` (z3) · `cdsctl` · `fleet-infra-cli` (+ `~/.fleet-infra-cli` config pointing at your three local checkouts, incl. `fleet-infra-generated` as output location) · `prod-cli` ([Prod-cli docs](https://confluence.ovhcloud.tools/display/SOV/Prod-cli) — install/config summary in §4.1).

---

## 4. Prod environments `demo` / `nuc0` — promote via `prod-cli`

Prod is updated by **promoting hieradata commits**, never by building locally: a **CDS pipeline** runs `fleet-infra-cli` and generates into the `stable` branch of `fleet-infra-generated`. `pick`/`rebase` applies **only to `fleet-infra-hieradata`** (no longer to `irobox`).

### 4.1 Install & configure `prod-cli` (once)

- **Install:** `pip3 install -U prod-cli` from the Artifactory index `gor-publiccloud-pypi` — pip index-url in `~/.pip/pip.conf` with your corp login + an Artifactory **Identity Token** (generate under artifactory.ovhcloud.tools → Edit Profile). Too-old python3? Use a pyenv/conda venv (py3.9 works).
- **Auto-upgrade check:** every command checks for updates — needs `~/.prod-cli-config.ini` with `[artifactory] user = … / password = <API_KEY>`. Bypass via `PROD_CLI_NO_CHECK_VERSION=true` (not recommended).
- **CDS access** (build/monitor fleet-infra): either `cdsctl` configured (`~/.cdsrc` is picked up automatically) or a CDS **consumer** (Groups: GOR · Scopes: Run/RW, RunExecution/RW, Service/R, User/R, Project/R) exported as `CDS_TOKEN`.
- **Git:** `~/.gitconfig` with your identity + `pull.rebase = true`.

### 4.2 The promotion flow

Flow: **`display` → `lock` → `pick` → `rebase` → `unlock`**

| Command | Description |
| --- | --- |
| `prod-cli display` | Your commits pending promotion to prod. |
| `prod-cli lock` / `unlock` | Lock/unlock production. ⚠️ **Never forget `unlock`** — it blocks other contributors. |
| `prod-cli pick <hash…> [--push]` | Cherry-pick onto prod branches — test locally first (no `--push`), then push. |
| `prod-cli rebase [--repo fleet-infra-hieradata] [--branch <env-branch>] [--push]` | Rebase prod branches (specific env or all). |
| `prod-cli changelog [--days N]` | Recently promoted commits (default 3 days). |
| `prod-cli build [--irobox-branch b --hieradata-branch b --fleet-infra-branch b]` | Manually launch + monitor a fleet-infra build (default: `master`; use `… stable` ×3 for the prod output). Normally not needed — merges to `master`/`stable` auto-build. |

**Troubleshooting:** if a picked commit doesn't show up, the [CDS `prod-cli-build` workflow](https://cds.ovhcloud.tools/project/GOR/workflow/prod-cli-build) may still be running or failed. For envs targeting a production branch (`prod-demo`/`prod-nuc0`), relaunch the build from the CDS UI with **both `hieradata-branch` and `fleet-infra-branch` set to `stable`** — or from the CLI: `prod-cli build --irobox-branch stable --hieradata-branch stable --fleet-infra-branch stable`.

---

## 5. Worked example — new Irobox version onto `demo`

1. **Ship the code in `irobox`.** ⚠️ Align with the **Platform team first**: every irobox change needs a **Jira** + an upfront **target version** (determines which branch to cut from — `master` vs. `release/3.1.x`; also check before creating tags). Branch → commit → **update `release-notes/x.x.x/`** (`UPGRADE.md` = breaking changes/required actions, `RELEASE-NOTES.md` = user-facing summary — **must be in the PR**, not left for later) → PR → merge to `master` → tag (`git tag 3.0.5 && git push origin 3.0.5`).
2. **Bump the version in hieradata.** Branch on `fleet-infra-hieradata`, set `environments.demo.iroboxVersion: 3.0.5` in `fleet-infra-build-config.yaml`, PR → merge to `main`.
3. **Promote with `prod-cli`:** `display` (grab the bump hash) → `lock` → `pick <hash>` (local test) → `pick <hash> --push` → `rebase --repo fleet-infra-hieradata --branch <branch_demo>` (+ `--push`) → `unlock`. Same pattern for `nuc0`.

**Summary:**

| Case | How to apply |
| --- | --- |
| Dev envs (`minint`, `gor-<login>`, …) | PR on `main` → `fleet-infra-cli build --env <name>` |
| Prod envs `demo` / `nuc0` | PR on `main` → `prod-cli pick` + `rebase` (**hieradata only**) |
| New Irobox version | release notes → merge + **tag** on `irobox` → bump `iroboxVersion` → `prod-cli pick`/`rebase` |

---

## 6. Cross-references

- [Irobox Deep Dive](summary.md) — structure/mechanics: deployment modes, controller-vs-compute split, hieradata lookup order, `fleet-infra-cli`.
- [OPCP Core Deep Dive §7](../opcp-core/summary.md) — the templating/GitOps chain (`{()}` decorator, "generated, not edited", multi-env builds).
- [EXTERNAL-REPOS.md](../../../../../_workspace/EXTERNAL-REPOS.md) — upstream repo inventory (irobox + GOR forks).
- Upstream per-repo docs: `irobox` `README.md`/`CONTRIBUTING.md`, `fleet-infra-hieradata` `README.md`.
- Context: the 2026-07-17 demo/IPA chat (Damien: "demo is a production environment", "don't push like that on generated") is exactly the failure mode this workflow prevents — direct pushes to `fleet-infra-generated` bypass review + CDS and are overwritten on the next build.
