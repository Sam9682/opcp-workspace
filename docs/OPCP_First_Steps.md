# OPCP First Steps Guide

This document outlines the initial steps for customers to begin their OPCP (Open Public Cloud Platform) journey, covering hardware receipt, software installation, training, and other essential components.

## Shared Responsibility Matrix

### Customer Responsibilities
- Security within OPCP
- Operations maintenance
- Hardware/Infrastructure management
- Operating Systems installation (other than CloudStore)
- Instance and configuration of CloudApps (Compute, Storage, DB, Networking)
- Landing Zone deployment and configuration for dedicated accounts
- Customer Network between DCs

### OVHcloud Responsibilities
- Security with OPCP
- Configuration of OPCP infrastructure
- Management of CloudStore deployment

### Disclaimer
This matrix is not contractual. Simplifications apply during technical workshops. Refer to precise OVHcloud Legal CGV for OPCP.

## Installation & Pre-requisites

### OPCP Pre-requisites (1/3)
OVHcloud handles OPCP configuration, but customers must provide:

#### Network Requirements
- Management network definition (Subnet, VLAN ID, IP Address, VIP address, Default gateway)

#### DNS Configuration
- Domain name definition
- External domain resolution capability (for S3 connections)
- IP Address for DNS resolution

#### NTP Configuration
- Connection to external NTP service (IP Address)

#### Syslog Servers
- Centralized logging from OPCP (IP Address)

#### Certificate Requirements
- Intermediate certificate (non-root-CA) provided by Customer MP
- Certificates must be recognized by public certification authorities

#### Backup Configuration
- S3 endpoint
- Access Key
- Private key
- Bucket name

#### LDAP Configuration
- Centralized user access across all OPCP Keycloak (IP of AD Servers)

### Certificate Details
Four options for certificate handling:
1. Private CA deployed in Control Plane
2. Customer provides private CA (automated by OPCP)
3. Customer provides certificates for all endpoints
4. OPCP generates own certificates (Let's Encrypt)

Note: Non-root-CA life duration extends to 2034.

## Connecting OPCP to Customer Network (2/3)

### Day 1 Configuration
OVHcloud handles edge configuration to existing on-premises network. Future API will enable network topology modifications.

### Network Topology Requirements
Complete schema for each edge:
- Port usage based on bandwidth
- VLAN configuration and topology
- VLAN IDs and Names (optional)
- Port configurations (access/trunk)
- Trunk settings (authorized VLANs + native VLAN)
- Routing information (IP addresses for each VLAN interface)

### Best Practices
- Ensure trunk consistency between switches
- Both sides must have same native VLAN to prevent traffic misrouting

## Environment Variables & Naming Convention (3/3)

### Configuration Variables
Confirm OPCP configuration variable values for each DC:
- `env`: "opcp-dcs" (used in logs, backups, etc.)
- `region`: "DCS" (OPCP region = OpenStack region)
- `stage`: "prod" (alerting, Control plane backup)
- `org`: "CLIENT" (not used)
- `site`: "DCS" (used in Netbox)
- `location`: "LUXDCS-1" (used in Netbox)

### Controller Naming Convention
Controllers are not fixed by OVHcloud. Customer-provided naming follows syntax:
```
opcp-{location}-{env}-{podID}-{control-plane-index}
```

## On-Premises Integration

### Log Management
- Syslogd and syslog forwarder architecture
- Syslog endpoint configuration
- Log debug level configuration
- OPCP Controller logging capabilities
- Optional dual logging (on-premises and LDP at OVHcloud)

## First Access & Configuration Agenda

### Step-by-Step Configuration
1. **Access, Project and Users**
   - Verify API and GUI admin accesses
   - Create management VLAN
   - Create Groups and Users
   - Create Projects (isolation)
   - Validate access to Netbox
   - Define number of Bare Metal servers in project

2. **Bare Metal Servers Installation**
   - Create project Users with reader/member permissions
   - Check BM availability on OPCP
   - Enroll servers into the Project
   - Install instances (reader/member user responsibility)

## PSMC Team Initiatives

### Training Content & Workshops
1. **OPCP First Steps**: Training content
   - Hands-on introduction to OPCP
   - 1-day training on user management, networking, compute
   - Focus on Keycloak and OpenStack CLI/Horizon interface
   - Target audience: Customer (SysAdmin) & Internal (TAM, Support)
   - [Training Link](https://opcp-psmc.com:6113)

2. **OPCP Automation**: Training content
   - 1-day training on access methods (API access, OpenStack SDK, Infrastructure-as-Code)
   - Target audience: Customer (SysAdmin) & Internal (TAM, Support)
   - [Training Link](https://opcp-psmc.com:6117)

3. **OPCP Explorer**: AI Demo & Use Case
   - Demo solution for hosting applications with AI-based management
   - Features: Shared GPU, Container, Agentic AI DevOps
   - Target audience: Software development engineers, ML engineers
   - [Demo Link](https://opcp-psmc.com)

4. **OPCP Simulator**: OpenStack Simulator
   - Pure-Python, in-memory OpenStack simulator
   - Simulates Keystone, Nova, Neutron, Cinder, Ironic, and Glance services
   - Target audience: Customer (SysAdmin) & Internal (TAM, Support)
   - [Simulator Link](https://opcp-psmc.com:6125)

### Internal Ongoing Initiatives
1. **OPCP Introduction**: Non-technical training
   - 1-day training on OPCP basics, first steps, concepts, operations, best practices
   - Target audience: Customers (non-tech) & Internal (Sales, Pre-Sales)
   - [Training Link](https://opcp-psmc.com)

2. **OPCP Proxmox**: Installation & GPU usage
   - Installation of Proxmox on OPCP bare metals
   - Core concepts, bare metal provisioning, VE installation, GPU passthrough, VM creation with GPU
   - Target audience: Customer for demo purposes
   - [Training Link](https://opcp-psmc.com)

3. **OPCP AI Start Labs**: DevOps AI
   - Introduction to AI on OPCP environment
   - Experiment Ops AI Agent + Dev AI Agent + GPU sharing + Serverless on OPCP
   - Target audience: Software development engineers, ML engineers for demo purposes
   - [Training Link](https://opcp-psmc.com)

4. **OPCP Companion**: Documentation Chatbot
   - AI-powered chatbot answering questions on OPCP based on documentation
   - Internal access only (for now)
   - Target audience: All OVH staff working on OPCP (for now)
   - [Chatbot Link](http://gw2sdev-docker.ovh.net:36798)