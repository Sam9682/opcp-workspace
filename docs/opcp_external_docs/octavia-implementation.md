# Octavia — implemented deployment (how it's ACTUALLY built & operated today)

> **Why this doc exists:** [`octavia-from-fdd.md`](octavia-from-fdd.md) is the *spec* distilled from the CB FDD v0.4. This doc is the *implementation* — the real, code-level Octavia that the OPCP/SNC team built and runs on **OpenStack 2025.2, on Kubernetes**, in the **demo-minint / BM-POD** environment. It goes well beyond the FDD: concrete ports, CIDRs, flavours, K8s/Terraform layout, PKI chain, Cilium policies, and the downstream patches against upstream Octavia.
>
> **Sources (Confluence space SOV, fetched 2026-06-09):** "Octavia Amphora — Control Plane Interactions" (pageId 963465107) + "Octavia — Downstream Changes from Upstream" (pageId 963465109). Companion docs: [`octavia-sizing-benchmark.md`](octavia-sizing-benchmark.md) (benchmark), [`../runbooks/octavia-debugging.md`](../runbooks/octavia-debugging.md) (ops). SNC hardening matrix in §11 below.
>
> **Environment caveat:** everything here describes **demo-minint / BM-POD** (a pre-prod/POC environment), **not** an SNC-qualified production deployment. Flavour numbers, network values, and the security context are all as-implemented in that environment. Label any value carried downstream as "demo-minint as-built".
>
> **Vocabulary:** "LB" here = **Octavia LBaaS** (tenant-facing — the thing this project ships). "Gateway" = Neutron L3 Router (not in this doc's scope). See [`../CLAUDE.md`](../CLAUDE.md) "Two LB layers" + "Gateway" conventions.

---

## 1. What this is in one paragraph

Octavia is OpenStack's LBaaS. A **control plane** (5 services on Kubernetes) manages the full lifecycle of **amphorae** — lightweight VMs that each run **HAProxy** and an **amphora-agent** REST endpoint. One or more amphorae back each load balancer; the controller boots them on Nova, pushes HAProxy config over mTLS, and watches them via UDP heartbeats. The implemented OPCP deployment runs the control plane on K8s (deployed by Terraform), backs it with PostgreSQL + RabbitMQ, and patches upstream Octavia (MySQL-only) to run on Postgres.

## 2. Control-plane components (5 services, single Docker image)

All 5 control-plane services run in the **`octavia` K8s namespace** and share a **single Docker image** with different entrypoints.

| Service | K8s shape | Role | Replicas |
|---|---|---|---|
| **octavia-api** | Deployment + Service + Ingress, TCP **9876**, HTTP `/healthcheck` probes | REST API entrypoint (tenant-facing) | `replicas = len(hosts)` |
| **octavia-worker** | Deployment, RabbitMQ consumer, no probe | Executes async flows (create LB, failover, etc.) | `replicas = len(hosts)` |
| **octavia-health-manager** | Deployment + **Service type LoadBalancer**, UDP **5555** | Receives amphora heartbeats, triggers failover | (see §9 Cilium LB) |
| **octavia-housekeeping** | Deployment | Spare-amphora pool, DB cleanup, cert rotation | **1** |
| **octavia-driver-agent** | Deployment, unix sockets | Provider-driver bridge | **1** |

> **Feeds [NSQ-014](../open-questions.md) (Octavia CP HA topology):** the implemented topology is **5 K8s deployments**, not a "1× standalone vs 3× HA VM" choice. api/worker scale to `len(hosts)`; housekeeping/driver-agent are singletons; health-manager is exposed via a Cilium `LoadBalancer` Service. **Anti-affinity on hostname** when `replicas > 1`. This is concrete evidence that the FDD's "1× or 3× HA VM" framing is superseded by a K8s-native multi-deployment model. *(See [NSQ-014 refinement note](../open-questions.md), 2026-06-09.)*

### Terraform / K8s layout

Deployed via Terraform (`hashicorp/kubernetes` provider). Module tree:

```
terraform/
├── root-control-plane         ← wires DB + RabbitMQ + Keystone + Octavia (single apply)
│   └── control-plane (child)  ← 5 Deployments + api Service/Ingress + ConfigMap octavia.conf
│                                + secrets + octavia-certs Secret + init-Job (DB migration)
├── root-post-setup            ← amphora flavors, mgmt networks, security groups
├── network-policies           ← the 8 CiliumNetworkPolicies (§9)
└── hieradata                  ← config data
```

Config injection: `oslo.config` ConfigMap from `etc/octavia.conf`; sensitive values via env `OS_SECTION__KEY` (e.g. `OS_DATABASE__CONNECTION`, `OS_HEALTH_MANAGER__HEARTBEAT_KEY`). `controller_ip_port_list` is auto-derived from the health-manager LoadBalancer Service IP.

## 3. Management network (`lb-mgmt-net`)

The CP↔amphora control channel rides a dedicated provider network. **Created in `root-control-plane` (single apply), with TF import blocks for migrating existing resources.**

| Property | Value |
|---|---|
| Network | `lb-mgmt-net` — VLAN provider network, **VLAN 410, physnet1** |
| Subnet | `lb-mgmt-subnet` — **`198.18.114.0/23`** `[verify — see §12 discrepancy]` |
| Gateway | **None** (`no_gateway=true`) — gateway-less by design (SNC control C9) |
| DHCP | Enabled — amphorae get their mgmt IP via DHCP |
| Allocation pool | `.21–198.18.115.254` (Page 1) / `.11–.254` (Page 5) `[verify minor inconsistency]`; first 10 IPs (`.1–.10`) reserved for CP |

Security groups (created in `root-control-plane`):
- **`lb-mgmt-sec-grp`** (amphora mgmt port): ingress **TCP 9443** from controller, **ICMP**, TCP 22 (SSH, debug-only).
- **`lb-health-mgr-sec-grp`** (health manager): ingress **UDP 5555** from amphora.

Each amphora also has a **2nd NIC on the tenant network** hosting the VIP; HAProxy listens on the VIP there.

## 4. Communication flows

```
                         RabbitMQ (oslo.messaging)
   octavia-api  ───────────────────────────────────────▶  octavia-worker
       │ TCP 9876                                              │
       │ (Ingress / nginx)                                     │ TCP 9443 mTLS
       ▼                                                       ▼
   tenant user                                          amphora-agent (HAProxy VM)
                                                               │ UDP 5555 (HMAC)
   octavia-health-manager ◀───────────────────────────────────┘
       (Service type LoadBalancer, Cilium LB IP)

   octavia-worker ──▶ Nova 443 · Neutron 443 · Glance 443 · Barbican 9311 · Keystone 5000
                      (all via K8s ingress)
```

| Flow | Transport | Detail |
|---|---|---|
| **Controller → Amphora** | TCP **9443**, **mTLS** | worker + housekeeping → amphora-agent HTTPS REST. Controller presents `client.pem`, amphora verifies against `server_ca.pem`; controller verifies amphora cert against the same CA. Ops: upload HAProxy config, upload listener TLS certs, start/stop/reload HAProxy, query status/stats, upload keepalived config (active-standby). |
| **Amphora → Health Manager** | UDP **5555**, HMAC | Periodic heartbeats, HMAC-signed with shared `heartbeat_key` (`OS_HEALTH_MANAGER__HEARTBEAT_KEY`). Payload: amphora ID, LB status, listener stats, HAProxy status, seq number. `controller_ip_port_list` tells amphorae where to send (Cilium LB pool IP, auto-injected by TF). No heartbeat within `heartbeat_timeout` → amphora OFFLINE → failover. |
| **API → Worker** | RabbitMQ (oslo.messaging) | `create_loadbalancer_flow` etc., async. **Must be `rabbit://`, not `amqp://`** (see runbook common issues). |
| **Worker → OpenStack APIs** | via K8s ingress | Nova 443 (amphora VMs), Neutron 443 (ports/networks/SGs), Glance 443 (amphora image), **Barbican 9311** (listener TLS certs), Keystone 5000 (token validation). |
| **Housekeeping** | internal + 9443 | Spare-amphora pool, DatabaseCleanup, CertRotation (via 9443). |

## 5. PKI certificate chain

Two **separate** cert systems — don't conflate them:

1. **Internal controller↔amphora mTLS** (`local_cert_generator`):
   - **Octavia CA** `[verify algorithm — Page 1: ECDSA P384; Page 5: RSA 4096 — see §12]`, self-signed, 10y → signs:
     - **Controller client cert** (`client.pem`, client_auth) — used by worker/housekeeping.
     - **Amphora server cert** (RSA 2048, `CN=amphora-uuid`) — generated **at boot** by `local_cert_generator`, signed with `ca_key.pem`.
   - K8s Secret **`octavia-certs`** (mounted `/etc/octavia/certs/`): `ca_cert.pem`, `ca_key.pem`, `client.pem`, `server_ca.pem`. Auto-generated by Terraform (`hashicorp/tls`).
2. **User-facing listener TLS** (`barbican_cert_manager`): Barbican (9311) stores the tenant's TLS certs for HTTPS / TERMINATED_HTTPS listeners. **NOT** the internal mTLS. Confirms [NSQ-001](../open-questions.md) (Barbican already available) — `cert_manager=barbican_cert_manager`.

## 6. Amphora lifecycle

**Boot:**
```
worker gets "create LB"
  → Nova create VM (image amphora-x64-haproxy from Glance,
                    flavor amphora.{small,medium,large},
                    network lb-mgmt-net, SG lb-mgmt-sec-grp)
  → cloud-init / ConfigDrive → amphora-agent starts
  → controller signs + pushes server cert
  → agent serves HTTPS :9443
  → amphora starts UDP heartbeats
  → worker configures HAProxy via REST
  → attach VIP port (Neutron)
  → ACTIVE
```

**Failover:** health-manager detects missing heartbeats → amphora OFFLINE → spin a new amphora (or pull from spares pool) → config replayed from DB → VIP moved → old amphora deleted.

**Image:** Debian Trixie minimal; HAProxy; amphora-agent (Python REST :9443); cloud-init; nftables; serial console `ttyS0,115200`. See §10 for the build pipeline.

## 7. Infrastructure dependencies

| Dependency | Implementation |
|---|---|
| **Database** | **CloudNativePG** (PostgreSQL operator) + **PgBouncer**. Upstream Octavia is MySQL/MariaDB only → downstream-patched (see §8). |
| **Message queue** | **RabbitMQ Cluster Operator**. Mgmt port 15672 only reachable from operators. |
| **Identity** | **Keystone registration** (`modules/openstack/keystone-registration`) — creates the Octavia service user + endpoints. |
| **PKI** | `hashicorp/tls` Terraform provider auto-generates the CA + client cert (§5). |

## 8. PostgreSQL downstream patches

Upstream Octavia targets MySQL/MariaDB. To run on PostgreSQL (CloudNativePG):

- **Alembic migrations patched** for PostgreSQL dialect branching via `op.get_bind().dialect.name`. Affected revisions: `fac584114642`, `a5762a99609a`, `e37941b010db`, `392fb85b4419` (uses `sa.inspect(bind)`), `9bf4d21caaea`.
- Dropped `SQLALCHEMY_WARN_20`; dropped `subtransactions=True`; SQLAlchemy 2.0 autoload.
- Added **`psycopg2`** (replacing `pymysql`).

## 9. Cilium network policies (8 CiliumNetworkPolicies)

Deployed by the `network-policies` TF module. The Cilium pool for the health-manager LB is in `fleet-infra/default-cluster-template/apps/cilium/cilium.yaml`, **conditioned on `octavia.enabled`**.

| Policy | Effect |
|---|---|
| `octavia-db-np` | DB access scoping |
| `octavia-init-np` | DB-migration init-job scoping |
| `octavia-mq-np` | RabbitMQ scoping |
| `octavia-api-np` | **ingress** nginx / Neutron / Prometheus on 9876; **egress** Keystone 5000, PostgreSQL 5432, RabbitMQ 5672, Barbican 9311 |
| `octavia-worker-np` | **egress** Amphora 9443 TCP `0.0.0.0/0` |
| `octavia-health-manager-np` | **ingress** Amphora 5555 UDP `0.0.0.0/0` |
| `octavia-housekeeping-np` | **egress** Amphora 9443 |
| `octavia-driver-agent-np` | driver-agent scoping |

Health-manager LoadBalancer: label `ippool:"health-manager"` → **CiliumLoadBalancerIPPool** from the mgmt subnet (`172.16.0.3–172.16.0.9` `[verify — see §12 CIDR discrepancy]`). The module reads the assigned IP and injects it into `controller_ip_port_list`.

## 10. Image builds (Docker CP image + amphora QCOW2)

**Control-plane Docker image:**
- Multi-stage **Debian Trixie**, venv `/opt/openstack/octavia`, internal pip + upper-constraints.
- Runtime: **uwsgi**, user **octavia UID 42424**, port 9876.
- CI: CDS `.cds/actions/build-octavia.yaml` → Artifactory `openstack/octavia:<version>`.

**Amphora QCOW2 image (`diskimage-builder`):**
- `debian-minimal` / **Trixie**, 2 GB, ConfigDrive, **NFTables** enabled, SSH enabled (debug), serial `ttyS0,115200`.
- Output: `amphora-x64-haproxy-<release>-<version>.qcow2`.
- CI: `.cds/actions/build-amphora.yaml`.
- Runtime pkgs: cloud-init, haproxy, nftables, openssh-server, curl, socat, tcpdump, logrotate, rsyslog.

## 11. Security context

Control-plane pods:
- **Non-root UID/GID 42424**
- **Read-only root filesystem**
- **Drop ALL capabilities**
- seccomp `RuntimeDefault`
- **No privilege escalation**

## 12. OpenStack resources — amphora flavors

Created in `root-post-setup`. **Private** (service project only).

| Flavor | vCPU | RAM | Disk | Maps to FDD §7.2 |
|---|---|---|---|---|
| `amphora.small` | 1 | 1024 MB | 3 GB | **S** ✅ |
| `amphora.medium` | 2 | 2048 MB | 5 GB | **M** ✅ |
| `amphora.large` | 4 | 4096 MB | 10 GB | **L** ✅ |

> **STRONG confirmation of [NSQ-002](../open-questions.md):** the implemented flavors are **exactly the locked S/M/L taxonomy** (1/2/4 vCPU, 1/2/4 GB). See [NSQ-002 refinement note](../open-questions.md), 2026-06-09. **But** the [benchmark](octavia-sizing-benchmark.md) tested an `amphora.xlarge` (8 vCPU) that is **outside** the locked taxonomy → capacity-planning tension (L caps ~90k req/s; a throughput tier beyond V1 may be needed post-V1). See benchmark doc + NSQ-002 note.

**Extra specs on all amphora flavors** *(Confluence "Downstream Changes" state — **stale vs current code, see annotation below**)*:
- `aggregate_instance_extra_specs:ovh.b3-milan=true` (routes to the host aggregate) — *superseded: current code targets `ovh.network`*
- `hw:cpu_policy=dedicated` (pinned) — *superseded: dropped in current code*
- `hw:cpu_thread_policy=require` — *superseded: dropped in current code*
- **`hw:vif_multiqueue_enabled=true`** ← load-bearing: the benchmark proved multiqueue is what lets the amphora guest CPU (not the hypervisor datapath) be the bottleneck. **Every amphora flavor must carry this.** See [benchmark](octavia-sizing-benchmark.md). — *still present in current code ✓*

> **⚠️ Stale vs current code (code-verified 2026-06-10):** current irobox master (`hieradata/fleet-infra/octavia_post_setup_vars.yaml`) has the amphora flavors carrying **ONLY** `aggregate_instance_extra_specs:ovh.network: "true"` (migrated off `ovh.b3-milan`) + `hw:vif_multiqueue_enabled: "true"` — **no `hw:cpu_policy=dedicated`, no `hw:cpu_thread_policy` anymore**. The landing aggregate `ovh.network` carries `flags: { pinning_enabled: false, qcow2_enabled: true }` (`hieradata/fleet-infra/compute/compute-vm-hosts-trunk_vars.yaml:153-159` — the only `pinning_enabled: false` in the repo). S/M/L sizes in the table above are unchanged.

> **🔁 Re-corrected vs [NSQ-006](../open-questions.md) (2026-06-10 Marc, "nach Code-Vorgabe" — code-verified 2026-06-10):** the **amphora aggregate runs CPU-pinning OFF**. Current irobox master migrated the flavors to the `ovh.network` aggregate (`pinning_enabled: false`) and dropped `hw:cpu_policy=dedicated` + `hw:cpu_thread_policy` — the code now implements the **original 2026-06-08 NSQ-006 sub-decision (pinning OFF)**. The 2026-06-09 ON-correction (previously carried by this note, based on the Confluence-derived specs above) is **superseded**. Multiqueue stays mandatory; V1-no-over-commit unchanged. **Verify with Damien:** confirm the flavor migration was deliberate remediation. See [NSQ-006 re-corrected note](../open-questions.md) + [`../decisions.md`](../decisions/index.md) 2026-06-10 re-correction entry.

---

## 13. SNC hardening compliance matrix (C1–C21)

> **Source:** "Octavia Amphora Hardening" (pageId 967395318) — the controls matrix prepared for the **SNC audit**. State after remediation branch `feat/amphora-iptables-sg` commit `e5b442f57`.
> **Layer A** = Neutron Security Group / hypervisor. **Layer B** = in-guest netfilter (nftables/iptables in the amphora).
>
> **This matrix is the concrete scoping input for [NSQ-025](../open-questions.md) (SNC M3 first-qualification).** The **C15–C20 GAPs** are ready-made M3 threat-model / ANSSI sub-tasks. **Demo-minint as-built — not yet ANSSI-validated.**

| # | Objective | Layer | State | Action | Severity |
|---|---|---|---|---|---|
| C1 | Default-deny mgmt plane (SG `delete_default_rules=true`) | A | OK | monitor SG drift | Low |
| C2 | Source-restricted REST ingress 9443 ← controller /32 | A+B | OK | — | — |
| C3 | Restricted ICMP supervision ← controllers /32 | A+B | OK | — | — |
| C4 | SSH disabled by default (`amp_ssh_enabled:false`) | A+B | OK | keep off outside debug | Low |
| C5 | Scoped heartbeat egress UDP 5555 → HM VIP /32 | A+B | OK | — | — |
| C6 | Scoped metadata egress 80/443 → 169.254.169.254/32 | A+B | OK | — | — |
| C7 | Scoped log egress 5140/5141 → forwarder /32 | A+B | OK | — | — |
| C8 | No outbound DNS (CP reached by IP) | A+B | OK | — | — |
| C9 | Gateway-less mgmt subnet (`no_gateway=true`) | A | OK | — | — |
| C10 | CP segmentation (CiliumNetworkPolicy fromCIDR/toCIDR lb-mgmt) | A | OK | — | — |
| C11 | In-guest mgmt-plane defense (amphora-mgmt-firewall, enforce-by-default) | B | OK (validate on real image) | real-image test → C16 · **impl on branch `feat/amphora-iptables-sg` — ⚠️ NOT yet merged to `2025.2`** (verified 2026-06-23; nftables rewrite + Py3 port, base `a90f9f41` 06-11) | High until validation + merge |
| C12 | Anti-lockout in-guest fw (9443 + heartbeat always permitted, fail→ACCEPT) | B | OK | — | — |
| C13 | Idempotent in-guest rules (`iptables-restore` no `--noflush`) | B | OK | — | — |
| C14 | Independence from Octavia upgrades (standalone image element) | B | OK | — | — |
| **C15** | In-guest data-plane (VIP) defense — nftables policy drop but **SR-IOV only**; OVH uses virtio → **inert** | B | **GAP** | scope in-guest VIP firewall for non-SR-IOV | Medium |
| **C16** | Real-image validation (build + boot + non-lockout + idempotence) | B | **GAP** | build amphora + validate E2E | **High** |
| **C17** | Mgmt ingress rate-limiting (anti brute-force/flood on 9443/ICMP) | B | **GAP** | add limit/hashlimit | Medium |
| C18 | VIP egress hardening | A | PARTIAL | strengthen VIP-port SG | Medium |
| C19 | Reduce single dependency on Neutron (defense-in-depth) | A+B | PARTIAL | mgmt covered (C11); VIP single-layer (C15) | Medium |
| **C20** | SG drift detection (TF/Neutron reconciliation) | A | **GAP** | set up drift monitoring | Medium |
| **C21** *(new 2026-06-10)* | HAProxy MAC confinement — AppArmor profile `usr.sbin.haproxy` (defense-in-depth beyond netfilter) | B | ✅ **MERGED to `2025.2`** (PR #11 06-12 + PR #14 `CAP_KILL` 06-16, verified 2026-06-23) | confirm enforce-mode on a real built image | — |

**The 5 open GAPs → candidate M3 SNC sub-tasks:**
- **C16 (High):** real-image E2E validation — build the amphora, boot it, prove non-lockout + idempotence. This also de-risks C11.
- **C15 (Medium):** the in-guest VIP firewall only works on SR-IOV; OVH runs virtio → the policy is inert. Scope a virtio-compatible in-guest data-plane defense.
- **C17 (Medium):** add rate-limiting (`limit`/`hashlimit`) on mgmt ingress (9443/ICMP) against brute-force/flood.
- **C20 (Medium):** TF↔Neutron SG drift detection/reconciliation.
- **C18/C19 (PARTIAL):** strengthen VIP-port SG egress; close the single-layer VIP dependency once C15 lands.

**📌 Image-hardening landed 2026-06-11 (update):** [PR #12](https://stash.ovh.net/projects/GOR/repos/octavia/pull-requests/12) **merged** — amphora image with **CIS separate-filesystem layout** (MBR+LVM, Debian 13; GPT/UEFI failed with the stock bootloader) · [PR #13](https://stash.ovh.net/projects/GOR/repos/octavia/pull-requests/13) **merged** — `/dev/shm` tmpfs `nodev,nosuid,noexec`. Companion Confluence page ["Octavia Amphora image partitioning"](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=967401703) (v4, 2026-06-11) compares vs the SNC-BMPOD layout — amphora is partly STRICTER (`/home` noexec, `/dev/shm`); **CIS *rules* are not applied yet** (planned `amphora-cis-hardening` element = next step); **path to full SNC parity = build the amphora as a `cloud-images-builder` target** (reuse `block-device-efi-bmpod-snc` + `bootloader-bmpod`) instead of octavia's diskimage-create → feeds NSQ-007. PR #9 (mgmt-firewall) rebased/active 2026-06-11; PR #11 (AppArmor) unchanged.

**📌 In-flight SNC-hardening PRs (Damien Rannou, GOR repos — observed 2026-06-10):**
- [`octavia` PR #9](https://stash.ovh.net/projects/GOR/repos/octavia/pull-requests/9/overview) — `amphora-mgmt-firewall` DIB element (default-deny in-guest mgmt firewall, `octavia-mgmt-firewall.sh`, SSH driven by `amp_ssh_enabled`) = the **C11 (+ C4/C12/C13)** implementation.
- [`octavia` PR #11](https://stash.ovh.net/projects/GOR/repos/octavia/pull-requests/11/diff) — `amphora-apparmor` element (HAProxy AppArmor profile) = new **C21**.
- [`ironic-python-agent` PR #21](https://stash.ovh.net/projects/GOR/repos/ironic-python-agent/pull-requests/21/diff) — withholds BM **rescue** credentials until the node's port is switched off the mgmt network (link-flap + control-plane-unreachable). **Ironic/BM-provisioning hardening** — relevant to CB + Object-Storage BM bring-up (Nova→Ironic), *not* amphora-specific; tracked here for the SNC-hardening trail.

**📌 Merge-status verified against the `octavia` clone — 2026-06-23 (`origin/2025.2` HEAD = PR #14, 06-16):**
- ✅ **Merged to `2025.2`:** PR #8 `stats_prometheus` driver (06-09) · PR #12 CIS partitions (06-11) · PR #13 `/dev/shm` tmpfs (06-11) · **PR #11 AppArmor + PR #14 CAP_KILL** (06-12 / 06-16, C21).
- ⚠️ **NOT merged (feature branches):** `feat/amphora-iptables-sg` (the C11 mgmt-firewall / nftables — no merged "PR #9" on `2025.2`) · **`fix/amphora-rsyslog-imuxsock-double-load`** (06-17 — *newest, post-doc-date*: stops imuxsock double-load in the amphora rsyslog socket conf). Both are candidates to merge before the Beta image freeze.

---

## 14. Implications for OPCP / Network Service

- **The CP HA story is K8s-native, not VM-native** — [NSQ-014](../open-questions.md) should be re-framed around the 5-deployment model + Cilium-LB health-manager, not "1× vs 3× HA VM".
- **Flavors confirm S/M/L** — but the benchmark says L caps at ~90k req/s. A throughput tier beyond V1 (8/16 vCPU) is a real post-V1 question. See [NSQ-002 note](../open-questions.md).
- **SNC M3 has a concrete punch-list** — the 5 C15–C20 GAPs are the threat-model/ANSSI work-items, not abstractions.
- **Amphora pinning = OFF (NSQ-006 re-corrected 2026-06-10, code-verified)** — current irobox master has the amphora flavors on the `ovh.network` aggregate (`pinning_enabled: false`) **without** `hw:cpu_policy=dedicated`; the code implements the original 2026-06-08 pinning-OFF sub-decision, superseding the 2026-06-09 ON-correction (which was based on the Confluence-era specs in §12, now annotated stale). Tenant-VM aggregate stays ON; V1-no-over-commit unchanged. Benchmark ceilings need re-validation on unpinned amphorae (see [benchmark caveat](octavia-sizing-benchmark.md)).
- **PostgreSQL + CloudNativePG + RabbitMQ-operator** are the infra deps to budget — Octavia is the first OPCP service to need this exact stack.

## 15. Discrepancies flagged (do NOT silently resolve) `[verify]`

| # | Conflict | Page 1 / 5 says | Page 4 (debug) / other says | Likely reconciliation |
|---|---|---|---|---|
| D1 | **mgmt CIDR** | `198.18.114.0/23` (lb-mgmt-subnet) | `172.16.0.0/24` (amphora `lb_network_ip`); Cilium health-manager LB pool `172.16.0.3–172.16.0.9` | **Likely two distinct ranges** — the amphora mgmt subnet (`198.18.114.0/23`) vs the Cilium LoadBalancer IP pool for the health-manager Service (`172.16.0.0/24`). But the doc text conflicts on which range the amphora `lb_network_ip` sits in. **Verify with Damien.** |
| D2 | **Octavia CA algorithm** | Page 1: **ECDSA P384**; Page 5: **RSA 4096** | — | One page is stale. **Verify against the actual `hashicorp/tls` TF resource + the deployed `octavia-certs` secret** (`openssl x509 -in ca_cert.pem -text`). |
| D3 | **mgmt alloc pool start** | Page 1: `.21`; Page 5: `.11` | — | Minor — verify the actual `lb-mgmt-subnet` allocation pool in `root-control-plane`. |
| D4 | **Provenance** | Benchmark + flavor numbers are from **demo-minint** (BM-POD), not prod | — | Label all values "demo-minint as-built" when carried into planning. |

---

## 16. Cross-references

- [`octavia-from-fdd.md`](octavia-from-fdd.md) — the FDD *spec* this implements; companion to this *implementation* doc.
- [`octavia-sizing-benchmark.md`](octavia-sizing-benchmark.md) — Damien's 2026-06-05 throughput benchmark (feeds §12 + NSQ-002/020).
- [`../runbooks/octavia-debugging.md`](../runbooks/octavia-debugging.md) — production debugging runbook (the ops view of these flows).
- [`code-survey-2026-06-08.md`](code-survey-2026-06-08.md) — the 4-week code survey (where the survey found *no* Barbican / mgmt-network refs — this doc fills that gap).
- [`code-have-vs-missing-2026-06-08.md`](code-have-vs-missing-2026-06-08.md) — gap analysis for KW24 estimation.
- [`../open-questions.md`](../open-questions.md) — NSQ-001/002/005/014/019/025 all reference this doc.
- Source: Confluence space SOV pageIds 963465107 (Control Plane Interactions) + 967395318 (Hardening) + 963465109 (Downstream Changes), fetched 2026-06-09.
