# OPCP - Managed Service

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 832064273](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=832064273) (v36, last modified 2026-07-09; re-synced 2026-07-15). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

|  |  |
| --- | --- |
| **Status** | Validated |
| **Owner** | Manuel Jenne |
| **Jira** | Projectsf0e70dd9-2bc3-31da-a16b-974623242708LVL2-13511 |
| **ETA** | September 2026 |

true

## Problem we are solving

Openstack (and OPCP) is a complex system with many moving parts which can be pushing back some customers from deploying and operating it; offering a managed service is a way for customers to reduce the operational risk, and offload responsibility to experts provided by OVHCloud.

## Objectives

* Define the scope of the managed services
  * Scope of changes performed by OVHCloud: Service Catalog
  * Continous activities (monitoring / alerting)
  * Proactive activities (capacity planning ?)
  * ...
* Identify functional and technical requirements
* Define internal processes to handle escalation (typically, what happens in case of MKS bug...)

## Solution

### Business Model

It is currently decided that this is part of the regular offer (and not optional in the pricing).

### Service Catalog

Generally, anything that the customer cannot do if he is not root.

* Deploy patches, updates, and releases
* Monitor and update devices firmware
* Maintain change records and rollback plans
* Troubleshoot bugs notified by the customer via remote access to the OPCP

### Continuous activities

* 24/7 alerting & on-call duty for the OPCP control plane, connected to OVHCloud alerting tools (opsgenie)
* 24/7 alerting & on-call duty for the remote access tunnels

### Deliverables

* Service Catalog: list of operations performed by OVHCloud as are part of the service
* Service Description:  with SLAs (WIP)
  * Technical and functional requirements
  * Documentation about what is monitored and what triggers alerts
* Service Contract (T&Cs)
* Documentation about which data OVHCloud can access:
* [Interconnection Architecture Design](https://confluence.ovhcloud.tools/display/PSPUSNC/%5BOPCP+Managed%5D+DAT+Interconnection+infrastructure+-+Minimal+version)

## UI/UX implications

### Offer evolution

* it will be possible to move from managed service to AirGap (but not the other way around)

### OPCP Installation

When deploying OPCP, one of the final steps of the installer is to decide if we are in managed mode or not; if not, then the *opcp-admin* UNIX user is sudoer; in managed mode

* the customer can only perform a limited set of actions
* a monitored connectivity link is setup between the customer premises and OVHCloud so that OVHCloud support can remotely connect into OPCP
* AlertManager is configured to forward alerts to OVHCloud alerting

### Example incident sequence

1. The local observability stack running inside OPCP triggers an alert
2. The alert is forwarded to the OVHCloud OpsGenie
3. The on-call team connects remotely to the OPCP customer platform and uses the observability stack to troubleshoot
4. The customer is informed that a problem is ongoing
5. Once fixed, the customer is informed of it
6. If needed, a root cause analysis is communicated to the customer

### Example change

1. The customer is notified that a new update is available, along with the changelog
2. He opens a ticket on the OVHCloud support platform and requests an upgrade deployment, suggesting time frames
3. After negociation on the time frame for the operation, OVHCloud deploys the upgrade and notifies the customer

## Topics to explore

* Jeremie Monsinjon (mks): How will these primitives (DB | Metrics | Logs | etc?) be managed in production? Who will be in charge of run/on call ?

