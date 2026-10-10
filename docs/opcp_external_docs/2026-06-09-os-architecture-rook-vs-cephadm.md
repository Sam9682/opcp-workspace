# 2026-06-09 — OS Architecture brainstorm: CephADM (FINAL) + the OSS-CP shape

**Date:** 2026-06-09 (the scheduled OS architecture brainstorm, Tue 15:00)
**Type:** design call / architecture brainstorm
**Source:** diarised recording transcript (`Input/_to_process/2026-06-09-os-rook-vs-cephadm-ossp-cp-recording.txt`) — **heavily ASR-garbled**, normalised on distill.

> ✅ **OFFICIAL SOURCE OF RECORD:** Eddy Medina's Confluence summary **"OS MN W24 — 2026-06-09 Architecture Brainstorm"** (pageId **963474590**, space **SOV**) is the authoritative record of this meeting. This doc has been **reconciled against it** (2026-06-09): attendees confirmed, the Rook→CephADM decision promoted from draft-lean to **FINAL**, own-K3S marked **deferred to the June-10 M3 Design Session**, and the auth model + SOV-916 + Keycloak-tunnel blocker added.

> 🧭 **Cascaded to [`decisions.md`](../decisions.md)** (2026-06-09): three ADR entries — CephADM+Ansible (no Rook) FINAL · own-K3S planning lean (cross-service choice deferred to 2026-06-10 M3 session) · OKMS ≥3-node resilience gate.

---

## Attendees *(confirmed — Eddy Medina's official summary)*

| Person | Role / topic in this meeting |
|---|---|
| **Zafar Akhtar** | SRE — VM allocation + K3S bring-up; starting now. |
| **Ibrahim Takouna** | Keystone operator / Apache-OIDC federation; "we already have the TF definition for Keystone"; federation-operator test deploy (SOV-916). |
| **Nathan M** *(SNC)* | SNC CephADM + Ansible precedent; the decisive K3S-doesn't-scale-for-Ceph input; SNC terraform-modules. |
| **Boris Behrens** | Ceph / CephADM / operational-resilience; OKMS-loss warning; RGW→Keystone token-validation pattern; host-storage TF evaluation. |
| **Eddy Medina** | Meeting lead + author of the official Confluence summary. *(= the "Eduardo Medina" rendered by the ASR transcript.)* |
| **Marc Dittmann** | PM / driver — CB-vs-OS infra-API contrast; "plan with our own K3S, don't block on the enabler cluster." |

> *Note: the ASR transcript rendered Eddy Medina as "Eduardo Medina" and the diarised SPEAKER_NN labels were guesses. Per Eddy's official summary the confirmed attendee list is the six people above.*

---

## Decisions made

- **✅ FINAL — Ceph deploy = CephADM + Ansible, NO Rook.** SNC (Nathan) runs **CephADM + Ansible** with no extra K8s layer on the Ceph nodes; K3S is used only for *small* edge clusters (≤5 nodes). Running Ceph at scale on K3S "shifts the complexity of maintaining a Ceph cluster to maintaining a real Kubernetes cluster." Rook adds operational overhead and is **rejected**. CephADM = no Kubernetes on the storage nodes themselves; Keystone lives in the service-CP K3S. **Eddy marked the "Final Rook vs CephADM decision" item DONE in his summary.** → **closes OSQ-15 + the Ceph-deploy axis of OSQ-04**; recorded in [`decisions.md`](../decisions.md).
- **🟡 PLANNING LEAN (NOT final) — own-K3S service control plane per package.** Each service instance gets its OWN K3S hosting Keystone + federation operator + Ceph orchestration + panel/LZM + proxies; CloudStore-UI → TF-runner-pod deploy. The current lean is own-K3S (avoid external deps). **BUT the own-K3S-vs-shared-"Enabler K3S cluster" choice is a CROSS-SERVICE architecture decision DEFERRED to the M3 Design Session on June 10 (2-week deadline). Do NOT block OS work on it.** → tracked as **OSQ-21** (new); recorded in [`decisions.md`](../decisions.md) as a planning stance, not a final decision.
- **Auth & IAM model (already running in SNC):** **ONE Keycloak, ONE Keystone, ONE Apache per account/realm** for JWT validation. The OPCP federation operator (Apache config, network policy, HTTP routes) is in testing — Ibrahim targeting a **test-env deploy this week (SOV-916)**. **Keystone needs its own DB when standalone** — the irobox/SNC Terraform modules cover this and are ready to reuse. → refines **OSQ-02**.
- **CB-vs-OS infra contrast confirmed.** CB uses the **OPCP Infra API** into opcp-core (special privileges) to orchestrate the OpenStack Keystone operator. **OS is standalone with no special privileges** → its Keystone operator runs **inside the service package** itself. *(Confirms the OSQ-15 / 2026-05-27 "VCF way" direction.)*
- **OKMS resilience gate.** For OKMS-encrypted objects you need a **failure-resistant K8S (≥3-node K3S)** — if the K3S hosting OKMS fails while encryption is enabled, the encrypted data is **permanently lost**. The **bare-minimum (non-SNC)** footprint = just **Keystone + one nginx proxy**. Enforce minimum-resilience requirements in `cloudstore.yaml` so the service **blocks OKMS enablement** below the bar (checkbox gating). → recorded in [`decisions.md`](../decisions.md).
- **Next step agreed: start now.** Zafar is starting VM allocation + K3S now; Boris + Zafar bring up K3S on the demo env via the existing Terraform/Ansible bricks. Ibrahim/Nathan to share the Keystone TF + host-storage TF + SNC terraform-module links.

> **🚨 KEY DEPENDENCY / BLOCKER:** auth **cannot be end-to-end tested until the public-cloud test env has a tunnel to Keycloak.** Must resolve before E2E auth testing.

> **⚠️ Ansible gap:** the Ansible role (node hardening, K3S init, Flux) is **NOT yet chained into the VM-provisioning Terraform module** — it is still manual after VM creation. Needs automation (action item #5, owner TBD).

> ✅ **ADR filed.** All three decisions are recorded in [`decisions.md`](../decisions.md) (cascaded 2026-06-09).

---

## Open questions raised / refined

- **OSQ-15** *(✅ CLOSED 2026-06-09)* — Cluster orchestration / Rook vs ceph-operator. **Resolved:** CephADM + Ansible, no Rook (Nathan/SNC precedent; Rook overhead rejected). Ceph stays off K8s; K3S hosts only the service control plane. → [decisions.md](../decisions.md).
- **OSQ-04** *(Ceph-deploy axis ✅ CLOSED 2026-06-09)* — Ceph deploy mechanism = **CephADM + Ansible** (SNC standard), no Rook. The host-provisioning part of OSQ-04 (Nova BM flavor) was already decided 2026-05-21 and is unaffected. → [decisions.md](../decisions.md).
- **OSQ-02** *(refined 2026-06-09)* — auth model confirmed: **ONE Keycloak, ONE Keystone, ONE Apache per account/realm** for JWT validation (already running in SNC). Standalone Keystone needs **its own DB** — covered by irobox/SNC TF modules. Federation operator in test deploy this week (SOV-916). RGW holds Keystone creds and asks Keystone to validate tokens — the standard local-zones / SNC pattern.
- **OSQ-21** *(NEW 2026-06-09)* — **own-K3S per package vs shared "Enabler K3S cluster."** Cross-service architecture decision, deferred to the **M3 Design Session 2026-06-10** (2-week deadline). Current lean = own-K3S. OS does NOT block on it. Owner = Architecture session / Marc.

---

## Action items

*(Owners + ordering per Eddy Medina's official summary.)*

| # | Action | Owner | By when |
|---|---|---|---|
| 1 | Deploy federation operator in test env | **Ibrahim** | this week (SOV-916) |
| 2 | Share Keystone TF links | **Ibrahim / Nathan** | next |
| 3 | Repo access for Eddy + Zafar (iRobox Terraform-module-reader) | **Ibrahim** | next |
| 4 | Evaluate host-storage TF (Bartosz & Stephan Hohn — BM node provisioning, LSCP config, VLAN tagging) | **Boris / Zafar** | next |
| 5 | Chain Ansible (node hardening, K3S init, Flux) into the VM-provisioning TF module — currently manual after VM creation | **TBD** | design |
| 6 | Start VM provisioning + K3S on demo env | **Boris / Zafar** | now / CW24 |
| 7 | Own-K3S-vs-Enabler decision (**OSQ-21**) | **M3 Design Session** | **2026-06-10** |
| 8 | Define minimum-resilience requirements in `cloudstore.yaml` for OKMS (≥3-node K3S gate) | **TBD** | design |
| 9 | Collect TF module links | **Ibrahim / Nathan** | next |
| 10 | Rook-vs-CephADM final decision | — | **✅ DONE** (CephADM + Ansible) |
| 11 | Zafar starting VM allocation + K3S | **Zafar** | now |

---

## Verbatim notes worth preserving

> **CB vs OS infra contrast (SPEAKER_00):** "In compute and block, we will use the infra API […] a special API into OPCP core to orchestrate the keystone operator of the OpenStack. […] Object storage of course it will be the object storage keystone — the operator also itself needs to run in the service package. […] the basic idea is that this object storage service is really standalone. It doesn't have any special privileges."

> **Keystone has one IdP per instance (SPEAKER_02):** "There is Apache in front of keystone, and that's an Apache instance, [that] is actually the one [that] will do the job." *(→ multiple Apache instances / one Keystone instance for the multi-tenant federation question.)*

> **Reuse the SNC Keystone TF (SPEAKER_02):** "We already have a Terraform definition for keystone deployment, so we can reuse it. […] the service control plane Terraform module will provision for you a keystone instance with the database. […] the question should be answered where this keystone will live — it will live in the cloud store control plane provisioned by the service itself."

> **Own K3S, don't wait for the enabler cluster (SPEAKER_00):** "I think we need to plan with our own. […] Even if we have a little bit of overhead in those service control planes, we need to do this. […] my standing: I don't want to wait for this and then we do X — because then we never do it. If it is not there in two weeks, we should not do it. For VMs I think this is achievable […] I would not make this dependency which can screw up our timings."

> **Pierre confirmed VMs are spawnable now (SPEAKER_01):** "We can launch VMs on a demo environment at this moment and get also IP address. So actually we could start rolling out a K3S via this Terraform."

> **TF-runner-pod provisioning vision (SPEAKER_01):** "You're currently logged in as a level 2 IT admin. You click 'I want to deploy this object storage' […] it spawns, it creates a namespace, it spawns a tf-podrunner whose only mission is to execute this Terraform module. […] You could also give it the credentials for the [service-CP] cluster, or for a third-party cluster."

> **Nathan's Rook / K3S-at-scale caution (SPEAKER_04):** "On SNC we use cephadm and we use Ansible to give directives to cephadm. […] we use K3S because we have small edge Kubernetes clusters that are five nodes max per cluster. […] If you want to go with K3S also for Ceph, I don't think it scales quite well. You would shift the complexity of maintaining a Ceph cluster to the complexity of maintaining a real Kubernetes cluster."

> **cephadm path → where does Keystone live (SPEAKER_03):** "When you use a cephadm package, you use the [built-in Ceph] orchestrator with it. […] then you do not need the Kubernetes cluster on the object-storage nodes itself, but then you need somewhere to put your Keystone instance, which will be the authentication endpoint. You put your keystone credentials in the RADOS gateway config and the RADOS gateway then asks the keystone […] we're using that everywhere in the local zones, [and] in the SNC thing."

> **OKMS-loss = permanent data loss (SPEAKER_03):** "We need a Kubernetes cluster that is failure resistant because we will put an OKMS there for the encryption of the objects. And if the OKMS fails […] all your data you put into the object is gone forever. […] If you want the bare minimum, I only need a Keystone and one nginx proxy. […] I would not allow a customer to [tick] 'encrypt all my objects with OKMS' without fulfilling the [resilience requirement]."

> **Gate it in cloudstore.yaml (SPEAKER_02):** "This requirement should be defined somewhere in the cloudstore.yaml file […] so you cannot provision the service without all this requirement checked." — "For something SNC-certified […] we need at least K3S with three minimum nodes."

> **The reusable bricks already exist (SPEAKER_04 → SPEAKER_00):** "We have a Terraform module called `host-storage` — done by Bartosz and Stephan Hohn — we use it standalone on SNC to spawn the instance. […] In `OpenStack-instance-V2` it's a quite simple module we use to spawn the virtual machines used as K3S machines. […] the provisioning of the K3S itself is not in there — it's just Ansible with the role `deploy-K3S`, `K3S-hardening`, `init-flux`."

> **Bus-factor flag (SPEAKER_00):** "Stephan Hohn has already ported [the Ansible roles] into iRobox for block storage. […] And then he's just sick, which is a nightmare." *(→ the reusable `host-storage` TF + Ansible roles the whole plan depends on were authored by Stephan Hohn, who is currently on sick leave — single-point-of-knowledge risk.)*

---

## ⚠️ Bus-factor / availability risk

The reusable bricks the start-now plan depends on — the **`host-storage` Terraform module** (authored by **Bartosz** + **Stephan Hohn / likely Stephan Hohn** [verify]) and the **Ansible roles** (`deploy-K3S` / `K3S-hardening` / `init-flux`, ported into iRobox by Stephan) — were authored largely by **Stephan Hohn, who is currently on sick leave**. The team explicitly noted this ("which is a nightmare"). **Single-point-of-knowledge risk** for the K3S/Ceph bring-up path — flag for Marc.

---

## Terms that could not be confidently decoded

- **SPEAKER_02 "one more thing says colombo"** [verify] — likely a name (a person) or a filler artefact; unresolved.
- **"Stephan Hohn" / "Stephan"** — the transcript says "Stephan Hohn"; mapped to **Stephan Hohn** [verify] per the brief, but the spelling differs.
- **Attendee names** generally — diarisation guesses, see the to-verify table above. Only Eduardo Medina + Zafar Akhtar were spoken explicitly.

---

## Cross-links

- [`decisions.md`](../decisions.md) — **3 ADR entries filed 2026-06-09** (CephADM+Ansible FINAL / own-K3S planning lean deferred to June-10 M3 / OKMS ≥3-node gate).
- **Official source of record:** Eddy Medina's Confluence summary *OS MN W24 — 2026-06-09 Architecture Brainstorm* (pageId **963474590**, space **SOV**).
- [`open-questions.md`](../open-questions.md) — OSQ-15 + OSQ-04 (✅ closed 2026-06-09) · OSQ-02 (refined) · OSQ-21 (new — own-K3S-vs-Enabler).
- [`README.md`](../README.md) — project dashboard (Current direction).
- Architecture index: [`architecture/README.md`](../architecture/README.md) — `provisioning-model.md` + `access-control.md` planned docs.
- Prior OS meetings: [`2026-06-05-os-tech-sync.md`](2026-06-05-os-tech-sync.md) · [`2026-06-05-architecture-thread.md`](2026-06-05-architecture-thread.md) · [`2026-06-02-controllers-secrets-alignment.md`](2026-06-02-controllers-secrets-alignment.md).
- Jira: SOV-855 (Provisioning Engine) · SOV-864 (OSQ-15 Provisioning Engine — Rook vs pure TF) · SOV-916 (RGW federation against Keycloak).
