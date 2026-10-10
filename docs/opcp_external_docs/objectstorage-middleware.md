---
id: object-storage-on-cloud-store/architecture-objectstorage-middleware
type: deep-dive
diataxis: explanation
title: "Object Storage Middleware (S3 credential proxy)"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Object Storage Middleware (S3 credential proxy)

> **Source:** Jira **SOV-514** "object storage middleware for panel" (Epic, *Analyzing*; reporter Jan Runkel; parent **LVL2-23684** PaaS SNC – urgent post-GA Q4FY26; start 25-Jun-26) + **ADR 0045** ([Confluence](https://confluence.ovhcloud.tools/display/PSPUSNC/0045+-+objectstorage+middleware+for+panel)). Comments by Asim Ijaz Ahmad + Boris Behrens.
>
> **Stance:** this is **SNC** middleware we want to **reuse** for OPCP Object Storage — same pattern as CB reuses SNC components. It's the concrete mechanism behind the Landing-Zone "create S3 credentials" user story (Product Brief §7) and answers half of **OSQ-02**.
>
> ---
>
> ⚠️ **This page describes the SNC design (ADR 0045). What OPCP actually shipped is simpler — read this section before relying on the detail below.**
>
> **As built** for Object Storage ([`SOV-857`](SOV-857), Done) — per Jan Stuhlmann, 2026-08-26:
>
> | | SNC design (below) | **OPCP as built** |
> |---|---|---|
> | **Own database** | metadata DB (description, created, expires) | ❌ **none** — it is a pure proxy |
> | **Temp-key format** | `TMP_OVH_<UUIDv7>` prefix | **ordinary access keys, no prefix** |
> | **Temp-key cleanup** | cron parsing the UUIDv7 timestamp | the middleware runs a **scheduled cleanup** of the temporary credentials |
> | **Key metadata** (naming, expiry) | stored locally, joined on list | ⚠️ not part of the built scope |
>
> **The purpose that did survive intact is the important one:** Keystone's OS-EC2 endpoint returns the **secret key on every read**, so the middleware **strips it from the GET response**. A secret is visible exactly once, at creation, and can never be retrieved afterwards. Its second job is issuing the temporary access keys the panel UI uses, and cleaning them up.
>
> Everything below is retained as the SNC reference design and as the source of the reuse decision — **not** as a description of the running service.

---

## 1. The problem it solves

The Cloud Panel must let a logged-in user manage S3 keys + buckets. Two issues with talking to Keystone directly:
- **Secret-key exposure** — Keystone's **OS-EC2** endpoint returns *all* of a user's access **and secret** keys on list. Secret keys should never be retrievable after creation.
- **No metadata** — Keystone EC2 creds are raw strings; the user can't name a key ("Cyberduck Key") or see when it was created.
- **STS is dead** — the prior STS-based workaround only worked due to a Keystone bug that's now fixed (Boris, 28-Jan-26). So a middleware is needed.

## 2. What the middleware does

A thin service between the Panel and Keystone OS-EC2 that **never stores secret keys** and validates its own access-key list against Keystone (no orphans). It does **not** proxy data — the Panel talks **directly to Ceph S3** for bucket/file ops (no middleware bottleneck).

| Concern | Mechanism |
|---|---|
| **Panel session** | Panel requests a **temporary** EC2 cred → middleware creates it in Keystone, returns access+secret **once** → Panel uses it directly against Ceph S3. |
| **Temp-key format** | `TMP_OVH_<UUIDv7>` (Boris's recommendation). UUIDv7 embeds the creation millisecond — no separate state needed. |
| **Temp-key cleanup** | Lightweight **cron** (hourly): lists Keystone keys, filters `TMP_OVH_*`, parses the UUIDv7 timestamp, deletes any older than the session TTL (e.g. 24 h). Temp keys are **not** stored in the middleware DB. |
| **Permanent keys** (Cyberduck, AWS CLI…) | Middleware creates a permanent EC2 cred in Keystone, stores **metadata only** (description, created, expires) in its own relational DB, returns the secret **once**. |
| **Secure listing** | Fetch raw keys from Keystone, join with local metadata, **strip all secret keys**, reconcile orphans (drop local rows whose Keystone key is gone). |

## 3. Flow

```
Panel → Regional Middleware → Regional Keystone (OS-EC2) → EC2 creds returned → Panel → Ceph S3
        (uses the user's Keystone token/session; NO cross-control-plane communication)
```

The Panel calls the **regional** middleware synchronously with the user's Keystone token; the middleware mints EC2 creds in the **appropriate regional Keystone**; the Panel then hits S3 directly.

## 4. API surface (project-scoped)

Endpoints are scoped by `project_id` (OpenStack/Keystone is multi-tenant — creds bind to a project, not a global user).

| Endpoint | Action |
|---|---|
| `POST /api/v1/projects/{project_id}/storage/session-credentials` | Create a temp `TMP_OVH_<UUIDv7>` pair (returns access+secret). |
| `DELETE …/session-credentials/{access_key}` | Logout — delete the temp pair from Keystone early (204). |
| `POST …/storage/credentials` | Create a **permanent** EC2 cred (+ description, optional `expires_at`); secret returned once. |
| `GET …/storage/credentials` | Reconciled, enriched list (access keys + description + expiry). **No secret keys.** Cleans orphan local rows. |
| `PATCH …/storage/credentials/{access_key}` | Update local description/expiry only (Keystone cred untouched). |
| `DELETE …/storage/credentials/{access_key}` | Delete from Keystone **and** local DB (204). |

## 5. Implications for OPCP Object Storage

- **Reuse target.** This SNC middleware is the credential layer the OPCP OS package needs for the Landing-Zone "create S3 credentials / account-segmented buckets" story. Plan to reuse, not rebuild (CB pattern).
- **It answers half of OSQ-02** — *how LZ users get S3 creds without secret-key exposure*. **Still open:** the **Keystone topology** the middleware points at (single OPCP Keystone vs SNC's 2-Keystone S3-user/S3-admin split), and how the middleware is **packaged + deployed** inside the OS CloudStore Package (it's "regional" in SNC).
- **Dependencies / links:** blocked-with **GSSNC-308** (S3 credentials not working — EC2/STS). It's a **Business-Logic-flavoured** component (Jira components: BL.businessLogic, BusinessLogic.CloudStore, Experience.CloudStore, Storage.OPCPCore) — so it sits in the **BL capacity** risk (OSQ-03).
- **Data plane unchanged** — Panel→Ceph S3 stays direct; the middleware is control-path only. No throughput concern.

## 6. Cross-references
- [Open questions](../open-questions.md) — OSQ-02 (access control), OSQ-03 (BL capacity).
- [Architecture index](README.md) · [Keycloak Federation deep-dive](../../../../../generic/keycloak-federation/summary.md) (Keystone topology).
- ADR 0045 — distilled in [SNC ADR alignment §2](../../compute-block-on-cloud-store/plans/snc-adr-alignment-2026-05-19.md).
- Jira: SOV-514 · GSSNC-308 (linked) · parent LVL2-23684.
