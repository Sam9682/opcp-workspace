# Object Storage — Architecture Thread Summary
**Date:** 2026-06-05
**Channel:** SOV CS Object Storage (Webex)
**Participants:** Marc Dittmann, Boris Behrens, Zafar Akhtar

---

## Context
Following Zafar's architecture proposal (2026-06-03) and the open questions on cluster orchestration (OSQ-15) and SNC identity design (OSQ-02), the team discussed the path forward in the channel.

---

## Key inputs

### Marc — Brainstorm session confirmed
- Right people for the architecture sync: **Stephan Hohn, Boris Behrens, Nathan (SNC), Ibrahim Takouna**
- Vincent Casse not needed — not deep enough in implementation details
- Format: 1h brainstorm to define what we have and what we should have
- Marc wants to know where he can support

### Boris — Rook vs ceph operator
- Current SNC implementation uses the **ceph operator** — well-written Ansible (written by Stephan). Could be usable out of the box today.
- Boris + Stephan prefer **Rook long-term** — k8s as management wrapper already known for creating/destroying resources
- Little experience with Rook at scale, but confident it will be fine
- Rook "only dispatches container handling and some management commands"

### Marc — Scale clarification
- OPCP Object Storage will not scale to 100 nodes — unrealistic for this use case
- If it did reach that scale, it would be split into multiple environments anyway
- **Removes the main concern about Rook performance at scale**

### Zafar — Rook + MKS proposal (⚠️ REJECTED)
- Proposed: use MKS as k8s dependency for Rook, consume dedicated cluster via kubeconfig
- **Boris (2026-06-05):** MKS has Object Storage as a dependency (source: Florent Thiery) — circular dependency, not viable.
- **MKS option is off the table.**

---

## Decisions / Direction
- Rook is the preferred long-term approach (Boris + Stephan aligned)
- MKS as k8s dependency ruled out — circular dependency (MKS depends on Object Storage)
- Decision now: **Rook + self-managed k3s vs ceph operator** — to be resolved in brainstorm
- Scale concern removed by Marc — Rook at OPCP scale is fine

## Still open
- Brainstorm session not yet scheduled — Eduardo to send invite
- SNC identity design (OSQ-02 dual-Keystone) not yet discussed in this thread

---

## Next steps
| Who | What |
|---|---|
| **Eduardo** | Schedule 1h brainstorm: Stephan, Boris, Nathan, Ibrahim |
| **Team** | Validate Rook + MKS dependency in the brainstorm |
| **Eduardo** | Check MKS availability timeline with Marc |

---

## References
- OSQ-15: [open-questions.md](../open-questions.md)
- OSQ-02: [open-questions.md](../open-questions.md)
- Previous alignment meeting: [2026-06-02-controllers-secrets-alignment.md](2026-06-02-controllers-secrets-alignment.md)
