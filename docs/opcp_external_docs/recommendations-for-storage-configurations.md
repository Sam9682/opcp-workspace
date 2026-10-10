# Recommendations for storage configurations

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 928978645](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=928978645) (v6, last modified 2026-04-16; mirrored 2026-06-10). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

## Future Block & Object Storage deployed via Cloud Store

  * Based on CEPH
  * CPU
    * 1 CPU Socket to get best performance - avoid NUMA issue
    * CPU : INTEL or AMD supported, no preference
  * Memory
    * Minimum RAM : 256GB (rule of thumb 8GB per SSD disk drive)
  * OS drive
    * M.2 960GB is enough



For both Block and S3 Service, the following rules apply: 

  * Minimum cluster size: 3 Nodes + 1 (for redundancy)
  * Best Practice : each node in a different rack - if OPCP sizing allows (for Nano POD, customer must accept less physical redundancy)
  * Cluster-level Node configuration: nodes can have different Gen/CPU/RAM, but Storage-wise nodes must have same configuration (N# of drives, Type and Capacity)
  * Scale-out upgrades: +1 Node supported
  * Scale-up upgrades: all nodes inside CEPH cluster must be upgraded together in order to get same Node configuration at cluster-level
  * Scale-up upgrade is being studied by Product Team if it will be an option for customer
  * Minimum DATA drives: 5x drives



## S3 Specifics & Rules

Meta DATA minimum :4x 1.92TB SSD

Meta DATA capacity needs: for every 8x HDD (LFF mechanical drives), we need 1x 7.68TB SSD

Useable Capacity = RAW Capacity (N-1) ÷ (3* 80%)

Disk usage should not surpass 80% of drive capacity

A warning is triggered when 75% consumption threshold is reached

## Base BOM

This is the BOMs that LocalZones are using (warning: the OS disks are not SED)

## [AG11-11406_Dubai.pdf](/display/CPO/Recommendations+for+storage+configurations?preview=%2F928978645%2F928978652%2FAG11-11406_Dubai.pdf)

  

