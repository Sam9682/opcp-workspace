---
id: object-storage-on-cloud-store/confluence-os-package-architecture
type: deep-dive
diataxis: explanation
title: "Object Storage Package Architecture — Confluence draft (CPO)"
owner: sov-copilot
status: approved
publish_target: confluence
product: cloudstore
tags: [object-storage, architecture, confluence, ceph, rgw, keystone]
---

> **This file is the source of a Confluence page**, drafted to match
> [LGTM Multi-Tenancy Architecture](https://confluence.ovhcloud.tools/spaces/CPO/pages/956661706/LGTM+Multi-Tenancy+Architecture)
> (Zafar Akhtar, space **CPO**) in shape and tone. Illustration:
> [`diagrams/os-package-architecture-v6.png`](../diagrams/os-package-architecture-v6.png)
> — attached to the page and placed at the top, as the LGTM page does. A hand-drawn technical
> companion exists as an
> [excalidraw drawing](https://excalidraw.ovhcloud.tools/document/1d464e56-fb47-4efa-887e-492555f7275e)
> — linked from the page as well.
>
> ✅ **Published 2026-08-25** as pageId **1022937871** —
> [Object Storage Package Architecture](https://confluence.ovhcloud.tools/spaces/CPO/pages/1022937871/Object+Storage+Package+Architecture),
> child of *Cloud Store - Object Storage* (825638540) under *3.3 Cloud Store* in the OPCP PRD tree.
> **This file stays the source of truth — keep the two in sync** (same rule as the glossary).

# Object Storage Package — How It Works

**Scope.** One CloudStore service package deploys a complete, standalone S3 service: a Ceph cluster
with RADOS Gateway, its own Keystone for S3 authentication, a credential middleware and a customer
panel. It deploys in two halves — **one OPCP-wide control plane**, plus **one data plane per Account**
that entitles that Account to use it. **The package creates every machine itself through the OpenStack API** — there is no operator
and no OPCP Infra API in the path. What is deployed today is a **POC on virtual machines**; the target
shape is bare metal and has not been run.

---

## Summary

* **The package owns the whole lifecycle.** The control plane's six VMs — one k3s node, one OOB node,
  three converged Ceph nodes and one OSD-only node — are created by the package's own Terraform through the OpenStack
  API, then configured by Ansible shipped inside the package. This follows the **2026-05-27 decision**
  (Marc Dittmann) to take the **"VCF way"**: Object Storage needs no elevated privileges, so
  it calls OpenStack directly rather than going through the OPCP Infra API the way Compute & Block does.
  **The cost of that choice is lifecycle ownership** — everything the Infra Operator gives Compute &
  Block for free (Ironic, CIS hardening, destroy hooks, `preventDestroy`, the health heartbeat) is
  package-owned here, which is why the durability gaps below exist.
* **Tenant identity is a Keycloak realm, resolved into Keystone.** The Account authenticates against
  CloudStore Keycloak L3; an in-package Keystone federated to it issues the S3/EC2 credentials that
  every RGW validates. The governing model is **ADR SOV-583 Option 4** — `s3.{role}` client-roles on
  a per-(service, region) client.
* **Two RGW zones exist and they differ by exactly one token** — the `admin` API. L2 exposes it, L3
  does not. **Today nothing routes to L2**, so an admin-API-enabled gateway is running with no path
  to it. The separation itself was confirmed as a **mandatory core requirement** on 2026-08-06.
* **The OOB node does three unrelated jobs** — egress proxy, S3 load balancer with generic CORS
  injection, and SSH jumphost. All three have to be re-homed after the POC, and the CORS job has no
  owner.
* **Object data is durable in Ceph; nothing else is durable at all.** The control plane runs a single
  Postgres instance with no backup, and there is no data-preserving upgrade path — an update means
  delete and redeploy, which destroys every OSD.
* **Nothing here has run on real hardware.** The Ceph layer runs on `b3-8` VMs with 10 GiB Cinder
  volumes as OSDs. No throughput, latency or capacity figure exists, and the production disk layout
  is unvalidated.

---

## What a deployment is

The package deploys in **two halves**: one **control plane** for the whole platform, and one **data
plane per Account** that entitles that Account to use it.

### Control plane

One control plane deployment = **one OPCP-wide Object Storage service**, identified by a CloudStore
deployment ID whose first block is used everywhere (`7bdb85f5` for the current staging deployment).

| | |
|---|---|
| **Package** | `cloudstore-service-object-storage` `0.2.0-alpha.18+` |
| **Ceph** | 20.2.4 (Tentacle) |
| **VMs** | 6 — `b3-8`, `volume_type = public_standard` *(current demo setup, no baremetal)* |
| **Provisioning path** | package Terraform → OpenStack API (Nova · Cinder · Neutron · DNS) |
| **Configuration path** | Ansible, shipped inside the package, run by the tf-runner |
| **Parent epic** | `LVL2-18375` |
| **Architecture drawing (hand-drawn, technical view)** | [excalidraw `1d464e56`](https://excalidraw.ovhcloud.tools/document/1d464e56-fb47-4efa-887e-492555f7275e) |

### The six machines

| Role | Count | What runs on it | Sized by |
|---|---|---|---|
| **k3s node** | 1 | Keystone + CloudNativePG · credentials-middleware · panel + auth helper · external-dns · Traefik Gateway | `flavor_name` |
| **OOB node** | 1 | tinyproxy (egress) · HAProxy (S3 LB + CORS) · SSH jumphost | `ceph_flavor_oob` |
| **Converged Ceph** | 3 | `mon` + `rgw` + `osd` | `ceph_flavor_mon_nodes` · `ceph_mon_node_count` |
| **OSD-only** | 1 | `osd` | `ceph_flavor_osd_nodes` · `ceph_osd_node_count` |

**How the counts work** — `ceph_osd_node_count` is the **total** number of OSD-carrying nodes
(default 4), and the **first `ceph_mon_node_count`** of those (default 3) are the converged mon nodes.
The remainder are OSD-only; the OOB node is in neither count. So `1 + 1 + 3 + 1 = 6`.

**The Ceph nodes have no public address.** They are reachable only through the OOB node.

### Data plane

One data plane deployment = **setting up an Account to use the Object Storage control plane**. There
can be **multiple data planes — one per eligible Account** — against the single control plane above.

The data plane deploys an **Auth-Adapter** into the package's own K3S, bound to that Account, and
configures the package's own Keystone for it.

**It is provisioned by the package's Terraform only — no Ansible**, and it creates **no new VMs**: a
data plane is a deploy *into* the existing control plane, which is why it cannot exist without one.

---

## Identity — who is allowed to write an object

| Layer | Role |
|---|---|
| **CloudStore Keycloak L3** | One realm per Account — the realm is the tenant. Client-roles `s3.{role}` on a per-(service, region) client. |
| **In-package Keystone** | Federated to Keycloak through an Apache-OIDC proxy. Issues the S3 / EC2 credentials RGW validates. Backed by CloudNativePG. |
| **credentials-middleware** | A thin **proxy for access-key CRUD onto Keystone** — it has **no database of its own**. Two jobs: **(1)** Keystone's OS-EC2 endpoint returns the secret key on *every* read, so the middleware **strips it from the GET response** — a secret is therefore only ever visible at creation time and can never be retrieved again; **(2)** it issues the **temporary access keys the panel UI uses** — ordinary access keys, with no special prefix — and runs a **scheduled cleanup** of them. |
| **RGW** | Validates every request against Keystone using the six `rgw_keystone_*` parameters. |

⚠️ **The Keystone API is effectively public.** `allowed_admin_cidr` defaults to `0.0.0.0/0`, and
Keystone is protected only by a Traefik IPAllowList using that value. It cannot be narrowed today
because the tf-runner's source range is unknown, and the tf-runner is the only reason Keystone needs a
public route at all. The same variable also gates SSH `:22` and the k3s apiserver `:6443`, so
tightening it naively widens those to the same range. Tracked as `SOV-2024` / **OSQ-36**.

---

## The two RGW zones

The package stands up two RGW service specs. They are identical except for one token in
`rgw_enable_apis`:

| Spec | `rgw_enable_apis` | Meaning |
|---|---|---|
| `rgw-l2-admin.yml.j2` | `s3,s3website,`**`admin`**`,sts,iam` | the RGW exposing the **admin API** |
| `rgw-l3-user.yml.j2` | `s3,s3website,sts,iam` | user-facing **S3 only** |

Observable at runtime with `ceph config dump | grep api` on a mon node.

**L2 is stood up but never exposed** — the OOB HAProxy routes only to L3. An admin-API-enabled
gateway is running with no route to it: harmless while nothing points there, live the moment
something does.

**The separation is a core requirement, not an SNC-only flavour** — confirmed 2026-08-06 on
`SOV-1938`: it is mandatory for every service, on the reasoning that OPCP and SNC must converge and
that security is easier to remove than to add; if the cost proves material it should be disableable
behind a feature flag. Two follow-ups are still open: the **quantified cost overhead** of the proxy
fleet, and the **switchability mechanism**. The separation also implies **two Keystones**, one per
plane, each with its own database and policy. Logical separation via Neutron/Cilium is sufficient —
physical hardware separation is not required — but the proxy must never share a CPU with the backend.

---

## The OOB node — three jobs on one host

| # | Responsibility | Why it is there | Where it goes next |
|---|---|---|---|
| **R1** | **Egress proxy** (tinyproxy) | The Ceph nodes have no route out. Covers **container image pulls** via a systemd `DefaultEnvironment` drop-in, not just apt. | Largely removable by pointing apt at the internal Artifactory remote — see *Air-gapped operation*. |
| **R2** | **Ingress LB + TLS** (HAProxy `:443` → `rgw:7490`) | The S3 endpoint customers actually reach. | 🔴 **Hard dependency on Network Service.** A publicly reachable Octavia LB needs LB + FIP + external-net/router, which is Beta scope. OOB cannot be removed before NS ships it. |
| **R3** | **Generic S3 CORS injection** | **RGW only supports per-bucket CORS**, so service-level operations (ListBuckets) have none without this layer. Without it the panel cannot talk to S3 from a browser. | 🔴 **No owner.** The credentials middleware was ruled out as a home — it would route object data through a Node.js app. |

Tracked as `SOV-2020` / **OSQ-30**.

---

## Air-gapped operation

**Container images are already handled** — `ceph_system_prep` carries `configure_registry_mirror` and
a Harbor air-gap mirror path. **apt is the unsolved half** (`SOV-2031`).

The host package set is small and known: `apt-transport-https`, `gnupg`, `ca-certificates`,
`systemd-resolved`, `chrony`, `openssl`, `podman`, `catatonit`, `python3-yaml`,
`python3-cryptography`, plus `tinyproxy` and `haproxy` on the OOB node — and **`cephadm` +
`ceph-common` from the third-party Ceph repository**, whose GPG key is fetched over the network.

**The Compute & Block side has already solved this**, and the answer transfers directly: point apt
**straight at the internal Artifactory remote** rather than at `download.ceph.com`.

```
deb [signed-by=/usr/share/keyrings/ceph.gpg] https://<rt-host>/artifactory/apt-ceph-debian-tentacle bookworm main
```

Artifactory proxies ceph.com's own signed repository rather than re-signing it, so the entry is signed
by the Ceph release key and ships its own keyring — which removes the network key fetch as well as the
third-party source. Two things worth carrying across:

* ⚠️ **Do not aggregate remote repositories into a virtual repository.** It is explicitly discouraged
  (dependency-confusion risk); use the remote's dedicated URL directly.
* ⚠️ **The apt suite carries only the current patch release.** `20.2.3` has already been withdrawn
  from `download.ceph.com/debian-tentacle`. A pinned container image can therefore silently diverge
  from what apt installs.

---

## Certificates

The **deployer** supplies `my_ca_cert` + `my_ca_key`, and the package mints leaves for **S3/RGW ·
panel · middleware · Keystone**. This is distinct from the platform-injected trust-only `ca_crt`.
LetsEncrypt was dropped (no ACME when air-gapped) and cert-manager was explicitly rejected in favour
of the Terraform `tls` provider.

Three findings, all in code (`SOV-2021` / **OSQ-35**):

1. **Every leaf is minted for 10 years** (`validity_period_hours = 87600`, three files) — set-and-forget.
2. **There is no renewal path.** Rotation is `taint` + re-apply; there is no revocation, CRL or OCSP
   for a key compromise.
3. **Browser trust is the binding constraint.** Three of the four endpoints are browser-facing, so a
   private-CA leaf requires every user's browser to trust that CA.

The CA private key currently lands in **Terraform state**.

---

## Durability and what happens on delete

| What | Where it lives | Survives |
|---|---|---|
| **Object data** | Ceph — replica 3, host failure domain | node loss, restart |
| **S3 credentials, projects, roles** | Keystone Postgres, `instances = 1` | 🔴 **nothing** — no backup exists |
| **Panel / middleware state** | in-cluster | 🔴 no backup |
| **OSD volumes** | `openstack_blockstorage_volume_v3` — **owned by the deployment's Terraform state** | 🔴 not a deployment delete |

🔴 **There is no data-preserving upgrade path.** CloudStore does not support upgrading a deployed
package, so an upgrade means delete and redeploy — and deleting a deployment deletes the control
plane, therefore all resources, therefore all disks, therefore all OSDs.

`modules/node/instance.tf:52` carries `delete_on_termination = false # better keep the data`. **That
comment reads as protection and is not**: it only stops Nova cascading on *instance* deletion. The
volumes are Terraform-owned resources, so a destroy deletes them regardless. `prevent_destroy` is not
the fix either — it makes `destroy` *error* rather than skip, and it blocks in-place replacement too.

**The Ceph side already works.** `roles/ceph/tasks/upgrade.yaml` (tag `upgrade-ceph`, opt-in) detects
in-progress upgrades, compares images and runs `ceph orch upgrade start`, forward-only. What is
missing is the **platform trigger** to re-run a deployment at a newer package version, and — the more
under-specified half — the **retained → reattached path**, because retention is worthless if a new
deployment cannot adopt the volumes.

Tracked as `SOV-2033`. It is CloudStore-team work, not ours; the Object-Storage-side design of
scale-in / node replace *without data loss* belongs to `SOV-855`.

---

## Known gaps

| Gap | Consequence | Tracked as |
|---|---|---|
| **No upgrade path** | Any update destroys all data. Also the only route to a security fix: patching Ceph today means redeploying, which is survivable for a POC and not for a deployment holding customer data | `SOV-2033` — **unassigned** |
| **No control-plane backup** | Cluster loss = every S3 credential, project and role gone | **OSQ-37** — no ticket, no owner |
| **Never run on real hardware** | No performance figures; production disk layout unvalidated; `encrypted: true` is immutable at OSD-create time | **OSQ-38** — no ticket, no owner |
| **Keystone publicly reachable** | See *Identity* | `SOV-2024` |
| **10-year certificates, no renewal** | See *Certificates* | `SOV-2021` |
| **L2 RGW unrouted** | Admin API running with no path to it | `SOV-1938` |
| **OOB node does three jobs** | R2 blocked on Network Service; R3 unowned | `SOV-2020` |
| **Air-gapped apt** | Third-party repo + network-fetched GPG key | `SOV-2031` |
| **OSD spec is the loose default** | `osd-test-single-spec.yml.j2` takes every disk — fine on VMs, wrong on real hardware | `SOV-2009` |

---

## Sources

* Package repo — `cloudstore-service-object-storage` `origin/main` @ `0.2.0-alpha.18`
* Hand-drawn architecture (technical view) — [excalidraw `1d464e56`](https://excalidraw.ovhcloud.tools/document/1d464e56-fb47-4efa-887e-492555f7275e)
* Deployment `7bdb85f5`, staging CloudStore
* Decisions: **ADR 2026-05-27** (OpenStack API directly, not the Infra API — Marc Dittmann · [Webex message](webexteams://im?space=10189660-55e3-11f1-8ad2-6f2488e76939&message=6a4c34f0-59c3-11f1-9504-0fa0b7ecc35c)) · **OSQ-01** (provisioning boundary: the package does everything) · **OSQ-16** (RGW co-located) · CephADM + Ansible, no Rook (2026-06-09) · **ADR SOV-583 Option 4** (authorization model) · **SOV-1938** (L2/L3 mandatory, 2026-08-06)
* Jira: `LVL2-18375` and the epics `SOV-849`…`SOV-863`

---

<!--
PUBLISHING NOTE (not part of the page body)

Published 2026-08-25 via the Confluence REST API (Jan's PAT from the local .mcp.json):
  page 1022937871 "Object Storage Package Architecture", space CPO, parent 825638540
  attachment os-package-architecture-v6.png (attachment id 1022547637)
To republish after edits: strip frontmatter + this comment + the header note, convert with
python-markdown (tables, fenced_code), prepend the ac:image macro, PUT to
/rest/api/content/1022937871 with an incremented version number.
-->
