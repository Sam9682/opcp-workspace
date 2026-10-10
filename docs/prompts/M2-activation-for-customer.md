---
id: object-storage-on-cloud-store/user-stories-m2-activation-for-customer
type: reference
diataxis: explanation
title: "Milestone 2 · 'Activation for Customer' *(compliance-deferred beta)*"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Milestone 2 · "Activation for Customer" *(compliance-deferred beta)*

> **User story:** *As an **IT-Admin**, I activate the Object Storage App for an Account, so an **end user** can create S3 credentials and account-segmented buckets and manage their objects — self-service, via the Landing Zone + S3 API.*
>
> **Reached at the end:** an Account has Object Storage enabled. An end user opens the Landing-Zone "Object Storage" section, **creates an S3 access key** (secret shown once), creates **buckets** scoped to their account, and uploads/downloads objects directly against RGW S3. Quotas-per-account are enforced via the Business Logic. *Like CB's M2, this is a **compliance-deferred beta**: direct endpoints, no proxies, single-Keystone acceptable — the SecNumCloud layer lands in M3.*
>
> **Why this milestone:** it proves the **identity chain + credential middleware + BL integration** end-to-end — the first real customer value. Done-test: an end user in an enabled Account creates a key, makes a bucket, and `s3 cp`s a file up and back.

---

## Visual

![M2 · Activation for Customer](visuals/os-m2-visual.png)

---

## Personas

| Tier | Persona | What they do in M2 |
|---|---|---|
| **L2** | **IT-Admin** | Activates the Object Storage App for an Account; sets the account quota. |
| **L3** | **End user** | Creates S3 credentials + buckets via the Landing Zone; uploads/manages objects (S3 API / UI). |

---

## Sequence

1. **① L2 activates** the App for an Account (per-account dataplane deploy).
2. **② Identity wired** — the Account federates into the dedicated Keystone (via the Keystone↔Keycloak federation); the BL provisions the account + quota.
3. **③ L3 requests a credential** — Landing Zone → S3 credential middleware → dedicated Keystone (EC2) → key returned (secret once).
4. **④ L3 creates buckets + objects** — Panel/S3 client uses the credential **directly against RGW S3** (account-segmented).

---

## Components introduced (M2)

| Component | Role in M2 |
|---|---|
| **Dedicated Keystone** | fronts RGW for S3/EC2 auth |
| **Keystone↔Keycloak federation** | Account identity, **reused from CB** (KeystoneDomain) |
| **S3 credential middleware** | temp + permanent EC2 keys (**SOV-514 reuse**) — see [middleware doc](../architecture/objectstorage-middleware.md) |
| **Business-Logic adapters** | account activation + quotas-per-account + usage |
| **Landing-Zone UI** | buckets (versioning, lifecycle, static-website), objects (upload, HTTP headers), access keys — see [L3 UX](../architecture/l3-ux-wireframes.md) |

**Identity chain:** `Ceph → RGW → Keystone (in oss-cp) → Keycloak (CloudStore BL)`.

---

## What's built (layer by layer)

- **`oss-cp`:** the dedicated Keystone + federation + S3 credential middleware + BL adapters join the control plane built in M1.
- **Ceph data plane:** unchanged from M1; now serving authenticated S3 traffic per account.
- **Landing Zone (L3):** the Object-Storage UI goes live — buckets, objects, access keys, per-account cost view.

---

## Beta cut (compliance deferred to M3)

- **No proxies** — S3/RGW endpoints exposed directly (beta consumers accept the endpoint change at M3).
- **Single-Keystone acceptable** — the SNC admin/user 2-Keystone separation is M3.
- **No KMS / per-bucket encryption** — M3.

---

## Dependencies + open questions

- **OSQ-02 deploy detail** — how the dedicated Keystone + middleware are packaged in `oss-cp`.
- **OSQ-03 (BL capacity)** — account activation + quota + usage need BL capacity (full until June). **The schedule driver for M2.**
- **OSQ-06** — public vs private S3 endpoints for the beta.
- Depends on **M1** (a healthy cluster + RGW).
