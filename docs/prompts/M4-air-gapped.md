---
id: object-storage-on-cloud-store/user-stories-m4-air-gapped
type: reference
diataxis: explanation
title: "Milestone 4 · 'Air-gapped'"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Milestone 4 · "Air-gapped"

> **User story:** *As a **disconnected customer**, I run and grow the Object Storage Service entirely offline — pulling artifacts locally and ordering hardware myself — with the responsibility boundaries made explicit.*
>
> **Reached at the end:** the Service deploys + operates with **zero external dependencies** — local artifact mirrors (Harbor, OS + firmware), offline upgrades, and a local IdP fallback. Because the platform **no longer monitors cluster health** on an air-gapped site, the **legal / SLA responsibility shifts to the customer**, and the product documentation makes capacity monitoring + hardware-ordering the customer's job (Product Brief §10).
>
> **Why this milestone:** air-gap is the SecNumCloud-grade deployment target and it changes the operating model (who watches the cluster, who orders hardware in time). Done-test: a full install + scale-out completes with no internet access, and the responsibility wording is signed off.

---

## Personas

## Visual

![M4 · Air-gapped](visuals/os-m4-visual.png)

---

> **M4 is mostly an L2 milestone.** The IT-Admin owns the cluster lifecycle, capacity monitoring, and hardware ordering. The L3 end user is unaffected — they just keep using the storage.

| Tier | Persona | What they do in M4 |
|---|---|---|
| **L2** | **IT-Admin** | **Owns it:** runs the cluster lifecycle (scale / upgrade), **monitors capacity + orders hardware in time**, operates offline from local artifacts. *Most of M4 is here.* |
| **L3** | **End user** | No change — just keeps using buckets/objects/credentials as in M2/M3. |
| **L1** | **DC Operator** | Physically racks the hardware the L2 IT-Admin ordered. (Minimal, reactive.) |

---

## Components introduced (M4)

| Component | Role in M4 |
|---|---|
| **Local artifact mirrors** | Harbor + OS/firmware images on-site; the package pulls locally. |
| **Offline upgrades** | upgrade flow with no external fetch. |
| **Local IdP fallback** | identity works without the upstream Keycloak. |
| **Responsibility / capacity model** | in-product capacity prediction + alerts + the legal/SLA wording + ordering docs. |

---

## What's built (layer by layer)

- **`oss-cp` (L2 surface):** the local mirrors + offline-upgrade flow + IdP fallback + the **L2 lifecycle & capacity admin** (scale, upgrade, capacity dashboard, hardware-ordering prompts) are added; everything from M1–M3 now runs disconnected.
- **Ceph data plane:** unchanged technically; capacity monitoring + ordering become the **L2 IT-Admin's** responsibility (per Brief §10).
- **Landing Zone (L3):** unchanged — the end user keeps using buckets/objects normally; the capacity-insight + ordering surfaces live in the L2 admin, plus the service-description / product docs that spell out the monitoring + ordering duties.

---

## Dependencies + open questions

- Depends on **M3** (the full compliant stack) running from local artifacts.
- **OSQ-13** — the **legal / SLA wording** for capacity monitoring + hardware ordering on a disconnected site (Product Brief §10). Needs legal + product sign-off.
- Aligns with the OPCP artifact-distribution direction (PCI S3 bucket — ADR 0054) for getting artifacts to customers.
