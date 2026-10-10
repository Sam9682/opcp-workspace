---
id: core/network-automation-stack-summary
type: deep-dive
diataxis: explanation
title: "OPCP Network Automation Stack — Zusammenfassung"
owner: sov-copilot
status: approved
publish_target: git
product: opcp-core
---

# OPCP Network Automation Stack — Zusammenfassung

> **Purpose:** Compact summary of how Neutron, ML2 OVH Driver, NOG, Ragnarok, and Arista switches interact. Created for the SOV-1751 (NOG State Drift) root cause review — 2026-07-08.
>
> **Full deep-dive:** [`shared/network-automation-stack.md`](network-automation-stack.md)

---

## Die Akteure

| Komponente | Rolle | Wo läuft es | Interface nach außen |
|-----------|-------|-------------|---------------------|
| **Neutron** | OpenStack Netzwerk-API — virtuelle Netzwerke, Ports, Trunks, VLANs | Controller (`oc-cp`), K8s Pod | OpenStack REST API |
| **ML2 OVH Driver** | Übersetzer: Neutron-Events → physische Switch-Kommandos. **Under investigation — evtl. nicht primärer Verlustpunkt.** | Controller, als Neutron Plugin geladen | Neutron ML2 Plugin API → NOG REST (HTTP) |
| **NOG** | Netzwerk-Gehirn (OVH-eigen, seit 2018). Empfängt Kommandos, pusht zum Switch. Kein Gedächtnis. | Controller + Agent auf jedem Arista Switch | NOG-eigenes Protokoll → Arista eAPI |
| **Ragnarok** | State Machine — sollte Drift erkennen. **Aktuell unzuverlässig.** | Controller, K8s Service | Heute: EOS serialization → geplant: gNMI/OpenConfig |
| **Netbox** | CMDB/DCIM — Inventar aller Racks/Switches/Ports. Generiert ZTP-Startup-Configs. | Controller | DHCP/PXE + config files |
| **Arista ToR** | Physische Switches (DCS-7050CX3-32S). VLANs, Trunks, LACP, BGP. 2× pro Rack (A+B HA). | Hardware | Arista eAPI / CLI |
| **Cisco IPMI** | Out-of-Band Management Switch (C9200-48T). Getrennt vom Data Plane. | Hardware | — |

---

## Kommunikationskette (Event Flow)

```
Tenant/Nova/Ironic
    │  OpenStack REST API
    ▼
Neutron API  ──(Port/Trunk/VLAN create/update/delete)──▶  ML2 OVH Driver
                                                                │
                                                                │  REST HTTP (NOG API)
                                                                ▼
                                                            NOG API (Controller)
                                                                │
                                                                │  NOG internes Protokoll
                                                                ▼
                                                            NOG Agent (auf Arista Switch)
                                                                │
                                                                │  Arista eAPI / CLI
                                                                ▼
                                                            Arista ToR Switch
                                                            (VLAN/Trunk/LACP/BGP config)
```

### ZTP — Switch Bootstrap
1. Switch bootet → DHCP/PXE (VLAN 200)
2. Pullt Firmware vom Controller
3. Netbox generiert Startup-Config (basiert auf Topologie-Position)
4. NOG Agent wird installiert → beginnt Live-Updates zu empfangen
5. Switch ist READY — Teil des Fabrics

### Ragnarok — Drift Detection (das Safety Net)
- Vergleicht **Expected State** (aus Neutron/Netbox) mit **Actual State** (von Switches)
- Sollte Drift erkennen und alarmieren
- **Aktuell:** ❌ Nicht alle ToRs enrolled · ❌ Spines fehlen · ❌ False Positives · ❌ Kein Auto-Reconcile

---

## Das State-Drift Problem — UNDER INVESTIGATION (2026-07-08)

> **Korrektur:** Die vorherige narrative ("ML2 Driver ist lossy") wurde nach Kollegen-Feedback und Code-Untersuchung teilweise korrigiert. Siehe [`network-automation-stack.md`](network-automation-stack.md) → "Root cause investigation status" für validierte Befunde vs. Hypothesen.

```
Layer 1: Neutron/Ironic   ── [VALIDIERT] ruft ML2 Driver nicht immer auf (Baremetal update/delete)
           │
Layer 2: ML2 OVH Driver   ── [HYPOTHESE] kein internes Retry; evtl. Exceptions verschluckt
           │
Layer 3: NOG API+Agent    ── [VALIDIERT] kein Reconciliation Loop
           │
Layer 4: Ragnarok         ── [VALIDIERT] unvollständig
```

**Validiert im Code:**
- Ironic ruft `update_port` (unbind) auf, NICHT `delete_port` — during baremetal tear_down
- Nova ruft `delete_port` nur für Nova-erstellte Ports auf; Ironic/pre-existing Ports werden nur ungebunden
- Neutron retryt DB-Errors und Port-Binding (10×), aber NICHT MechanismDriverError

**Hypothesen (noch nicht validiert — Logs nötig):**
- ML2 Driver macht NOG-Cleanup evtl. nur auf `delete_port_postcommit`, verpasst `update_port_postcommit`
- ML2 Driver verschluckt evtl. Exceptions → Neutron kann nicht retryen
- Lock-Konflikte hauptsächlich bei Terraform-Parallel-Calls (SOV-286), nicht bei Lifecycle

**Ticket-Mapping:**
- SOV-1293, SOV-473, SOV-286, SOV-468 → Layer 1/2 (Driver nicht aufgerufen / evtl. Events verpasst)
- SOV-1378, SOV-653 → Layer 3 (NOG Konfiguration/Bootstrap)
- SOV-1213 → Layer 4 (Ragnarok unvollständig)

---

## Langzeitlösung: ML2 Rewrite (SOV-110)

```
HEUTE                                    ZUKUNFT (SOV-110)

ML2 Driver → NOG direkt                  ML2 Driver → RAGNAROK State Machine
(under investigation)                  (state-machine, auto-reconciliation)
                                              │
NOG Agent → Arista Switch                     ▼
                                         Ragnarok reconciles → NOG Agent/gNMI → Arista
                                         (Drift wird automatisch erkannt + korrigiert)
```

**Voraussetzungen:**
- SOV-1213 — Ragnarok Drift Detection zuverlässig (alle Switches, keine False Positives)
- SOV-60 — Ragnarok Migration zu OpenConfig & gNMI
- SOV-1746 — nog-cli dump in opcp-diag (Diagnose-Tooling)

---

## Physische Fabric-Topologie

```
              External
                 │
         ┌───────▼────────┐
         │ Edge A+B (HA)  │  Arista DCS-7050CX3-32S
         └───────┬────────┘
         ┌───────▼────────┐
         │ Spine A+B      │  Arista DCS-7050CX3-32S
         └─┬────┬─────┬───┘
    ┌──────▼┐ ┌─▼───┐ ┌▼────────┐
    │ToR A+B│ │ToR  │ │ToR A+B  │  (pro Rack, MLAG HA)
    │Rack 1 │ │A+B  │ │Rack 3   │
    └───┬───┘ │Rack2│ └────┬────┘
   ┌─────▼──┐ └──┬──┘ ┌────▼───┐
   │3× Ctrl │    │     │ BM     │
   │(HA)    │  BM nodes  nodes  │
   └────────┘ └────────└────────┘
```

- **VxLAN + BGP EVPN** für Inter-Rack VLAN-Persistenz
- **MTU 9000** end-to-end (jumbo frames)
- **MLAG** für ToR A+B HA-Paare

### VLAN Map

| VLAN | Name | Zweck |
|------|------|-------|
| 199 | Discovery | Neue/unbekannte Maschinen |
| 200 | Provisioning | BM PXE Boot (auch "Admin" genannt) |
| 128 | In-band Mgmt | Controller In-Band Management |
| 198 | Inter-Ctrl K8s | K8s Traffic zwischen 3 Controllern |
| 666 | Garage | Nicht zugewiesene/decomissionierte BM |
| 20 | Management | Controller → ToR Switch Management |
| 4 | IPMI | Out-of-Band Management |

---

## Communication Interfaces (Protokoll-Übersicht)

| From → To | Protokoll | Was fließt |
|-----------|-----------|-----------|
| Tenant/Nova → Neutron | OpenStack REST API | Network/Port/Trunk CRUD |
| Neutron → ML2 Driver | Python Plugin Callbacks | Port/Trunk Lifecycle Events |
| ML2 Driver → NOG | REST HTTP | Übersetzte Switch-Operationen 🟡 UNDER INVESTIGATION |
| NOG → NOG Agent | NOG intern (push) | Switch Config Deltas |
| NOG Agent → Arista | Arista eAPI (JSON/HTTP) | Direkte Switch-Config-Änderungen |
| Ragnarok → Arista | EOS serialization (→ gNMI geplant) | State Polling / Drift Detection |
| Netbox → Switch (ZTP) | DHCP/PXE + config files | Startup-Config basierend auf Topologie |
| Ragnarok API → K8s | K8s Service (Cilium LB) + HTTPRoute | Bootstrap & Management |
