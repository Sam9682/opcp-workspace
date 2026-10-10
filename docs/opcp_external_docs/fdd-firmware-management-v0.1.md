# OPCP Core — Firmware Management
## Feature Design Document — v0.1

| | |
|---|---|
| **Status** | Draft — Functional Spec Complete, Awaiting Technical Design |
| **Version** | v0.1 |
| **Date** | 2026-06-16 |
| **Document owner** | OPCP Product Team |
| **Audience** | Customer IT Administrator, Security Architect, Platform Operations |
| **Classification** | Restricted — Design Partners (NDA) |

---

## 1. Overview

### 1.1 What this feature delivers

**Firmware management** covers the full lifecycle of firmware across every hardware component in an OPCP deployment — from inventory and alerting through controlled update, validation, and rollback.

Keeping firmware up to date is a security obligation: unpatched firmware is a persistent attack surface that bypasses OS-level defences and is typically invisible to standard vulnerability scanners. At the same time, an uncontrolled firmware update can break certified workloads. The tension between *must patch* and *must not break* requires a structured, auditable process.

This feature gives IT Administrators a **single pane of glass** for firmware state across all managed hardware, automated alerting when out-of-date components are detected, a safe update procedure triggered through the standard OPCP node-management API, and a verified rollback path. OVHcloud manages the upstream qualification and distribution of firmware bundles; customers apply them on their schedule.

### 1.2 Intended audiences

| Audience | Relevant sections |
|---|---|
| **IT Administrator** | §2 (capabilities), §3 (features), §5 (operational model), §6 (service levels) |
| **Security Architect** | §2 (capabilities), §3 (alerting), §5 (policy), §6 (CVE response) |
| **Platform Operations** | §3 (features), §4 (supported hardware), §5 (RACI), §6 (service levels) |

---

## 2. Service Capabilities

### 2.1 What the IT Administrator can do

- View a **complete, real-time firmware inventory** for every managed hardware component — out-of-band, without requiring OS access to the target machine.
- **Export the firmware inventory** for compliance reporting, asset management tooling, or audit evidence.
- **Trace every firmware version change**: when it was applied, which node, which component, and from which bundle.
- Receive **automated alerts** when any component's firmware falls behind the currently qualified version, categorised as a security-priority alert.
- **Trigger a firmware update** on a specific node (or a set of nodes) through the standard OPCP management API — the platform handles the update procedure, including rebooting through the Ironic clean lifecycle without wiping tenant data.
- **Roll back** a firmware update to the previous known-good version when a regression is detected.
- Trust that when a bare-metal node is **de-provisioned**, any tenant-applied firmware changes are reverted before the node is returned to the pool.

### 2.2 Out of scope (V1)

| Item | Note |
|---|---|
| Fully automated (no-touch) firmware updates | Updates are IT Admin-triggered; no autonomous self-update |
| Real-time streaming firmware telemetry | Inventory is polled / event-driven, not a live stream |
| Firmware updates without a node reboot | Depends on hardware vendor support; the default path reboots through Ironic clean |
| Distributed firmware update tooling for customer-managed components (outside OPCP) | Only OPCP-managed hardware is in scope |
| Network equipment firmware (Arista / Cisco) — full automation | Vendor tooling is referenced; OPCP-native automation is roadmap |

### 2.3 Known limitations (at V1)

| Limitation | Detail |
|---|---|
| Hardware qualification gates out-of-band reporting | Only components that expose firmware version via out-of-band interfaces (IPMI/Redfish) are tracked automatically. Components that cannot be reported are documented in the hardware qualification catalogue. |
| Firmware update requires node clean | The Ironic clean workflow is used; this does not wipe tenant workload data but does require a controlled maintenance window for the affected node. |
| Tenant-applied firmware (bare metal) is reverted on de-provision only | If a bare-metal tenant flashes firmware during their lease, OPCP detects and reverts this only at de-provision time, not continuously during the lease. |
| Two consecutive OPCP versions maintained | OVHCloud qualifies firmware for the two currently active OPCP versions only. Deployments on older versions are outside the update policy. |

---

## 3. Feature Catalogue

### Inventory & visibility

| Capability | Notes |
|---|---|
| Out-of-band firmware version reporting | Polled via IPMI/Redfish without OS access |
| Per-component version tracking | BIOS, BMC, disks, RAID controllers, NICs, GPUs (VBIOS) |
| Exportable inventory | CSV/JSON export for compliance and asset management |
| Version history per component | Audit trail: when each version was applied and by which operation |
| CMDB (Netbox) integration | Firmware version and history surfaced in Netbox; OpenStack API provides the same data before full Netbox integration ships |
| Components without out-of-band reporting documented | Hardware qualification catalogue lists any exceptions |

### Alerting

| Capability | Notes |
|---|---|
| Automated alert: firmware out of date | Alertmanager rule; security-related category; medium severity |
| Alert scope | Per-component, per-node |
| Alert destination | Customer SIEM / notification channel (configurable) |
| Alert suppression during planned update windows | TBD — depends on Alertmanager configuration |

### Update management

| Capability | Notes |
|---|---|
| IT Admin-triggered update via OPCP API | `ironic node-clean` lifecycle; no manual SSH |
| Security release bundle | OVHCloud-qualified bundle containing firmware + changelog + supported-platform test results |
| Parallel node updates | Multiple nodes can enter the clean/update workflow in parallel |
| Supported-platform validation gate | Bundle release is gated on successful regression tests for all officially supported OPCP workloads (see §5.2) |
| Changelog published with every bundle | Contents, qualifying test summary, CVE references where applicable |

### Rollback

| Capability | Notes |
|---|---|
| Previous version retained locally | The immediately preceding qualified version is stored on the deployment so any node can be rolled back without network access |
| IT Admin-triggered rollback | Same API trigger as update; selects the previous pinned version |
| Pinning | A specific node can be pinned to the previous version temporarily (e.g. while a regression is investigated) |

### Tenant isolation

| Capability | Notes |
|---|---|
| Tenant firmware reversion on bare-metal de-provision | When a bare-metal node is returned to the pool, OPCP verifies and restores the qualified firmware baseline |
| Detection of tenant-applied changes | Firmware version delta detected at de-provision time via out-of-band interface comparison against CMDB baseline |

---

## 4. Supported Hardware & Components

### Target hardware

| Category | Models / Variants |
|---|---|
| **Controllers** | OPCP Core controllers |
| **Switches** | Arista (ToR) · Cisco |
| **Servers** | SCALE-1 · HPE Gen11 |
| **PDUs** | Managed PDUs (vendor TBC) |

> Note: Arista switch firmware automation is a roadmap item. OPCP V1 covers inventory and alerting for switches; the update path uses vendor tooling (EOS).

### Target components per server

| Component | Out-of-band reporting | Update via Ironic |
|---|---|---|
| BIOS | Yes (Redfish) | Yes |
| BMC | Yes (IPMI/Redfish) | Yes |
| Disks | Vendor-dependent — qualified per model | Vendor-dependent |
| RAID controllers | Vendor-dependent | Vendor-dependent |
| Network cards (NICs) | Yes (Redfish where supported) | Yes |
| GPUs (VBIOS) | Yes (where VBIOS exposed via OOB) | TBC |

> The hardware qualification process is the gate: a component is tracked in the inventory only if out-of-band firmware reporting is confirmed during qualification. Any component that cannot be reported is listed as an exception in the hardware catalogue with a manual inspection procedure.

---

## 5. Firmware Management Policy

OVHCloud commits to the following firmware lifecycle policy:

- **Monitoring**: OVHCloud actively monitors manufacturer security advisories and firmware release channels for all hardware in the OPCP supported hardware list.
- **Qualification cadence**: When a new firmware release contains a security fix or major problem fix, OVHCloud targets qualification and release of an updated bundle **within 1 month** of the upstream release.
- **Supported-version coverage**: OVHCloud maintains qualified firmware for the **two currently active OPCP major versions**. Older deployments are outside the update policy scope.
- **Regression testing**: Every bundle is validated against:
  - The full Ironic node lifecycle (provisioning, de-provisioning, reboot, clean)
  - All officially supported third-party platforms deployed on OPCP (e.g. Debian, VMware Cloud Foundation)
- **Distribution**: Bundles are distributed as OCI artefacts, compatible with air-gapped local Harbor deployments. No external connectivity is required to receive updates.
- **Changelog**: Every bundle ships with a changelog listing firmware versions, target components, CVE references, and test results.

---

## 6. Service Levels

### 6.1 Update SLA targets

| Event | Target |
|---|---|
| Security / major fix firmware bundle released by OVHCloud | Within **1 month** of upstream release |
| IT Admin-triggered node firmware update (single node, clean workflow) | Duration determined by hardware vendor + Ironic clean time; typically **30–90 minutes** per node |
| Rollback to previous version | Same duration as update |

### 6.2 CVE response (firmware bundles)

| Severity | Target bundle release time |
|---|---|
| Critical (CVSS ≥ 9.0) | ~7 days |
| High (CVSS 7.0–8.9) | ~14 days |
| Medium (CVSS 4.0–6.9) | ~30 days |
| Low | Next scheduled bundle |

> CVE response timelines mirror the OS/software patching commitments for the platform and apply to firmware with confirmed CVE assignments from hardware vendors.

### 6.3 Air-gap operation

All firmware bundles are distributed as OCI artefacts and can be pre-loaded into the local Harbor registry. No external connectivity is required to apply firmware updates in an air-gapped deployment.

---

## 7. Related Resources

- [Ironic firmware update documentation](https://docs.openstack.org/ironic/latest/admin/firmware-updates.html#how-it-works-via-firmware-interface)
- [OPCP Core — Compatibility with 3rd party platforms](https://confluence.ovhcloud.tools/display/CPO/OPCP+Core+-+Compatibility+with+3rd+party+platforms)

---

## 8. Appendix

### 8.1 Glossary

| Term | Definition |
|---|---|
| **OPCP** | On-Premises Cloud Platform — OVHcloud's converged private-cloud stack, running on customer hardware |
| **Ironic** | The OpenStack bare-metal provisioning service used by OPCP; firmware updates are triggered through its node-clean workflow |
| **Ironic clean** | A lifecycle operation that runs a configurable set of cleaning steps on a node, including firmware update, before returning it to the available pool |
| **CMDB** | Configuration Management Database — Netbox in OPCP; the authoritative record of hardware inventory including firmware versions |
| **Out-of-band (OOB)** | Management access to hardware that does not require the OS to be running — via IPMI, iDRAC, iLO, or Redfish |
| **Redfish** | A modern DMTF standard for out-of-band hardware management; used by OPCP to query and update firmware on supported components |
| **IPMI** | Intelligent Platform Management Interface — the legacy OOB protocol; used alongside Redfish for older hardware |
| **Security release bundle** | An OVHCloud-produced artefact containing qualified firmware binaries, a changelog, CVE references, and regression test results |
| **Alertmanager** | The Prometheus alerting component used by OPCP; firmware drift alerts are implemented as Alertmanager rules |
| **PU.Bare Metal** | OVHCloud's Bare Metal product unit — responsible for firmware qualification and bundle assembly |
| **SNC** | SecNumCloud — the French ANSSI-certified sovereign cloud framework; firmware CVE response timelines are aligned with SNC commitments |
| **Air-gap** | A deployment with no external network connectivity; firmware bundles are delivered via the local Harbor OCI registry |

### 8.2 Revision history

| Version | Date | Author | Changes |
|---|---|---|---|
| v0.1 | 2026-06-16 | OPCP Product Team | Initial draft — functional spec from Confluence source |
