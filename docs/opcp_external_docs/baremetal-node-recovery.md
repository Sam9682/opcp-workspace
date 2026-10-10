---
id: core/baremetal-node-recovery
type: runbook
diataxis: how-to
title: "Baremetal node recovery / re-enrollment (Ironic)"
owner: compute-team
status: published
last_verified: 2026-07-13
next_review: 2026-10-13
publish_target: confluence
tags: [ironic, baremetal, openstack, recovery]
confluence_id: 963476150
sync:
  git_hash: pending-first-sync
  confluence_version: 6
  synced_at: 2026-07-13
---

# Baremetal node recovery / re-enrollment (Ironic)

> **When to use:** a baremetal host fell out of the fleet and needs **re-enrollment** into Ironic · **BMC credentials were killed / rotated** · a server is **not visible at all** (present but absent from Ironic).
>
> ⚠️ **Orientation, not self-service** — without Ironic experience you'll get stuck between bullet points; pair with the Compute team on first runs. **Scope:** lab / test fleets where the affected nodes carry no workloads (`provide` wipes disks by design).
>
> **See also:** [triage & common failures](../troubleshooting/baremetal-ironic-triage.md) · [reaching a node's BMC / iLO](baremetal-bmc-access.md) · [operator access — minint / demo](../../environments/env-access-onboarding.md).

## TL;DR

```
0. openstack baremetal port list --node <node_uuid> --long     # find node/port physically
1. openstack-system baremetal node delete <node_uuid>          # remove from Ironic
2. Delete the node from Netbox                                 # re-creation syncs automatically
3. Power ON, force PXE boot (KVM)                              # BMC one-time-boot if OS installed
4. Node auto-enrolls → Ironic state "enroll"
5. openstack baremetal node manage <node_uuid>                 # → "manageable" (fails ⇒ BMC unreachable/auth)
6. openstack baremetal node provide <node_uuid>                # → "available" (wipes disks)
```

## ⚠️ Provisioning prerequisite — update firmware before production

**New baremetal nodes MUST be updated to the latest HPE SPP (Service Pack for ProLiant) before going into production.** Out-of-date factory firmware has caused nodes that *look* healthy to fail in non-obvious ways — most notably a **controller/system-firmware bug on the SAS path** that made automated cleaning fail with `dd: Input/output error` on a subset of HDDs while the iLO/Redfish drive view reported every drive **Health=OK / Unlocked**. It read like "dead disks" but was pure firmware: flashing the SPP (HPE SR932i-p controller, System ROM, iLO, SPS) and re-cleaning fixed it with **no disk replacement**. *(Demo Scality pool, HPE Alletra 4140, 2026-06-22 — SOV-1327/1328/1399. See the `erase_devices_metadata` row in [triage & common failures](../troubleshooting/baremetal-ironic-triage.md).)*

- Flash the **current Gen11 SPP** (offline via iLO Virtual Media) at enrollment; keep components on HPE's *recommended* baseline. ⚠️ Mind pulled releases — e.g. A4140 35LFF BP `2.17` was retracted (keep `1.59`).
- This is also HPE's **pre-RMA requirement**: they won't accept a hardware RMA unless the box is on current firmware — and as above, the firmware pass often *is* the fix.

## Background

Ironic drives each BM host via its **BMC** (iDRAC/iLO/IPMI) through the state machine `enroll → manageable → available → active`. Recovery = delete the broken record, let the node **auto-enroll** via PXE discovery, walk it back to `available`.

Auto-enrollment is **rule-driven** (`irobox` → `ironic-post-setup/etc/rules.d/`): inspection sets the IPMI/Redfish driver per motherboard vendor, discovery user is `ironic_ovh`, and the BMC password is taken from the node's `ovh_data` during inspection. **HPE quirk:** HPE nodes get their **serial number** as Ironic node name (other vendors: product serial).

## Prerequisites

- [ ] Physical access + **KVM / crash-cart** (to watch boot + force PXE).
- [ ] OpenStack CLI on the controller with Ironic admin rights.
- [ ] Node identified: `<node_uuid>`, or asset tag / serial / rack-U.
- [ ] **Working BMC credentials on the node** — see the killed-creds recipe below *before* starting if that's your case.
- [ ] Netbox access (delete only — re-creation syncs automatically).

---

## Special case first — killed BMC credentials

Re-enrollment does **not** heal dead BMC credentials by itself: the discovery rule that injects the BMC password into Ironic only fires if the node's `ovh_data` carries a valid one — and Ironic still needs a working BMC user to manage the node afterwards.

**→ The BMC user must be restored manually first, via `ipmitool` locally on the host or via the BIOS/BMC console.** Once the BMC auths again, continue with the normal flow below; discovery picks the credentials up automatically.

> **⚠️ TYAN S8036 — the BMC password rotates on every clean; don't mistake it for killed creds.** These boards flash the BMC **in-band during cleaning** (the `firmware/update_bmc` clean step — in-band `agent` firmware interface, SOV-488 — because their AMI MegaRAC BMC can't be updated out-of-band via Redfish). The full-SPI flash (`socflash`) **resets the BMC config**, so the agent **regenerates the IPMI password on each clean** and hands it back to Ironic. Before treating an S8036 node as "killed creds", read the **current** password from the node rather than reusing an old value:
> ```bash
> openstack baremetal node show <uuid> -f json -c driver_info | jq -r '.driver_info.ipmi_password'
> ```
> The rotated password is persisted into `driver_info` (`ipmi_password` / `redfish_password`). **Incoming (SOV-488):** inspection/introspection data will stop keeping the BMC password in cleartext (masked before storage), so `driver_info` becomes the single source of truth.
>
> **Scope — this is S8036-only in practice.** Fleet default is `default_firmware_interface = no-firmware` and the `agent` firmware interface isn't in the enabled set fleet-wide (`irobox/hieradata/fleet-infra/ironic_vars.yaml` → `enabled_firmware_interfaces: no-firmware,redfish`). The in-band BMC flash runs **only where the `update_bmc` step is wired in — currently just the TYAN S8036 (AMI MegaRAC)**. Redfish-capable boards update firmware out-of-band and are **not** affected (their BMC password is not rotated by cleaning). The mechanism isn't hard-locked to the S8036 model — any future AMI-MegaRAC board with the step enabled would behave the same — but today S8036 is the only one.

---

## Re-enroll (physical access)

### 0 — Locate the node

```bash
openstack baremetal port list --node <node_uuid> --long
```

MAC(s)/port info → cross-reference against physical NIC / switch port.

### 1 — Delete from Ironic

```bash
openstack-system baremetal node delete <node_uuid>
```

*(TBC: confirm `openstack-system` wrapper vs plain `openstack` on the controller.)*

### 2 — Delete from Netbox

Remove the stale Netbox record. Re-creation happens **automatically** via sync — no manual re-add.

### 3 — Power ON + force PXE (KVM)

Watch via KVM. If an OS is already installed the node won't PXE by itself — force a **one-time PXE boot** via the BMC boot-override (or interrupt POST and pick the NIC).

### 4 — Auto-enroll

```bash
openstack baremetal node list    # node appears in state "enroll"
```

### 5 — `manage`

```bash
openstack baremetal node manage <node_uuid>    # → "manageable"
```

**Fails ⇒ Ironic can't reach or auth on the BMC** → that's the killed-creds case; fix the BMC user first (see above), re-run.

### 6 — `provide`

```bash
openstack baremetal node provide <node_uuid>   # → "available"
```

Node boots once to **wipe disks** (automated cleaning is on fleet-wide), then lands in `available` — ready for normal provisioning (incl. the Compute Operator path).

---

## Verification

```bash
openstack baremetal node show <node_uuid> -f value -c provision_state   # available
openstack baremetal node show <node_uuid> -f value -c maintenance       # False
```

> **Polling state transitions** (e.g. watching `manage`/`provide`/`undeploy` walk `cleaning → clean wait → available`): on the controller `openstack` is usually a **shell alias**, and `watch` runs a non-interactive `sh -c` that **won't expand it**. Two ways around it:
>
> ```bash
> # bash: expand the alias into watch
> watch -n5 "${BASH_ALIASES[openstack]} baremetal node show <node> -f value -c provision_state -c instance_uuid -c reservation"
> # or just loop at the interactive prompt (aliases expand there):
> while true; do openstack baremetal node show <node> -f value -c provision_state -c instance_uuid; echo ---; sleep 5; done
> ```

## Safe power operations on SED nodes (reboot / power-off) — avoid the lockout race

**When to use:** any time a **SED-enabled BM node** needs a reboot or power-off — the *how* decides whether the disks come back unlocked.

**Background:** SED disks lock on power loss. Ironic drives the unlock (`unlock_wait` state) when it **observes** a power transition — but it observes by **polling**. A fast out-of-band power-cycle (metalconsole/IPMI: off→on within one polling interval) is invisible to Ironic → no unlock phase → disks stay locked → the node falls into a **PXE bootloop**. Seen in SNC production (Nathan Malo, 2026-07-27; case chain CS15513468/INC0205591/PRB0043369). Tracked as SOV-1963.

| Operation | Do it like this | Why |
|---|---|---|
| **Reboot** | `systemctl reboot` on the node itself | Ironic sees the node as power-on throughout — no unlock cycle needed; fastest safe path |
| **Power-off** | via the OpenStack API (Ironic-driven) | Ironic observes the off state, powers the node back on, and triggers the unlock phase |
| **Never** | raw IPMI / metalconsole power-cycle on a SED node | Race with Ironic's power-sync → locked disks + PXE bootloop |

**If it already happened** (node PXE-bootloops after an out-of-band cycle): power the node **off with Ironic**, then on again — Ironic pushes it into `unlock_wait` and unlocks. *(Workaround per Florent Thiery 2026-07-15 — behaviour to be confirmed; update this line once verified.)* If the node instead sits **stuck in `unlock_wait`**, that's the other variant — see the GOR Confluence page *"[IRONIC] Handling SED Nodes Stuck in unlock wait State"*.

## Recover an Opal/SED-locked NVMe (PSID revert)

**When to use:** automated cleaning (`erase_devices`) fails with `sedutil-cli … NOT_AUTHORIZED` / `takeOwnership failed` on an NVMe — the drive is **Opal/SED-locked** and still owned by a lost SED password. Cleaning can't pass until the drive is reverted, so the fix has to run **outside** the failing clean step.

> **Related — controller-side SED tooling:** the Controller Debian Image installer bundles the same `sedutil` + an Opal PBA image on the controllers' base OS (though it does **not** yet enable Opal locking at install time). Same TCG-Opal toolchain, controller side.

> ⚠️ **`--PSIDrevert` is destructive by design.** It cryptographically resets the drive to factory (the data-encryption key is regenerated → all data gone). That's exactly what we want for a node going through cleaning (`provide` wipes disks anyway) — but **never** run it on a drive whose data you need. Test-env only; no workload-safety concern here.
>
> 🔒 **The PSID is a master unlock secret — keep it out of Git.** It comes off the physical drive label (a 32-char code) or out-of-band from whoever has the node. Do **not** paste the value into this runbook, tickets, or the work-list. *(drannou `WM20CS601401` / SOV-1271: Morgan supplied the PSID out-of-band 2026-06-25 — held off-repo.)*

**This is NOT an expert-only task.** The revert itself is one deterministic command; the only non-trivial part is getting a root shell on the node. Any operator with BMC/iLO + controller access and this runbook can do it — no need to escalate to the Ironic owner.

### Prerequisites

- The **PSID** for the locked drive (off the label, or out-of-band).
- **BMC/iLO access** to the node — see [Reaching a node's BMC / iLO](baremetal-bmc-access.md) §1 (creds + reachability) and §4 (web UI / Virtual Console).
- The node parked so Ironic isn't fighting you: `openstack baremetal node abort <uuid>` if it's stuck in `clean wait`, then it sits in `clean failed` / `manageable`.

### Path A — iLO Virtual Media live-boot *(default — depends on nothing Ironic-specific)*

Use this when you don't know whether the IPA/rescue image ships `sedutil-cli`. A live Linux image carries its own tools.

1. Reach the node's iLO (web UI via [Reaching a node's BMC / iLO](baremetal-bmc-access.md) §4).
2. **Mount a live ISO** that includes `sedutil-cli` (and `nvme-cli`) via **iLO → Virtual Media**, set one-time boot to it (iLO → Boot settings), power-cycle.
   - Any small live distro works; if none has `sedutil-cli`, a SystemRescue/Ubuntu-live + `apt/pacman install sedutil` (or the `sedutil-cli` static binary on a second VM image) does it.
3. At the live shell, identify the drive and confirm it's Opal-locked:
   ```bash
   nvme list                         # find the right /dev/nvmeXnY
   sedutil-cli --query /dev/nvme0n1  # Locked = Y / "Locking enabled" ⇒ this is the one
   ```
4. **Revert** (PSID held out-of-band — not shown here):
   ```bash
   sedutil-cli --PSIDrevert <PSID> /dev/nvme0n1
   # success: "revertTper completed successfully" (or no error + Locked = N on re-query)
   ```
5. Re-query to confirm it's unlocked, unmount the Virtual Media, set boot back to normal/PXE.
6. Hand the node back to Ironic and re-clean:
   ```bash
   openstack baremetal node manage <uuid> && openstack baremetal node provide <uuid>
   ```
   → cleaning's `erase_devices` now passes; node reaches `available`.

### Path B — `openstack baremetal node rescue` *(fastest, IF rescue is set up + the image has sedutil)*

1. `openstack baremetal node rescue <uuid> --rescue-password <pw>` → boots the rescue ramdisk with SSH.
2. SSH into the rescue env, run the **step 3–4 commands** from Path A (`sedutil-cli --query` / `--PSIDrevert`).
3. `openstack baremetal node unrescue <uuid>`, then `manage` → `provide` to re-clean.

> Only works if (a) rescue is configured for this Ironic, **and** (b) the rescue image bundles `sedutil-cli`. If unsure, use Path A. *(Confirm with the Compute team which drannou images include `sedutil-cli`.)*

### Path C — IPA manual-clean hold *(if the IPA image bundles sedutil-cli)*

Some IPA builds let you pause cleaning / run an in-band step. If the deploy ramdisk already has `sedutil-cli` (the same one that *reports* the `NOT_AUTHORIZED` error usually does), you can SSH into the cleaning ramdisk during a hold and run the revert in place, then resume cleaning. Setup-specific — only reach for it if Path A/B don't fit.

### Verification

- `sedutil-cli --query /dev/nvmeXnY` → **Locked = N**, locking disabled.
- `openstack baremetal node show <uuid> -c provision_state` → `available`; `last_error` empty; `maintenance=False`.
- Update the node's **Status** in the work-list / ticket (e.g. SOV-1271 #4 → recovered).

### What this case taught us (provenance)

- **drannou `WM20CS601401`** (SOV-1271, 2026-06-25): the *diagnosis* recipe already existed (see [triage & common failures](../troubleshooting/baremetal-ironic-triage.md)); what was missing was the **execution path** to actually run `sedutil-cli` when the failing step is cleaning itself. The PSID was supplied by Morgan out-of-band; this section closes the gap so the next Opal-lock is self-serve.

## Identifying disks for replacement (serial / WWN / slot)

When a node lands in `clean failed` because `deploy.erase_devices_metadata` can't write to a drive (`dd … oflag=direct` → **Input/output error**), the disk is physically failing → it needs replacement, not a clean retry. To raise an RMA / DC ticket you need the **serial** (RMA key) and ideally the **physical slot** (which bay to pull). The `/dev/sdX` name from the clean error is **not** stable — resolve it to serial/WWN/slot.

**Step 1 — serial / WWN (read-only, no boot): Ironic's stored inventory.**
`baremetal node inventory save` just dumps the inventory blob from the last inspection — it does **not** change state, power-cycle, or re-inspect (safe, like `node show`). Note `inventory save` writes JSON to **stdout** (or `--file`); it does **not** accept `-f json`.

```bash
openstack baremetal node inventory save <node> \
  | jq '.inventory.disks[] | {name, serial, wwn, model, size, by_path, rotational}'
```

Map the failing `/dev/sdX` from the clean `last_error` to its `serial` + `wwn` + `model`. ⚠️ The inventory is a **snapshot from inspection** — it lists every disk with identity but carries **no live health flag**, and a dead drive may even be missing if the controller has since dropped it. So it gives *identity*, not *which is broken*.

**Step 2 — confirm which are dead + the physical slot: Redfish (live).**
Reach the BMC per [Reaching a node's BMC / iLO](baremetal-bmc-access.md), then:

```bash
curl -sk -u "$BMC_USER:$BMC_PW" https://$ILO/redfish/v1/Systems/1/Storage | jq '.Members'
curl -sk -u "$BMC_USER:$BMC_PW" https://$ILO/redfish/v1/Systems/1/Storage/<ctrl>/Drives/<id> \
  | jq '{Name, SerialNumber, Model, MediaType,
         slot: .PhysicalLocation.PartLocation.ServiceLabel, health: .Status.Health}'
```

`Status.Health = Critical/Warning` confirms the dead drives independently of the `sdX` mapping, and `PhysicalLocation…ServiceLabel` is the **bay** to pull. **Serial → RMA; slot → which bay.** If the failed drive returns a blank serial (controller dropped it), the **slot + `Status.Health=Critical`** is enough to replace it.

**Step 3 — record on the ticket.** Put `device · serial · WWN · model · slot` for each failed drive on the recovery ticket so DC/RMA needs no guessing. After replacement: `node maintenance unset` → re-run cleaning → `available`.

> *Worked example (SOV-1328 / CZ2D47086W, 2026-06-18):* 16× Seagate ST16000NM005J on `pci-0000:14:00.0`; failed `/dev/sdn,sdo,sdp` → serials `ZR5G4TQE0000R524L1YS`, `ZR5G3X1T0000R523HLXX`, `ZR5G4S9B0000R524M5XF`.

---
