---
id: object-storage-on-cloud-store/architecture-ceph-rgw-osd-spec
type: reference
diataxis: reference
title: "Ceph RGW — Production OSD Spec (OSQ-31)"
owner: sov-copilot
status: draft
publish_target: git
product: cloudstore
---

# Ceph RGW — Production OSD Spec (OSQ-31)

> **Answers OSQ-31 — "OSD Spec, tighten for production."** The package ships an
> intentionally-loose OSD spec (takes any free disk — valid for the VM test setup). This doc specifies the
> **production-ready** OSD spec (device class · min-size guard · data/DB disk layout · encryption) and the
> concrete gaps to close before any staging / production Ceph deploy.
>
> **Status: DRAFT — proposed 2026-07-16, grounded in the actual package code, pending Boris + Jan review +
> real-hardware confirmation.** Technical owners: **Boris Behrens · Jan Stuhlmann** (per OSQ-31). Everything
> below marked ⚠️ needs a fact from the delivered hardware or a policy call before it's authoritative.

**Source of truth for "current state":** [`cloudstore-service-object-storage`](https://stash.ovh.net/projects/CLOUDSTORE/repos/cloudstore-service-object-storage/browse)
@ `main` (cloned + read 2026-07-16), Ceph role at
`terraform/controlplane/modules/ceph/…/roles/ceph/`. Ceph release = **Squid `v19.2.3`** (role default).

---

## 1. How the OSD spec is applied today (verified from code)

1. `roles/ceph/tasks/osd.yaml` renders **one** Jinja template — the one named by the Terraform variable
   **`ceph_osd_spec_file`** — to `/etc/ceph/spec_files/osd-spec.yml` on the bootstrap MON, then runs
   `ceph orch apply -i /etc/ceph/spec_files/osd-spec.yml`.
2. `ceph_osd_spec_file` is a **TF variable** (`terraform/controlplane/variables.tf`) with default
   **`osd-flash-hdd-spec.yml.j2`** — i.e. the **block-storage** hybrid spec, *not* the object one. An Object
   Storage deploy must override it to the object spec **and** set `ceph_object_storage = true`.
3. The device-class → CRUSH-rule → pool-placement chain is wired in `crush.yaml` + `rgw-pools.yaml`
   (only when `ceph_object_storage: true`):
   - `crush.yaml` creates `replicated_hdd` (class `hdd`) and `replicated_ssd` (class `ssd`) rules —
     **but only if those device classes already exist** on the cluster.
   - `rgw-pools.yaml` moves pools ending in `.data` / `.ec` → **`replicated_hdd`**, and **all other** RGW
     pools (index / meta / log / control) → **`replicated_ssd`**.

**Design intent (correct):** bucket **data** on HDD; bucket **index + metadata** (OMAP-heavy) on flash. The
OSD spec is what has to make that split real.

### The four shipped OSD specs

| Template | Role | `encrypted` | Shape |
|---|---|---|---|
| `osd-test-single-spec.yml.j2` | **the loose one (OSQ-31)** | `false` | `data_devices: {all: true}`, `host_pattern:'*'` — grabs **any** disk on **any** host |
| `osd-flash-only-spec.yml.j2` | all-flash | `false` | flash data OSDs ≥1TB |
| `osd-flash-hdd-spec.yml.j2` | **block** hybrid *(TF default)* | `false` | 2 flash data OSDs + HDD OSDs w/ 512 GiB `block.db`, `db_slots: 6` |
| `osd-object-flash-hdd-spec.yml.j2` | **object** hybrid *(the prod candidate)* | `false` | 1 flash OSD (≤1TB) + HDD OSDs w/ 860 GiB `block.db`, `db_slots: 12`, DB on 13–15TB NVMe |

---

## 2. The problem — the loose spec

```yaml
# osd-test-single-spec.yml.j2  — CURRENT loose spec
service_type: osd
service_id: osd_1_ssd
placement:
  host_pattern: '*'          # every host, incl. OOB / mon-only
spec:
  data_devices:
    all: true                # ⚠️ ANY free block device — incl. the OS/boot disk
  encrypted: false           # ⚠️ no at-rest encryption
```

On test VMs (one clean data disk per node) this is harmless. On real hardware it is not: `all: true` will
consume the **boot device** the moment it looks free, gives **no device-class control** (so the
`replicated_ssd`/`replicated_hdd` rules can't place RGW pools deterministically), offloads **no `block.db`**
to flash (RocksDB/OMAP lands on slow HDD — bad for RGW), and leaves data **unencrypted at rest**.

---

## 3. Gap analysis — object candidate → production

The object candidate (`osd-object-flash-hdd-spec.yml.j2`) is fundamentally the **right shape** (HDD data +
NVMe `block.db` offload + a flash OSD for the metadata pools). "Tightening for production" = (a) make OS
deploys actually select it, and (b) close these gaps:

| # | Gap | Severity | Fix |
|---|---|---|---|
| **G1** | `encrypted: false` on every OSD | 🔴 High | `encrypted: true` (LUKS/dmcrypt). **Immutable after OSD creation** — must be right *before* first prod OSD. ⚠️ confirm SNC/SecNumCloud mandate + key custody (cephadm keeps dmcrypt keys in the MON config-key store by default → does SNC require OKMS-backed escrow?). |
| **G2** | **No explicit `crush_device_class`.** Relies on Ceph auto-detect. A 13–15TB flash is almost certainly **NVMe → auto-class `nvme`**, and even the ≤1TB index flash may be NVMe. The `replicated_ssd` rule targets class **`ssd`** → it would match **zero OSDs** → RGW **index/meta pools strand** (PGs `unknown`/`inactive`). | 🔴 High | Pin `crush_device_class: ssd` on the flash/index OSD and `crush_device_class: hdd` on the data OSDs. (Alternatively retarget the `replicated_ssd` rule at the real class — but pinning in the spec is the robust fix and keeps `rgw-pools.yaml` unchanged.) |
| **G3** | **Boot-disk safety.** `osd_1_ssd` = `rotational:0, size: :1TB` can match a small SATA boot SSD; the loose spec's `all:true` matches it outright. | 🔴 High | Add a **size floor** to the flash-OSD band (below) and/or a model/path denylist. ⚠️ confirm the boot-device type on the delivered HW. |
| **G4** | `db_slots: 12` + `block_db_size: 860 GiB` are hard-coded to a **12-HDD / 13–15TB-NVMe** node. If a node has **> `db_slots` HDDs**, the extra HDD OSDs silently fall back to **colocated `block.db` on the slow HDD**. | 🟡 Med | Set `db_slots` **≥ HDD count per node**. ⚠️ confirm HDD count + NVMe size from real HW. Sanity: `12 × 860 GiB ≈ 10.1 TiB` fits a ~11.8 TiB (13 TB) NVMe with ~15% headroom — tight; validate. |
| **G5** | No min-size floor on HDD `data_devices` (only `rotational: 1`). | 🟡 Low | Add `size: '<floor>:'` — explicit intent + guards against small/leftover spinners. (OSQ-31 names "min size" specifically.) |
| **G6** | `placement: host_pattern: '*'` → **all** hosts, incl. the **OOB** node and any mon/mgr-only host. | 🟡 Med | Target only OSD-role hosts via a **label** (`ceph-osd`) or the `osd` inventory group. The OOB node must never get OSDs. |
| **G7** | `block.db` = 860 GiB/OSD rationale vs actual HDD size. | 🟢 verify | 860 GiB ≈ **4–5 %** of a ~18–20 TB HDD — appropriate for OMAP-heavy RGW (vs ~1 % for pure RBD). ⚠️ re-check once HDD size is known; align to RocksDB level boundaries. |

---

## 4. Proposed production OSD spec

> ⚠️ **Parametric.** The `size:` bands and `db_slots` below encode a *specific* disk topology (see §5). Confirm
> against the delivered hardware before applying — the **structure** is the deliverable, the **numbers** need HW.

```yaml
# osd-object-flash-hdd-spec.yml — PRODUCTION (proposed, OSQ-31) · Ceph Squid v19.2.x
# apply: ceph orch apply -i /etc/ceph/spec_files/osd-spec.yml
---
# (1) Flash OSDs — carry the RGW metadata pools (index / meta / log / control)
service_type: osd
service_id: osd_object_ssd
placement:
  label: ceph-osd                 # G6 — was host_pattern:'*'
crush_device_class: ssd           # G2 — pin so replicated_ssd matches even if the device is NVMe
spec:
  data_devices:
    rotational: 0
    size: '400GB:1TB'             # G3/G5 — floor clears the boot SSD; ceiling excludes the DB NVMe
    limit: 1
  filter_logic: AND
  encrypted: true                 # G1
  objectstore: bluestore
---
# (2) HDD data OSDs — the S3 bucket-data pools (.data / .ec); block.db offloaded to the NVMe
service_type: osd
service_id: osd_object_hdd
placement:
  label: ceph-osd
crush_device_class: hdd           # G2
spec:
  data_devices:
    rotational: 1
    size: '3TB:'                  # G5 — min-size floor
  db_devices:
    rotational: 0
    size: '3TB:'                  # selects ONLY the big DB-NVMe, not the ≤1TB index flash
  db_slots: 12                    # G4 — MUST be >= HDD count per node ⚠️ confirm
  block_db_size: 923417968640     # 860 GiB/OSD (~4-5% of HDD; RGW OMAP-heavy) ⚠️ confirm vs HDD size
  filter_logic: AND
  encrypted: true                 # G1
  objectstore: bluestore
```

**Why the three size bands don't overlap** (the whole layout hinges on this):

| Device role | Filter | Becomes |
|---|---|---|
| HDD data | `rotational:1`, `≥3TB` | `osd_object_hdd` data OSD (class `hdd`) |
| Index/meta flash | `rotational:0`, `400GB–1TB`, `limit:1` | `osd_object_ssd` data OSD (class `ssd`) |
| `block.db` NVMe | `rotational:0`, `≥3TB` | `db_devices` for the HDD OSDs (not an OSD itself) |

Boot device is excluded **iff** it is < 400 GB or otherwise outside the 400 GB–1 TB flash band. ⚠️ **If the
boot disk is a ≥400 GB SATA SSD it will be caught** — confirm the boot-device model and add an explicit
denylist (`data_devices: model:` exclusion or a `paths:` allowlist) if so.

---

## 5. Hardware facts to confirm (the parametrics) ⚠️

The known product-brief spec: **256 GB RAM · 25 GbE · ≥5 data drives + metadata SSD(s) · min 4 nodes (1
reserved) · 80 % capacity cap** ([README](../README.md), SOV-854). To lock
the spec above, Boris/Jan confirm:

- [ ] **HDD count per node** → sets `db_slots` (must be ≥ this).
- [ ] **HDD size** → validates `block_db_size` (target ~4–5 %) and the `3TB:` floor.
- [ ] **DB-NVMe size + count** → validates `db_slots × block_db_size` fits with headroom.
- [ ] **Index-flash device** — is it present, is it ≤1TB, is it `ssd` or `nvme` class?
- [ ] **Boot device** — model/size, so we know if the 400 GB floor clears it.
- [ ] **Encryption policy** — is OSD-level dmcrypt an SNC requirement, and does key custody need OKMS?

---

## 6. Rollout notes

- **Encryption is create-time and immutable.** Set `encrypted: true` *before* the first production OSD is
  created; converting an existing unencrypted OSD means drain → destroy → re-create.
- **`ceph orch apply` is declarative and additive** — it governs *new* OSDs; it does not re-provision
  existing ones. On a cluster stood up with the loose `all:true` service, first
  `ceph orch ls --service-type osd` and **remove/unmanage the old service** (`osd_1_ssd`) before applying the
  named prod spec, or the two specs fight over devices.
- **Deployment wiring:** OS deploys must set `ceph_osd_spec_file = "osd-object-flash-hdd-spec.yml.j2"` **and**
  `ceph_object_storage = true` (else the `crush`/`rgw-pools` tasks are skipped and the TF default block spec
  is used).
- **Verify after apply:** `ceph osd tree` (classes correct?), `ceph osd crush rule ls` (both rules exist?),
  `ceph osd pool ls detail` (`.data`→`replicated_hdd`, index/meta→`replicated_ssd`?), `ceph osd metadata`
  (`bluefs_db_*` on NVMe?, `encrypted=1`?).

---

## 7. Open sub-questions this raises

- **Device-class of the index flash** — if it is NVMe, is pinning it to class `ssd` (so `replicated_ssd`
  matches) the right call, or should the CRUSH rule target `nvme`? (Feeds back to `crush.yaml`.)
- **dmcrypt key custody** — MON config-key store vs OKMS escrow for SNC. Likely a new SOV / SNC-hardening item.
- **L2 admin vs L3 user RGW share one cluster** (OSQ-32) — both RGW zones sit on the
  same OSDs/pools; nothing here changes that, but the metadata-pool placement above is what both zones rely on.

---

## 8. Cross-references

- OSQ-31 — the question this answers · OSQ-32 — L2/L3 RGW purpose.
- [`SOV-854`](../jira/SOV-854-ms1-ceph-rgw.md) — Ceph + RGW development (OSD layout in scope).
- [`architecture/README.md`](README.md) — architecture index · adjacent planned `ceph-rgw-sizing.md` (cluster
  sizing / capacity math — distinct from this OSD-layout spec).
- [`oss-cp-components.md`](oss-cp-components.md) — where Ceph OSD/MON/MGR + RGW sit in the control plane.
- [Project `decisions.md`](../decisions.md) — CephADM + Ansible, no Rook (2026-06-09).
- Upstream: [Ceph — Advanced OSD Service Specs](https://docs.ceph.com/en/squid/cephadm/services/osd/#advanced-osd-service-specifications).
- Package code: `cloudstore-service-object-storage` @ `terraform/controlplane/modules/ceph/…/roles/ceph/`
  (templates `osd-*-spec.yml.j2`, tasks `osd.yaml` · `crush.yaml` · `rgw-pools.yaml`).
