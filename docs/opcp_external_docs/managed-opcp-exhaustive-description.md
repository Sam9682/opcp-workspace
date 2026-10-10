# Managed OPCP Exhaustive description

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 878636848](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=878636848) (v49, last modified 2026-06-23; re-synced 2026-07-15). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

|  |  |
| --- | --- |
| **Status** | Version 1 |
| **Owner** | Manuel Jenne |

2true

# Purpose

This document serves to comprehensively define the scope, responsibilities, and methodologies through which OVHcloud delivers the managed services for the On-Premise Cloud Platform (OPCP).

This offering, herein referred to as "Managed OPCP," is designed to provide customers with a fully operational, monitored, and maintained private cloud environment deployed within their own data center or a co-location facility, leveraging OVHcloud's expertise in cloud infrastructure management.

# Objective and Scope

The primary objective of the Managed OPCP service is to relieve the customer of the day-to-day operational burden associated with managing a complex cloud infrastructure.

The scope of this document encompasses all essential managed services necessary for the sustained health, performance, security, and availability of the underlying OPCP components, including but not limited to:

* **Service Operation & Monitoring**
* **Incident and Problem Management**
* **Change & Release Management**
* **Service Request Fulfillment**
* **Configuration & Asset Management**
* **Capacity and Performance Management**
* **Security & Compliance Operations**
* **Backup, Recovery & Continuity**
* **Vendor & Third-Party Management**
* **Documentation & Knowledge Management**
* **Reporting & Service Governance (SDM Role if provided)**

Some topics mentioned in this document are part of OPCP Core and not belong to Managed OPCP.

# Service Delivery Model

The Managed OPCP service is delivered through a managed approach where OVHcloud takes responsibility for the infrastructure layer (IaaS) up to the hypervisor, and potentially the core cloud orchestration tools, depending on the specific service agreement.

The customer retains responsibility for the workload deployed on the platform (e.g., virtual machines, containers, applications) and the management of operating systems and applications running within those instances.

By opting for the Managed OPCP offering, customers benefit from:

* **Reduced Operational Expense (OpEx):** Shifting the burden of infrastructure management to OVHcloud eliminates the need for specialized in-house staff dedicated to maintaining the cloud platform.
* **Enhanced Reliability and Availability:** Leveraging OVHcloud's established processes and expert teams ensures higher service uptime and faster incident resolution.
* **Focus on Core Business:** Freeing up internal IT resources to focus on strategic, value-generating activities and application development rather than infrastructure maintenance.
* **Security and Compliance:** Regular patching and configuration management adherence to best practices contribute to a more secure and compliant cloud environment.

This document serves as the foundational agreement detailing the operational partnership between OVHcloud and the customer for the Managed OPCP service.

# Service Operation & Monitoring

**Proactive Service**: Primary focus on anticipating and preventing platform impairments through continuous monitoring and preventive maintenance ensuring steady state operations.  
**Indirect Engagement**: Customers engage with regular OVHCloud support teams. In turn, Managed OPCP team may engage directly with customer IT teams when required.  
**Platform Scope**: Coverage includes OPCP Core and Cloud Store foundational infrastructure, OVHcloud built Cloud Applications and OPCP Landing Zone Manager.

## In-Scope OPCP components

|  |  |  |
| --- | --- | --- |
| **Component** | **Key Elements Managed** | **Operational Responsibility** |
| **OPCP Core** | Compute, storage, and network infrastructure; Orchestration & automation layers; Platform APIs & control plane; Full lifecycle management (deployment, upgrade, retirement). | **Full Operational Responsibility** (OVHcloud owns end-to-end operation, health, and evolution of the platform). |
| **Cloud Store** | Application marketplace catalog; Service deployment automation; Integration with OPCP Core; OVHcloud built lifecycle updates. | **Platform Layer Only** (OVHcloud manages the store mechanism and OVHcloud made services; customer manages applications deployed by himself on OPCP Core or Cloud Store). |

## Cloud applications Services Matrix

|  |  |  |  |
| --- | --- | --- | --- |
| Cloud applications  Services | Examples | Packaging /  Integration | Managed  Services |
| OVHcloud Built | OpenStack instances, Block Storage, Object Storage… | ✅ | ✅ |
| OVHcloud Packaged | VMware Cloud Foundation (VCF) | ✅ | ❌ |
| Customer/External | 3rd party ISV solutions, custom applications  (Openshift) | ❌ | ❌ |

## Monitoring of systems and services

Continuous 24/7 monitoring of all components to proactively identify and respond to potential issues including but not limited to:

* **Platform Health Metrics:** Tracking key indicators of system health (e.g., service restart counts, internal API latency, control plane availability).
* **Service Availability:** Real-time checking of the accessibility and responsiveness of critical platform services.
* **Resource Saturation:** Continuous assessment of resource pools (CPU, RAM, Storage, Network) against defined utilization thresholds.

## Monitoring of hardware (Server / Network switches)

The essential operational functions of all underlying hardware (servers, networking equipment, storage arrays) are monitored continuously on a 24/7 basis.

**Hardware Failure Response**: In the event of a detected hardware failure, OVHcloud initiates remedial action, which includes coordinating the diagnosis, securing replacement components, and managing the repair or replacement process in cooperation with the manufacturer/vendor.   
**Service Contracts**: OVHcloud is responsible for securing and maintaining all necessary service contracts, warranties, and support agreements for the platform hardware.   
**On-Site Access**: It is a mandatory requirement that the customer grants OVHcloud employees or authorized subcontractors the appropriate level of access to the data center facility and the OPCP environment to perform necessary on-site diagnostics, troubleshooting, and repairs. The customer is required to provide the necessary secure process and procedures for enabling and governing such On-Site interventions.

## Alert management

All alerts triggered by monitoring are categorized according to their urgency in accordance with Incident Priority Definition and treated as incidents. OVHcloud has a structured process for handling monitoring alerts.

## Service health reporting

This will be performed by the TAM.

## Self-service catalog (Cloud Store) support

Alerts triggered by the Cloud Store or the OVHCloud Services deployed through it are handled by the OVHCloud teams; it includes deployment failures, cluster scaling failures, control planes issues, etc... In other terms, any management feature covered by the Cloud Store API/UI and relative to an OVHCloud Service (i.e, excluding third party service) should be considered part of OVHCloud scope.

## Remote access

OVHcloud will establish and maintain secure, audited remote access mechanisms to enable all necessary operational, maintenance, and repair activities by OVHcloud teams.  
Remote access is mandatory for managed OPCP, 24/7.  
Technical details are defined in APPENDIX REMOTE ACCESS

# Service Desk, Incident & Problem Management

The Managed Service will apply the process defined in the T&Cs.

## Restore service during incidents

The primary objective of Incident management is the shortest possible time-to-restore (TTR) of the impacted service.

## Root cause analysis for recurring or major incidents

All P1 incidents, or those that exhibit a repeating pattern, trigger a formal Problem Management process, including a detailed RCA report.

## Implementation of preventive actions

Problem Management outputs include formal recommendations for permanent fixes, known as Preventive Actions, which are then fed into the Change Management process.

## Incident reporting

OVHcloud will promptly notify the customer upon the detection of an incident categorized as P1 through P2.

# Change & Release Management

Defined processes for managing and documenting all changes to the OPCP environment to maintain stability and prevent unauthorized modifications.  
Scheduled deployment of security patches, bug fixes, and version upgrades for the core OPCP software stack to ensure compliance and access to the latest features.

## Plan, review, and execute changes

A **Change** is formally defined as any addition, modification, or removal of anything that could potentially have an effect on the OPCP platform or its services. Specifically, this refers to any alteration to the underlying cloud infrastructure components managed by OVHcloud: hardware, network configuration, virtualization layer, core cloud orchestration software, and associated configurations.   
**Ownership**: All changes within the managed scope will be planned, rigorously reviewed, and executed exclusively by the OVHcloud operation team.

**Change Notification and Scheduling**:

|  |  |  |
| --- | --- | --- |
| **Change Type** | **Communication Lead Time** | **Scheduling Constraint** |
| **Standard/Routine Changes** (No planned service interruption) | 1 business day | Executed **only during standard working hours** (or as otherwise agreed). |
| **Significant Changes** (With planned service interruption) | 5 business days | Executed during **working hours or scheduled outside working hours** to minimize customer impact. |
| **Emergency Changes** (Required to fix a P1/P2 incident or security breach) | 1 hour in advance | Executed immediately, regardless of time, with maximum governance oversight. |

**Post-Maintenance Reporting**: For all significant or high-impact changes, OVHcloud will provide a formal post-maintenance report upon request by the customer. This report will include a summary of actions taken, the specific services affected, any anomalies encountered, and a brief assessment of any residual risks.

## UAT environment

An UAT environment, which implementation is aligned with the customer production environment, is necessary to be able to reduce the risk of performing changes by executing the same changes on this UAT environment before production when possible.

# Service Request Fulfillment

## Service Catalog

The following Service Catalog defines requests covered by the Managed Service:

* Actions for configuration or operation that cannot be done by the customer using APIs or UIs (e.g, OPCP Core configuration change acceptable by OVHCloud)
* Initial onboarding / offboarding actions that cannot be done by the customer using APIs or UIs

Requests outside of this Service Catalog may require custom paid services.

## Planned DC maintenance & DRP tests

OVHCloud must be informed of DC maintenance windows which have an expected impact within a reasonable delay to avoid incidents. Depending on the impact, such operations may be billed to the customer.

The customer is responsible for the full DRP process, OVHcloud can contribute to a DRP test, such operations may be billed to the customer.

# Security & Compliance Operations

## Access management and reviews for managed Access

## Log retention and audit support

Long term retention responsibility is on the Customer, who must provide a compatible log forwarding destination.

# Backup, Recovery

## Manage backup policies and execution.

The controllers backup policies are managed by OVHCloud; the data plane backup is to be managed by the customer.

## Perform recovery testing.

If the customer owns a UAT environment, periodic deployment/restoration tests of the control plane will be achieved by OVHCloud no more than once a year. They will not use production data.

# Documentation & Knowledge Management

## Maintain operational documentation and runbooks

OVHCloud is responsible for maintaining generic operational documentation, whereas the customer should handle specific documentation (e.g, keycloak federation configuration).

# Reporting & Service Governance

## SLA/SLO tracking and reporting.

OVHcloud will provide quarterly SLA reports covering KPIs, breaches and availability.  
In the event of SLA breach, OVHcloud will provide and execute a performance improvement plan in order to continuously improve its performance in accordance to the agreed KPI's.

## Service reviews and continuous improvement

This will be performed by the TAM

# Annex

## RACI

## Remote access requirements

To be able to access OPCP on-premise OVHcloud offer different options:

### Provided by OVHcloud

OVHcloud provide remote Access for managing OPCP remotely through VPN.  
Public Internet access is required. Can be limited with firewall rules.

### Provided by customer

#### **SSH Access**

Secure administrative access from the OVHcloud Bastion Host (identified via DNS Name) to the Controller(s) shall be established.  
**Infrastructure**: The use of a JumpHost or SSH Proxy is permitted and shall be configured to enforce centralized access control by customer.  
**Authentication:** Access shall be secured via Public-Key.  
**Provisioning:** OVHcloud shall provide the necessary public SSH keys.  
**Credential Management:** The parties agree to the use of a Single Dedicated Service Key for the automated/technical connection, provided that internal logging at the OVHcloud Bastion level ensures individual traceability (Audit Log) of the initiating user.

#### **HTTP(S) Access**

Web-based or API access from the **OVHcloud Bastion Host** to the **Controller(s)** shall be routed through a **Reverse Proxy**.

* **Encryption:** All traffic will be encrypted using **TLS 1.2 or similar** by OVHcloud.
* **Authentication:** To ensure secure access and user authentication, OVHcloud will use its own IdP with MFA to access to the bastion.

## Outbound Monitoring & Alerting

The **Controller(s)** need to be authorized to initiate outbound HTTP(S) requests to the **OVHcloud Proxy Server** (identified via DNS Name) for the sole purpose of transmitting system alerts, telemetry data and receive Updates.

* The Customer is responsible for configuring firewall egress rules to permit this specific traffic flow.
* Protocol of send and received data can be audited.

## Governance and Approval

* **Logging:** All sessions (SSH and HTTP) will be logged with timestamps and user identifiers for auditing purposes.
* **Review Clause:** This technical configuration is subject to final security review and written approval by **OVHcloud Security Compliance**.

