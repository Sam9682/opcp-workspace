---
id: compute-block-on-cloud-store/architecture-snc-deployment-flow
type: deep-dive
diataxis: explanation
title: "SNC manual deployment flow — what we have to industrialise"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# SNC manual deployment flow — what we have to industrialise

> Source: `source-material/runbooks/PaaS-SNC-deployment-runbooks.pdf` (the per-stream runbook table) + `source-material/runbooks/deployment-dryrun-meeting-notes.pdf` (the cross-stream dependency graph + open TODOs).

This is what the **PaaS SNC team does today, by hand, to deploy a PaaS-SNC instance**. M3's job is to fold all of these steps into the `cloudstore-vm-bs-service` package + the operator chain so they happen automatically (or close to).

## The 11 deployment streams (from the dryrun)

```
panels                        ← global panel + regional panel + middleware
proxies                       ← 6 proxy VMs (Global L2/L3, Regional L2/L3, DP L2/L3) + proxy-redis
control plane                 ← keycloak, keystone instances, Horizon, monitoring components
paas-snc storage (block + object)
paas-snc block storage        ← Ceph block cluster + cinder integration
paas-snc object storage       ← Ceph object cluster + RGW (L2 + L3)
business logic                ← BL API + BL Controller + BL Services + BL External Services
global control plane          ← global k3s + ingress L2 + ingress L3
regional control plane        ← regional k3s + ingress L2 + ingress L3 + monitoring + okms
keycloak (in global ctrl pln) ← Keycloak L1/L2/L3 + federation to BMPod keystone
L2 + L3 keystones (regional, for object storage)
```

## Cross-stream dependencies (the dryrun mermaid graph, simplified)

```
                         start_deployment
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
       start_bm_pod_deployment        start_tls_certificate_generation
                │                               │
       bm_pod_hardware_ready                    │
                │                               │
       configure_palo_alto_fw &                 │
       configure_networks_in_openstack          │
                │                               │
            bm_pod_ready ─────────────┬─────────┘
                │                     │
   ┌────────────┼────────────┐        │
   ▼            ▼            ▼        ▼
 storage      proxies     ctrl planes (global + regional)
 (block +                     │
  object)                     ▼
                       global_ctrl_plane_ready_to_deploy_workload
                              │
                              ├─→ start_global_panel_deployment
                              ├─→ start_bl_deployment
                              └─→ start_keycloak_deployment
                                   ↓
                         regional_ctrl_plane_ready_to_deploy_workload
                                   │
                                   ├─→ start_l2_keystone_deployment
                                   └─→ start_l3_keystone_deployment

object_storage_ready  →  configure_proxy_backends  →  proxies_ready
                                                          ↓
                                            configure_bmpod_glance_to_use_object_storage

block_storage_ready   →  configure_bmpod_cinder_to_use_block_storage
```

## Open TODOs called out in the dryrun

(Comments marked `%% TODO:` in the mermaid)

- check BL deployment order — **Martin Znamirowski**
- configure cinder once block storage is ready — **SNC compute-hardening engineer**
- setup LDP for every component to log into — **SNC compute-hardening engineer**
- configure logging to LDP on bmpod — **SNC compute-hardening engineer**
- configure logging to LDP on control planes — **Benjamin Hofer**
- configure logging to Loki on block and object storage — **the SNC block+object storage engineers**
- configure logging to LDP on block and object storage — **the SNC block+object storage engineers**

These are the **last-mile manual steps** that the SNC team itself flagged as needing automation/industrialisation. They give a concrete shopping list for M3.

## "Already DONE / BACKLOG / CANCELED" follow-ups (top of the dryrun)

- ✅ DONE — `clarify internet connectivity situation` (GSSNC-220)
- ✅ DONE — `review BL dependencies` (GSSNC-221)
- 📝 BACKLOG — `sanitize control plane industrialization (remove OVH federation, S3 pool for rook-ceph)` (GSSNC-222)
- ❌ CANCELED — `make sure only flavors and images that actually work are available to customers` (GSSNC-223)

Plus risks called out:
- *make sure our docker images are slim and rely on uptodate software to avoid too many vulnerabilities*
- *potential risk: hardware for object storage is changing*

## Per-stream manual steps + people we'll need

Excerpted from the runbooks PDF — the **"does step require manual interaction?"** column is `y` for every step, which is the point.

### panels (regional + global SNC panel)
- First-time only: setup Keycloak for panel
- First-time only: setup OIDC provider on radosGW + Keycloak (the SNC block+object storage engineers; *"Later this should be done by the business logic when creating realms"*)
- Clone gridscale Docker image into oci-artifact-mirror (the assignee Stuhlmann / Tobias Brandenberg + signed-commit gymnastics)
- Create Pull-Request and wait for review
- Trigger CDS pipeline (`paas-snc-docker-image-js-ovh-opcp-frontend-{regional|global}-panel-paas-snc`)
- Update `image_tag` in `paas-fleet-infra` flux-builder values.yaml
- Run `flux-builder generate manifest` over SSH on `fw-peerx-paas-dev-rbx.pu-snc.ovh`

### proxies
- Create TLS certificates for all FQDNs
- Build proxy image (image-building pipeline is WIP per [GSSNC-211](#) — workaround: retrieve image built on Gridscale platform, needs TLS certs) — owners **the proxy-image team**
- Create `.tfvars` for target environment (in `paas-snc-proxy-tf` repo, under `etc/`)
- Apply terraform with `AWS_*` env vars set for the tfstate S3 bucket
- Instances configured through user-data

### paas-snc storage (block + object common)
Owners: **the SNC storage + compute-hardening team**
- Prepare baremetal node RAID (terraform-modules `hosts-storage/node-preparation/configure_storage_raid.py`)
- Prepare baremetal node LACP (`configure_storage_lacp.py`)
- Deploy/create instances with terraform (`hosts-storage/hosts-storage`)
- OS base config (NTP, artifactory logins, repos, hardened kernel — done with iRobox Ansible roles + GOR/irobox/ansible/roles) — refs [GSSNC-66](#) [GSSNC-69](#)
- Basic ceph deployment with `cephadm` via Ansible role (SNC/ansible-library/roles/ceph) — refs [GSSNC-64](#) [GSSNC-70](#)

### paas-snc block storage (specific)
- Ceph block storage deployment with Ansible role — same owners + same role base

### paas-snc object storage (specific)
- Ceph object storage deployment with Ansible role — same owners + same role base

### control plane (keycloak, keystones for object storage, Horizon, monitoring)
- Several sub-steps; all manual; owners: **Benjamin Hofer, proxy-image team, Aleksandr Mikheev, Martin Znamirowski, Asim Ijaz Ahmad**

### Federation steps (regional ↔ global)
- `federate_l2_keystone_with_bmpod_keycloak`
- `federate_l3_keystone_with_global_keycloak`
- `add_extra_l2_keystone_role_objectstore_admin`
- `add_extra_l3_keystone_role_objectstore_member`
- `add_identity_providers_s3_keystone_l2/l3`
- `add_mapping_s3_keystone_l2/l3`

## What this means for the milestones

- **M1** doesn't touch any of this — it's pre-control-plane, pre-account.
- **M2** touches a slice: deploy proxies, deploy proxy redis, manage TLS certs, manage DNS records, "Implement Keystone Controller & API" (the centerpiece of M2's red circle).
- **M3** is where ~80% of this list collapses into the `cloudstore-vm-bs-service` package + CloudStore Core. Specifically:
  - All proxy steps (currently manual, will live in cbs-cp via the Service control-plane TF)
  - All control-plane Keycloak/Keystone steps (Keystone Controller)
  - BL deployment ordering (move into a CloudStore Service or Core Service)
  - Federation chains (Keystone Controller + CloudStore API)
  - Logging to LDP / Loki (observability — overlaps with Pod #0 deferral)
  - Image build + push pipeline (use CloudStore Service Packager → Harbor 3AZ instead of `oci-artifact-mirror` + signed PR + CDS dance)
- **M4** is the airgap dimension on top of all of M3.
