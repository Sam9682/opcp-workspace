---
id: core/baremetal-firmware-update
product: opcp-core
type: runbook
diataxis: how-to
title: "Baremetal / HPE — updating firmware (iLO · BIOS · NVMe · NIC) with ilorest"
owner: compute-team
status: draft
last_verified: 2026-07-30
publish_target: confluence
tags: [ironic, baremetal, firmware, ilo, bios, nvme, ilorest, hpe, redfish]
---

# Baremetal / HPE — updating firmware with ilorest

> Manual, out-of-band firmware update of a single HPE baremetal node — **iLO/BMC, System ROM (BIOS), NVMe drives, NIC**. One flow covers all of them, because `ilorest flashfwpkg` takes any HPE `.fwpkg`; what differs per component is *how the update activates* and *whether the host has to reboot*. Prerequisite: [reaching a node's BMC / iLO](baremetal-bmc-access.md). If a flash leaves a node unbootable: [Baremetal node recovery / re-enrollment](baremetal-node-recovery.md).
>
> **Status: DRAFT — for review.** Generalised from the iLO-only Confluence page
> [How to update HPE iLO firmware?](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=942130881)
> (PSPUSNC) and the working procedure validated on 8 demo nodes under
> SOV-21. See [§8](#8--what-has-actually-been-validated)
> for exactly what is verified and what is not.

**Audience:** Operations — the team that owns applying changes to customer infrastructure. Per
SOV-21 (Pierre-Yves, 2026-05-18): *"until it's automated
it should be handled by someone in Operation, because they own the process of applying such changes
to the customer infrastructure."*

Design context: [Firmware Management FDD v0.1](../../misc/firmware-management/fdd-firmware-management-v0.1.md) ·
parent epic LVL2-23206.

---

## 1 — Know what you are flashing before you start

The component decides the activation path and the customer impact. Get this straight first; it is the
difference between a transparent maintenance and an unplanned reboot.

| Component | Where the running version lives | Activation | Host impact |
|---|---|---|---|
| **iLO / BMC** | `/redfish/v1/Managers/1` → `FirmwareVersion` | applies on the iLO itself; the BMC resets | **none to a running host** — validated, see §8 |
| **System ROM (BIOS)** | `/redfish/v1/Systems/1` → `BiosVersion` | staged, flashes on reboot | reboot required — and see the **cold-boot** caveat in §5 |
| **NVMe drive** | `/redfish/v1/Chassis/<n>/Drives/<n>` → `Firmware` | staged, flashes on reboot | reboot required |
| **NIC** | see `FirmwareInventory` below | staged, flashes on reboot | reboot required |

The vendor-neutral way to list *everything* installed, which is also the reliable route for
components without an obvious Redfish path (NIC, storage controllers):

```bash
curl -sk -u "$BMC_USER:$BMC_PW" \
  https://$ILO/redfish/v1/UpdateService/FirmwareInventory?\$expand=. \
  | jq -r '.Members[] | "\(.Name)\t\(.Version)"'
```

> ⚠️ **NIC paths are not yet verified on our hardware.** The `FirmwareInventory` listing above is the
> standard Redfish mechanism and should cover NICs, but nobody has run a NIC flash on an OPCP node —
> SOV-21's demo run covered NVMe, BIOS and BMC only. Treat NIC as untested until someone does one.

---

## 2 — Prerequisites

- **BMC address + credentials.** Do not guess them — they come from Ironic, and the per-node BMC
  password is *not* in gopass. Follow [§1 of the BMC access runbook](baremetal-bmc-access.md) to get
  `$ILO`, `$BMC_USER` (`ironic_ovh`) and `$BMC_PW`, and to confirm the host you are working from
  actually routes to the OOB network.
- **`ilorest`** — the HPE RESTful Interface Tool, on the host that reaches the OOB net.
  Verified with 7.1.0.0.
- **A maintenance window** for anything other than an iLO update (see the table in §1).
- **The node's Ironic state.** If the node is `active` and carrying a customer workload, the reboot
  in §5 is a customer-visible event; coordinate it. An `available` node can be rebooted freely.

---

## 3 — Check whether the firmware needs updating

**Running version** — the BMC example; swap the path per §1 for other components:

```bash
read -s BMC_PW
curl -sk -H "Content-Type: application/json" -u "ironic_ovh:$BMC_PW" \
  https://$ILO/redfish/v1/Managers/1 | jq '{FirmwareVersion, Model}'
```

```json
{ "FirmwareVersion": "iLO 6 v1.76", "Model": "iLO 6" }
```

**Target version.** Two different questions, don't conflate them:

- *What does the hardware vendor ship?* — the [HPE Support Center](https://support.hpe.com) page for
  the component. Pick the version, then use the **`curl Copy`** button, which yields both the
  `.fwpkg` and its `.json`, each with a published SHA256.
- *What is validated for this platform?* — a workload may pin a version. VCF, for example, requires
  NVMe **HPK4** where the nodes shipped with HPK3; that mismatch is what opened SOV-21. OVH's own
  validated-firmware set lives in [hardware-nest](https://interne.ovh.net/ui/hardware-nest-app/).
  **The vendor's latest is not automatically the right target.**

```bash
curl -fL -o "ilo6_176.fwpkg" https://downloads.hpe.com/pub/softlib2/software1/fwpkg-ilo/p788720876/v284075/ilo6_176.fwpkg
curl -fL -o "ilo6_176.json"  https://downloads.hpe.com/pub/softlib2/software1/fwpkg-ilo/p788720876/v284075/ilo6_176.json
```

**Always verify the checksum before flashing:**

```bash
echo "752ae14d1ca9add2b7521e4f5ab53b9a867bbf98bbc61f32879dc41d49f0975c  ilo6_176.fwpkg" | sha256sum --check
echo "3fd183a9d59c3f71732f9602bbc3e8436de1186562309d812a9456ee131fde3c  ilo6_176.json"  | sha256sum --check
```

> For repeat use, push the package into the internal file server / Artifactory rather than pulling
> from HPE each time — see the GOR pages
> [Add a Firmware binary in the file server](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=741738430)
> and [Firmware Update helper script](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=741738367).
> Air-gapped sites have no other route.

---

## 4 — Flash the package

Same command for every component — this is why one runbook covers them all:

```bash
ilorest flashfwpkg <package>.fwpkg --url "$ILO" -u "$BMC_USER"
# password is prompted; -p "$BMC_PW" also works but puts the secret in your shell history
```

Real output from the SOV-21 NVMe run:

```text
iLORest : RESTful Interface Tool version 7.1.0.0
Discovering data...Done
Uploading firmware: Kioxia_CM7_KACM7ALFHPK4.fwpkg
Successfully checked 'Kioxia_CM7_KACM7ALFHPK4.fwpkg'.
Uploading component Kioxia_CM7_KACM7ALFHPK4.fwpkg.
[200] The operation completed successfully.
Created UEFI Task for Component Kioxia_CM7_KACM7ALFHPK4.fwpkg successfully.
This firmware is set to flash on reboot.
```

That last line is the whole point of §5: **the upload succeeded, the firmware is not yet live.**

Two flags worth knowing:

- `--tpmover` — proceed when a TPM is present. Needed on the OPCP demo nodes; without it `ilorest`
  refuses on TPM-equipped hardware.
- If the component is already at that version, `ilorest` will offer to overwrite the uploaded
  component — answering `y` re-uploads, it does not re-flash by itself.

---

## 5 — Activate

**iLO/BMC:** activates itself, then the BMC resets. You lose the iLO session for a minute or two.
The host keeps running.

**Everything else: reboot — and for BIOS, a *cold* boot.**

> ⚠️ **A warm reboot silently does not take the BIOS update.** On the SOV-21 run, 7 of the 8 nodes
> needed *"another cold boot to catch the latest bios fw"*. If you verify in §6 and the version is
> unchanged, this is almost always why. Power the node fully off and on rather than resetting it.

```bash
# from the Ironic side for an available node
openstack baremetal node power off <node> && openstack baremetal node power on <node>
```

---

## 6 — Verify

Re-run the §3 query and confirm the version changed. For drives, `ilorest` prints the per-drive
state directly — this is the real post-flash output from SOV-21 showing `HPK4` live:

```text
  Path         : /redfish/v1/Chassis/2/Drives/8
  Name         : CM7
  Model        : VO003840YXUHV
  Firmware     : HPK4
  Type         : SSD / NVMe
  Health       : OK
  State        : Enabled
```

**Do not close the ticket on the upload.** The only evidence that counts is the running version read
back after activation.

---

## 7 — When it goes wrong

- **Version unchanged after reboot** → cold boot (§5), then re-verify.
- **`NoValidSession` / auth errors** → credential problem, not connectivity. Re-read `$BMC_PW` from
  Ironic introspection data per [the BMC access runbook](baremetal-bmc-access.md).
- **Node won't boot after a BIOS/NVMe flash** → [Baremetal node recovery](baremetal-node-recovery.md).
  Watch the boot over iLO serial console (VSP) to see where it stops.
- **iLO unreachable / console lost after a BMC update** → see the open issue in §9.
- **Rollback.** HPE iLO holds two firmware banks and can revert to the previous image; BIOS likewise
  keeps a backup ROM. **Neither has been exercised on OPCP hardware** — do not assume rollback works
  until someone tests it. This is the biggest gap in this runbook.

---

## 8 — What has actually been validated

| Claim | Evidence |
|---|---|
| Procedure works for **NVMe** (HPK3 → HPK4) | 8 demo nodes, SOV-21 comments 2026-04-20 / 2026-05-05 |
| Procedure works for **BIOS** (A56_3.12) and **BMC** (iLO 6 v1.75) | same 8-node run |
| BIOS needs a **cold** boot | 7 of 8 nodes required a second cold boot |
| An **iLO update does not impact a running instance** | Pierre-Yves + Stephan, SOV-21 2026-05-18 |
| **NIC** firmware update | ❌ never run — see §1 |
| **Rollback** | ❌ never run — see §7 |
| Production use | ❌ demo env only. The source Confluence page's caveat *"before using this procedure in production, we'll need to test it on demo env"* **is now satisfied** for NVMe/BIOS/BMC, but no customer-site run has happened. |

---

## 9 — Open items

- **iLO 6 KVM-loss incidents** (PUSNC-2047) — nine
  RCS nodes on iLO 6 v1.68 repeatedly lose console until the BMC is reset. An upgrade is proposed as
  the remedy, but **no HPE release note has been found naming this defect**, so treat the upgrade as
  hygiene rather than a diagnosis, and capture the iLO event log + AHS dump *before* flashing —
  a flash destroys the evidence. Note the ticket's own target versions (1.74 in the body, 1.76 in
  the title) are already behind: iLO 6 **1.77** shipped 2026-06-08.
- **`ilorest` is not in the firmware file server.** Until it is, DEEP cannot run this procedure
  out-of-band at customer sites (Benoit, PUSNC-2047 2026-06-02).
- **Automation.** Ironic can drive firmware updates natively and irobox already enables the
  interface (`enabled_firmware_interfaces: "no-firmware,redfish,agent"` in
  `hieradata/fleet-infra/ironic_vars.yaml`). The manual flow here is the interim step — see
  [Firmware update (Ironic)](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=741737518)
  and the [upstream Ironic docs](https://docs.openstack.org/ironic/latest/admin/firmware-updates.html).
- **Documentation consolidation — decided 2026-07-30: the published home is GOR.** This doc is the
  git-KB source; it publishes into the **GOR** space under
  [Firmware update](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=741737518),
  alongside the existing *Add a Firmware binary in the file server* and *Firmware Update helper
  script* children. Remaining work: reduce the PSPUSNC page
  [942130881](https://confluence.ovhcloud.tools/pages/viewpage.action?pageId=942130881) to a pointer
  at the GOR page rather than a second copy, and re-point
  PUSNC-2047 at it. Worth a word with Benoit
  Lefebvre first — he wrote the PSPUSNC page.
