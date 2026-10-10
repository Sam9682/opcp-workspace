---
id: generic/artifact-mirroring-topology
type: reference
diataxis: explanation
title: "Artifact Mirroring Topology — upstream, Artifactory, mirrors, nodes"
owner: sov-copilot
status: approved
last_verified: 2026-08-18
publish_target: git
product: generic
---

# Artifact Mirroring Topology

> **Why this exists.** Working out where to add a Ceph apt repository took a full day of
> archaeology across four repos, and two of the conclusions on the way were wrong. Nothing in the
> workspace described how the pieces fit. This is that description.
>
> Everything below was read out of the repos on **2026-08-18**, not recalled. One inference is
> flagged as such at the end.

---

## The four layers

```
┌─ UPSTREAM ────────────────────────────────────────────────────────────────┐
│  quay.io   docker.io   ghcr.io   gcr.io   harbor.clyso.com   …            │
│  deb.debian.org        download.ceph.com/debian-{squid,tentacle}          │
└───────────────┬──────────────────────────────┬────────────────────────────┘
                │  OCI                         │  APT
                ▼                              ▼
┌─ ARTIFACTORY REMOTES ─── OVH/jfrog : settings.repositories.remote.yml ────┐
│  quay-remote          docker-hub-remote    ghcr-remote    gcr-remote      │
│  registry-k8s-io-remote  nvcr-remote  mcr-microsoft-remote  …             │
│  clyso-remote                                                             │
│                                                                           │
│  apt-deb   apt-deb-security   apt-k8s   apt-ubuntu   apt-archives   …     │
│  apt-ceph-debian-squid    apt-ceph-debian-tentacle                        │
└───────────────┬──────────────────────────────┬────────────────────────────┘
                │      aggregated by OVH/jfrog : namespace/gor.yml
                │      components.publiccloud.repositories.{docker,debian}
                │            .includeRemotes                │
                ▼                                           ▼
   ┌─ gor-publiccloud-docker (virtual) ─┐    ┌─ gor-publiccloud-debian ─────┐
   │ + include:                         │    │  (generated from the         │
   │   enablers-kms-docker-release      │    │   namespace file — see the   │
   │   pu-snc-default-docker-release    │    │   inference note below)      │
   │   pu-snc-bmpod-docker-release      │    └──────────────┬───────────────┘
   │   ⚠ NOT artifactory-pu-snc-paas    │                   │
   └───────┬──────────────────┬─────────┘                   │
           │ pull             │ consume                     │ consume
           ▼                  ▼                             ▼
┌─ GOR/artifact-mirrorer ─┐  ┌─ NODES (GOR/irobox) ─────────────────────────┐
│ CDS, one workflow per   │  │ docker_registry_url  → k3s, flux, podman     │
│ (image, tag).           │  │ ceph_container_image → ceph/ceph:v20.2.3     │
│ source_repository =     │  │ gor_repository_url   → gor_repos.list,       │
│   gor-publiccloud-      │  │                        signed-by artifactory │
│   docker.rt…            │  │ cephadm, ceph-common ← from the apt side     │
│ push → …-snapshot       │  └──────────────────────────────────────────────┘
│      → …-release (main) │
└─────────────────────────┘

┌─ SNC, parallel and mostly separate ───────────────────────────────────────┐
│ snc/oci-artifact-mirror → artifactory-pu-snc-{paas,bmpod,default}         │
│   pulls Clyso DIRECT from harbor.clyso.com (no Artifactory remote)        │
│   GOR includes …-default-release + …-bmpod-release, but NOT …-paas        │
│   ⇒ SNC's Clyso copy is NOT reachable from GOR                           │
└───────────────────────────────────────────────────────────────────────────┘
```

## Who owns which knob

| To do this | Change this repo | In this file |
|---|---|---|
| Add a new upstream source | `OVH/jfrog` | `settings.repositories.remote.yml` |
| Let GOR see an existing remote | `OVH/jfrog` | `namespace/gor.yml` → `…includeRemotes` |
| Pin a tag for retention / air-gap | `GOR/artifact-mirrorer` | `workflows_list.yml` (then `generate_workflow.py`) |
| Consume it on a node | `GOR/irobox` | `hieradata/…` or the playbook vars |

## The counter-intuitive bit — mirrors pull from the *internal* registry

99 of the 100 docker entries in `artifact-mirrorer` use
`source_repository: gor-publiccloud-docker.rt.ovhcloud.tools` — the internal registry, not the
upstream one. That looks circular and isn't:

1. `gor-publiccloud-docker` **proxy-caches** upstream through `quay-remote` and friends. Cached
   artifacts are transient — subject to `retrievalCachePeriodSecs` and eviction.
2. The mirror workflow **promotes** a specific tag into a *local* repo
   (`…-docker-snapshot` on a feature branch, `…-docker-release` on `main`). Local means retained,
   Xray-indexed, and distributable to air-gapped zones via Advanced Distribution.

So the mirror is not "fetch from the internet" — it is "pin this tag permanently". Pointing an
entry at `quay.io` directly makes it the exception for no benefit, and additionally relies on a
quirk described under Gotchas.

## Worked examples

**`ceph/ceph:v20.2.3` on a storage node.**
`ceph_container_image` → `{{ docker_registry_url }}/ceph/ceph:v20.2.3` →
`gor-publiccloud-docker` → `quay-remote` → `quay.io/ceph/ceph:v20.2.3`. Works today with no
mirror entry at all; the `artifact-mirrorer` entry exists to *pin* it.

**`cephadm` on a storage node.**
`gor_repos.list` carries `gor_repository_url` = `gor-publiccloud-debian`, signed by
`artifactory.gpg`. Whatever `namespace/gor.yml` lists under `debian.includeRemotes` is what apt
sees. Aggregate `apt-ceph-debian-tentacle` and `cephadm 20.2.3-1bookworm` appears; aggregate
nothing and you get Debian's own `16.2.15+ds-0+deb12u2` (Pacific).

**The Clyso image.**
`harbor.clyso.com/custom-ceph/ceph/ceph:gridscale-v20.2.1-sse-s3-kmip-v1` needs a `clyso-remote`
*and* an entry in `docker.includeRemotes`. Neither existed before
[jfrog #3265](https://stash.ovh.net/projects/OVH/repos/jfrog/pull-requests/3265/overview) (create) and [#3266](https://stash.ovh.net/projects/OVH/repos/jfrog/pull-requests/3266/overview) (use) — two PRs, not one, for
the reason under Gotchas.
SNC's mirrored copy is no help: it lands in `artifactory-pu-snc-paas`, which GOR does not include.

## Gotchas

**apt cannot select between two suites of the same package.** Aggregating both
`apt-ceph-debian-squid` and `apt-ceph-debian-tentacle` into `gor-publiccloud-debian` lets apt pick
whichever version is higher, with no per-node way to choose. Since
[`SOV-2033`](SOV-2033) records no data-preserving path for a
Ceph major upgrade, that is a real hazard. **Aggregate exactly one**, and treat changing it as a
deliberate fleet-wide move.

**`artifact-mirrorer` cannot mirror apt at all.** Its CDS template branches only on
`type: docker` and `type: helm`. Debian mirroring is an Artifactory *remote repository*, which is
why it lives in `OVH/jfrog` and not there. `apt-wazuh-4.x` and `proofpoint-open-suricata-5.0` are
the precedents for third-party apt repos.

**The GOR mirror template logs in to the source unconditionally.** `gor-release-mirror.yml` runs
`docker login <source>` with the Artifactory token before pulling. Against an external registry
that login fails — non-fatally, because the step has no `set -e` and its exit status comes from a
trailing `echo`, so an anonymous pull still succeeds. SNC's template does this properly, gating
the login on the source being the internal registry. Another reason to use the internal source.

**Creating a remote and using it must be TWO PRs. This is a house rule, not a lint artefact.**
Adding a remote to `settings.repositories.remote.yml` *and* listing it in a namespace's
`includeRemotes` in one change makes the autoconf dry run report:

```
[ERROR]: error applying namespace/<ns>
Lint Errors
  ⚠️ unable to include a not found remote repository <name>
```

The *mechanism* is benign: a dry run applies nothing, so the remote genuinely does not exist when
the namespace is validated, and on a real apply remotes are created before namespaces and the
include resolves. PR #2907 (rabbitmq, April 2026) merged in exactly that shape and worked.

**Do not conclude from that precedent that you can ship it as one PR.** Tried on 2026-08-18 with
[#3263](https://stash.ovh.net/projects/OVH/repos/jfrog/pull-requests/3263/overview) — a code owner **declined** it, with *"please make 2 pr. One for create
remote, then another to use it into your configuration file"*. Sequence instead:

1. **Create** the remote — `settings.repositories.remote.yml` only.
2. Wait for it to merge **and for autoconf to apply it**. Merged ≠ applied.
3. **Use** it — the namespace `includeRemotes` line. Open this one as a *draft* meanwhile; its dry
   run stays red until step 2 completes, and a red draft reads as sequencing rather than breakage.

An include that references an *already-existing* remote is not subject to this at all — it creates
nothing, so it is a one-PR change ([#3264](https://stash.ovh.net/projects/OVH/repos/jfrog/pull-requests/3264/overview) aggregating `apt-ceph-debian-tentacle`,
live since #2443, is the worked example).

⚠️ Splitting does have the cost the earlier version of this note warned about: the dry-run report
marks the *whole* namespace apply as errored, so a red step-3 PR gives no signal about the other
entries in the same file. Review those by reading, not by trusting the check.

**`.jira` and `.md` ticket pairs, and Jira's own converter.** Unrelated to mirroring but adjacent
in practice: posting to Jira REST `api/2` takes wiki markup verbatim, so a `.jira` file lands
byte-identical. See the memory note on the Atlassian MCP's mangling if you use the MCP instead.

## One inference, flagged

`gor-publiccloud-debian` does **not** appear in `settings.repositories.virtual.yml`. I conclude
the automation generates the virtual repo from `namespace/gor.yml`. Supporting evidence: the docker
side behaves exactly that way — `quay-remote` is listed only in the namespace file, yet
`gor-publiccloud-docker.rt.ovhcloud.tools/ceph/ceph` demonstrably resolves. Well-supported, but not
read directly from the automation code. Verify before relying on it for anything expensive.

## Cross-references

- [`SOV-2193`](../../products/cloudstore/misc/compute-block-on-cloud-store/jira/SOV-2193-ceph-apt-mirror.md) — the ticket that produced this map
- [`handover-sov-687-storage-minint.md`](../../products/cloudstore/misc/compute-block-on-cloud-store/handover-sov-687-storage-minint.md) — the storage run that surfaced it
- [`EXTERNAL-REPOS.md`](../../_workspace/EXTERNAL-REPOS.md) — clone paths for `jfrog`, `artifact-mirrorer`, `oci-artifact-mirror`, `irobox`
- [Dev Infrastructure session summary](summary.md) — the recording this folder was originally created for
