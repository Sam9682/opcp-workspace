---
id: core/cloudstore-project-baremetal-availability
product: opcp-core
type: runbook
diataxis: how-to
title: "Make a project selectable in CloudStore and its baremetal nodes visible (demo)"
owner: TBD
status: draft
last_verified: 2026-08-28
next_review: 2026-11-28
publish_target: confluence
tags: [keycloak, bmpod, openstack, ironic, baremetal, cloudstore, demo, projects, federation, first-responder]
---

# Make a project selectable in CloudStore and its baremetal nodes visible (demo)

> **When to use:**
> - You open the CloudStore UI / API on `demo`, and **the project you want isn't in the project picker**.
> - You picked a project and the **baremetal-node list is empty** (or the API errors out).
> - You're setting up a **new project for a demo / test** and need free BM nodes attached to it.
>
> **Scope:** `demo` (BMPOD). The same mechanism should hold on `minint`, but the URLs and the
> node inventory differ — **verify before reusing** (`TBC`). **`demo6` is a known exception** — it
> runs OPCP 3.0.1 and the default project attribute only landed in 3.0.5, see
> OFR-27.
>
> **Owner:** **TBD**.
>
> **Status:** DRAFT 2026-08-28 — captured from Jan Stuhlmann's working knowledge, **not yet
> re-executed against the environment step by step**. Two `TBC` markers inline.

---

## TL;DR (the order matters)

```
1. Create the project in BMPOD OpenStack   ← MUST be first, or the CloudStore API breaks
     openstack project create --domain Default --parent default <project>
2. Add the project to your user's Attributes in BMPOD Keycloak (L1)
3. Re-login to CloudStore  → L2 Keycloak picks the attribute up by federation
4. Find UNCLAIMED BM nodes (available + power off + no Owner) and assign them
     ↳ owned by someone else? ask them first — `node set --owner` has no guard
5. Release the nodes when you're done
```

## Background — what actually drives the CloudStore project picker

CloudStore does **not** own the list of projects you can select. The list comes out of your **OIDC
token**, and the token's project claim is sourced from a **user attribute in the BMPOD Keycloak
(L1)** — the OPCP Core Keycloak. CloudStore's own **L2 Keycloak is federated with L1**
(see [Keycloak Federation](../../../../generic/keycloak-federation/summary.md) §2), so it only learns
about a new attribute **at the next login**.

Underneath that, the project name in the attribute is not free text — it has to resolve to a **real
OpenStack project in BMPOD**. If it doesn't, the CloudStore API tries to scope onto a project that
Keystone has never heard of and **breaks**. Hence the ordering above: OpenStack first, Keycloak
second, re-login third.

```
 BMPOD OpenStack (demo)          BMPOD Keycloak L1                CloudStore
 project must exist   ◀── name ── user Attributes ── federation ──▶ L2 Keycloak
   Default domain                 (projects attr)                      │
   parent = default                                                    ▼
                                                            project picker + BM node list
```

## Prerequisites

- [ ] Bastion + proxy access to `demo` — see
      [Environment access](../../environments/env-access-onboarding.md) (bastion → `gatewayseed` →
      `seedadmin` → `ssh demo`).
- [ ] SSO account that can log in to the BMPOD Keycloak admin console and **edit your own user's
      attributes** (realm-admin, or someone who has it).
- [ ] An OpenStack CLI on the `demo` controller with admin credentials sourced (the usual
      `seedadmin` → `ssh demo` shell already has them).
- [ ] The project name you want, agreed in advance — renaming later means redoing all four steps.

---

## Step 1 — Create the project in BMPOD OpenStack (do this first)

On `demo`, via `seedadmin`:

```bash
# bastion → gatewayseed → seedadmin → demo
seedadmin
ssh demo

openstack project create --domain Default --parent default <project-name>
```

**Two constraints, both load-bearing:**

| Constraint | Why |
|---|---|
| `--domain Default` | The project must live in the **`Default`** domain — that's the domain the CloudStore ↔ Keystone federation scopes into. |
| `--parent default` | The project must be a **child of the `default` project**. |

**Expected:** a project table with the new `id`, `domain_id`, `parent_id`.

Verify:

```bash
openstack project show <project-name> -c name -c domain_id -c parent_id -c enabled
```

> ⚠️ **Skipping this step is the classic failure.** If you put a project name into the Keycloak
> attribute that doesn't exist in BMPOD OpenStack, **the CloudStore API breaks** — it isn't a
> graceful "no such project" error.

## Step 2 — Add the project to your user's attributes in BMPOD Keycloak (L1)

Browse (via the relay proxy — see [Environment access](../../environments/env-access-onboarding.md)):

**`https://admin.keycloak.demo.bmp.ovhgoldorack.ovh`** — log in via **SSO**.

Then:

1. **Users** → select **your user**.
2. **Attributes** tab — this is where the projects you currently have are listed.
3. **Add** an entry for the project you created in Step 1:

   - **Key:** `project`
   - **Value:** a JSON object —

     ```json
     {"domain":{"name":"Default"},"name":"jan-ceph-test","roles":[{"name":"admin"}]}
     ```

   | Field | Value |
   |---|---|
   | `domain.name` | **`Default`** — must match the `--domain Default` from Step 1 |
   | `name` | the OpenStack project name from Step 1, **spelled exactly** |
   | `roles[].name` | the Keystone role to grant on that project — `admin`, `member`, … |

4. **Save**.

> **How this becomes a token claim:** a **client mapper** aggregates the `project` attribute(s) into
> the JWT's **`projects`** list — singular attribute in Keycloak, plural claim in the token. That
> claim is what Keystone's federation mapping reads to scope you onto the project.
>
> **Same pattern, different key at L2/L3:** the CloudStore per-Account (L3) realm keys the
> *same-shaped* JSON under **`project_<region>`** on a role **sub-group** rather than plain
> `project` on the **user** — see
> [Business Logic & IAM](../../../cloudstore/architecture/conceptions/business-logic-iam/summary.md)
> §3 and the [Manual Keycloak Account activation runbook](../../../cloudstore/misc/compute-block-on-cloud-store/runbooks/manual-keycloak-account-activation.md)
> §1d. Both funnel into the same `projects` claim. **Don't copy one key into the other tier.**

## Step 3 — Re-login to CloudStore so L2 picks up the change

The attribute is federated from **L1 → CloudStore's L2 Keycloak at the next login only**.

- If you are **already logged in to CloudStore: log out and log back in.** Refreshing the page is
  not enough — your existing session carries the old token.
- The project should now appear in the CloudStore project picker (UI) / project list (API).

## Step 4 — Find *unclaimed* baremetal nodes and assign them

Back on `demo` (same `seedadmin` → `ssh demo` shell).

### 4a. A node is free only when **all four** are true

| Column | Free value | Why it counts |
|---|---|---|
| **Provisioning State** | `available` | nothing is deployed on it |
| **Power State** | `power off` | idle |
| **Maintenance** | `False` | not deliberately parked |
| **`Owner`** | **empty** | 🔑 **nobody has claimed it** |

> 🔑 **`Owner` is the one people skip, and skipping it takes a node off a colleague.**
> `available` + `power off` says *"nothing is running on it"*. It does **not** say *"it is yours to
> take"* — a project can hold a node it hasn't deployed to yet, and that is a completely normal
> state. **`Owner` is the only field that answers "is this claimed?".**
>
> This is not hypothetical: **OFR-28
> (2026-08-31)** is exactly this — a node `available` + `power off` but owned by `OPCPsupport` was
> re-`--owner`ed during work on *this runbook*, and the team that held it reported it as lost three
> days later. It cost an FR case to hand back. The runbook said "ask first" in prose then and it
> **was not enough**, which is why `Owner` is now a listing filter and a hard gate below.

### 4b. List only the genuinely unclaimed nodes

**Filter on `Owner` — don't eyeball the column.**

```bash
openstack baremetal node list --long -f json \
  | jq -r '.[]
      | select(.["Provisioning State"] == "available"
           and .["Power State"]        == "power off"
           and .Maintenance            == false
           and ((.Owner // "") == ""))
      | [.UUID, .Name] | @tsv'
```

**Expected:** only nodes that are free *and* unclaimed. **An empty result means there is nothing to
take** — go to 4c, do not fall back to the unfiltered list.

> `TBC` — column names in `-f json` follow the client's display titles and have moved between
> `python-openstackclient` versions. If the filter returns nothing when you expect hits, print one
> record raw (`openstack baremetal node list --long -f json | jq '.[0]'`) and adjust the keys —
> **don't drop the `Owner` condition to make it match.**

Human-readable equivalent, if you'd rather read a table — the `Owner` column is **mandatory**:

```bash
openstack baremetal node list --long \
  -c UUID -c Name -c "Power State" -c "Provisioning State" -c Maintenance -c Owner
```

### 4c. If every free node is already owned — **ask, don't take**

There is no technical guard here: `node set --owner` will happily reassign a node out from under
whoever holds it, with no warning and no notification to them. **The gate is you.**

1. Resolve who holds it — the `Owner` field is a project **ID**:
   ```bash
   openstack project show <owner-id> -c name -f value
   ```
2. **Contact that project's team and get an explicit yes** before touching the node.
3. If you can't identify or reach them, **stop** and raise it with the First Responder on duty
   rather than taking the node.

Record the previous owner ID before you change it — that's the rollback value:

```bash
openstack baremetal node show <node-uuid> -c owner   # ← note this down first
```

### 4d. Assign the node

Only once 4b returned it as unclaimed, **or** 4c got you an explicit yes. Use the project's **ID**,
not its name:

```bash
PROJECT_ID=$(openstack project show <project-name> -c id -f value)

# last-second re-check — confirm it is still unowned right before you write
openstack baremetal node show <node-uuid> -c owner -c provision_state -c power_state -c maintenance

openstack baremetal node set --owner "$PROJECT_ID" <node-uuid>
```

Repeat per node. Confirm:

```bash
openstack baremetal node show <node-uuid> -c owner -c provision_state -c power_state
```

**Expected:** `owner` = your project ID, `provision_state` still `available`.

### 4e. Hand a node back when you're done

Nodes you claimed for a test stay claimed until you release them, and a claimed node is invisible
to everyone else's 4b filter. **Releasing is part of the job, not a courtesy.**

```bash
openstack baremetal node set --owner <original-owner-id> <node-uuid>   # hand back
openstack baremetal node unset --owner <node-uuid>                     # or release outright
```

---

## Verification

1. **CloudStore UI/API** — the project appears in the picker, and selecting it returns a
   **non-empty** baremetal node list.
2. **OpenStack** — the nodes you assigned carry the project as their `owner`:
   ```bash
   PROJECT_ID=$(openstack project show <project-name> -c id -f value)
   openstack baremetal node list --owner "$PROJECT_ID" \
     --long -c UUID -c Name -c "Provisioning State" -c "Power State" -c Owner
   ```

## Common failures + fix recipes

| Symptom | Likely cause | Fix |
|---|---|---|
| Project isn't in the CloudStore picker after adding the attribute | You're still on the **old CloudStore session** — L1 → L2 federation only happens at login | Log **out** of CloudStore and log back in (Step 3). A page refresh does not do it. |
| CloudStore API **breaks / errors** when the project is selected | The project name in the Keycloak attribute has **no matching OpenStack project** in BMPOD | Create it (Step 1), then re-login. Check spelling — the attribute value must match the project name exactly. |
| Project exists in OpenStack but CloudStore still misbehaves | Project created in the **wrong domain** or **without `--parent default`** | `openstack project show <name> -c domain_id -c parent_id` → recreate under `Default` / `default`. |
| Project shows up, but the **node list is empty** | No node is in `available` + `power off`, or no node has your project ID as its `owner` | `openstack baremetal node list` → look for `available`; nodes in `active`, `clean failed`, `manageable` or with `Maintenance=True` are not free. See [Baremetal / Ironic triage](../troubleshooting/baremetal-ironic-triage.md). |
| Node stuck in `clean failed` / `enroll` instead of `available` | Enrollment or cleaning problem, not an identity problem | [Baremetal node recovery](baremetal-node-recovery.md) + [Ironic triage](../troubleshooting/baremetal-ironic-triage.md). |
| Attribute set correctly, but the token has **no `projects` claim** | The **client mapper** that aggregates `project` → `projects` is missing or misconfigured on the client | Decode the JWT and check for `projects`. If absent, the attribute is fine — the mapper on the Keycloak client is the problem, not your entry. |
| A colleague reports a node "lost" or reassigned after you took one | You claimed a node that was `available` + `power off` but **already owned** | Hand it back: `node set --owner <their-project-id> <uuid>`. Precedent + the exact handback sequence: OFR-28. Then re-read §4a. |
| On **demo6**: role assigned but no OpenStack rights at all | **Version skew** — demo6 runs 3.0.1; the default project attribute landed in **3.0.5** | Set the project attribute by hand; the real fix is the env update to **3.0.6** (target confirmed 2026-08-31) — SOV-2286 / OFR-27. |

---

## Related

- [Environment access — bastion · proxy · SSO · kubectl](../../environments/env-access-onboarding.md) — how to reach `demo`, the Keycloak admin URL, the proxy
- [Keycloak Federation & KeystoneDomain reconcile](../../../../generic/keycloak-federation/summary.md) — the L1 / L2 / L3 tier model this runbook rides on
- [Business Logic & IAM deep dive](../../../cloudstore/architecture/conceptions/business-logic-iam/summary.md) §3 — the CloudStore-side (L3) project-attribute → `projects` claim → Keystone mapping shape
- [Runbook — Manual Keycloak Account activation (M2 fallback)](../../../cloudstore/misc/compute-block-on-cloud-store/runbooks/manual-keycloak-account-activation.md) — the *per-Account L3* equivalent; different tier, don't confuse them
- [Baremetal / Ironic — triage & common failures](../troubleshooting/baremetal-ironic-triage.md) · [Baremetal node recovery](baremetal-node-recovery.md)
- OFR-28 — the FR case that produced §4a/§4c: a node claimed by `OPCPsupport` was re-owned during work on this runbook and reported lost three days later
- OFR-27 — the FR case that flagged the OPCP Keycloak role / project-attribute model as a **KB gap**. This runbook covers the *procedure*; the *role model* (`reader` / `dc_operator` / `it_admin` / `master_admin`) is still undocumented.

## Source / changelog

- **2026-08-28** — drafted from Jan Stuhlmann's working knowledge of the `demo` environment.
  Partially fills the gap OFR-27 identified.
- **2026-08-28** — Jan supplied the Step 2 attribute **value** shape (the `{"domain":…,"name":…,"roles":[…]}`
  JSON) and the Step 4 assignment command (`openstack baremetal node set --owner <project-id>`).
- **2026-08-28** — Jan confirmed the Step 2 attribute **key** is `project`, aggregated into the JWT
  `projects` claim by a client mapper. **No `TBC` items remain.**
- **2026-09-01** — **Step 4 reworked after OFR-28.**
  The v1 text carried a prose *"ask first"* warning and a listing that merely *included* the `Owner`
  column; a claimed node was taken anyway during the very work that produced this runbook. OFR-28's
  *Contribute back*: *"a prose warning is not a guard."* So: `Owner` empty is now a **listed free-node
  criterion**, 4b **filters** on it instead of showing it, 4c is an explicit ask-first gate with a
  rollback value to record, 4d re-checks immediately before writing, and **4e (hand back / release)**
  is new. Also corrected the demo6 target to **3.0.6** (confirmed 2026-08-31, SOV-2286).
- Not yet re-executed end to end against `demo` from this document — `status: draft` until someone
  does, then flip to `published` and set `last_verified`.
