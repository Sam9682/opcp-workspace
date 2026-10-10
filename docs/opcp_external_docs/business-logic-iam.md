---
id: compute-block-on-cloud-store/architecture-business-logic-iam
type: deep-dive
diataxis: explanation
title: "SNC Business Logic + IAM — architecture + OPCP reuse map"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# SNC Business Logic + IAM — architecture + OPCP reuse map

> **Source:** Material attached to [`SOV-406`](SOV-406) ("Merge IAM/BL Design", BLOCKED). 13 PDFs + 1 Excalidraw PNG dropped 2026-05-12 PM into `Input/Business Logic Cloud Store/` (gitignored). Distilled here so OPCP M2 has a concrete reuse-vs-net-new map.
>
> **Why this doc exists:** Vincent Casse's 2026-02-11 flag on `LVL2-22779` ("this work needs more design to define what we use on business logic team and CloudStore team") + Q-111 in [`open-questions.md`](../open-questions.md). The CAIM material answers most of it; what remains is captured as Q-208–Q-216.
>
> **Status:** First-pass extraction 2026-05-12 PM. **Likely unblocks `SOV-406`** modulo ~5 concrete decisions (see [§6.1](#61-new-open-questions-q-208--q-216)). Owner for review: Ibrahim Takouna (EXT) + Vincent Casse.
>
> **2026-05-19 — Related SNC ADRs (cross-reference when extending this doc):**
> - **ADR 0047 *Keycloak HA Deployment*** *(Distributed Topology PostgreSQL clusters via S3 — selected solution)* — the deployment-layer topology that sits under the L1/L2/L3 federated Keycloak framing in §3 + §5. Confirms Infinispan distributed cache + cnpg PostgreSQL replication. Affects how each Keycloak (L1 OPCP Core / L2 CloudStore / L3 per-Account) is actually deployed.
> - **ADR 0052 *Keystone wrapper credentials and access*** *(domain-scoped `service-keystone-wrapper` role, per-deployment Keystone credential)* — answers **Q-214** (how does CAIM authenticate to OPCP Keystone(s) when wrapper-drone calls them?) with a concrete pattern. The `region-wrapper-drone` consumes this. Q-214 should refine / close once OPCP-Compute confirms it inherits this pattern (or defines its deviation).
> - **Full ADR cross-mapping with impact analysis:** [`snc-adr-alignment-2026-05-19.md`](../plans/snc-adr-alignment-2026-05-19.md) (PM-private).

---

## 1. Executive summary

SNC's "Business Logic" is owned by **Team CAIM** and is a **Python micro-services stack** that exposes a single REST API for managing the IDAM object hierarchy (Organization → Project → User → Role). It is the **only** software allowed to write to the IDAM persistence layer (global Keycloak + per-region Keystones). It is **not** the IAM data plane itself — Keycloak and Keystone remain the source of truth; CAIM is the **management plane** that mediates all customer-driven IDAM changes.

**For OPCP M2 this means:**

- **Reuse as-is (deploy SNC's CAIM stack inside CloudStore Service)** — the API drones, service drones, wrapper drones, controller drone, and CAIM-Redis are concern-separated containers, packaged with Helm + distroless images. They are already designed to talk to "Region Keystones" *plural* — OPCP-Compute regions can be additional Keystone targets without re-architecting CAIM. This is the path `CLOUD-587` (IAM/BL Implementation) should take.
- **Reuse with adaptation** — the **OIDC token shape** (claim `projects` aggregated from Keycloak group attributes, with regex-guarded `json_mapping` in Keystone) is the contract that the OPCP-side `KeystoneDomain` reconciler must honour. `CLOUD-600` (cloudstore.yaml IAM adaptation) and `SOV-254` mapping resources must produce the same claim/mapping structure SNC uses today.
- **Net-new in OPCP** — SNC's current bootstrap (creating an Organization = Realm + four Keystone pairs) is a **manual L2 admin runbook**: edit `paas-apps-infra` and `paas-secrets-infra` repos, encrypt secrets with sops/age, raise MRs. OPCP cannot ship this. The OPCP M2 path replaces it with the `KeystoneDomain` CR + `SOV-254` Keystone Controller's 6-resource chain. What is genuinely net-new is the **automated equivalent of the manual howtos** — and Q-113's "manual fallback" is exactly those howtos.

### Top 3 risks / open questions

1. **Bootstrap of the first Organization is still manual in SNC.** Team CAIM Overview §3.1 explicitly says *"The initial setup of a customer's organization and the first admin user is at the moment a documented manual layer 2 admin interaction."* The CAIM BL API does NOT cover Organization creation today — `/organizations` only exposes `GET / PATCH / DELETE`, no `POST`. OPCP M2 needs to decide who creates the Organization (Realm + Keystone Domain) per Account: KeystoneDomain CR via SOV-254, manual Cloud Packager, or extended CAIM API.
2. **CAIM only knows Organization / Project / User / Role.** It does NOT manage Keycloak Groups, Group attributes (`project_<region>`), Client scopes, or Mappers — those are still set up manually per the howtos. For OPCP M2, the "Group attribute drives Keystone project membership" wiring is **net-new automation** even if the CAIM stack is reused.
3. **CAIM's design assumes a "Global Control Plane Keycloak" and many "Region Keystones".** OPCP-Compute regions slot in cleanly as additional Region Keystones — but the Keystone instance topology in SNC is *four pairs per Organization* (BMPOD-admin, BMPOD-user, S3-admin, S3-user). OPCP-Compute is **one** Keystone per region (no admin/user split, no S3 axis). The CAIM `region-wrapper-drone` config and `json_mapping` regex need to be re-validated for this simpler topology.

---

## 2. SNC BL architecture

### 2.1 Component map (Team CAIM stack)

CAIM is a **single stack** of containerized Python drones running on a Control Plane Kubernetes cluster, fronted by a Layer-3 Global Control Plane Proxy. It has **four functional container types**:

| Container type | Role | Concrete drones in scope |
|---|---|---|
| **API drones** | Sole customer entry point; horizontally scalable; unified URI path via NGINX | `CAIM-idam-api-drone`, `CAIM-requests-api-drone` |
| **Controller drone** | Supervisor: governs task-wise execution, rollbacks, transactionality, recoverability | `CAIM-controller-drone` |
| **Service drones** | Concern-separated; each owns one IDAM object type (Organization, Project, User); can call other services + wrappers | `CAIM-organization-service-drone`, `CAIM-project-service-drone`, `CAIM-user-service-drone` |
| **Wrapper drones** | Concern-separated; each owns ALL communication with one external system (Keycloak, Keystone). Terminal — never call other wrappers/services. Throttle outgoing traffic per destination. | `CAIM-keycloak-wrapper-drone`, `CAIM-region-wrapper-drone`, `CAIM-object-storage-wrapper-drone` |
| **CAIM-Redis** | Shared working memory, queue, locks, comms layer. Transient only. | `CAIM-redis` |

All persistence is **outside** CAIM (in Keycloak + Keystone). CAIM-Redis holds only ephemeral request state.

**Outside dependencies:** fluentd (log scooping), observability stack (OpenTelemetry), L3 proxy, connectivity to all wrapped backends (Regional Keystones, Object Storage Keystones, global Keycloak).

**Build/deploy stack** (relevant for `CLOUD-616` Terraform):

- Python services packaged with **Pants** + **PyInstaller** → single-file binary
- Distroless runtime image: `gcr.io/distroless/base:nonroot`, non-root user, ldd-trimmed shared libs
- **Helm** charts package K8s resources; **GitLab CI** runs the pipeline; **BuildKit/Buildx** for multi-arch
- K8s resources used: `Deployment`, `Service`, `Ingress`, `NetworkPolicy`, `Namespace`, `ConfigMap`, `Secret`. HPA enabled where configured.
- Secrets fetched at startup from a central **OpenBao** (formerly Vault) in the global control plane.

### 2.2 Object model

The CAIM API exposes **three first-class resources** plus relationships:

| Object | Defined in | Who creates it | Where it lives | Notes |
|---|---|---|---|---|
| **Organization** | API path `/organizations` — `GET / PATCH / DELETE` only (no `POST`!) | **Manual L2 admin** today (per "How to create a new Organization" howto) | Keycloak **Realm** + Keystone **Domain** (one Realm maps to one Domain per Keystone pair) | Top of the hierarchy. CAIM cannot create Organizations via API yet. |
| **Project** | `/projects`, plus nested under `/organizations/{name}/projects` | CAIM via `createOrganizationProject` (POST) | Keycloak **Group** + Keystone **Project** in the org's Domain | "A Group in Keycloak represents a Keystone Project" (How to manage Users §How to create a Group). |
| **User** | `/users`, plus nested under `/organizations/{name}/users` | CAIM via `createOrganizationUser` (POST) — and manually in Keycloak today (per howto) | Keycloak **User** in the realm | Username + email required. New users get default composite role `default-roles-<realmname>`. |
| **Role (org-level)** | Implicit in `related_users` relationship payloads (string array `roles`) | Manual Keycloak: assigned via "Role mapping" tab; org roles tagged `realm-management` | Keycloak realm role | "Organization-role allows to manage users and projects." |
| **Role (project-level)** | Implicit; carried in the `projects` claim of the OIDC token | Manual: create a **Keycloak sub-group** named `<role>.<project>` inside the project's group, with attribute `project_<region>` = JSON role assignment | Keycloak sub-group + sub-group attribute | Pattern is **strict**: subgroup name must be `<role_name>.<project_name>` or Keystone fails to interpret. |
| **Realm** | Manual in Keycloak Admin Console | L2 admin | Keycloak | Realm name must be snake_case. |
| **Client** | Manual in Keycloak Admin Console — one client **per Keystone instance** that federates with this Realm | L2 admin | Keycloak (per Realm) | Type: OpenID Connect; Client auth ON; Standard flow ON; everything else OFF. Valid redirect URI: `https://<keystone-addr>/identity/v3/redirect_uri`. |
| **Client scope (dedicated)** | Manual; auto-created with client (`<client-name>-dedicated`) | L2 admin | Keycloak | Hosts the OIDC token mappers. |
| **Mapper: `projects`** | Manual on dedicated client scope | L2 admin | Keycloak | Type: *Aggregate User/Group Attribute (as JSON String)*. Name=`projects`, Attribute=`project_<region>`, Token Claim=`projects`, Multivalued ON, Aggregate ON. **This is how project membership flows into the OIDC token.** |
| **Mapper: `username`** | Manual on dedicated client scope | L2 admin | Keycloak | Type: User Attribute. Name=`username`, User Attribute=`username`, Token Claim=`username`. |
| **Group** | Manual in Keycloak; **= Keystone Project** | L2 admin / future CAIM | Keycloak | Top-level group named after the project (e.g. `qa`). |
| **Sub-group (project-role)** | Manual; sub-group of the project's group | L2 admin | Keycloak | Name pattern `<role>.<project>` (e.g. `member.qa`). Carries `project_<region>` attribute. |
| **Identity Provider mapping** | Manual; YAML in `paas-apps-infra` (S3) or `fleet-infra-hieradata` (BMPOD) | L2 admin / future CAIM (out of scope today) | Keystone config | Tells Keystone how to consume the Keycloak OIDC token (see [§2.4](#24-authentication--federation-flow-end-user--openstack-api)). |

### 2.3 Data flow — what happens when an IT-Admin "enables Compute & Block for an Account"

In SNC today, this maps to **"How to create a new Organization"** (Org = Account). The flow has **4 steps**, each setting up a separate **Keycloak ↔ Keystone pair**:

1. **BMPOD Keystone ← L2 → BMPOD Keycloak** (admin path into bare-metal / control plane)
2. **Regional S3 Keystone ← L2 → BMPOD Keycloak** (admin path into S3)
3. **BMPOD Keystone ← L3 → Global Keycloak** (end-user path into compute)
4. **Regional S3 Keystone ← L3 → Global Keycloak** (end-user path into S3)

Each step contains the same sub-pattern:

| Sub-step | Action | Target | Manual today? |
|---|---|---|---|
| a | Log into Keycloak Admin Console | Keycloak (BMPOD or Global) | Yes |
| b | Create Realm (if not exists) | Keycloak | Yes |
| c | Create Client (one per Keystone target) | Keycloak | Yes |
| d | Configure client scope: add `projects` + `username` mappers | Keycloak | Yes |
| e | Create first user + first group/sub-group + assign role | Keycloak | Yes |
| f | Add IdP entry to Keystone YAML (`identity_providers` block) | `paas-apps-infra` / `fleet-infra-hieradata` repo | Yes — git MR |
| g | Encrypt `client_secret` with sops+age, store in `paas-secrets-infra` / passwords yaml | secrets repo | Yes — git MR |
| h | Add Keystone federation mapping (`post_setup.identity_providers.<name>.json_mapping`) with the big regex | Keystone config | Yes — git MR |

**No API call exists for steps b–h.** This is the manual bootstrap that Q-111 + Q-113 are about. After the MR is merged and Flux propagates (~minutes), end-users in that Realm can SSO into the corresponding Keystone.

**Day-2 ops (after bootstrap)** flow through the CAIM REST API:

- IT-Admin / customer admin calls `POST /organizations/{org}/projects` → CAIM controller-drone schedules the request → `project-service-drone` calls `keycloak-wrapper-drone` (create Group) + `region-wrapper-drone` (create Keystone Project in the Domain).
- IT-Admin calls `POST /organizations/{org}/related_users` → `user-service-drone` creates Keycloak user, `project-service-drone` (via relationship endpoints) attaches roles by adding the user to the right sub-group.
- All calls are **async-first**: every mutating call returns 202 with a `request_uuid`; client polls `/requests/{request_uuid}` for status. Synchronous GETs are deferred.

### 2.4 Authentication / federation flow (end-user → OpenStack API)

Pieced together from the howtos:

1. End-user opens Horizon (or another customer GUI) → redirected to **Global Keycloak**, logs into their Realm.
2. Keycloak issues an OIDC token. Token contains claims:
   - `sub` (HTTP_OIDC_SUB) → maps to Keystone `user.id`
   - `username` (HTTP_OIDC_USERNAME) → maps to Keystone `user.name` (prefixed `global-keycloak/` in the `json_mapping`)
   - `projects` (HTTP_OIDC_PROJECTS) → JSON array of `{name, domain, roles}` aggregated from all the user's sub-groups' `project_<region>` attributes
3. User clicks a regional service → redirected to that **Region Keystone**'s `/identity/v3/redirect_uri`.
4. Keystone consults its `identity_providers` config (per Realm), validates the token via the `issuer_url`'s `.well-known/openid-configuration`, decrypts using `client_secret`.
5. Keystone applies the `json_mapping` (federation mapping):
   - **Local rules**: `user.id={0}`, `user.name=global-keycloak/{1}`, `domain.name=<realm-name>`, plus `projects_json={2}`
   - **Remote claims**: `HTTP_OIDC_SUB`, `HTTP_OIDC_USERNAME`, `HTTP_OIDC_PROJECTS`
   - A large **regex** in the L3 (global) mapping prevents privilege escalation: it blocks any token that tries to claim a Keystone domain other than its own Realm, blocks `admin` and `service` roles from L3 users, etc.
6. Keystone issues its own scoped token for OpenStack API calls.

### 2.5 The Excalidraw diagram

The PNG (`Input/Business Logic Cloud Store/excalidraw_export.png`, 5 MB) is a **dense, multi-panel design diagram**. What's visible:

- **Top-left panel: "CAIM NETWORK TOPOLOGY"** — same as in the Team CAIM Overview PDF (page 2). Shows: Customer → Panels → Global L3 Control Plane Proxy → NGINX → CAIM API Layer (`idam-api-drone`, `requests-api-drone`) → CAIM Logical Services (`organization`/`user`/`project-service-drones`) → CAIM-Redis ← Communication Wrappers (`keycloak`/`object-storage`/`region wrapper drones`) → outside services (Object Storage Keystone, Region Keystone). Control Plane Keycloak is drawn alongside NGINX, only for "Logins, Cred Management and Recovery". Colour legend: blue = "Local Component", green = "Team CAIM Component", yellow = "Other Layer Internal Component", grey = "OVH Internal".
- **Middle panel: "Cloud user creates the Enterprise"** — a deployment-flow swim-lane. Lanes labelled: *Enterprise*, *Cloud Packager*, *Tooling*, *Hardware* (right-most says "Acid scripts process unless filed automatically..."). Shows the flow from user → flux/git → kustomize → Hardware. Bottom strip: "MVP1 → ... operator → kustomize → flux".
- **Large bottom-left blue/green panel** — a stack diagram with three vertical bands: green "tooling+deployment" band on top (`PaaSinfra`, `RuntimeIdentity`, `paas-infra-mgmt`, `paas-app-infra`, `paas-policies-infra`, etc.), blue middle band (`Cluster + Cluster Catalog`, `Cluster Deployment`, `Cluster Networking`, `Cluster Storage`, `Cluster Identity`, `Cluster Observability`, `Cluster Auditing`), grey bottom band labelled "Hardware / IaaS Targets". Arrows flow top-down from tooling into cluster.
- **Pink/red panels on the right** — text blocks. Largest titled "**Skeleton**" — rollout/lifecycle rules for the stack. Below it a pink box "**Pool Use:**" with a feature checklist (Create a pause ✓, ssh control ✗, ssh deploy plan ✓, IA/RBAC, multi-tenant?). Smaller red boxes show the **3-level resource hierarchy** Organization → Project → Identity (User/Group/Role).
- **Bottom-most strip — numbered legend (16 items)** of deployment execution stages. Readable: 1) Infrastructure layout · 2) Layer 1 / Federation · 3) APIs out · 4) Infrastructure validation · 5) Workload project + Auth management · 6) Super-controllers deployed · 7) **Realm creation** · 11) Identity + tooling/Quota + spaces + agents/spaces provided · 12) Hardware retrieved from polling · 13) Python option configuration · 14) Power deployment and reconciliation · 15) Pivot ConfigMaps and Secrets.

**Interpretation for OPCP:** the diagram codifies the **SNC view of a "create Enterprise" deployment** as a layered tooling pipeline (git → flux → kustomize → cluster), with CAIM living inside the Control Plane K8s. The 3-tier identity hierarchy (Organization → Project → User/Group/Role) is confirmed visually. The "Realm creation" step (#7) and the swim-lane "Cloud Packager" being a distinct actor reinforces that **bootstrap is currently a human-driven operation**, not an API call.

### 2.6 BL API surface (Business Logic API Design Spec)

Full API tree (from §5.0 "MVP-0 Information"):

```text
/requests
  /requests/{request_uuid}                       GET                ← async polling
/organizations                                   GET                ← NB: NO POST
  /organizations/{org_name}                      GET PATCH DELETE
    /users                                       GET POST
    /projects                                    GET POST
    /related_users                               GET POST
      /{user_uuid}                               PUT DELETE
/users                                           GET
  /users/{user_uuid}                             GET PATCH DELETE
    /related_projects                            GET POST
      /{project_uuid}                            PUT DELETE
/projects                                        GET
  /projects/{project_uuid}                       GET PATCH DELETE
    /related_users                               GET POST
      /{user_uuid}                               PUT DELETE
```

**Key API design decisions** (Part 2 of the spec):

- **Async-first**: every mutating call returns `202` + `request_uuid`; clients poll `/requests/{request_uuid}`. Synchronous GETs, webhooks/SSE, GraphQL are deferred features.
- **Minimal Unambiguous Pathing**: any UUID-bearing resource is reachable directly at `/resource/{uuid}` (decoupled from parent ancestry). Hierarchical collections allowed (`/parent/{uuid}/children`).
- **Relationship URIs** use `related_` prefix and are **terminal** (cannot extend further). Relationships are managed **bidirectionally** (`/projects/{p}/related_users` and `/users/{u}/related_projects` are functional duals).
- **JSON:API standard** for advanced querying (pagination, sorting, filtering, field selection) — deferred to Phase 2.
- **SemVer 2.0.0** strictly applied.
- **Auth model is 3-layered sequential**: (1) Authentication via OIDC bearer token at API entrypoint, (2) optional service-level authorization checks, (3) **Delegated Final Authorization to a central IAM service** — the OIDC token is passed through; authorization decisions are made by Keycloak/Keystone, not by CAIM itself. *"Authorization itself is not decided within the CAIM stack."*
- **Auth scheme**: Bearer JWT (`bearerAuth`).
- **Caller**: a logged-in user via Panels/GUI, sending their OIDC token + their UUID in the request header.

**Linked Jira context (from screenshot in spec):**

- `GSSNC-360` (CLOSED): PaaS SNC BL — CAIM user and project management
- `SOV-515` (DONE): BL API to create projects, list projects, give users project roles — FY26Q3 MVP0+MVP1
- `GSSNC-361` (DONE): BL API to create users, list users — FY26Q3 MVP0+MVP1
- `SOV-440` (WAITING): update/delete users and projects — FY26Q3 BL MVP2

So **SNC's own BL MVP0+MVP1 is shipped**; update/delete is in flight; **organization creation is not even on the BL roadmap** in this material.

---

## 3. Manual operational recipes (Keycloak howtos)

These are the **runbook fallback** for Q-113 — if BL automation isn't ready in M2, a Cloud Packager / IT-Admin can hand-execute them.

| Howto | What it does | Who runs it today | Where it'd run in OPCP |
|---|---|---|---|
| **Create a Realm in Keycloak** | Manage realms → Create realm → name (snake_case) → Create. Represents one Organization. | L2 admin in Keycloak Admin Console | Output of `CLOUD-589` (Keystone domain config) and the OPCP-side `KeystoneDomain` reconciler (SOV-254 resource #1: domain creation). Manual fallback: Cloud Packager. |
| **Create a Client in Keycloak** | One client per Keystone target. Type=OpenID Connect. Client auth ON, Standard flow ON. Redirect URI=`https://<keystone>/identity/v3/redirect_uri`. Naming convention: `bmpod-keystone`, `regional-keystone`, `regional-s3-keystone`. | L2 admin | OPCP needs one client per OPCP-Compute regional Keystone per Realm. Owned by KeystoneDomain reconciler (SOV-254 resource #2: IdP). Manual fallback: Cloud Packager. |
| **Configure Client scope** | On `<client>-dedicated` scope, add two mappers: `projects` (Aggregate User/Group Attribute as JSON String, attribute=`project_<region>`, claim=`projects`, multivalued+aggregate ON) and `username` (User Attribute, claim=`username`). | L2 admin | This is the **token-shaping contract**. OPCP CloudStore must keep the same claim names so existing Keystone `json_mapping` regex works. Owned by `CLOUD-600` (cloudstore.yaml IAM adaptation) + KeystoneDomain reconciler. Manual fallback: Cloud Packager. |
| **Create a mapping between Keycloak and regional Keystones** (S3 / L2) | Edit `paas-apps-infra/apps/base/keystone-s3-identity/software/keystone.yaml` → append to `identity_providers` block. Edit `keystone-post-setup.yaml` → append to `post_setup.identity_providers` (json_mapping with `HTTP_OIDC_SUB`/`USERNAME`/`PROJECTS`). Edit `paas-secrets-infra/clusters/<cluster>/<dir>/{kustomization,secrets}.yaml` → sops-encrypt `client_secret` with age. MR + Flux propagation. | L2 admin via git MRs | OPCP-equivalent: KeystoneDomain reconciler (SOV-254) renders the same K8s objects — Keystone CR + Secret + federation-mapping CR. `CLOUD-616` (BL deployment via TF) owns the Terraform side. Manual fallback: Cloud Packager doing git MRs against OPCP's gitops repo. |
| **Create a mapping between Keycloak and BMPOD Keystone** (admin / L2) | Same idea, different repo: `fleet-infra-hieradata/hieradata/prod/gor-minint.yaml` → `keystone_vars.identity_providers` + `keystone_vars.post_setup.identity_providers` + `json_mapping_paas_<realm>` (the big regex-armoured federation rule). Secrets in `fleet-infra-hieradata/secrets/prod-minint-passwords.yaml` (sops+age). | L2 admin via git MRs | Same as above. **Note the explicit "TODO change link to prod environment when known"s** — even SNC hasn't finished productionising this. |
| **How to create a new Organization** (4-step master recipe) | Sequences the four Keystone-Keycloak pair setups (BMPOD-L2, S3-L2, BMPOD-L3, S3-L3). For each: realm + client + scope + mappers + first user/group + repo mapping. | L2 admin | The OPCP M2 "enable CB for Account" flow is a simplified version: **no admin/user split, no S3 axis** — just one OPCP-Compute Keystone per region behind one Keycloak Realm. Owned end-to-end by SOV-254 + CloudStore-side (SOV-680 children). Manual fallback: Cloud Packager runs an abbreviated form. |
| **Create first user, role, assign role** (part of step 1.4) | Manual: Users → Add user → set temp password → Role mapping → assign org role (tagged `realm-management`). | L2 admin | Same as above; M2 needs at least *one* admin user per Account. |
| **How to manage Users and Projects** (post-bootstrap day-2) | Day-2 manual: create user, set temp password, assign org role; create Group (=Keystone Project); create sub-group `<role>.<project>` with attribute `project_<region>` = `{"name":"<proj>","domain":{"name":"<org>"},"roles":[{"name":"<role>"}]}`; add user to sub-group. Optional `objectstorage_<role>` for S3 access (custom Keystone role). | L2 admin (today) — eventually customer admin via CAIM API | OPCP M2 only needs the bootstrap subset (first admin user). Ongoing day-2 (more users, more projects) is what CAIM BL API automates — `CLOUD-587` implements this for OPCP. **Q-113 mapping fallback = this howto.** |

---

## 4. Mapping to OPCP — reuse vs net-new

| SNC component / pattern | Classification | OPCP ticket(s) | Adaptation needed |
|---|---|---|---|
| **CAIM API drones** (`idam-api`, `requests-api`) — REST entrypoint, OIDC token auth | **Reuse as-is** | `CLOUD-587`, `SOV-680` parent | Deploy CAIM Helm chart inside CloudStore Service. Front with CloudStore's own L3 proxy. |
| **CAIM controller-drone** — async request supervisor, rollback/transactionality | **Reuse as-is** | `CLOUD-587` | Same chart; CloudStore inherits the async-first pattern. |
| **CAIM service-drones** (organization, project, user) | **Reuse as-is** | `CLOUD-587` | The Org/Project/User concept maps 1:1. OPCP Account = SNC Organization. |
| **CAIM `keycloak-wrapper-drone`** | **Reuse with adaptation** | `CLOUD-587`, `CLOUD-589` | Point at the OPCP-side Keycloak (whether that's an OPCP-deployed Keycloak or the SNC global one — open question, Q-209). Throttling rules per backend may need tuning. |
| **CAIM `region-wrapper-drone`** | **Reuse with adaptation** | `CLOUD-587`, `SOV-254` | Configure the OPCP-Compute regional Keystone(s) as additional region targets. SNC's "four-pair-per-org" topology drops to "one Keystone per OPCP region per Realm". |
| **CAIM `object-storage-wrapper-drone`** | **Not used in M1/M2** | (none) | Object Storage is out of M2 scope (Q-115 parked). Leave drone deployed but unused, or strip from chart (Q-215). |
| **CAIM-Redis** | **Reuse as-is** | `CLOUD-587`, `CLOUD-616` | Standard Redis chart; CloudStore deploys its own instance. |
| **BL API surface** (REST, async polling, JSON:API, `related_` prefixes, JWT bearer) | **Reuse as-is — this is THE contract** | `SOV-398`, `SOV-406`, `CLOUD-587` | The OPCP Manager / CloudStore UI consume this same API. UX (`SOV-398`) should validate against the API tree in BL Design Spec §5.0. |
| **Object model: Organization → Project → User → Role** | **Reuse as-is conceptually** | `SOV-398`, `SOV-406` | OPCP terminology: Account = Organization (decide and lock — affects naming everywhere). Project, User, Role unchanged. |
| **OIDC token shape: claims `projects`, `username`, aggregated from group attribute `project_<region>`** | **Reuse as-is — this is the federation contract** | `SOV-254`, `CLOUD-600` | The KeystoneDomain reconciler's federation-mapping resource (SOV-254 resource #3) must emit the exact same `json_mapping` template SNC uses. |
| **Keystone federation `json_mapping` + regex armour** | **Reuse with adaptation** | `SOV-254`, `CLOUD-600` | The big regex prevents L3 users from grabbing admin/service roles or cross-realm domains. OPCP needs to decide if the OPCP-Compute single-Keystone topology still needs the regex (probably yes — defence in depth). See Q-212. |
| **Keycloak Realm-per-Organization model** | **Reuse as-is** | `CLOUD-589`, `SOV-254` | One Realm per OPCP Account. KeystoneDomain CR triggers Realm creation. |
| **Keycloak Client-per-Keystone model** | **Reuse with adaptation** | `SOV-254` resource #2 (IdP) | SNC: 4 clients per Realm (one per Keystone pair). OPCP-Compute M2: 1 client per regional Keystone per Realm. Fewer clients, same mechanism. |
| **Keycloak Client scope mappers (`projects`, `username`)** | **Reuse as-is** | `CLOUD-600`, `SOV-254` | Same mapper config, programmatically applied. |
| **Keycloak Group = Keystone Project; sub-group `<role>.<project>` with `project_<region>` attribute** | **Reuse as-is — this is the membership contract** | `CLOUD-587` (when CAIM creates projects), `SOV-398` | OPCP CAIM `project-service-drone` creates Group + role sub-groups identically. Q-113 fallback: manual. |
| **Manual bootstrap of first Organization (4-step howto)** | **Net-new in OPCP** | `SOV-254` 6-resource chain, `CLOUD-589` | OPCP replaces with KeystoneDomain CR + Keystone Controller automation. Manual howto is the Q-113 fallback. |
| **Git-MR-driven Keystone federation config** (paas-apps-infra, fleet-infra-hieradata, sops+age) | **Net-new in OPCP — replaced by reconciler** | `SOV-254`, `CLOUD-616` | OPCP KeystoneDomain reconciler emits these YAMLs / CRs declaratively. Cloud Packager git workflow goes away. |
| **OpenBao for secret pickup at container startup** | **Reuse with adaptation** | `CLOUD-616`, `CLOUD-587` | OPCP standard is `ExternalSecrets` + cluster secret store. Either swap OpenBao for the OPCP convention or keep OpenBao if the chart hard-depends on it (Q-210). |
| **Build: Pants + PyInstaller + distroless + Helm** | **Reuse as-is** | `CLOUD-616` | OPCP TF/Helm wiring should consume the upstream chart unchanged. |
| **Async `/requests/{uuid}` polling pattern** | **Reuse as-is** | UX in `SOV-398` | UX must handle 202+poll, not 200+body. |
| **Organization creation API** — DOES NOT EXIST in CAIM BL | **Net-new for OPCP or stay manual** | **`SOV-406` design decision needed (Q-208)** | Either (a) extend CAIM BL with `POST /organizations`, (b) drive Org creation from OPCP-side via KeystoneDomain reconciler (SOV-254) and have CAIM just discover the Org afterwards, or (c) stay manual via Cloud Packager. Option (b) is the natural OPCP fit. |
| **Day-2 UX permission model (who sees what)** | **Net-new in OPCP** | `SOV-398` | SNC has no public UX spec in this material; OPCP defines its own based on the CAIM API surface. |

---

## 5. Cross-link to OPCP artefacts

### 5.1 What this material does for each existing open question

- **Q-111 — CloudStore preconditions for M2.** *Partially answered.* CAIM stack is shipped (MVP0+MVP1 done per `SOV-515` and `GSSNC-361`); day-2 CRUD on Users/Projects/Roles is available via REST. **Still open**: Organization-creation precondition. CAIM can't create Orgs; SNC does this manually today. OPCP M2 must decide who creates the Account/Realm/Domain — KeystoneDomain reconciler (SOV-254) is the natural answer, but the handoff between SOV-254 and CAIM is unspecified. This is the precondition Vincent flagged as needing more design (Q-208 below).
- **Q-113 — Manual Keycloak project-group mapping if BL not ready in M2.** *Fully answered.* The fallback path is "How to manage Users and Projects" §How to create a Group + §How to create a Project-role + §How to add Users to Groups. Concretely: create Keycloak group named after the project, create sub-group `<role>.<project>` with attribute `project_<region>` = `{"name":"<proj>","domain":{"name":"<org>"},"roles":[{"name":"<role>"}]}`, add user to sub-group. Cloud Packager / IT-Admin can do this in the Keycloak Admin Console UI in ~5 minutes per project per Account.
- **Q-002 / Q-102** — unaffected; this material is identity-only.
- **Q-115** — confirmed parked; CAIM has an `object-storage-wrapper-drone` ready when scope expands.

### 5.2 `SOV-254` 6-resource provisioning chain ↔ CAIM seam

| SOV-254 resource | BL input or output? | Notes |
|---|---|---|
| 1. Keystone Domain | **OPCP output, BL input** | KeystoneDomain CR creates the Domain. CAIM `region-wrapper-drone` then creates Projects inside it. |
| 2. Identity Provider (Keycloak Client) | **OPCP output, BL input** | KeystoneDomain reconciler creates the Keycloak Client; CAIM `keycloak-wrapper-drone` treats it as existing config. |
| 3. Federation Mapping (Keystone `json_mapping`) | **OPCP output** | Pure SOV-254 territory. Template must use `HTTP_OIDC_SUB`/`USERNAME`/`PROJECTS` claims to match the CAIM-driven token shape. |
| 4. Apache + `mod_openidc` pod | **OPCP output** | Pure infra; CAIM doesn't see it. |
| 5. HTTPRoute | **OPCP output** | Pure infra. |
| 6. NetworkPolicy | **OPCP output** | Pure infra. |

The **handoff is "OPCP creates resources 1–6; CAIM then writes day-2 IDAM objects into resources 1 + 2"**. The seam needs an ordering guarantee (CAIM must not try to create Projects in a Domain that isn't ready). Concrete proposal: `KeystoneDomain.status.federationReady: true` condition is the signal CAIM watches for.

### 5.3 `SOV-680` IAM/BL chain — refined understanding of each child

| Child | Role in M2 | Implementation note from this material |
|---|---|---|
| `SOV-398` UX permission model | Define OPCP UX on top of CAIM BL API | Must match CAIM's Org/Project/User/Role + `related_` relationship model. Async-poll UX. |
| `SOV-406` IAM/BL Design (BLOCKED) | Architectural decision doc | **This material UNBLOCKS most of it.** Remaining decisions: Q-208–Q-212. |
| `CLOUD-587` IAM/BL Implementation (UNASSIGNED, 8-week M2 blocker) | Stand up CAIM stack in OPCP CloudStore | Reuse SNC Helm chart wholesale; adapt wrapper-drone config to OPCP Keystone topology. |
| `CLOUD-589` Keystone domain config | Per-Account Keystone domain setup | Replaces SNC manual howto. Output of KeystoneDomain reconciler. |
| `CLOUD-600` cloudstore.yaml IAM adaptation | CloudStore Service config | Carries the token-claim/mapper contract (`projects` + `username` claims, `project_<region>` group attribute). |
| `CLOUD-616` BL deployment via TF | Terraform wiring for CAIM stack | Pants/PyInstaller/Helm chain is ready upstream; TF just consumes Helm. Secret-store decision (OpenBao vs OPCP standard) goes here (Q-210). |

### 5.4 Does this material unblock `SOV-406`?

**Mostly yes.** Team CAIM Overview + BL API Design Spec together give us: deployed component topology, the full REST API contract (paths, schemas, async pattern), the auth model (OIDC bearer + delegated authorization), the build/deploy stack (Pants/PyInstaller/Helm/GitLab CI), the security posture (OpenBao secrets, distroless, NetworkPolicies, sanitization). The howtos add the OIDC token contract (claims `projects`, `username`, sub-group attribute pattern), the Keystone federation `json_mapping` template with regex, and the Realm/Client/Scope/Mapper layout per Organization.

**What's still missing for SOV-406 to ship:** Q-208 (Org-creation handoff), Q-209 (Keycloak topology), Q-210 (secret store), Q-211 (wrapper-drone region config), Q-113 (manual fallback disposition).

If those five are answered, SOV-406 can move from BLOCKED → IN PROGRESS.

---

## 6. Risks + open questions

### 6.1 New open questions (Q-208 → Q-216)

These land in [`open-questions.md`](../open-questions.md) under a new "Business Logic / IAM (CAIM)" section.

- **Q-208 — Who creates the Organization (Realm + Keystone Domain) for an OPCP Account in M2?** SNC does this manually today (4-step L2 admin runbook). CAIM has no `POST /organizations`. Options: (a) extend CAIM with org-creation API (new SNC work), (b) drive it from OPCP-side KeystoneDomain reconciler with CAIM discovering it after the fact (preferred — fits SOV-254), (c) keep it manual (Q-113 fallback applied to bootstrap). **Owner:** Ibrahim Takouna (SOV-406) + Stephan Hohn (SOV-256/SOV-254 cross-team alignment).
- **Q-209 — Single Keycloak or per-OPCP Keycloak?** SNC has Global Keycloak (L3 users) + BMPOD Keycloak (L2 admins). OPCP CloudStore could (a) federate against SNC's global Keycloak, (b) deploy its own Keycloak in CloudStore. (b) is consistent with "CloudStore Service runs on OPCP Core" but creates a second Keycloak per OPCP deployment. **Owner:** SOV-406 / Vincent Casse.
- **Q-210 — Secret store: OpenBao or OPCP standard?** CAIM containers fetch secrets from OpenBao at startup. OPCP convention is `ExternalSecrets` + cluster-secret-store. Either adapt CAIM Helm values, or carry OpenBao as a CAIM dependency. **Owner:** CLOUD-616.
- **Q-211 — Region-wrapper-drone config: which Keystones per Account?** SNC has 4 Keystones per Account. OPCP-Compute M2 has 1 Keystone per region per Account (no S3 in M2 per Q-115). Confirm the `region-wrapper-drone` config schema can express "1 Keystone, no admin/user split". **Owner:** CLOUD-587.
- **Q-212 — Does the federation `json_mapping` regex still apply with a single-Keystone-per-region topology?** The regex blocks L3 users from claiming `admin`/`service` roles or cross-realm domains. OPCP-Compute single-Keystone may not need the cross-realm guard but should keep the role guard. **Owner:** SOV-254 (Keystone Controller team).
- **Q-213 — Async-first impact on OPCP Manager UX?** Every mutating CAIM call returns 202 + `request_uuid`. OPCP Manager UI must implement polling, not assume sync. **Owner:** SOV-398.
- **Q-214 — How does CAIM authenticate to OPCP Keystone(s) when wrapper-drone calls them?** The howtos imply manual Keystone admin tokens or per-client-secret federation. CAIM `region-wrapper-drone` needs its own service identity. **Owner:** SOV-254 + CLOUD-587.
- **Q-215 — Object Storage path: keep `object-storage-wrapper-drone` deployed?** Not used in M2 (object storage out of scope per Q-115). Deployed-but-idle adds attack surface. Decide deploy vs strip. **Owner:** CLOUD-616.
- **Q-216 — Multi-region per Account in M2?** OPCP "start a VM per Account" implies at least one region. SNC's group attribute `project_<region>` makes region a first-class concept in the token. Confirm M2 supports single region only, or designs for multi-region from day one. **Owner:** SOV-406 / SOV-680.

---

## 7. Next steps

1. **Unblock SOV-406 by answering Q-208 + Q-209.** Owner: Ibrahim Takouna with Vincent Casse + Stephan Hohn. Lands in: `SOV-406` design doc (paste this analysis as the foundation, then resolve the two questions).
2. **Validate the CAIM Helm chart against OPCP CloudStore constraints.** Pull the chart from upstream, dry-run a Helm install on a CloudStore dev cluster. Confirm: distroless+nonroot works, OpenBao dependency, NetworkPolicy compatibility with CloudStore networking. Owner: CLOUD-587 implementer (currently UNASSIGNED — this is the 8-week M2 blocker — staff it). Lands in: `CLOUD-587` execution plan.
3. **Define the SOV-254 ↔ CAIM handoff contract.** Specify which CR/event signals "Keystone Domain ready for CAIM to start writing Projects into it". Likely a `KeystoneDomain.status.federationReady: true` condition. Owner: Stephan Hohn (SOV-256/SOV-254 lead) + CLOUD-587 implementer. Lands in: `SOV-254` design + `CLOUD-587` integration spec.
4. **Codify the token contract.** Write a one-page "CloudStore OIDC token shape" doc with: claims `sub`, `username`, `projects`, and the `projects` JSON structure (`{name, domain.name, roles[]}`). Reference the `json_mapping` template. This is the seam between CAIM's day-2 ops and SOV-254's federation mapping. Owner: CLOUD-600 + SOV-254 jointly. Lands in: a shared `architecture/oidc-token-contract.md`.
5. **Decide Q-113 final disposition for M2.** Either (a) CAIM ships project-group automation in time → fully automated, or (b) manual fallback → write a Cloud-Packager-targeted runbook based on §3 of this doc. Owner: Vincent Casse + SOV-680 PM. Lands in: Q-113 resolution in `open-questions.md` + (if (b)) a new `runbook/manual-iam-bootstrap.md`.
6. **Estimate effort for the Org-creation handoff option chosen in step 1.** If option (a) — extend CAIM with `POST /organizations` — that's net-new SNC work, ~4–6 weeks of CAIM team. If option (b) — KeystoneDomain reconciler drives it — that's already in SOV-254 scope and adds maybe 1–2 weeks. Owner: PM. Lands in: M2 effort-estimation Sub-task.
7. **Strip or stub `object-storage-wrapper-drone` for M2.** Confirm with CAIM team that the drone can be disabled via Helm values without breaking the chart. Owner: CLOUD-616. Lands in: CLOUD-616 TF values.

---

## Cross-references

- **Source PDFs (gitignored):** `Input/Business Logic Cloud Store/` — Team CAIM Overview, BL API Design Spec, Keycloak howtos, excalidraw export.
- **Jira tickets:** [`SOV-406`](SOV-406) (this material's parent, BLOCKED), [`SOV-680`](SOV-680) (`[MS2][CloudStore] Development`), [`SOV-254`](SOV-254) (`[MS2][Keystone Controller] Development`), [`CLOUD-587`](CLOUD-587), [`CLOUD-589`](CLOUD-589), [`CLOUD-600`](CLOUD-600), [`CLOUD-616`](CLOUD-616).
- **Open questions:** [`open-questions.md`](../open-questions.md) — Q-111 (preconditions), Q-113 (manual fallback), Q-115 (Object Storage scope), Q-208–Q-216 (new from this analysis).
- **Workshop notes (related):** [`meetings/2026-05-12-keystone-workshop.md`](../meetings/2026-05-12-keystone-workshop.md) — the OPCP-side Keystone Controller workshop; this BL material is the CloudStore-side counterpart.
- **M2 user story:** [`user-stories/M2-start-a-vm.md`](../user-stories/M2-start-a-vm.md) — the IT-Admin enable-CB flow that depends on both sides.
- **SOV-680 paste-ready description:** [`jira/SOV-680-cloudstore-m2.md`](../jira/SOV-680-cloudstore-m2.md) — references the children covered here.
