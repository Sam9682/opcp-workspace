# OPCP - Managed Kubernetes

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 818641729](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=818641729) (v47, last modified 2026-07-07; re-synced 2026-07-15). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

|  |  |
| --- | --- |
| **Status** | Validated, implementation in progress |
| **Owner** |  |
| **Jira** | Projectsf0e70dd9-2bc3-31da-a16b-974623242708LVL2-20103 |
| **ETA** | Beta: 09/2026  GA: 01/2027 |

## Timeline

Octave / Yaniv are looking for delivery on OPCP && SNC in June 2026, by porting OVHCloud Managed Kubernetes Service (MKS) (decision taken on  during LSD).

### Q2FY26

Projectsf0e70dd9-2bc3-31da-a16b-974623242708LVL2-19716

|  | Topic | Cost |
| --- | --- | --- |
| WHAT | Build a dependency matrix: Public Cloud vs Cloud Store | **2 FTE during 1,5 months** |
| Identify components and feature dependencies |
| Anticipate SNC constraints and impacts |
| HOW | Cost estimation for components migration and/or adaptation | **2 FTE during 1,5 months** |
| How to transform MKS Public Cloud product into a "Packaged Product" : Package / Release management | **1 FTE during 1 month** |
| RACI for each deployment model (packaging, build, run, support levels,...) | **-** |

Excalidraw planning <https://excalidraw.ovhcloud.tools/document/3245ba7f-2173-467a-9668-bcaea490c6a2>

### Q3FY26: POC

Projectsf0e70dd9-2bc3-31da-a16b-974623242708LVL2-21811

Estimations indicate that the reachable state by June will have the following limitations

* Features available
  * Cluster basic features: create, delete, reset
  * OIDC
  * IPrestrictions
  * Loadbalancer management
  * Volumes management

* Limitations
  * No auth on the API for the e2e user (i.e the provisioning API), impact is that anyone is admin
    * can create/delete any cluster
    * obtain credentials for any cluster
    * ...
  * No cluster update (to confirm depending on the work done until the defined ETA)
  * No Autoscaler (relying on APIv6 for now)
  * Node pool management only available from MKS API (not via CRD)
  * No Self-healing
  * Not deployable on AirGap (only possible on "MinINT" shared environment Croix)

We all agree that this is the scope of a test environment and not a finalized GA product. The customer may perform functional and resiliency testing on it.

### Q1FY27: Beta

Customer expects a beta by October with

* Cloud Store packaging
  * Install
    * Control Plane with API v2
  * Uninstall
* Airgap documentation
  * Install
  * API documentation (v2) in product
  * Logs extract procedure (manual) → grep on  API-server (MKS Customer controle plane - layer 3)
* Additional features to the POC
  * Authentication
  * Cluster upgrades

### Q2FY27: GA

Customer expects a production version by **January** with

* Self-healing (must)
* Observability
* Service Lifecycle (control plane updates)
* Admin tools & procedures

### Out of scope

1. Private registry with Trivy (at risk, no bandwidth)
2. Node management using CRDs
3. Autoscaling
4. Readwrite many volumes
5. GPU flavors
6. Multiple MKS versions

## Related

## Functional requirements

### 1. Core Lifecycle Management (The "Update Engine")

*Goal: Provide a zero-downtime, unbreakable upgrade experience for customers and operators.*

#### 1.1 Cluster Upgrades

* **Granularity:**

  * **Control Plane Upgrades:** Must occur *before* worker upgrades.
  * **Worker Upgrades:** Rolling updates via MachineDeployments.
  * **OS Upgrades:** Handled immutably (replace node with new OS image) rather than in-place patching.
* **Trigger Mechanisms:**

  * **Manual Upgrades:** Customer triggers version bump via API/UI.
  * **Automatic Upgrades:** System auto-upgrades minor versions if configured by policy.
  * **Maintenance Windows:** Respect `spec.rollout.after` (CAPI) to ensure upgrades only happen during customer-defined windows.
* **Reliability & Performance:**

  * **Surge Nodes:** Provision new nodes *before* draining old ones to ensure capacity never drops (MaxSurge > 0).
  * **Multi-node Sync:** Capability to update batches of nodes simultaneously to reduce total upgrade time.
  * **Zero-Failure Standard:**

    * *Requirement:* Upgrade failure rate must be effectively 0%.
    * *Implementation:* "Atomic" upgrades. If a new node fails to join or pass health checks, the rollback is automatic, and the old node is not deleted.
  * **Rollback:** Manual and automatic rollback capabilities to the last stable state.

#### 1.2 Node Lifecycle

* **Recycling:** Ability to delete a specific node and have CAPI automatically provision a healthy replacement.
* **Reboot:** API capability to drain and reboot a node safely.
* **Self-Healing:** Automatic replacement of unhealthy nodes (failed health checks) without human intervention.

#### 1.3 Lifecycle Policy

* **Deprecation Plan:** Support for N-2 versions.
* **End of Life (EOL):** 6-month deprecation window.
* **Force Upgrades:** If a cluster remains on an EOL version past the window, the system forces an upgrade to the minimum supported version

### 2. Compute & Scaling Capabilities

#### 2.1 Control Plane (Master) Architecture

* **High Availability:** 3 Availability Zones (AZ) for ETCD and API Server.
* **Dynamic Sizing:**

  * Ability to resize Control Plane resources (CPU/RAM) vertically based on cluster load.
  * *Tech Note:* If using **Kamaji**, this is a Pod resize. If using **VMs**, this requires a VM resize/reboot.

#### 2.2 Autoscaling

* **Horizontal Scaling:**

  * **Node Pools:** Support for distinct MachineDeployments (e.g., "General Purpose," "High Memory").
  * **Autoscaler:** Cluster Autoscaler integration with CAPI.
  * *Investigation:* Evaluate **Karpenter** for CAPI. (Note: Karpenter is faster but complex to implement on-prem; standard Cluster Autoscaler is the MVP).
* **Vertical Scaling:** "Right-sizing" recommendations for worker nodes (or vertical autoscaling if using virtualization features).

#### 2.3 Scheduling Logic

* **Taints & Tolerations:** Full support for dedication logic (e.g., dedicating nodes to specific teams).
* **Affinity Zones:** Anti-affinity rules to ensure worker nodes for a single deployment are spread across physical racks/zones.

### 3. Networking & Connectivity

* **Global Load Balancer:**

  * Single endpoint for the API Server across AZs.
  * Integration with **Octavia** (OpenStack) or external HW Load Balancer.
* **CNI:** Cilium (as per Known Knowns).
* **Network Policies:** Customer ability to define ingress/egress rules (enabled by Cilium).
* **Private Clusters:**

  * Option for "Private Only" API access (no public Internet exposure).
  * VPN/Peering required for customer access.
* **DNS:** Managed CoreDNS setup.

### 4. Enterprise Value Features (The "Selling Points")

#### 4.1 Billing & Reporting (High Priority)

* **CloudStore Integration:** Push metrics to the central billing engine.
* **Granular Reporting:**

  * Usage reporting per **Cluster**.
  * Usage reporting per **Namespace** (CPU/RAM requests vs. limits). *Crucial for customers doing internal chargebacks.*

#### 4.2 Security & Compliance

* **Certificate Handling:** Automatic rotation of internal K8s certificates (ETCD, API) and admin certificates.
* **Audit Logs (v2):**

  * Configurable Audit Policy.
  * Logs shipped to an external sink (Customer S3 or similar).
* **Alerting:**

  * Default alerts for "Cluster Down," "Node Not Ready," "High API Latency."

### 5. Storage Strategy

#### 5.1 Core Storage

* **Block Storage:** Cinder integration via CSI.
* **Redundancy:** 3AZ replication for persistent volumes.

#### 5.2 Lower Priority / Day 2

* **RWX Volumes (ReadWriteMany):** Shared storage (NFS/CephFS) support. *Marked as "Quick Win" candidate.*
* **Local Storage:** Passthrough local disk for high-performance workloads (logging/caching).

### **6. Cloud Store + SNC integration**

#### 7.1 IAM

* Accounts can own multiple clusters, and all users in an account should be able to see all clusters - this is managed through our Keycloak IAM which we should hook into.

#### 7.2 Observability

* Layer 2 customers should be able to debug all clusters and the control plane
* Layer 3 customers should only be able to debug their own clusters
* The observability platform for cloud store isn't planned in yet, so we might need to go with native observability first

#### 7.3 KMS

* We will have a KMS platform for l3, which can be used by customers to encrypt their own resources
* Layer 2 KMS isn't on the roadmap yet.

#### 7.4 SNC Certification

* We should involve pu.snc in q2 2025 to validate cluster and cloud store for potential certification.

## Roadmap & Prioritization Matrix (DRAFT)

| Feature Set | **P0: MVP (Must Have)** | **P1: Enterprise Ready (Should Have)** | **P2: Optimization (Could Have)** |
| --- | --- | --- | --- |
| **Lifecycle** | Auto-Upgrades, Rollbacks, 0% Failure logic, Force Upgrades | Maintenance Windows, Multi-node sync |  |
| **Compute** | 3AZ Control Plane, Node Recycling, Cluster Autoscaler | Dynamic CP Sizing | GPU Worker Nodes, Surge Node tuning |
| **Network** | Global LB, Private Clusters, Network Policies |  |  |
| **Storage** | 3AZ Block Storage |  | RWX Volumes, Local Storage |
| **Observability** | Cluster Health Alerts | **Namespace Usage Reporting** (Billing) | Granular Metrics for Customers |
| **Security** | Cert Rotation, RBAC | Audit Policy v2 |  |
| **UX** |  | Provision DB via YAML |  |

## Technical requirements

* VM
* LB
* Arsenal
* S3 for backups

