---
id: object-storage-on-cloud-store/architecture-l3-ux-wireframes
type: deep-dive
diataxis: explanation
title: "Object Storage — L3 UX (Landing-Zone wireframes)"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Object Storage — L3 UX (Landing-Zone wireframes)

> **Source:** wireframe deck *"Object Storage.pdf"* (Partner Panel / Landing Zone, shared by Marc 2026-05-21, *"how it should look for L3 later"*). The L3 **end-user / dataplane** surface (OSQ-05 dataplane). *Drop the PDF into `Input/_to_process/ObjectStorage/` for the archive.*
>
> **Why it matters:** defines the concrete L3 feature scope the OS Package + middleware must support, and confirms the **SOV-514 access-key UX** (one-time secret).

---

## Context binding
- S3-compatible storage **bound to the current project + selected region** (region selector seen: *development (RBX)*, *Production GRV*). → multi-region, project-scoped (matches the SOV-514 middleware's `project_id` scoping).
- Surfaces: Partner Panel → OPCP Core → Cloud Store → **Landing Zone**.

## Three management areas

### 1. Buckets
- Create buckets (name **unique across the whole storage cluster** — may already be taken by another user).
- List shows per bucket: **size**, **object count**, **status** (*Not publicly shared* / *Public website*).
- Per-bucket settings: **access · versioning · life cycles** (flat object structure).
- Action menu: *Show Bucket Settings · Copy Web-URL · Delete*. Clicking the shared-indicator opens settings; public buckets expose a copyable URL.
- Perf note: for >1,000 objects, displayed size = total of the **first 1,000 objects** only.

### 2. Objects / Files
- Upload via **drag-and-drop**; folders; click opens a **detail view** (File Information).
- **Object Configuration — HTTP headers** controlling how an object is served:
  - **Content-Disposition**: Auto (default) / Inline / Attachment (download).
  - **Cache-Control** (e.g. no-cache), **Content-Type** (e.g. text/html), **Content-Encoding** (e.g. UTF-8).

### 3. Access Keys
- "Create Access Key" → programmatic access to all buckets (access-key ID + secret).
- **Secret shown only once** — "copy and store securely, you will not be able to retrieve it again" → **exactly the SOV-514 middleware's one-time-secret behaviour**. The UI is the front-end of that middleware.

## Bucket-as-website (static hosting)
- Toggle **"Serve this bucket as a website"** (Off/On) → all objects publicly viewable via the bucket URL.
- **Website Content Settings**: index document (`.index.html`), file upload.
- → public/private exposure is a **per-bucket** user choice — feeds **OSQ-06** (where storage is available + who can access).

## Background Jobs panel
- A dedicated UI element for long-running ops (uploads, deletes) so the user isn't blocked. Minimise / clean / close.

---

## What this pins down (cross-links)
- **OSQ-05 (dataplane)** — confirms the L3 feature set: buckets (CRUD + versioning + lifecycle + public-website), objects (upload + HTTP-header config), access keys, cost view.
- **SOV-514 middleware** — the Access-Keys area is its UI; one-time secret + permanent keys confirmed. See [`objectstorage-middleware.md`](objectstorage-middleware.md).
- **OSQ-06 (exposure)** — per-bucket public-website toggle is the customer-facing "who can access" control.
- **OSQ-09 (feature scope)** — versioning, lifecycle, static-website, object metadata headers are the concrete S3 features to commit to (check against the [OVH Local-Zone limitations KB (KB0065306)](https://help.ovhcloud.com/csm/en-public-cloud-storage-s3-local-zone-limitations?id=kb_article_view&sysparm_article=KB0065306)).
- **Note:** wireframes are L3-only — **L1/L2 admin views** (cluster health, capacity, quota-per-account, price-per-GB, feature-flags from Brief §7) are a separate UX, not in this deck.
