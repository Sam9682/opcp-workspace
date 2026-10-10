# Object Storage on CloudStore — Action Plan

> Living roadmap from kickoff (2026-05-21) to a shippable OS CloudStore Package. Phase 0 (Discovery) is where we are. Each phase lists exit criteria; `[blocked: OSQ-NN]` marks dependence on an open question.

---

## Phase 0 — Discovery & framing *(now)*

- [x] Ingest the Input drop (Product Brief, LVL2-18375, GSSNC-411 HLD stub) → digest in [README](README.md).
- [x] Seed [`open-questions.md`](open-questions.md) (OSQ-01…14).
- [ ] **Marc runs through OSQ-01…14** — answers fold back into the docs.
- [ ] Obtain the missing material: **GSSNC-411 HLD content**, the **SNC Object-Storage Product Note**, the **[Product Brief / Confluence OPCP–Object Storage page](https://confluence.ovhcloud.tools/display/CPO/OPCP+-+Object+Storage)**, the **[OVH Local-Zone limitations KB (KB0065306)](https://help.ovhcloud.com/csm/en-public-cloud-storage-s3-local-zone-limitations?id=kb_article_view&sysparm_article=KB0065306)** + compliancy KB (JS-rendered — capture manually).
- [ ] **Access-control clarification meeting** (Florent / Vincent / Ibrahim) → resolves OSQ-02. *The pacing item for the whole project.*

**Exit:** OSQ-01 (provisioning boundary) + OSQ-02 (access control) answered; HLD + Product Note in hand.

## Phase 1 — Architecture proposal `[blocked: OSQ-01, OSQ-02, OSQ-04]`

- [ ] Architecture doc in [`architecture/`](architecture/README.md): the no-operator, package-via-OpenStack-API model; the OPCP-Core-node-prep ↔ package-cluster-bring-up boundary; component map; auth model; data flow; contrast with CB.
- [ ] Decide the OpenStack/Ceph API surface the package uses (OSQ-04).

**Exit:** architecture proposal reviewed by the storage squad + Vincent.

## Phase 2 — Jira structure `[blocked: Phase 1]`

- [ ] Build the LVL2-18375 → `[MSx][Subsystem]` work-block tree (see [`jira/README.md`](jira/README.md)).
- [ ] Fold GSSNC-411 + any existing child tickets in.

**Exit:** work-block Epics defined with scope; ready for estimation.

## Phase 3 — Estimation & governance `[blocked: Phase 2]`

- [ ] Per-work-block estimation (reuse the CB `M*-effort-estimation` pattern).
- [ ] Stand up [`tracking/`](tracking/README.md) for real (dependency-graph + blockers + weekly-status + demo-confidence RAG).

**Exit:** baselined estimate + a confidence RAG against the July target.

## Phase 4 — Build *(out of scope to plan in detail yet)*

---

## Immediate next actions — top 10 *(updated 2026-05-27)*

### Marc

- [ ] **Schedule the OSQ-02 access-control meeting** (Florent + Vincent + Ibrahim) — pacing item; Phase 1 architecture doc cannot start without it
- [ ] **Confirm BL capacity timeline with Vincent** (OSQ-03) — BL full until June for SNC; this is the schedule driver for the July target
- [ ] **Book the operator-reuse architecture session** with storage squad (OSQ-15) — pure-TF vs reuse OPCP Infra Operator; day-2 lifecycle is the deciding factor
- [ ] **Answer OSQ-06 / OSQ-07 / OSQ-08** — proxies in V1 or M3? KMS (OKMS) in V1 or later? Consumption/billing in V1 or later? These shape the M2 vs M3 scope cut
- [ ] **Flag Storage Squad load to CB** — Stephan Hohn + Boris Behrens are on both SOV-256 (CB Block Storage, In Progress) and OS; parallel demand on the same people is a risk

### Eddy

- [ ] **Pull GSSNC-411 HLD from Jira** (attachments or linked Confluence page) → drop in `Input/` → `/distill`
- [ ] **Pull SNC Object-Storage Product Note** from Florent / Vincent / SNC Cloud Platform team → drop in `Input/` → `/distill` — defines "what's manual in SNC today", the reuse base
- [ ] **Capture KB0065306 manually** — open `https://help.ovhcloud.com/csm/en-public-cloud-storage-s3-local-zone-limitations?id=kb_article_view&sysparm_article=KB0065306` in browser, copy the full feature/limitation table into a `.md` file → `Input/` → `/distill` — this defines the V1 acceptance list
- [ ] **Draft `architecture/ceph-rgw-sizing.md`** — brief is in hand (4-node min, replication vs EC 3:2, 256 GB RAM / 25 GbE, ≥5 data drives + SSDs, 80% cap); not blocked on any open question; can start now
- [ ] **Stand up first weekly-status in `tracking/`** — open with July-target confidence RAG (currently 🔴: date slipped once, OSQ-02 + OSQ-03 unresolved); use the CB weekly-status format
