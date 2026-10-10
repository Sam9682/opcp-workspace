---
id: core/recover-rabbitmq-pod-stuck-terminating
type: runbook
diataxis: how-to
title: "Recover a nova RabbitMQ pod stuck in Terminating (blocked queues)"
owner: opcp-core-compute
status: draft
last_verified: 2026-07-29
next_review: 2026-10-29
publish_target: confluence
tags: [rabbitmq, nova, nova-compute-ironic, kubernetes, terminating, queues, minint, first-responder]
---

# Recover a nova RabbitMQ pod stuck in Terminating (blocked queues)

> **When to use:** an OpenStack service's messaging goes quiet and the symptom points at RabbitMQ — most often the **nova** RabbitMQ cluster pod is wedged in **`Terminating`**, so the queues it hosts are blocked and the affected agents can't exchange RPC. Classic tell-tale on the compute side:
> - **`nova-compute-ironic`** (and other nova agents) logging repeated reconcile warnings such as
>   `Found orphan compute node <N> hypervisor host …` / `We are not deleting this as the driver says this node has not been deleted.`
> - agents appearing `up` but not making progress; RPC timeouts; conductor/compute log gaps.
>
> **Symptom, verbatim (FR-20260729-151310, minint, 2026-07-29):** *"is it normal for nova-compute-ironic ds to produce warnings like 'Found orphan compute node 12 hypervisor host' … 'We are not deleting this as the driver says this node has not been deleted'?"* — root cause turned out to be the nova RabbitMQ cluster pod stuck in `Terminating`.
>
> **Scope:** the OPCP control-plane K8s (minint / demo) where the OpenStack services run. This clears a **wedged pod** so the StatefulSet/operator can recreate it — it does not fix *why* the pod got stuck (see Root cause / after).
>
> **Owner of this runbook:** opcp-core-compute — **TBD** confirm.
>
> **Status:** DRAFT — the **force-delete unblocked the queues** and was **validated 2026-07-29** against FR-20260729-151310 (minint). Namespace / label / pod-name specifics below are marked `[inference]` where not captured verbatim in that session — verify against the live cluster before running.

---

## TL;DR (the skeleton)

```
1. Confirm a nova RabbitMQ pod is stuck in Terminating (kubectl get pods)
2. Confirm the queues are actually blocked (agent logs / rabbitmqctl), not a cosmetic warning
   2b. If the rabbitmq pod is Running but logs flag ONE broken queue (quorum error etc.):
       delete just that queue → owner service recreates it (Step 3b) — least-disruptive, try first
3. Force-delete the stuck pod:   kubectl delete pod <pod> -n <ns> --force --grace-period=0
4. Verify the pod is recreated Running and the cluster is healthy
5. Verify the symptom clears (warnings stop, RPC flows again)
```

> The action that fixed FR-20260729-151310:
> ```bash
> kubectl delete pod <nova-rabbitmq-pod> -n <openstack-ns> --force --grace-period=0
> ```
> Force-deleting the wedged pod let the operator/StatefulSet recreate it and **unblocked the impacted queues**.

## Background — what a stuck-Terminating RabbitMQ pod does

The OpenStack services talk over RabbitMQ. Nova runs its own RabbitMQ cluster on the control-plane K8s; the queues live in that pod. When the pod is deleted (upgrade, node drain, eviction, OOM) Kubernetes marks it `Terminating` and waits for graceful shutdown. If shutdown never completes — a hung process, a stuck finalizer, a lost node, an unmounted PVC — the pod sits in `Terminating` **indefinitely**. While it does, the StatefulSet won't bring up a replacement (the identity is still "in use"), so the queues that pod hosted stay **blocked**: producers can't publish, consumers can't drain, and nova agents that depend on those queues stall.

On the compute side that shows up as **reconcile warnings from `nova-compute-ironic`** — it can't complete the compute-node bookkeeping it normally does over RPC, so it logs *"orphan compute node … not deleting"* and similar. `[inference]` The warnings are a **symptom** of the blocked messaging, not an independent fault: once the queues flow again they stop. Treating the warning in isolation (chasing the "orphan node") is a dead end — check RabbitMQ first.

`kubectl delete pod --force --grace-period=0` removes the wedged pod from the API without waiting for the (never-arriving) graceful shutdown, letting the operator/StatefulSet recreate a healthy one and restoring the queues.

## Prerequisites

- [ ] `kubectl` against the affected control-plane K8s (see [env-access-onboarding — Surface B](../../environments/env-access-onboarding.md#surface-b--ssh-to-a-controller--env): `gatewayseed → seedadmin → ssh <env> → ssh cloudstore`).
- [ ] The **namespace + pod name** of the nova RabbitMQ cluster (`[inference]` — often the `openstack`/`nova` deploy namespace; confirm in Step 1).
- [ ] Awareness that **force-delete is destructive to that pod** — only do it once you've confirmed the pod is genuinely wedged (`Terminating` and not progressing), not mid-normal-restart.

---

## Step 1 — Confirm the pod is stuck in Terminating

```bash
# Find the nova RabbitMQ pod and its state (adjust ns/selector to the cluster)
kubectl get pods -A | grep -i rabbit
kubectl get pods -n <openstack-ns> -l app=rabbitmq        # [inference] selector varies by operator
```

**Expected (stuck):** a RabbitMQ pod in **`Terminating`** for far longer than a normal shutdown (minutes, not seconds), and no healthy replacement coming up. Inspect why it won't die:

```bash
kubectl describe pod <nova-rabbitmq-pod> -n <openstack-ns> | tail -40   # finalizers, events, volume detach hangs
```

## Step 2 — Confirm the queues are actually blocked

Don't force-delete on a cosmetic warning alone. Corroborate that messaging is stalled:

```bash
# Nova agent logs showing the reconcile warnings / RPC stalls
kubectl logs -n <openstack-ns> ds/nova-compute-ironic --tail=50 | grep -Ei 'orphan compute node|not deleting|MessagingTimeout|reply queue'

# If you can reach a healthy rabbitmq pod, check queue depth / consumers [inference]
kubectl exec -n <openstack-ns> <healthy-rabbitmq-pod> -- rabbitmqctl list_queues name messages consumers | sort -k2 -n | tail
```

**Expected:** the nova warnings are recurring **and** the RabbitMQ pod is the wedged one — the two line up in time. That correlation is the go/no-go for Step 3.

## Step 3 — Force-delete the stuck pod

```bash
kubectl delete pod <nova-rabbitmq-pod> -n <openstack-ns> --force --grace-period=0
```

**Expected:** the pod is removed immediately; the StatefulSet/operator schedules a fresh one within seconds.

## Step 3b (alternative) — delete a single broken queue instead of the whole pod

Sometimes the RabbitMQ pod is **Running**, not `Terminating`, but its **logs flag a specific queue** — a **quorum error** (lost quorum / minority / `not_enough_replicas`), a crashed/undeliverable queue, or any per-queue fault. In that case you don't need to force-delete the whole pod: **delete just the offending queue — the owner OpenStack service recreates it automatically** on its next connect. This is the least-disruptive mitigation; reach for it before Step 3 when the fault is isolated to one queue.

```bash
# Read the rabbitmq pod logs and pick out the queue named in the error
kubectl logs -n <openstack-ns> <nova-rabbitmq-pod> -c rabbitmq --tail=100 | grep -Ei 'quorum|not_enough_replicas|crash|queue'

# Delete the broken queue — the owning service (nova here) will recreate it
rabbitmqctl nova delete_queue scheduler_fanout
```

Sample output (queue deleted cleanly, no messages lost):

```
Defaulted container "rabbitmq" out of: rabbitmq, setup-container (init)
Deleting queue 'scheduler_fanout' on vhost 'myqueue' ...
Queue was successfully deleted with 0 ready messages
```

> `[inference]` `rabbitmqctl <service>` here is the local helper that wraps `kubectl exec` into that service's rabbitmq pod (hence the *"Defaulted container rabbitmq"* line) — `nova` selects the nova cluster. If you don't have that helper, run `rabbitmqctl` inside the pod directly: `kubectl exec -n <openstack-ns> <nova-rabbitmq-pod> -c rabbitmq -- rabbitmqctl delete_queue <queue> --vhost <vhost>`.

**Safe because** these RPC/fanout queues (`scheduler_fanout`, reply queues, etc.) hold only in-flight transient messages — the owner service redeclares them on reconnect. Deleting a queue with **`0 ready messages`** loses nothing; a queue with a backlog would drop those messages, so check `list_queues name messages` first if the count matters.

**Then** re-run Step 2 / Verification to confirm the fault cleared. If deleting the queue doesn't help and the pod is genuinely wedged, fall through to Step 3 (force-delete the pod).

## Verification (final smoke test)

```bash
# 1. Pod recreated and healthy
kubectl get pods -n <openstack-ns> -l app=rabbitmq          # -> Running, Ready

# 2. Cluster rejoined (if a multi-node rabbit cluster) [inference]
kubectl exec -n <openstack-ns> <new-rabbitmq-pod> -- rabbitmqctl cluster_status

# 3. The symptom clears — nova warnings stop recurring
kubectl logs -n <openstack-ns> ds/nova-compute-ironic --tail=20 --since=2m | grep -i 'orphan compute node' || echo "clean — no new orphan-node warnings"
```

**Expected:** RabbitMQ pod `Running`/`Ready`, cluster healthy, and **no fresh** `orphan compute node` warnings after the pod recovered — proving the queues drained and RPC resumed.

## Common failures + fix recipes

| Symptom | Likely cause | Fix |
|---|---|---|
| Pod goes back to `Terminating` / new pod also wedges | The underlying cause is still there — a stuck **PVC/volume detach** or a hung node, not the pod itself. | `kubectl describe` the pod + node; if a node is `NotReady`, the volume can't detach — cordon/drain or recover the node. Escalate to infra if the PVC won't release. |
| Force-delete leaves the StatefulSet not recreating | Stale finalizer on the pod, or the operator is unhealthy. | Remove the finalizer (`kubectl patch pod <p> -p '{"metadata":{"finalizers":null}}'`) `[inference]`; check the rabbitmq operator pod is `Running`. |
| Warnings persist after RabbitMQ is healthy | The orphan-compute-node entry is a **real** stale record, not just blocked messaging. | Now (and only now) investigate the nova compute-node/hypervisor record itself — it wasn't purely a queue symptom. |
| Not sure which rabbit is nova's | Multiple RabbitMQ clusters (nova / neutron / cinder / keystone) on the same K8s. | Match the blocked agent to its cluster — nova agents → the nova rabbitmq; confirm via the pod's labels/namespace before deleting. |
| RabbitMQ pod is `Running` but its logs flag a **quorum error** (or another per-queue fault) on a specific queue | A single queue lost quorum / crashed; the pod itself is healthy. | Delete just that queue — the owner service recreates it: `rabbitmqctl <service> delete_queue <queue>` (Step 3b). No pod force-delete needed. |

## What happens after (root cause)

Force-delete is a **mitigation**, not a fix — the pod will wedge again if the cause (stuck shutdown / PVC detach / node loss) recurs. Recurrences are tracked in the [Root-Cause Backlog](../../../../generic/root-cause-backlog.md) — *"nova RabbitMQ pod stuck in Terminating → blocked queues"*. At ≥2 occurrences, open a SOV ticket for the source fix (pod lifecycle / PDB / graceful-shutdown handling).

---

## References

- **First occurrence:** FR bot case **FR-20260729-151310** (minint, 2026-07-29) → OFR-20 — nova-compute-ironic orphan-node warnings; root cause = nova RabbitMQ pod stuck `Terminating`; force-delete unblocked the queues.
- Recurring-issue tracking: [Root-Cause Backlog](../../../../generic/root-cause-backlog.md).
- Cluster access: [Environment access — Surface B](../../environments/env-access-onboarding.md#surface-b--ssh-to-a-controller--env).
