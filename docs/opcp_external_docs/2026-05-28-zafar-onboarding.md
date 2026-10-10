# Object Storage — Onboarding session with Zafar Akhtar

**Date:** 2026-05-28
**Attendees:** Zafar Akhtar (SRE), Boris Behrens (SRE), Eduardo Medina (PO)

---

## What is CloudStore

Internal platform with a UI where IT admins deploy managed infrastructure services. Services are packaged as bundles containing Terraform modules, Helm charts, and Docker images. The Object Storage project = building the Object Storage service package.

## How the delivery flow works

```
Terraform code written
  → packaged locally
  → pushed to central registry (Harbor)
  → syncs to environment-specific registries (~15 min)
  → appears in CloudStore UI (~1 hour after Harbor push)
  → IT-Admin deploys from UI
  → TF Pod Runner executes Terraform logic against OpenStack
```

## Repo structure

| File/folder | Purpose |
|---|---|
| `cloudstore.yaml` | Declares what credentials/secrets to inject at deploy time |
| `terraform/control-plane/` | Main business logic — talks to OpenStack API |
| `terraform/data-plane/` | End-user facing resources (e.g. self-service S3 access keys) |

## Credentials & access

- Team secrets stored in **GoPass** — kubeconfigs for all environments, hardware credentials, CA certs
- Access requires a PGP key added by an existing member (contact: Marion)
- CloudStore UI login: `IT-Admin / 123456` (Keycloak, same across environments)

## Reference project

**VCF project** (under CloudStore org) — best example of how to:
- Structure `cloudstore.yaml`
- Inject OpenStack credentials into Terraform
- Provision resources via the OpenStack API

Use it as the starting point for Object Storage modules.

## Known gotchas

- Always use `BYPASS_DOCKER=true` when running `make` commands
- `skopeo` must be installed locally
- Use **Infra environment** for testing — Dev is broken
- Package only builds if there is at least one `non-chore:` commit
- Harbor sync ~15 min; CloudStore UI needs ~1 additional hour — plan accordingly

## Open questions raised in this session

| ID | Question | Note |
|---|---|---|
| OSQ-18 | Are there OpenStack resources available in the Infra environment for testing? | Zafar to investigate and report |
| OSQ-19 | Why do some UI input fields require manual input instead of being auto-injected via `cloudstore.yaml`? | Needs clarification on field injection model |
| — | How to provision Keystone in the Control Plane for Object Storage | Covered by OSQ-02 / OSQ-17 |

## Pending actions from this session

| Action | Owner | Status |
|---|---|---|
| **Hello World OpenStack module** — simple connectivity test; first concrete step before writing real Ceph/RGW modules | Zafar + Boris | 🟡 In progress — Zafar onboarded Boris 2026-06-02. Boris has Mac dev env issues (sdev can't install tools) — escalated to Pierre-Yves. |
| Get GoPass access (PGP key via Marion) | Stephan | ✅ Done |
| Get GoPass access (PGP key via Marion) | Boris | ✅ Done |
| Install `skopeo` locally | Everyone | ⚪ Check at next weekly |
| Share Repo/Stash links | Zafar | ⚪ Pending |
| Report Infra environment error | Zafar | ⚪ Pending |

---

## Cross-links

- Open questions: [`open-questions.md`](../open-questions.md) (OSQ-18, OSQ-19)
- Weekly tracker: [`tracking/weekly.md`](../tracking/weekly.md)
- Reference project: VCF project (CloudStore org)
- Onboarding doc: [`onboarding.md`](../onboarding.md)
