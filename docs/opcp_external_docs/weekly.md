# Object Storage — Weekly

> Updated before each CS Weekly. Fill in outcomes after the call.
> Owner: Eddy (PO).

---

## 2026-05-29

### What happened this week

- Jira is done: SOV-849–867 (Storage), CLOUD-644 (CloudStore), GSSNC-475/476 (SNC), all under LVL2-18375, all with descriptions — pending confirmation from Marc and Thomas
- Marc confirmed: Package calls OpenStack directly (VCF way) — not via the OPCP Infra API → [ADR](../decisions.md)
- Ibrahim confirmed: Keystone Controller (SOV-254) works for OS too; the 6 RGW config params are known
- Zafar onboarded Boris and the team on the CloudStore Package setup (2026-05-28)
- Boris and Stephan have GoPass access
- Stephan found 3 free `ceph-block-*` VMs in `paas-storage-block` — usable for the Rook POC
- Infra env error from the onboarding session: fixed

### Decisions from the 2026-05-29 weekly

- **Stephan is out of this workstream** — Boris takes over Object Storage packaging + Rook discovery
- **Keystone is not a blocker for M1** — M1 is node provisioning only. May be needed for M2, could be done manually if needed
- **Jira is the central tracking tool** (Thomas). Confluence = meeting notes only
- **Hello World** (OpenStack connectivity test) is unblocked — ready to start

### What's blocked

| # | What | Who unblocks it | Impact |
|---|---|---|---|
| OSQ-15 | Rook POC — Boris takes over from Stephan. Needs Kubernetes support from Zafar. | Boris + Zafar | M1 provisioning engine |
| OSQ-17 | How do RGW admin credentials get into the RGW config after Keystone creates them? | Ibrahim / Boris | RGW can't talk to Keystone until this is solved |
| OSQ-02 | Keystone/SNC topology — dedicated meeting with Ibrahim. Marc to lead, Zafar to be included. | Marc to schedule | M2/M3 architecture |
| OSQ-03 | BL team on SNC until June. No account activation, no usage until then. | Marc → Vincent | M2 date |

### Actions

| Action | Owner | Done? |
|---|---|---|
| VCF + packaging walkthrough session | Zafar + Boris | No — after the call |
| Rook exploration (k8s support from Zafar) | Boris | No |
| Add Zafar to the Ibrahim/Keystone meeting | Eddy | No |
| Post meeting notes to the channel | Eddy | No |
| Hello World — OpenStack connectivity test | Boris + Zafar | No — unblocked, start now |
| Review VCF project as reference | Everyone | No |

---

## How to use this file

Before the weekly: paste `open-questions.md` + `blockers.md` into Claude and ask to regenerate.
After the call: paste your notes and Claude will tell you what to close and what to update.
