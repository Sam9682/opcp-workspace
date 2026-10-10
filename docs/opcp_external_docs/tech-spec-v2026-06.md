---
id: core/opcp-core-tech-spec-v2026-06
type: deep-dive
diataxis: reference
title: "OPCP Core — Technical Specification v2026-06 (distill + delta)"
owner: sov-copilot
status: approved
publish_target: git
product: opcp-core
---

# OPCP Core — Technical Specification v2026-06 (distill + delta)

> **Source:** PDF *"Technical Specifications — OPCP Core, Release v2026-06"* (valid for **OPCP 3.0.0**), received 2026-06-10 via Marc. This is the **official, final-picture tech spec** for OPCP Core — written exactly in the target-state style Florent's Tech-Specs definition asks for (and the model for our CB spec pivot).
> **§B below = what's NEW vs. our workspace knowledge** — the delta Marc asked for. Facts here describe the **platform contract**, not vision (contrast: [`generic/product-vision/`](../../../../../generic/product-vision/README.md)).

---

## A. Distilled reference

### A.1 Controller & topologies

- **OPCP Controller** = the central management node: K3S-based control plane running OpenStack, Keycloak IAM, observability, config tooling. Hardened immutable OS, IaC-managed. Operator interfaces: **`opcp-cli`** + web (Horizon / Grafana / NetBox via "OPCP Dashboard").
- **Topologies:** **1× single controller** (single-rack / PoC, no redundancy) · **3× HA cluster** (required for Standard/Fabric production; active/active K3S HA + embedded etcd; L4 LB via Cilium/Traefik).
- **Reference controller HW:** HPE ProLiant **DL325 Gen11** (1U) · 1× AMD EPYC 9115 (16c/32t) · 64 GB DDR5 ECC · 2× 960 GB NVMe (SW-RAID 1, OS) + 4× 1.92 TB NVMe (data) · 4× 25 GbE SFP28 + 1 GbE mgmt · iLO 6. *(The OS-disk SW-RAID-1 + LVM layout is laid down by the [Controller Debian Image installer](../controller-debian-image/summary.md#3-the-disk-layout--software-raid-1--lvm-the-core-substance) — the concrete "how" of this line.)*
- **Controller NICs (4):** OOB 25 GbE (admin/BMC reach) · ToR-mgmt 1 GbE · Provisioning+BMC 25 GbE (PXE/TFTP, Ironic) · OVS/Neutron data 25 GbE.

### A.2 Software stack (containerized on K3S)

Debian 12 host (vanilla kernel) · K3S · **Keycloak** (OIDC+SAML broker) · PostgreSQL · **Prometheus + Thanos + AlertManager** · Grafana (Community) · Loki · Traefik · Cilium (eBPF CNI + Hubble) · **Ceph S3 gateway (internal-only)** · FluxCD (GitOps) · **Barbican** (OpenStack secrets) · cert-manager · **Velero** (CP backup/DR).

### A.3 Networking

- SDN L2 fabric: Neutron + OVS. **MTU 9000 end-to-end** (mandatory on all physical switching). **802.1Q** VLANs.
- **No in-transit encryption at the data plane** — isolation via VLAN segmentation + controller-level policies; tenants needing crypto must do app-layer encryption.
- **Max 2,000 Neutron networks per Pod.**
- **QinQ (802.1ad) required on the customer backbone** when multiple 3rd-party hypervisor platforms (VCF, Nutanix, Proxmox) share one Neutron network — alternatives: dedicated Neutron net per tenant/platform, or L3-introspecting router/firewall.
- **Per-BM-server uplinks:** 2× 25 GbE data (LACP-bonded *where supported*) · 1× 25 GbE provisioning (PXE/Ironic) · 1× 25 GbE management.
- Rack-to-edge: Nano optional +100 GbE; Standard/Large 4–6× 100 GbE per rack.
- Switches: ToR/Edge **Arista DCS-7050CX3-32S** (MLAG, LACP, VXLAN, BGP EVPN, MTU 9000) · IPMI/OOB **Cisco C9200-48T**. *(SKU note 2026-06-15: the OVH **Local Zone** uses the `-R` variant — **`DCS-7050CX3-32S-R`** (`-R` = rear-to-front / reversed airflow; same switch + feature set otherwise). OPCP's hardware catalog follows the LZ BOM, so it is effectively the same switch — only the airflow SKU may differ per rack hot/cold-aisle orientation. Confirm `-R` vs base for the OPCP rack with the network/HW team.)*
- DC envelope: half-rack 5–12 kW / full-rack 5–15 kW (excl. GPU), 10–35 °C, PDU 2× 32A 3Ø + 2× 16A 1Ø.

### A.4 Bare-metal provisioning (Ironic)

- **UEFI only** (no legacy BIOS) · PXE/TFTP · **QCOW2 only** (Glance-streamed) · KVM console via Horizon.
- Network configs: standalone, **active/passive bonding**, LACP 802.3ad (Neutron trunking needs cloud-init).
- **Pre-built BM images:** **Debian 12 (default production — NO LACP via Ironic)** · **Debian 13 (the one supporting LACP at provisioning)** · CentOS Stream 9 (no LACP). Custom QCOW2 accepted.
- **Disks: SEDs mandatory** — TCG Opal 2.0/2.01, **AES-256 XTS hardware-enforced (cannot be disabled)**, **Instant Secure Erase at decommissioning**, **software RAID 1 only (no HW RAID)**.

### A.5 Observability

- 4 pillars internal to the controller cluster (no external deps): Prometheus+Thanos / Loki / AlertManager / Grafana.
- **Metrics retention tiers:** Hot 7 d or 20 GB (raw, local TSDB) → Warm 30 d (5-min downsample, Ceph S3 ≤200 GB) → **Cold 10 y** (1-h downsample, Ceph S3 ≤200 GB).
- **Logs:** 7 d or 50 GB default · **syslog-forwarding with TLS for external SIEM**. Sources: BMC event log (PSU/fan/temp/ECC/watchdog…) + K8s + OpenStack services.
- 14 built-in Grafana dashboards (OpenStack health, Ironic BM metrics, K8s, Ceph, PostgreSQL, Cilium/Hubble, FluxCD, BMC events, controller host, cert expiration…).

### A.6 Backup & recovery

- PostgreSQL **full backup hourly, 30 d retention, PITR** · KMS secrets hourly (encrypted at rest) · Glance images hourly · OCI artifacts daily · `/opt/opcp` config on each `opcp-cli deploy`. Footprint ~300 GB.
- Backend = internal Ceph S3 — **no server-side encryption at the S3 layer**.
- `opcp-cli restore`: full / PITR / selective (KMS, Glance, OCI independently).

### A.7 Security

- **IAM:** dedicated Keycloak = OIDC/SAML IdP for everything (Horizon, Grafana, K8s API, Terraform). MFA TOTP per role. AD/LDAP sync + external-IdP federation.
- **Built-in RBAC:** Master Admin (platform-wide incl. IAM) · IT Admin (infra, no IAM changes) · DC Operator (physical layer, read CMDB/IPMI) · Member / Reader (per OpenStack project). Project access via **custom attribute on role/group/user**. **Two realms: Master realm** (built-in roles) + **Pod realm** (separates platform admins from OPCP-Core users — e.g. SecNumCloud contexts).
- **KMS:** built-in, internal-only — SED keys + ISE authorization, backup-secret keys, TLS private keys. **External HSM / 3rd-party KMS NOT supported in the current release.**
- **TLS 1.2+** everywhere; CA modes: platform self-signed CA (auto-issue/rotate) or **customer-provided CA import**.
- Segmentation: L2 VLAN isolation (mgmt/provisioning/tenant/OOB strictly separated, physical + OVS) · L3/L4 Cilium eBPF micro-segmentation in the CP.

### A.8 Configuration & IaC

- Declarative IaC: authoritative config = **local git repo on the controller** (FluxCD); changes via `opcp-cli` (validate→commit→reconcile). `/opt/opcp` holds service overrides, network topology (VLAN maps, IP plans, uplinks), Keycloak realm exports, alerting/dashboards.
- **Terraform:** official OpenStack + Keycloak providers supported, BUT: **auth = OpenStack application credentials only (no OIDC to Keycloak from TF)**; **advanced Ironic features (LACP bonding, HW-RAID config) NOT exposed via the TF provider** → `opcp-cli`/Ironic API directly.

### A.9 CMDB / DCIM (NetBox)

Auto-synced with Ironic live inventory: racks, switches, BM servers (incl. Ironic Node ID, BMC IP), provisioned instances, full IPAM (prefixes/VLANs/roles). Operator features: **"Atelier" tab** (Ironic log history, HW checks, Horizon/KVM links, power control) · Journal (free-text ops log) · automatic Changelog audit trail.

### A.10 Constraints & known limitations (the official list)

No data-plane in-transit encryption · **LACP via Ironic only on Debian 13** (12/CentOS need custom workaround) · no HW RAID (SW RAID 1 only) · SED can't be disabled · TF: no Keycloak-OIDC, no advanced-Ironic · **no S3 server-side encryption on backups** · **no external HSM/KMS** · QinQ requirement (3rd-party hypervisor sharing) · ≤2,000 Neutron networks · internal Ceph S3 not externally accessible.

---

## B. Delta — what's NEW vs. our workspace knowledge (2026-06-10)

| # | New fact (spec) | Impact on our work |
|---|---|---|
| 1 | **LACP via Ironic only on Debian 13**; Debian 12 = default prod image *without* LACP support; active/passive bonding supported everywhere | 🔴 **Direct hit on SOV-694 / Deep×OpenShift**: the platform contract itself says LACP-at-provisioning is the exception, active-backup the broadly-supported path — strengthens the active-backup track (Alex). Also clarifies the CB image confusion: **BM-provisioning images** (Debian 12/13) ≠ **guest images** (datasheet "Debian 13 vanilla" / matrix "Debian 12 CIS") — two different layers. |
| 2 | **External HSM / 3rd-party KMS not supported** in current release | ~~An HSM story would be net-new platform work — sizing input for the SNC qualification.~~ **✅ Resolved 2026-06-10 (Marc): kein externes HSM nötig — Key Store = KMS/OKMS** (SNC-etabliert). The platform fact is therefore *consistent* with the chosen line, not a gap. NSQ-023 closed; residual verification (OKMS vs ANSSI custody expectations) rides the NSQ-025 qualification track. |
| 3 | **No in-transit encryption at the data plane** (VLAN isolation only) | FDD §5 (Security) material for CB **and** NS; SNC threat-model input. Tenants needing encryption → app-layer. |
| 4 | **Max 2,000 Neutron networks per Pod** + **QinQ requirement** for shared 3rd-party hypervisor networks + **MTU 9000 mandatory** | Sizing/requirements rows for CB tech-spec Ch5 + NS planning; QinQ = customer-backbone prerequisite to surface in FDDs. |
| 5 | **Per-server uplink layout: 2×25 data + 1×25 provisioning + 1×25 mgmt** | ⚠️ **Differs from the Cloud-Store datasheet** ("2 ports LACP host + 2 ports LACP VMs, 3 trunk VLANs") quoted in our CB tech-spec Ch2 `[verify]` — reconcile with Damien/network squad which layout applies to CB hypervisor hosts. |
| 6 | **Thanos** (metrics archival: 7d/30d/**10y** tiers, Ceph-S3 ≤200 GB) + **Velero** (CP backup) + AlertManager + cert-manager in the Core stack | Extends our observability picture (we tracked Prometheus/Loki/Grafana); **syslog-TLS forwarding for external SIEM** is the official answer-shape for Q-219 (on-prem log destination). |
| 7 | **No server-side encryption on the S3 backup layer** | Security/audit flag for SNC contexts (worth a question to the platform team — backup content incl. KMS secrets is itself encrypted, the S3 layer is not). |
| 8 | **SED mandatory (AES-256 XTS, hw-enforced) + ISE at decommissioning + software RAID 1 only, UEFI-only, QCOW2-only** | Confirms + sharpens our BM-layer picture: explains the IPA downstream PRs (SED/RAID fixes #13/16/17), aligns with SOV-271 (RAID-TF = software RAID), SOV-488 hardening scope, and the "revert to safe state on de-provision" firmware-brief requirement (ISE!). |
| 9 | **Terraform constraints:** app-credentials only (no Keycloak-OIDC), advanced Ironic (LACP/RAID) not in the TF provider → `opcp-cli`/Ironic API | Context for our operator/TF work (the provisioner pattern can't drive LACP/RAID via TF — matches what the squad builds around). |
| 10 | **RBAC built-ins** (Master Admin / IT Admin / DC Operator / Member / Reader) + **Master- vs Pod-realm** split; project access via custom attribute on role/group/user | Slots underneath the SOV-583 Option-4 model as the **L1/Core layer** — the custom-attribute mechanism is exactly the group-attribute machinery SOV-583 builds on. Useful for the CB tech-spec Ch4 IAM stack picture. |
| 11 | **`opcp-cli`** as the single operator entry point + "OPCP Dashboard"; **OPCP 3.0.0** release versioning; controller reference HW (DL325 Gen11) + DC envelope (5–15 kW etc.) | Runbook-relevant vocabulary + the hardware/DC requirements rows our CB tech-spec Ch5 was missing (controller side). |
| 12 | **NetBox "Atelier" tab / Journal / Changelog** operator features | Directly useful for the runbooks we owe (baremetal-node-recovery, firmware design phase — the inventory/traceability substrate exists). |

**Format note:** this spec IS the template for the CB target-state pivot — final-picture, present tense, constraints table at the end, no build-status noise. Our `cb-tech-spec.md` restructure should mirror its chapter shape.

## Cross-references

- [`generic/product-vision/`](../../../../../generic/product-vision/README.md) — the VISION mirror (product intent; this spec = platform contract).
- [`products/cloudstore/misc/compute-block-on-cloud-store/architecture/cb-tech-spec.md`](../../../../cloudstore/misc/compute-block-on-cloud-store/architecture/cb-tech-spec.md) — CB spec (Ch2 host-topology `[verify]` ↔ delta #5; Ch4 ↔ #3/#10; Ch5 ↔ #4/#11).
- NS [`open-questions.md`](../../../../cloudstore/misc/network-service-lb-l3-gateways/open-questions.md) — NSQ-023 (HSM, delta #2) · Q-219 via CB (SIEM, delta #6).
- BAU LACP active-passive (private) — delta #1.
