# OPCP - Hardware Catalog

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 858809276](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=858809276) (v239, last modified 2026-07-10; re-synced 2026-07-15). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

This page is the source of truth for the commercial hardware catalog

## Network catalog

Switches are DCS-7050CX3-32S

## HPE servers catalog

### Definitions

* EDSFF = very small form factor NVMe
* SFF = 2,5"
* LFF = 3,5"
* Bare Metal = "Debian 12, 13, CentOS Stream"

### Qualified hardware ranges

According to HPE qualifying one Intel and one AMD per Generation is enough (except special configs like GPU or Alletra)

* Gen 11 Intel
* Gen 11 AMD
* Alletra Gen 11
* DL380a Gen 12

### Common requirements

* All disks are SED = Self-encrypting FIPS 140-3 KIOXIA CM7 and Read-intensive (1.92, 3.84 or 7.68 TB)
* All PSUs are redundant
* NICs
  * are always NVidia Mellanox MCX631102 (25Gb Ethernet, 2 x SFP28) unless specified otherwise
  * must support NC-SI (for out-of-band firwmare inventory)
* All components (BMCs, NICs, GPU, ...) must support for out-of-band firwmare inventory (MCTP, PLDM, VDM)

### Server catalog

Sales-wise, customers cannot create a rack with less than 4 servers + 1 CONTROLLER

Server specs can be customized only by upgrade (e.g, increase disk or RAM count/size)

| **Item name** | **Rev** | **Compatibility Tag Service** | **Recommended use** | **CPU** | **Memory** | **OS Disks** | **Data Disks** | **Network cards** | **Chassis** | **End of sales (EOL)** | **End of support** | **U/Server** | **GPU** | **Power (W)** | **Weight (kg)** | **BTU (W/h)** | **Qualification report** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CONTROLLER | 1 | * OPCP Controller * CloudStore Controller * Bare Metal * Ceph S3 * Openstack Block Storage | Pre-installed with OPCP Control Plane | 1 x AMD EPYC 9115 (16c@2,6GHz) | 64GB (2 x 32GB) | 2 x 960GB NVMe (with mandatory [PBA](https://en.wikipedia.org/wiki/Pre-boot_authentication) support) | 4 x 1.92TB NVMe | 4x 25Gbps SFP28 | DL325 Gen 11 (8 x SFF) | 06/28 | 07/33 | 1 | N/A | 377 | 15 | 1285,57 |  |
| COMPUTE-MINI | 1 | * Bare Metal * Openstack VM * VCF Bootstrap Server | Cost-effective compute for demo/test/dev | 1 x AMD EPYC 9115 (16c@2,6GHz) | 64GB (2 x 32GB) | 2 x 960GB NVMe | No Storage Option | 4x 25Gbps SFP28 | DL325 Gen 11 (8 x SFF) | 06/28 | 07/33 | 1 | N/A | 168 | 13,74 | 572,88 |  |
| COMPUTE-BALANCED | 1 | * Bare Metal * Openstack VM | Balanced profile | 1 x AMD EPYC 9654P (96c@2.4GHz) | 512GB (8 x 64GB) | 2 x 960GB NVMe | No Storage Option | 4x 25Gbps SFP28 | DL345 Gen 11 (24 x SFF) | 07/28 | 07/33 | 2 | N/A | 358,6 | 15,76 | 1222,826 | Ok because Gen 11 AMD already qualified |
| HIGH-CAPACITY-STORAGE | 1 | * Bare Metal * Ceph S3 | Min 4 nodes for HA | 1 x Intel Xeon-Gold 6538N (32c@2,1GHz) | 256GB (8 x 32GB) | 2 x 960GB NVMe | Available SAS HDD options (behind 41X0 Raid controller):   * 16 x 16TB + 3 x 7.68TB NVMe for metadata * 33 x 16TB + 5 x 7.68TB NVMe for metadata * 16 x 24TB + 3 x 7.68TB NVMe for metadata * 33 x 24TB + 5 x 7.68TB NVMe for metadata | 4x 25Gbps SFP28 | Alletra 4140 Gen 11 (60 x LFF + 8x EDSFF) | 05/28 | 05/33 | 4 | N/A | 1113 | 22,8 | 3753 |  |
| HIGH-PERFORMANCE-STORAGE | 1 | * Bare Metal * Openstack Block Storage (min 4 nodes) * High-perf Ceph S3 (min 4 nodes) | Scality   * Min 3 nodes * 6x disk option not supported | 1 x AMD EPYC 9334 (32c@2.7GHz) | 256GB (4 x 64GB) | 2 x 1.92TB NVMe | Available NVMe options:   * 6 x 3.84TB * 12 x 3.84TB * 18 x 3.84TB * 22 x 3.84TB * 6 x 7.68TB * 12 x 7.68TB * 18 x 7.68TB * 22 x 7.68TB | 4x 25Gbps SFP28 | DL345 Gen 11 (24 x SFF) | 07/28 | 07/33 | 2 | N/A | 448 | 16,5 | 1527 | Ok because Gen 11 AMD already qualified |
| GPU-S | 1 | * Bare Metal * Openstack VM | Inference workloads | 2 x AMD EPYC 9354 (32c@3.25GHz) | 384GB (12 x 32GB) | 2 x 1.92TB NVMe | 4 x 3.84TB NVMe | 4x 25Gbps SFP28 | DL385 Gen11 (8x SFF) | 07/28 (platform)  11/26 (GPU) | 07/33 | 2 | 4 x NVIDIA L40S 48GB | 2341 | 33 | 7982,81 |  |
| GPU-M | 1 | * Bare Metal * Openstack VM | Intensive inference or model training | 2 x Intel Xeon 6747P (48c@2.7GHz) | 1024GB (16 x 64GB) | 2 x 1.92TB NVMe | 4 x 1.92TB NVMe | 4x 25Gbps SFP28 | DL380a Gen12 (8 x EDSFF) | 05/28 | 07/33 | 4 | 4 x NVIDIA H200 141GB | 3566 | 41,2 | 12160,06 | No report available but was tested |
| GPU-L | 1 | * Bare Metal * Openstack VM | Very intensive inference or model training | 2 x Intel Xeon 6747P (48c@2.7GHz) | 2048GB (32 x 64GB) | 2 x 1.92TB NVMe | 4 x 1.92TB NVMe | 4x 25Gbps SFP28 | DL380a Gen12 (8 x EDSFF) | 05/28 | 07/33 | 4 | 8 x NVIDIA H200 141GB | 6281 | 46,2 | 21418,21 | No report available but was tested |
| HCI-AMD-S | 1 | * Bare Metal * VMware VCF |  | 1 x AMD EPYC 9254 (24c@2.95GHz) | 384 (6 x 64GB) | 2 x 960GB NVMe | Storage NVMe options:   * 6x3.84TB | 4x 25Gbps SFP28 | DL325 Gen 11 (8 x SFF) | 06/28 | 07/33 | 1 | N/A | 307 | 13,96 | 1046,87 |  |
| HCI-AMD-M | 1 | * Bare Metal * VMware VCF |  | 2 x AMD EPYC 9354 (32c@3.25GHz) | 1024GB (16 x 64GB) | 2 x 1.92TB NVMe | Available NVMe options:   * 6 x 3.84TB * 12 x 3.84TB * 18 x 3.84TB * 22 x 3.84TB * 6 x 7.68TB * 12 x 7.68TB * 18 x 7.68TB * 22 x 7.68TB | 4x 25Gbps SFP28 | DL385 Gen 11 (24 x SFF) | 07/28 | 07/33 | 2 | N/A | 723 | 16,36 | 2465,43 |  |
| HCI-AMD-L | 1 | * Bare Metal * VMware VCF |  | 2 x AMD EPYC 9454 (48c@2.75GHz) | 1536GB (24 x 64GB) | 2 x 1.92TB NVMe | Available NVMe options:   * 6 x 3.84TB * 12 x 3.84TB * 18 x 3.84TB * 22 x 3.84TB * 6 x 7.68TB * 12 x 7.68TB * 18 x 7.68TB * 22 x 7.68TB | 4x 25Gbps SFP28 | DL385 Gen 11 (24 x SFF) | 07/28 | 07/33 | 2 | N/A | 781,6 | 17,06 | 2665,256 |  |
| HCI-INTEL-S | 1 | * Bare Metal * VMware VCF |  | 1 x Intel Xeon-Gold 6542Y (24c@2.9GHz) | 384GB (6 x 64GB) | 2 x 960GB NVMe | Storage NVMe options:   * 6x3.84TB | 4x 25Gbps SFP28 | DL320 Gen 11 (8 x SFF) | 05/27 | 05/32 | 1 | N/A | 434 | 12,3 | 1479,94 | Ok because Gen 11 AMD already qualified |
| HCI-INTEL-M | 1 | * Bare Metal * Mware VCF |  | 2 x Intel Xeon-Gold 6542Y (24c@2.9GHz) | 768GB (12 x 64GB) | 2 x 1.92TB NVMe | Available NVMe options:   * 6 x 3.84TB * 12 x 3.84TB * 18 x 3.84TB * 22 x 3.84TB * 6 x 7.68TB * 12 x 7.68TB * 18 x 7.68TB * 22 x 7.68TB | 4x 25Gbps SFP28 | DL380 Gen 11 (24 x SFF) | 05/27 | 05/32 | 2 | N/A | 809 | 16,5 | 2758,69 |  |
| HCI-INTEL-L | 1 | * Bare Metal * VMware VCF |  | 2 x Intel Xeon Gold 6548Y+ (32c@2.5GHz) | 1024GB (16 x 64GB) | 2 x 1.92TB NVMe | Available NVMe options:   * 6 x 3.84TB * 12 x 3.84TB * 18 x 3.84TB * 22 x 3.84TB * 6 x 7.68TB * 12 x 7.68TB * 18 x 7.68TB * 22 x 7.68TB | 4x 25Gbps SFP28 | DL380 Gen 11 (24 x SFF) | 05/27 | 05/32 | 2 | N/A | 602 | 15,12 | 2052,82 |  |

### HPE hardware lifecycle

We will match HPE's lifecycle, meaning

* we will make sure to renew configurations 6 months before they get End Of Life (e.g, 05/27 for Intel Gen 11) by issuing a new catalog version
* we will notify customers at least 6 months before officially dropping support for a specific configuration, after which we will eventually remove the server from the qualification infrastructure
* we will support them until HPE End of Support (usually, EOL + 5 years); if extensions are possible (depending on the model), extra costs may be applied
* we will display the End Of Sales dates in the public OPCP Core datasheet
* we will display the End Of Sales and End Of Support dates in the quotes
* 12 months before eaching the End Of Support date, OVH (TAM, as part of the monthly capacity planning) will offer the choice between extending support (whenever possible) or renewing the hardware

250

## Minimum Production Footprints

The deployment mode / architecture of Cloud Store is not defined yet so these numbers are provisional (in red)

An OPCP Core Pod must be sold with at least 4 workload servers

| Feature | Minimum NANOPOD footprint for production | Minimum STANDARD POD footprint for production |
| --- | --- | --- |
| Racks | 1x 24U, 2x electric inputs | 3x 24U, 2x electric inputs per rack |
| Supported failures | 1x storage server failure or 1x storage disk failure  1x switch failure  1x electric input failure | 1x entire rack  1x storage server failure or 1x storage disk failure  1x switch failure per rack  1x electric input per rack |
| OPCP Core | 1x CONTROLLER | 3x CONTROLLER |
| Cloud Store | 1x COMPUTE-BALANCED (cloudstore + enablers/control plane TBC) | 3x COMPUTE-BALANCED (cloudstore + enablers/control plane TBC) |
| OpenStack Compute and Network Services | 1x COMPUTE-BALANCED (network services)  1x COMPUTE-BALANCED (customer VMs)  4x HIGH-PERFORMANCE-STORAGE (Block storage) | 2x COMPUTE-BALANCED (network services)  2x COMPUTE-BALANCED (customer VMs)  4x HIGH-PERFORMANCE-STORAGE (Block storage) |
| **Total servers (min)** | **8** | **14** |
| S3 (optional) | 4x HIGH-CAPACITY-STORAGE | 4x HIGH-CAPACITY-STORAGE |
| VCF (optional) | 5x per Management Domain + 3x per Workload Domain | 5x per Management Domain + 3x per Workload Domain |

## Demo racks

Two variants are considered here: one with HA and one without; this will allow to offer two prices depending on the scope of the customer evaluation objectives

### Customer objectives

* Learn and evaluate OPCP Core & CloudStore IaaS / hardware-agnostic services:
  * UI, API
  * bare metal provisioning, VM, Object storage, network services and their operations (maintenance, live migration – hence, requires at least 2 nodes), MKS (when available)
* build & test homemade Ironic images
* develop a CloudStore package
* pentesting
* optionally (HA variant)
  * simulate/test HA (failed switch / NIC, service maintenance operations...)
  * prepare / test changes / procedures without availability impact (UAT env)

### OVH Objectives

* acquire 4 demo racks which will be shipped to customer locations for **up to 6 months**
* reduce delivery delays for NFR (not for resale)/demo/POCs by keeping stocks of standardized configurations

### Out of scope

* evaluate hardware-specific solutions like VCF, Nutanix, GPU
* production workloads (because of reduced resiliency and reduced costs like no real storage servers)
* performance evaluations

### [NANOPOD](https://confluence.ovhcloud.tools/display/SOV/03.01.03.03+Wiring) (non-HA)

| Item | Qty | Unit Cost | Used for | Notes |
| --- | --- | --- | --- | --- |
| 24U 19" cabinet | 1 | 15k |  |  |
| Top of Rack switch | 2 |  |  |
| IPMI switch | 1 |  |  |
| CONTROLLER | 1 | 35k | * OPCP Core control plane |  |
| COMPUTE-MINI | 6 | 15k | * 2 cloud store compute nodes (cloud store, cloud store obs stack, MKS control plane, proxies...) * 2 dataplane nodes (network services, cinder) * 2 compute nodes for user VMs | 2 nodes required for testing live migrations, interruption-free maintenances, ... Because of CPU pinning, only 6 vCPU per host are available (6 VMs max for 2 nodes) |
| CONTROLLER | 6 | 35k | * 3 Block Storage server * 3 Object Storage server | Auto-healing of Ceph is not available (need 4 nodes) |
| Server count | 11 |  |  |  |
| Used U | 13/24 |  |  | Usable by the customer to add custom hardware |

Estimated cost: ~350k€

Cost reduction options

* skip the Object Storage servers and make the customer choose between Object and Block (wipe and redeploy)
* implement single-node Ceph deployment
* hyper-converged deployment
* run merge dataplane and cloud store VMs on same aggregate (-2 COMPUTE-MINI)

### [STANDARD POD](https://confluence.ovhcloud.tools/display/SOV/03.01.03.03+Wiring) (HA variant)

Made of 3 racks. Can be used to validate that losing a single rack is possible.

| Item | Qty | Unit Cost | Used for | Notes |
| --- | --- | --- | --- | --- |
| 24U 19" cabinet | 3 | 15k |  |  |
| Top of Rack switch | 6 |  |  |
| IPMI switch | 3 |  |  |
| PDU | 6 |  |  |
| CONTROLLER | 3 | 35k | * OPCP Core control plane |  |
| COMPUTE-MINI | 3 | 15k | * Control plane dedicated computes nodes (inc. Cloud Store, Enablers) |  |
| COMPUTE-MINI | 6 | 15k | * 2: compute nodes * 2: network nodes * 2: free for bare metal (with GPU ?) | 2 nodes required for testing live migrations, interruption-free maintenances, ... |
| CONTROLLER | 8 | 35k | * 4: Block Storage cluster * 4: Object Storage cluster |  |
| Free U | 43 |  |  | Usable by the customer to add custom hardware |

Estimated cost ~420k€

## Sizing rules

### VM CPU/RAM ratio

For now, sync with SNC Cloud Platform BOM: 

Later, follow PCI practices , assuming that compute nodes are not flavor-specific:

* 4GB per core if < 64 cores
* 3GB per core otherwise

* Keep core per NUMA node
  * 1 core per socket for Intel
  * 4 cores per socket for AMD
* Keep some RAM for the hypervisor (~2GB / NUMA node)

Flavors are related to aggregates (e.g b3-8 belows to ovh.b3 aggregate); a new server is added to an aggregate manually when provisioned.

### Ceph metadata disk size

But for every Data HDD we need ~5% in NVMe Storage

### Disk Options Weight & Power Rules

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
|  |  | Watt @100% | Poids (Kgs) | BTU/h |
| P61027-B21 | 3,84TB | 22 | 0,19 | 75,02 |
| P61035-B21 | 7,68TB | 24,9 | 0,19 | 84,909 |
|  |  |  |  |  |
| P70674-K21 - Alletra | 7,68TB E3S | 24 | 0,145 | 81,84 |
| P79122-K21 - Alletra | 15,36TB E3S | 26 | 0,145 | 88,66 |
| P83709-K21 - Alletra | 16TB SAS SED | 10,1 | 0,7 | 34,441 |
| P82544-K21 - Alletra | 24TB SAS SED | 8,4 | 0,7 | 28,644 |

## Key contacts

The maintenance agrement has been signed directly with HPE, so we can open a ticket directly to HPE for any issue related to OPCP projects, you can contact Joseph Carlos and Alexandre Leclerc for more information

| Name | Role | Contact |
| --- | --- | --- |
| Raphaël Maurice | OVHCloud account manager at Celeris | [raphael.maurice@celeris-informatique.fr](mailto:raphael.maurice@celeris-informatique.fr) 06 20 18 43 04 |
| Damien Cerclé | PCI hardware |  |

## Changelog

### History

* April
  * Renamed COMPUTE-XS to COMPUTE-XXS
  * Replaced HIGH-PERFORMANCE-CONFIGURATION by a single socket one with 256GB of RAM to comply with SOV.OPCPCore.Storage recommendations
* May
  * Replaced 4x 3,84TB disks of CONTROLLER by 4x 1,92TB for cost savings
  * sync with SNC Cloud Platform compute approach:
    * remove COMPUTE-S and COMPUTE-L
    * rename COMPUTE-M to COMPUTE-BALANCED
    * rename COMPUTE-XXS to COMPUTE-DEMO
* June
  * Upgrade COMPUTE-DEMO from 8 cores to 16 cores (AMD EPYC 9015 > 9115)
* July
  * Sync of HCI-AMD-S with HCI-INTEL-S so that customers are not pushed to INTEL: RAM 512 > 384 GB and CPU 9354P > 9254
  * Rename COMPUTE-DEMO to COMPUTE-MINI for clarity

### Customer requests / Next topics

* Add B300 GPUs to catalog
* Sept
  * Replace Gen11 by Gen12 Intel HCI-INTEL-S (required NS204i qualification)
  * replace GPU-S L40S GPU by RTX PRO 6000 BSE

