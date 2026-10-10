# Octavia — sizing benchmark (amphora.large vs amphora.xlarge)

> **Why this doc exists:** the [NSQ-002 decision](../open-questions.md) locked the amphora sizing taxonomy to **S/M/L**. This benchmark — run on the **real implemented Octavia** — measures what those flavors actually deliver in throughput/latency, verifies *where* the bottleneck is, and gives a capacity-planning baseline. It also surfaces a tension: the L flavor (4 vCPU) caps at ~90k req/s, and the benchmark's `amphora.xlarge` (8 vCPU) — which is **outside** the locked taxonomy — is the evidence that a throughput tier beyond V1's S/M/L may be needed post-V1.
>
> **Source:** "Octavia Benchmark" (Confluence space SOV, pageId 963465114), **dated 2026-06-05, author Damien Rannou**. Target: Octavia LB on **OpenStack 2025.2, BM-POD demo-minint**.
>
> **Provenance caveat:** all numbers are from **demo-minint (BM-POD)**, not an SNC-qualified production deployment. Treat as as-built POC evidence, not a production SLA. The flavor definitions are in [`octavia-implementation.md`](octavia-implementation.md) §12.
>
> **⚠️ Pinning caveat (added 2026-06-10, NSQ-006 re-correction):** this benchmark ran on amphorae whose flavors **then** carried `hw:cpu_policy=dedicated` + `hw:cpu_thread_policy=require` (CPU-pinned, per the Confluence-era specs). **Current irobox master flavors are UNPINNED** — they land on the `ovh.network` aggregate (`pinning_enabled: false`, `compute-vm-hosts-trunk_vars.yaml:153-159`) and no longer carry `hw:cpu_policy=dedicated` (`octavia_post_setup_vars.yaml`). The **~90k (large) / ~152k (xlarge) req/s ceilings and the guest-CPU-bottleneck conclusion should be re-validated on unpinned amphorae** before being used for binding capacity planning. See [`../decisions.md`](../decisions/index.md) 2026-06-10 NSQ-006 re-correction entry.

---

## 1. Objective + method

**Objective:** throughput + latency of `amphora.large` (4 vCPU / 4 GB) vs `amphora.xlarge` (8 vCPU / 8 GB).

| Knob | Setting |
|---|---|
| Topology | **SINGLE** (1 active amphora, **no HA**) — measures throughput, not failover |
| Listener | HTTP `:80` |
| Pool | ROUND_ROBIN, 2 members (b3-32 nginx, in-memory ~150 B response) |
| Load gen | 1× b3-120 (32 vCPU), `wrk -t32`, keepalive, 60s/step, public FIP |
| Flavors | both `hw:vif_multiqueue_enabled=true` |
| Steps | 200 / 1000 / 2000 / 4000 / 8000 connections |

> **`amphora.xlarge` (8 vCPU / 8 GB) is NOT part of the locked S/M/L taxonomy** — it was created specifically as a benchmark probe to see what one tier *beyond* L would deliver. Don't treat it as a shipping flavor.

## 2. Results

| Flavor | vCPU | Peak throughput | p50 latency (low→high conns) | Errors |
|---|---|---|---|---|
| **amphora.large** | 4 | **~90.7k req/s** (at 2000 conns) | 2.4 → 97 ms | zero 5xx |
| **amphora.xlarge** | 8 | **~152.8k req/s** plateau (1000–8000 conns, <3% variation) | 2.2 → 45.9 ms | zero 5xx; 18 timeouts at 8000 |

Confirmation run: **154,440 req/s peak** → the established `amphora.xlarge` CPU ceiling is **~152–154k req/s**.

## 3. Interpretation — vertical scaling

- **×1.68 throughput for ×2 vCPU** → **~84% scaling efficiency** (sub-linear, attributed to HAProxy multi-thread contention).
- Per-vCPU efficiency: **22.7k (large) → 19.1k (xlarge)** req/s per vCPU.
- Beyond saturation, throughput is flat; extra connections turn into **queueing latency** (p50 roughly doubles per doubling of conns — Little's law). **Zero 5xx at all steps.**
- **Vertical vCPU scaling is the primary capacity lever.**

## 4. Bottleneck — VERIFIED = amphora guest CPU

The key finding, with evidence:

- **Bottleneck = the amphora GUEST CPU, not the hypervisor datapath.**
- virtio **multiqueue active and effective** (8/8 queues; vhost threads ~10–12% each).
- HAProxy ~**758% CPU** (7 workers saturated); guest ~**98%** (70% in kernel). **No steal time.**
- **The earlier hypervisor-PPS hypothesis is REFUTED** for multiqueue amphorae.

> **Fleet caveat:** **pre-multiqueue amphorae** (single virtio queue) hit a **single-vhost PPS wall well below the CPU ceiling** — they need a **failover** to be re-created with multiqueue. Audit the fleet for pre-multiqueue amphorae and schedule failovers; ensure **every** flavor carries `hw:vif_multiqueue_enabled=true`.

**Side finding:** `rsyslogd` consumed ~20% CPU in the amphora shipping per-request flow logs (~150k lines/s). **Optimization candidate:** `[haproxy_amphora] connection_logging=False`.

## 5. Capacity planning

| Flavor | vCPU | Ceiling | req/s per vCPU | Comfort zone (p99 < 60 ms) |
|---|---|---|---|---|
| `amphora.large` | 4 | ~90k req/s | ~22.7k | ≤ 2000 conns |
| `amphora.xlarge` | 8 | ~152k req/s | ~19.1k | ≤ 2000 conns |

**Takeaways:**
- Use **large** below ~80k req/s/LB; reach for **xlarge** beyond.
- **Recommend tenants set `--connection-limit ≈ 2000`** — both flavors withstand 8000 conns without errors (only latency degrades, p99 ~300 ms), but ~2000 is the comfort point.
- **16 vCPU** is the natural next step (~250–280k req/s expected).
- **Operational action:** audit the fleet for pre-multiqueue amphorae + schedule failovers; ensure every flavor has `hw:vif_multiqueue_enabled=true`.

## 6. Study limits

- Single load generator.
- Small payloads (~150 B) → this is a **request-rate ceiling, not a bandwidth ceiling** (traffic was only ~22 MB/s).
- 60s per step.
- **SINGLE topology only** — ACTIVE_STANDBY tests HA, not throughput.
- **HTTP only** — TLS would shift the bottleneck further onto CPU.

## 7. Implications for Network Service planning

- **NSQ-002 tension (the headline):** the locked taxonomy is S/M/L = 1/2/4 vCPU. **L (4 vCPU) caps at ~90k req/s.** A tenant needing more throughput per LB has no flavor for it in V1. The `amphora.xlarge` (8 vCPU, ~152k) and a hypothetical 16-vCPU tier (~250–280k) are **post-V1 throughput-tier candidates**. This is concrete evidence — not a brief-Q&A guess — that V1's S/M/L may need a throughput extension post-V1. See [NSQ-002 refinement note](../open-questions.md), 2026-06-09. *(Also relevant to [NSQ-020](../open-questions.md) — max members per pool / listener separation.)*
- **`hw:vif_multiqueue_enabled=true` is mandatory on every amphora flavor** — without it, amphorae hit a single-vhost PPS wall well below CPU. This is now a hard config requirement for M1 flavor setup, not an optimization.
- **`--connection-limit ≈ 2000` per LB** is the recommended tenant default — fold into M2 API defaults / docs.
- **`connection_logging=False`** is a per-LB performance optimization worth defaulting (or making tenant-configurable) — saves ~20% amphora CPU at high request rates.
- **Pre-multiqueue fleet audit** is an operational runbook candidate (failover to re-create with multiqueue).

## 8. Cross-references

- [`octavia-implementation.md`](octavia-implementation.md) §12 — the amphora flavor definitions + extra-specs (`hw:vif_multiqueue_enabled=true` etc.).
- [`octavia-from-fdd.md`](octavia-from-fdd.md) §1 — the FDD S/M/L spec.
- [`../runbooks/octavia-debugging.md`](../runbooks/octavia-debugging.md) — amphora CPU / multiqueue debug.
- [`../open-questions.md`](../open-questions.md) — NSQ-002 (sizing) + NSQ-020 (pool limits).
- Source: Confluence space SOV pageId 963465114, "Octavia Benchmark", Damien Rannou, 2026-06-05 (demo-minint / BM-POD).
