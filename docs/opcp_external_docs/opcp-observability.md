# OPCP - Observability

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 818640885](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=818640885) (v190, last modified 2026-07-09; re-synced 2026-07-15). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

|  |  |
| --- | --- |
| **Status** | Validated by PU |
| **Owner** |  |
| **Jira** | Projectsf0e70dd9-2bc3-31da-a16b-974623242708LVL2-18370 |
| **Tech lead** | Tech lead: Benjamin Hofer (responsible) Thomas Poehler (accountable) |
| **Consulted** | SNC: Francois Vaillant /  Charly Gregoire  / Nathan Malo / Guillaume Allard   Consumption: Kai Lange |
| **Others** | LDP Product Manager: Cedric Poirier   Mimir specialist: Wilfried Roset, Julien Girard |
| **ETA** | Beta: 09/2026 (at risk) |

## 

---

## 1. Overview & Problem Statement

### 1.1. Context

Most large scale customers/prospects already have a *Centralized Observability Platform*, used to comply with security (SIEM) and legal requirements (e.g. controlled retention, immutability, security analysis, ...) for which their technical teams are trained, and central alerting system for on-call and escalation management; they rely on these tools for managing their own services company-wide. However, in case this *Centralized Observability Platform* is unavailable, they usually keep a fallback local observability stack.

The gold standard User Interface is usually Grafana, but some of them use Zabbix, Centreon, etc...

Similarly the SNC products are expected to use the mainstream OVHCloud observability stack (like all internal and mainstream products):  [LDP](https://www.ovhcloud.com/en-gb/identity-security-operations/logs-data-platform/) + [Internal Metrics](https://observability.pages.ovhcloud.tools/). However, the mainstream observability stack is currently not SecNumCloud compliant, which is another problem we need to address in the long term (< 3 years).

Last, observability tools are required to provide a Managed OPCP Service, where logs, metrics and alerts are expected to be sent over into OVHCloud systems.

Finally, the promise of OPCP integrates **that** **data plane is architecturally isolated and encrypted****, ensuring that OVHcloud staff cannot access, read, or modify customer workload data at any time.**

### 1.2. Definitions

* **Data Provider**: object generating the data
* **Data Platform**: datastore
* **Data Consumers**: dashboards, alerting system, ...
* **Value Metric**: metric which reflects the value brought to the customer in relationship with the product and which can be used for the billing/pricing, e.g,
  * Cores count managed by OPCP Core (excl. Cloud Store)
  * Cores managed by Cloud Store
* **OPCP Core Observability Stack:** built-in, local observability stack used to collect data from all data providers, and which does not rely on openstack
* **Cloud Store Observability Service**: multi-tenant and scalable observability service deployed using a dedicated CloudStore package
* **Cloud Store Observability Service Tenant:** the Cloud Store observability service supports multi-tenancy, which may or may not be related to a Landing Zone Manager account/project; this is the underlying multi-tenancy mecanism which allows for separating data between usecases
* **Centralized Observability Platform**: central, scalable and external longterm observability stack, usually provided by the customer
* **Managed Service Provider:** entity who will manage the platform (i.e. the Root IT Admin), can be OVHCloud or someone else

### 1.3. Problems we are tackling

| Problem | Solution |
| --- | --- |
| We need to offer a managed OPCP service which can scale to the objective (100 racks, 4400 servers) | We need an observability stack which can reach the target scale for  ~4400 machines in order to provide [OPCP Managed Service](https://confluence.ovhcloud.tools/display/CPO/OPCP+-+Managed+Service), see  for a detailed analysis |
| * If we are the Managed Service Provider, our customer may ask that the observability data cannot leave the customer premises * the Centralized Observability Stack may not be reachable in case of network issue | We need local observability stack(s) |
| Observability Data Providers are scatterered all around, and it's complicated to expose/forward all these into a central system | We need to centralize collecting all control plane observability data and offer an easy way to forward/expose it to the Managed Service Provider Centralized Observability Platform (both for core components, and for CloudStore packaged apps) |
| The main objective of our service is to guarantee that our platform (based on Openstack) works as expected | The stack observing Openstack must keep working even if Openstack is broken |
| An AirGap customer may prefer to use his Centralized Observability Stack in order to minimize the footprint of the platform | The observability stack should be optional |
| It's easy to get overwhelmed by irrelevant alerts, and hard to define relevant alerts | There is Product Value in providing a default set of alerts and dashboards relevant for providing a managed service (both for core components and for CloudStore packaged apps) that can be used by the customer if he deploys our Observability product |
| Not all environments are equal (e.g. temperature alerts are different with watercooled systems) and customers should not wait for a new release to adjust alerts and parameters | The Managed Service Provider should be able to override/customize alerts and dashboards |
| Because it has been decided that the CloudStore licence is optional and that we want at some point to provide the CloudStore standalone, the OPCP Core observability cannot depend on it | * We need an observability stack built into OPCP Core * The CloudStore must be configurable to ship it's observability data somewhere else |
| End-users need access to critical logs (e.g, S3 http access logs, LB access logs) | The observability data related to the end-user (e.g, Load Balancer access logs) must be accessible by the end-user, typically by downloading data from a S3 bucket and/or using a UI like Grafana |
| End-users may request all their available data when leaving (as per GDPR requirements) | The data related to the end-user must be extractible upon request |
| * CloudStore deployment actions may take a lot of time * End-users may need to see live logs for debugging (e.g, LB) | The observability stack must allow for realtime log display in a web UI (typically, CloudStore admin panel) |
| Some high-security production environments must use a dedicated observability stack (TBC) | It must be possible to configure some projects to use a dedicated observability stack (TBC) |

## 2. Target Personas & User Stories

Refer to  for a reminder of personas.

### 2.1. IT Admin

As a Root IT Admin / IT Admin...

* i need to be able to configure the system to expose/forward logs/metrics/alerts to one (or more) *Production Observability Stack* using standards (syslog, OTLP, webhooks, prometheus exporters, ...) and from a central, unified setting
* i need to get notified in case of hardware problem: out of range temperature, failed disk, failed PSU, link down, dead server, dead switch, ... (Datacenter operator role)
* i need to access networking logs, metrics and alerts (switch port status / bandwidth usage / packet loss / ...) in order to identify failures
* i need access to OPCP Core and CloudStore control plane logs (e.g, K3S logs, host logs, Openstack, VM nodes, ...), metrics (hardware, software), dashboards, alerts
* i need a way to override/customize alerts and dashboards
* i need access to Openstack audit logs
* i need to perform capacity planning both for servers and network
* i need my external billing system to be able to scrape (value) metrics per tenant
* i need access to some data plane logs so that i can assist end-users (e.g, S3 access logs), **possibly after requiring end-user admin consent and/or providing an audit log showing when i access the data**

### 2.2. Service packager

As a Service Packager i need

* manifest / framework features and related documentation to understand how to expose metrics/logs/grafana dashboards/relevant alerts for my application, and how they will consumed / displayed
* deploying a new service must 
  * initialize the service control plane components to ingest the observability data into a dedicated tenant of the CloudStore observability service
  * initialize the service data plane components to ingest the observability data into the data plane of the Account (typically, an encrypted S3 bucket)

Example users:

* OVHCloud
  * Core-related (VM, Load Balancer, Object Storage)
  * Internal contributions (MKS, DBaaS, ...)
* External
  * CleverCloud
  * Scality

### 2.3. Tenant

As an Tenant admin ...

* I need to be able to receive my observability data into my data plane (e.g. S3 http access logs, Load Balancer logs, ...) **for each project with isolation**
* i need to be able to allow project admins to create custom logs forwarding locations, and to define an optional logs forwarding location for all my projects (default value for all projects)
* i need to be able to define default retention duration
* i need to be able to explore observability UI for the tenant-wide observability data (user/project audit logs)

As a Project admin...

* i need to be able to define an optional logs forwarding location for my projects (if allowed by the Tenant admin)
* i need to be able to configure a different retention duration for my project

As a Project member

* i need to be able to explore the observability data of my project using the observability UI
* i can customize dashboards in the observability UI

As a Project reader

* i have read-only access to observability UI

## 3. Functional Requirements

### 3.1. General guidelines

Refer to OPCP

[Ideally](https://confluence.ovhcloud.tools/display/CPO/Prioritization+and+General+guidelines), we should match the mainstream stack for a consistent User Experience and internal skills reuse, which is:

* LDP : Graylog/Opensearch/**Grafana**
* Metrics (M4M): Mimir/Prometheus/**Grafana**

### 3.2. Data Providers to collect

See dedicated subpage

### 3.3. Performance requirements & sizing

TL;DR: We must keep in mind that we need to scale out both observability stack(s), especially in terms of CPU, in order to fulfill the requirement of having 4,400+ nodes in the data plane. SAs discussed in  we found out that CPU is the bottleneck here, as storage can be easier tacklee by reducing retention.

Key metric is: Number of active series per node.

Beware that the Grafana Mimir's / Loki's recommendations are considered as somewhat conservative by OVH observability experts running these tools large-scale.

## 4. Solution

The main downside of this solution is that it requires the customer to provide an S3 bucket for the OPCP Core observability stack for production use (which is also required anyway for backups)

### 4.1. General overview

The following approach can fullfill the aforementioned requirements:

* The OPCP Core observability stack is collection-oriented and
  * must collect relevant BMC, networking, control plane observability data
  * must collect relevant CloudStore control plane data (because it is deployed and managed by OPCP Core) (**urgent**)
  * must be upgraded to scale better by using Mimir instead of Prometheus (**urgent**)
  * provides a best-effort retention
* A CloudStore Observability Package offers a multi-tenant and scalable observability stack
* Optionally when installing OPCP Core / CloudStore, the configuration should state if the Core observability data should go into a single "IT Admin" observability tenant running in the CloudStore Obs stack, accessed by Grafana inside the Cloud Store admin panel

### 4.2. Functional architecture diagram

<https://excalidraw.ovhcloud.tools/document/45a30ecb-1a70-498e-baca-ece0bfbd3fef?element=OwgjQ2Cubjq5W-I2yACQ3>

Examples

* K3S > core stack > "IT Admin" obs tenant (if enabled)
* Compute hosts > core stack > "IT admin" obs tenant (if enabled)
* clevercloud app > "IT admin" and/or "Clevercloud obs" tenant
* S3 logs (all) > "IT Admin" obs tenant
* S3 access logs (project-related) > tenantA-project1 obs tenant (if enabled)

## 5. UI/UX implications

### 5.1. User journey overview

* When the IT admin deploys a new service available in the Service Catalog (e.g. Object Storage)
  * The IT admin configures where control plane observability data should go (cumulative)  
      
    * into the "Platform tenant"; grayed out if the service is not deployed, trying to enable should suggest the user to enable it first
    * into one or several "Logs Forwarding Locations" (defined in the Observability Settings defined in 5.3)
  * If "Cloud Store" observability has been enabled, the IT admin can access observability data from within the Cloud Store admin panel (Grafana) – data is located in the "IT Admin" tenant
* When an account end-user creates a first resource in the service from the Landing Zone Manager (e.g. an Object Storage bucket)
  * The end-user decides where the account-related observability data should go (cumulative) – the cloudstore package defines how to filter and duplicate the account-related data
    * into a project-related observability tenant (will cost him storage at least)
    * or forwarded / exposed into one target
  * All S3 access logs for this bucket are sent into this tenant

**Delegated maintenance**: in some cases, a third party may have to maintain the Cloud Store service (e.g, Scality); if the 3rd party has an external logs forwarding location, the IT Admin has to add it to the list of available logs forwarding locations, but if not, the IT Admin can create a Tenant for them (which will provision a tenant inside the shared observability dataplane) and add it to the list of logs forwarding locations

### 5.2. OPCP Installation

When installing OPCP with Cloud Store, the following actions should occur:

* Configure the Cloud Store control plane to ship/expose observability data into the OPCP Core stack
* The logs forwarding locations configured on OPCP Core should appear in the list of available logs forwarding targets

### 5.3. CloudStore

*(Grafana: open in new link)*

* A new Observability section with
  * A "Logs" button in the sidebar which embeds Grafana on a predefined logs dashboard showing Loki
  * A "Dashboards" buttons which embeds the list of dashboards available (depends on the deployed resources)
  * An "Alerts" button which embeds the list of alerts
  * a "Grafana" button which opens Grafana in a new tab (for power users)
  * with pre-configured data sources for the "IT Admin" tenant (logs, metrics)
  * with pre-configured dashboards and alerts
* Observability configuration
  * List of logs forwarding locations (read-only for the one inherited from OPCP Core), syslog endpoints only for now
  * Modals which enable and show how to scrape metrics (prometheus endpoints)
* CloudStore Observability Package
  * deploy a cluster (allocates VMs)
  * configure default retention
  * add node to cluster (mimir / loki separate ?)
  * update observability stack
  * global capacity indicators
* Configure observability when deploying a new service (control plane): logs forwarding

### 5.4. Landing Zone Manager

NB: like all items in the sidebar, observability data of the current **project** goes to a specific project-related tenant

* A new Observability section (Grafana data scoped per project) with
  * A "Logs" button in the sidebar which embeds Grafana on a predefined logs dashboard showing Loki
  * A "Dashboards" buttons which embeds the list of dashboards available (depends on the deployed resources)
  * An "Alerts" button which embeds the list of alerts
  * a "Grafana" button which opens Grafana in a new tab (for power users)
* Additional observability-related parameters when creating a resource (e.g, an S3 bucket, a load balancer, ...) to enable logs forwarding (default: Disabled, but should be enableable later)
* An "Observability" configuration area
  * A "retention\_duration" configuration item
* Trying to delete the bucket used for storing observability data should refuse
* Add a new "Observability" user role (TBC) which allows to grant users access to Grafana and data sources

## 6. Open Issues / Q&A

* how do cloudstore apps ship their own alerts and dashboards ?

## Related resources

### Meeting notes

* Thomas Poehler
  * <https://excalidraw.ovhcloud.tools/document/b6c6b8db-9574-47e4-928e-4d143bc73332>
  * <https://excalidraw.ovhcloud.tools/document/d49abac3-0421-4959-abc5-b9c096f0e54e>
* Benjamin Hofer / Team UI:
  * panels logs from browser sessions must be added (see also SNC context ADR-0044)
  * UIs / panels will be react-based; tools that make it easy to implement dashboard components can make sense, not a high prio as of now

### OPCP



### Mainstream: LDP & M4M

|  | LDP (logs only) | M4M | Custom unified stack |
| --- | --- | --- | --- |
| Minimum footprint | LDP: 3 nodes |  |  |
| Architecture | LDP: |  |  |
| Dual-layer multi-tenancy | Service / DataStream |  |  |
| "External" dependencies | * Postgress puppetdb * Arsenal * Bastion * S3 * IPLB * IAM * Splunk * Artifactory |  |  |

### SNC

* workshop notes
* [Observability Specifications](https://confluence.ovhcloud.tools/display/PSPUSNC/0039b+-+Control+Plane+Observability%3A+Logs%2C+Metrics+and+Alerting)
* [BMC Monitoring](https://confluence.ovhcloud.tools/display/GOR/0038+BMC+Monitoring+-+Logs+into+LDP)
* SNC retention policy <https://pu-snc.pages.ovhcloud.tools/documentation/storage_retention_policy/dmz/index.html>
  * look at bucket-log-controller1-bmpod-${LOCAL\_REGION}  prod-${LOCAL\_REGION}-nuc1-metrics

### OVHCloud Mainstream Observability

* <https://observability.pages.ovhcloud.tools/self-assessment>
* Enablers roadmap

