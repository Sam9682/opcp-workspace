# OPCP Observability - Data Providers

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 903052339](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=903052339) (v3, last modified 2026-03-25; mirrored 2026-06-10). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

#### Logs

Source type| OPCP Layer| Sources| Retention  
---|---|---|---  
Log files| 

  * L1
  * L2

| 

  * K3S logs
  * K3S components logs
  * Controller system log files
  * Cloud Store host log files

|   
  
Journald| 

  * L1
  * L2

| 

  * Controller host systemd logs
  * CloudStore host systemd logs

|   
  
Syslog sources| 

  * L1
  * L2

| 

  * Arista switches
  * Cisco switches
  * Custom CloudStore apps

|   
  
[GELF](https://go2docs.graylog.org/current/getting_in_log_data/gelf_format.html) sources| 

  * L2

| 

  * MKS

|   
  
OpenTeleMetry protocol (OTLP) sources?| 

  * L3

| 

  * CloudStore apps

|   
  
Frontend logs / traces| 

  * L1
  * L2
  * L3

| 

  * Web Browser
    * Admin Panel
    * Manager Panel

|   
  
  
#### Audit logs

Source type| OPCP Layer| Sources| Retention  
---|---|---|---  
Horizon| 

  * L1
  * L2
  * L3

| 

  * User creation
  * User modification
  * User login
  * User logout
  * Resource creation
  * Resource deletion
  * ...

| 12 months  
Keycloack|   
|   
|   
  
  
#### Metrics

Source types| OPCP layer| Sources| Example data| Protocols| Retention  
---|---|---|---|---|---  
Servers hardware metrics| 

  * L1

| 

  * BMC (via Ironic)

| 

  * BMC/BIOS/HDD/SSD/NVME Firmware !versions/Serial Event Log
  * Temperature
  * Power usage
  * PSU state
  * Global CPU usage
  * CPU frequency
  * Fan speed

| 

  * IPMI
  * Redfish

|   
  
Switches metrics| 

  * L1

| 

  * Arista switches
  * Cisco Switches

| 

  * CPU
  * Memory
  * Fan speed
  * Temperatures
  * PSU state
  * Link speed
  * Advanced SFP/QSFP metrics
  * Firmware versions
  * Bytes in/out
  * Latency
  * Drops / collisions / ...
  * MAC & ARP table size
  * EVPN / VXLAN status and traffic counters
  * QoS

| 

  * SNMP

|   
  
L1 Openstack metrics| 

  * L1

| 

  * Control plane
  * Compute nodes (physical VM hosts)

| 

  * CPU utilization
  * Memory
  * Load average
  * Disk I/O
  * Network
  * Software versions
  * Service health
    * Openstack HTTP error rates

| 

  * Prometheus

|   
  
L2 Openstack metrics| 

  * L2

| 

  * Control plane VMs

| 

  * CPU utilization
  * Memory
  * Load average
  * Disk I/O
  * Network

|   
|   
  
L3 Openstack metrics| 

  * L3

| 

  * Account VMs
  * TBD Bare Metal instances (GA)

| 

  * CPU utilization (of Bare Metal instances?)
  * Memory
  * Load average
  * Disk I/O
  * Network
  * Ping

|   
|   
  
Cloud Store service metrics| 

  * L2

| 

  * Prometheus exporters
  * TBD OpenTeleMetry protocol (OTLP) sources ?

| 

  * Software versions
  * Control plane health
  * CPU usage
  * Memory
  * Filesystem usage
  * Services metrics
    * Health, e.g. HTTP Error rates
    * Capacity, e.g. free space

| 

  * Prometheus

|   
  
Value metrics| 

  * L2

| 

  * CloudStore API (prometheus exporter ?)

| 

  * Number of cores managed by OPCP
  * Number of cores managed by Cloud Store
  * Ceph storage cluster usage (GB)
  * ?

| 

  * Prometheus?

| Infinite
