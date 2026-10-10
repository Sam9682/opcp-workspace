---
id: core/tofu-controller-terraform-cr-stuck-stale-revision
type: runbook
diataxis: how-to
title: "Diagnose a tofu-controller Terraform CR stuck on a stale revision (blocked dependsOn chain)"
owner: opcp-core-infra
status: draft
last_verified: 2026-08-24
next_review: 2026-11-24
publish_target: confluence
tags: [flux, tofu-controller, terraform, tfctl, suspend, dependsOn, gitops, minint, first-responder]
---

# Diagnose a tofu-controller Terraform CR stuck on a stale revision

> **When to use:**
> - A commit is provably in the cluster (`flux get sources git -A` shows your SHA, all Kustomizations `Applied revision: <your SHA>`) but the resource the Terraform module renders — a ConfigMap, a Secret, an OpenStack object — **never changes**.
> - `kubectl get terraform -A` shows a wall of `dependency '<ns>/<name>' is not ready` / `is not updated yet`, and you need to find the one CR at the head of the chain.
> - A Terraform CR reports **`READY=True`** yet its `lastAppliedRevision` is an old SHA.
>
> **The trap this runbook exists for:** a suspended Terraform CR looks *healthy*. It reports `Ready=True`, has no error condition, emits no events, and — unlike a Flux `Kustomization` or `HelmRelease` — **`kubectl get terraform` has no `SUSPENDED` column**. It blocks every dependent CR silently and indefinitely.
>
> **Scope:** the OPCP control-plane K8s running the irobox GitOps stack (`k3s` → Flux → `tofu-controller` → `tf-runner`), i.e. `minint` / `demo` / `nuc0`. Applies to any `infra.contrib.fluxcd.io` `Terraform` CR.
>
> **Owner of this runbook:** opcp-core-infra — **TBD** confirm.
>
> **Status:** DRAFT — **validated 2026-08-24 on minint**, where `keystone` had been suspended via `tfctl` since 2026-08-14 and had blocked ten downstream CRs (the entire OpenStack tier) for 10 days. Steps 1–5 and the fix are `[verified]` against that session; items marked `[inference]` were not exercised.

---

## TL;DR (the skeleton)

```
1. Prove the commit reached the cluster      (flux get sources git / get kustomizations)
2. Find the head of the dependsOn chain      (kubectl get terraform -A)
3. Read the head CR's status                 (revisions frozen? observedGeneration mismatch?)
4. Check the invisible fields                (spec.suspend — needs custom-columns!)
5. Find out WHO and WHY before touching it   (managedFields → field manager + timestamp)
6. Un-suspend, ideally behind a plan gate    (see Step 6 — the gate needs one extra step)
7. Watch the cascade + verify your own change
```

> The single command that resolved the validated occurrence:
> ```bash
> kubectl -n flux-system patch terraform keystone --type=merge -p '{"spec":{"suspend":false}}'
> ```

## Background — why a suspended Terraform CR is invisible

`tofu-controller` gates every `Terraform` CR on `spec.dependsOn`. A dependency counts as satisfied only when it is **`Ready` *and* its `lastAppliedRevision` equals the current source revision**. So a CR frozen on an old SHA blocks its dependents forever, even though it says `Ready=True` — that condition describes its *last successful apply*, not its currency.

Two properties make this hard to spot:

| Property | Consequence |
|---|---|
| `kubectl get terraform` prints no `SUSPENDED` column | Suspension is invisible in the listing every responder starts from |
| A suspended CR is skipped **before** logging | `kubectl logs deploy/tofu-controller \| grep <name>` returns **nothing at all** — which reads like "controller isn't running" rather than "CR is suspended" |

And because `tfctl suspend` writes `spec.suspend` **imperatively**, the field is absent from the rendered manifest in Git. Flux's server-side apply only owns fields the desired manifest declares, so it **never reverts a stray suspend**. The suspension survives every reconcile, indefinitely.

## Prerequisites

- [ ] `kubectl` against the env's control-plane K8s — see [environment access, Surface B](../../environments/env-access-onboarding.md).
- [ ] `flux` CLI on the controller.
- [ ] `jq`.
- [ ] The commit SHA you expect to be live.

---

## Step 1 — Prove the commit actually reached the cluster

Rule out everything above tofu-controller first; it is cheap.

```bash
flux get sources git -A
flux get kustomizations -A
```

**Expected:** the `GitRepository` for the env branch and every Kustomization show `<branch>@sha1:<your SHA>`, `READY=True`, `SUSPENDED=False`.

If the revision is older than your commit, the problem is Flux-side (wrong `ref`, pinned tag, suspended Kustomization) — stop here, this runbook does not apply.

## Step 2 — Find the head of the dependsOn chain

```bash
kubectl get terraform -A
```

Read the `STATUS` column as a graph, not a list. Two distinct messages matter:

| Message | Meaning |
|---|---|
| `dependency '<ns>/<X>' is not ready` | X is not `Ready` — follow to X |
| `dependency '<ns>/<X>' is not updated yet` | X **is** `Ready` but sits on an **older revision** — X is your suspect |

Walk the `is not updated yet` edges to the root. In the validated occurrence the whole OpenStack tier resolved to a single head:

```
keystone (Ready=True, stale revision)          ← the actual blocker
└─ keystone-post-setup      "keystone is not updated yet"
   ├─ nova · glance · neutron · cinder · horizon
   ├─ octavia · placement · barbican
   └─ (ironic depends on keystone directly)
```

The head CR's `metadata.finalizers` confirm the blast radius — `tofu-controller` writes one `tf.dependency.of.<name>` finalizer per dependent:

```bash
kubectl -n flux-system get terraform <head> -o jsonpath='{.metadata.finalizers}' | jq
```

## Step 3 — Read the head CR's status

```bash
NS=flux-system
CR=<head>

kubectl -n $NS get terraform $CR -o jsonpath='{.status}' | jq '{
  lastAppliedRevision, lastAttemptedRevision, lastPlannedRevision,
  observedGeneration, lock,
  lastPlanAt, lastDriftDetectedAt, lastAppliedByDriftDetectionAt, lastHandledReconcileAt,
  conditions }'
```

Read three signals:

**a) All three revisions identical and stale.** `lastApplied == lastAttempted == lastPlanned`, all older than the source. The controller is not even *trying* — a failing CR would show `lastAttemptedRevision` at the *current* SHA with an error condition.

**b) The generation mismatch — the decisive tell.**

```
status.observedGeneration:          73     ← controller has seen generation 73
conditions[*].observedGeneration:   72     ← conditions never written for 73
```

The spec changed (generation bumped), the controller registered it, and no condition was ever produced for it. That gap means *the reconcile for the current generation never ran*. Combined with an empty `status.lock` (no stuck state lock) and no error condition, suspension is the leading explanation.

**c) No error, no events.** `kubectl describe terraform $CR | tail -5` shows `Events: <none>`. Suspension is not a failure — nothing is logged because nothing happens.

> ⚠️ **Do not read `conditions[].lastTransitionTime` as "when this last ran".** Kubernetes only stamps it when a condition's *status* changes. In the validated occurrence the `Plan` condition read `2025-03-06` — 17 months old — while `status.lastPlanAt` showed the real last plan **10 days** earlier. Use the `status.last*At` timestamps for timing; the condition timestamps will mislead you into over-estimating drift. `[verified]`

## Step 4 — Check the fields the listing hides

`kubectl get terraform` will not show you this. Ask explicitly:

```bash
kubectl -n flux-system get terraform -o custom-columns='NAME:.metadata.name,SUSPEND:.spec.suspend,READY:.status.conditions[?(@.type=="Ready")].status,REV:.status.lastAppliedRevision'
```

**Expected:** one line per CR. `SUSPEND=true` on the head CR is your answer. `<none>` means the field is absent (the normal state).

> Keep this on **one line**. Shell line-continuation inside the `custom-columns` argument breaks the parse and kubectl reports the whole format string as a missing resource name. `[verified]`

Also dump the head CR's full spec — the plan-gate in Step 6 depends on three fields most responders never look at:

```bash
kubectl -n flux-system get terraform $CR -o jsonpath='{.spec.suspend} | {.spec.approvePlan} | {.spec.storeReadablePlan} | {.spec.alwaysCleanupRunnerPod}{"\n"}'
```

## Step 5 — Find out who suspended it, and why

`spec.suspend` was set by a human. Find out which tool and when **before** reverting it — someone may have suspended the CR deliberately to stop drift detection reverting a manual change.

```bash
kubectl -n flux-system get terraform $CR \
  -o jsonpath='{range .metadata.managedFields[*]}{.manager}{"\t"}{.operation}{"\t"}{.time}{"\n"}{end}'
```

**Expected:** a `tfctl` (or `kubectl-patch`) entry whose timestamp marks the suspension. In the validated occurrence:

```
kustomize-controller   Apply    2026-08-06T13:36:47Z
tf-controller          Update   2026-08-14T08:37:01Z
tfctl                  Update   2026-08-14T08:37:01Z     ← the suspend
```

Correlate that timestamp against the status timestamps from Step 3. A suspend shortly after a `lastAppliedByDriftDetectionAt` is a hint that someone was fighting drift detection over a manual change — treat it as a reason to read the plan in Step 6, not as proof.

⚠️ **`tfctl` records no user identity.** The timestamp is all you get. Ask the team who worked on that component at that time — a minute-precision timestamp is usually enough for someone to remember.

---

## Step 6 — Un-suspend

The minimal fix is one patch:

```bash
kubectl -n flux-system patch terraform $CR --type=merge -p '{"spec":{"suspend":false}}'
```

With `approvePlan: auto` (the house default) this plans **and applies immediately**. Whether that is acceptable depends on how much drift has accumulated — check every blocked CR's `lastAppliedRevision` in the Step 4 output first. They are often on *different, much older* SHAs than the head CR, so the cascade can apply a far larger backlog than the head CR's own staleness suggests.

### 6a — Plan-gated variant (recommended when drift is unknown)

To read the plan before it applies, three things must be true at once — and this is where the obvious approach fails:

```bash
# 1. STOP FLUX FIRST. Without this the gate does not hold — see the warning below.
OWNER=$(kubectl -n flux-system get terraform $CR \
  -o jsonpath='{.metadata.labels.kustomize\.toolkit\.fluxcd\.io/name}')
echo "$OWNER"
flux -n flux-system suspend kustomization "$OWNER"

# 2. Un-suspend in plan-only mode, with a readable plan and a surviving runner pod
kubectl -n flux-system patch terraform $CR --type=merge -p '{
  "spec": {
    "suspend": false,
    "approvePlan": "",
    "storeReadablePlan": "human",
    "alwaysCleanupRunnerPod": false
  }}'

kubectl -n flux-system get terraform $CR -w
```

> 🔴 **The gate fails without step 1.** `approvePlan` **is** declared in the rendered manifest, so `kustomize-controller` owns it. Patch it imperatively and Flux reverts it to `auto` on its next reconcile, and tofu-controller then auto-approves the pending plan. Observed verbatim in the validated session: three `Plan generated: set approvePlan: "plan-…" to approve this plan.` lines, then `Initializing → Applying → Applied successfully`. The plan happened to be trivial, so no harm — but the gate did not hold. `[verified]`
>
> `spec.suspend` is the opposite case: **absent** from Git, so Flux never touches it. That asymmetry is the whole reason this failure mode exists.

Read the plan from the ConfigMap `storeReadablePlan: human` produces:

```bash
kubectl -n flux-system get cm | grep -i 'tfplan.*'"$CR"
kubectl -n flux-system get cm tfplan-default-$CR -o jsonpath='{.data.tfplan}' | cat
```

**Expected:** ordinary OpenTofu plan text. In the validated occurrence:

```
Plan: 0 to add, 1 to change, 0 to destroy.
  # module.db.kubernetes_manifest.cluster will be updated in-place
  ~ externalClusters = (known after apply)
```

Judge it: **any `to destroy`, or a change that would revert something a colleague set by hand, means stop.** Re-suspend and find the person from Step 5.

Approve:

```bash
PLAN=$(kubectl -n flux-system get terraform $CR -o jsonpath='{.status.plan.pending}')
echo "$PLAN"        # format: plan-<branch>-<short-sha>
kubectl -n flux-system patch terraform $CR --type=merge \
  -p "{\"spec\":{\"approvePlan\":\"$PLAN\"}}"
```

Restore the fields you borrowed, then let Flux own them again:

```bash
kubectl -n flux-system patch terraform $CR --type=merge -p '{
  "spec":{"approvePlan":"auto","storeReadablePlan":"none","alwaysCleanupRunnerPod":true}}'
flux -n flux-system resume kustomization "$OWNER"
```

`suspend: false` persists on its own — Git does not declare it, so the resume will not undo the fix.

### Abort at any point

```bash
kubectl -n flux-system patch terraform $CR --type=merge -p '{"spec":{"suspend":true}}'
```

## Step 7 — Watch the cascade

```bash
kubectl -n flux-system get terraform -w
```

**Expected:** the head CR reaches `Ready=True` at the **current** source revision, then each tier unblocks in dependency order. Every downstream CR now applies its own accumulated backlog — stay watching; a failure in any of them is the next blocker, not a new problem.

---

## Verification (final smoke test)

```bash
# 1. Head CR current, and nothing suspended any more
kubectl -n flux-system get terraform -o custom-columns='NAME:.metadata.name,SUSPEND:.spec.suspend,READY:.status.conditions[?(@.type=="Ready")].status,REV:.status.lastAppliedRevision'

# 2. Generation mismatch gone
kubectl -n flux-system get terraform $CR -o json | \
  jq '{status: .status.observedGeneration, conditions: [.status.conditions[].observedGeneration] | unique}'

# 3. The resource you were actually waiting for
kubectl -n <app-ns> get cm <configmap> -o jsonpath='{.data}' | jq 'keys'
```

**Expected:** (1) every `REV` at the current source SHA, no `SUSPEND=true`; (2) `status` and `conditions` generations equal; (3) your rendered change present.

> A ConfigMap change does **not** restart its consumers. Roll the Deployment that mounts it, or the running pods keep the old file.

## Common failures + fix recipes

| Symptom | Likely cause | Fix |
|---|---|---|
| `kubectl logs deploy/tf-controller` → `deployments.apps "tf-controller" not found` | The deployment is named **`tofu-controller`**; `tfctl`/`tf-controller` is the upstream project name, not the workload. | `kubectl -n flux-system logs deploy/tofu-controller --tail=300 \| grep -i <cr>` `[verified]` |
| `grep`ping controller logs for the stuck CR returns nothing | A suspended CR is skipped before any logging. Absence of log lines is **evidence of suspension**, not of a dead controller. | Confirm the controller is alive by grepping for a *downstream* CR — you should see `Dependencies do not meet ready condition, retrying in 15s` every 15 s. Then go to Step 4. `[verified]` |
| `custom-columns` command errors with the whole format string quoted as a resource name | Shell line-continuation inside the `-o custom-columns=` argument. | Put it on one line. `[verified]` |
| `approvePlan: ""` patch has no effect — the plan applies anyway | `kustomize-controller` owns `approvePlan` from Git and reverts it to `auto`. | Suspend the owning Kustomization first (Step 6a step 1). `[verified]` |
| No `tfplan-*` ConfigMap appears | `spec.storeReadablePlan` is `none` (house default) — no readable plan is stored anywhere. | Set `storeReadablePlan: "human"` before planning. `[verified]` |
| Runner pod vanishes before you can read its logs | `spec.alwaysCleanupRunnerPod: true` (house default). | Set it to `false` for the duration, or use the `tfplan-*` ConfigMap instead — more reliable. `[verified]` |
| Head CR is stale but **not** suspended, and `lastAttemptedRevision` equals the current SHA | A genuine apply failure. | Read `conditions` for the error, then the runner pod logs. Different problem — this runbook ends here. |
| Head CR is stale, not suspended, `lastAttemptedRevision` also stale, `status.lock` **populated** | Orphaned tfstate lock. | Check `spec.tfstate.forceUnlock` (`auto` clears it on the next run). `[inference]` — not exercised; the validated occurrence had an empty `lock`. |
| Chain unblocks, then a downstream CR fails | It is applying its own long-accumulated backlog. | Treat as a fresh incident on that CR; the head CR is fixed. |

## What happens after (root cause)

Un-suspending is the **fix for this occurrence**, not for the pattern. Nothing prevents the next stray `tfctl suspend`, and nothing detected 10 days of a fully blocked OpenStack control plane. Both gaps are tracked in the [Root-Cause Backlog](../../../../generic/root-cause-backlog.md) — *"tofu-controller Terraform CR silently stuck on a stale revision"*.

---

## Related

- [Contributing to Irobox — branching, releases & deploying to environments](../../architecture/conceptions/irobox/contributing-and-releases.md) — how a change is *supposed* to reach an env, and why hand-edits to `fleet-infra-generated` are transient.
- [Irobox Deep Dive](../../architecture/conceptions/irobox/summary.md) — hieradata lookup order, `fleet-infra-cli`, the generated tree.
- [OPCP Core Deep Dive §7](../../architecture/conceptions/opcp-core/summary.md) — the templating / GitOps chain.
- [Environment access — bastion, proxy, SSO, kubectl](../../environments/env-access-onboarding.md).
- [Root-Cause Backlog](../../../../generic/root-cause-backlog.md).
- [Glossary](../../../../shared/glossary.md) — `tofu-controller`, `tf-runner`, `tfctl`.

## Source / changelog

- Drafted **2026-08-24** from a live minint debugging session: a `dashboard_fqdns` / `novncproxy allowed_origins` change was rendered, committed to `prod-minint`, confirmed applied by Flux — and never materialised, because `keystone` had been suspended via `tfctl` on **2026-08-14 08:37:01Z** and had blocked ten downstream Terraform CRs for 10 days.
- All commands, outputs and failure modes marked `[verified]` were exercised in that session. `[inference]` items were not.
- **Open:** who ran the `tfctl suspend`, and why — `tfctl` records no identity. The eventual plan was a single in-place change, so the "protecting a manual edit" reading is **not** supported by evidence.
