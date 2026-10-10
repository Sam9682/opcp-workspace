# OPCP - Landing Zone Manager

> **🧭 VISION — Product idea (Product Management), NOT implementation status.** Mirror of the Confluence page [pageId 927201280](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=927201280) (v5, last modified 2026-06-24; re-synced 2026-07-15). Source = Confluence; on drift, Confluence wins. Use: planning/doc context for projects + runbooks.

---

Projectsf0e70dd9-2bc3-31da-a16b-974623242708LVL2-18606

## Overview

This page describes the initial target for the Landing Zone Manager adapted from the SNC Cloud Platform design.

## Philosophy

The UI should cover 80% use cases; the corner / power user cases should be possible using Horizon.

## Features

* User and group Management (without keycloack)
* Project Management and global switch
* Resource consumption
  * OPCP Core related: VM, Block, Networks, Load Balancer
  * Other apps
    * S3
    * OVHCloud products like MKS, KMS, ...
    * Third party products
* Observability
* Profile management
  * Name, email
  * 2FA
  * SSH keys
  * Language
  * API credentials

## Open questions



## Design

<https://www.figma.com/design/x3kCSfzWPKwKta6DjAFRwI/OPCP-Flow?node-id=10324-3831&p=f&t=P0DoCqIraL6qV3BE-0>

## Future work

In order to reuse mainstream UIs (typically, the MKS UI), this interface will need to converge towards the Mainstream Manager

