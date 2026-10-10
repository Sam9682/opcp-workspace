---
id: core/baremetal-ironic-triage
type: troubleshooting
diataxis: how-to
title: "Baremetal / Ironic — triage & common failures"
owner: compute-team
status: published
last_verified: 2026-08-24
next_review: 2026-11-24
publish_target: confluence
tags: [ironic, baremetal, troubleshooting, openstack]
confluence_id: 998705304
sync:
  git_hash: pending-first-sync
  confluence_version: 1
  synced_at: 2026-07-13
---

# Baremetal / Ironic — triage & common failures

> ⚠️ **Confluence copy is behind git as of 2026-08-24** — page `998705304` predates the *Recovering a port's lost `local_link_connection`* recipe and the two new Common-failures rows added for SOV-2270. This `.md` is the source of truth; **re-publish it.** (The session that added them had read-only Confluence access.)
>
> Diagnostics for baremetal nodes that are stuck, unreachable, or failing clean/deploy. To actually *recover* a node, see [Baremetal node recovery / re-enrollment (Ironic)](../runbooks/baremetal-node-recovery.md); to reach a node's console/BMC, see [Reaching a node's BMC / iLO](../runbooks/baremetal-bmc-access.md).

## Triage — which nodes are broken, and how

```bash
openstack baremetal node list --long -c UUID -c Name -c "Power State" -c "Provisioning State" -c Maintenance
openstack baremetal node show <uuid> -f value -c last_error -c maintenance_reason
```

**`Power State = None` + `last_error` is the criterion** — Ironic's periodic power-sync fails when it can't
talk to the BMC. (`None` is normal only in `enroll` state — those nodes aren't power-synced yet; test them with
`manage`.) **Do not trust `node validate`:** for IPMI it only checks that credentials are *present* in
`driver_info`, it makes no real BMC call — a node can show `power: True` while every actual BMC call fails.

**`IPMI call failed` is ambiguous (auth OR unreachable) — qualify with a reachability check before classifying:**

```bash
addr=$(openstack baremetal node show <uuid> -f json -c driver_info | jq -r '.driver_info | .ipmi_address // .redfish_address')
ping -c2 -W2 "$addr"
curl -sk -o /dev/null -w "Redfish: HTTP %{http_code}\n" --connect-timeout 5 "https://$addr/redfish/v1/"
```

BMC answers (ICMP ok / HTTP 200-401) ⇒ credentials case. Dead ⇒ network/hardware case — and if the BMC also
speaks Redfish, test fleet creds against it first (`curl -sk -u '<user>:<pw>' https://$addr/redfish/v1/Systems/`):
a 200 means a **remote fix** (re-enable IPMI via Redfish, or switch the node's driver to `redfish`) may avoid the
DC visit entirely.

## Common failures

| Symptom (`last_error`) | Cause | Fix |
|---|---|---|
| `IPMI call failed: power status` / `manage` fails on auth | **Killed BMC credentials** | Restore BMC user **manually via ipmitool / BIOS**, re-run `manage` (see recovery runbook → *Killed BMC credentials*) |
| `No route to host` (Redfish/IPMI URL) | **BMC network-unreachable** — *not* a creds problem (IP/cable/VLAN/BMC dead) | On-site: check BMC network/IP, cold-reset the BMC; only then assess creds |
| Clean step `erase_devices` fails: `sedutil-cli … NOT_AUTHORIZED / takeOwnership failed` | **SED/Opal-locked NVMe** — drive still owned by a lost SED password | **PSID revert** — full step-by-step in the recovery runbook → *Recover an Opal/SED-locked NVMe (PSID revert)*. TL;DR: get a root shell (iLO Virtual Media live-boot), `sedutil-cli --PSIDrevert <PSID> /dev/nvmeXnY`, return to Ironic, re-clean |
| `Maintenance = True` with empty `maintenance_reason`, no error | Maintenance set manually / cleaning agent never started | `openstack baremetal node maintenance unset <uuid>`, watch cleaning; else abort + retry |
| Node won't PXE | OS on disk boots first | One-time PXE boot via BMC boot-override |
| Never appears in Ironic after PXE | Provisioning network / DHCP / inspector issue | Check provisioning VLAN + inspector logs; verify NIC/port |
| `provide` cleaning hangs | Disk-wipe / cleaning-network issue | Check node console; `openstack baremetal node abort` + retry |
| Node not visible at all | Never enrolled | Locate physically (rack/serial), then run the recovery flow from step 3 |
| `clean failed` but `last_error` is **empty** | Ironic auto-clears `last_error` after it powers the node off post-failure (conductor log: *"Clearing last_error … after confirmed power state match"*) | Don't trust the empty field — read the **`ironic-conductor` log** for the real error + `driver_internal_info` for the failing clean step (see *Triage when Ironic runs on Kubernetes* below) |
| `node set --resource-class` → **HTTP 409**, or `node manage` → **HTTP 400**, node in **`error`** | A prior deploy/teardown failed; `error` blocks `manage` and most field edits | `openstack baremetal node undeploy <uuid>` walks `error → deleting → cleaning → available`; then set resource_class while `available` (`manage` is *not* valid from `error`) |
| Clean times out in `clean wait`; node powers off; `agent_last_heartbeat` is **stale** | IPA ramdisk never called back — boot path broke before the agent started | Trace the boot path (K8s triage below); if the kernel downloads but the node never boots, see next row |
| iPXE fetches `boot.ipxe` + `deploy_kernel` (repeatedly, backing off) but **never** `deploy_ramdisk`; reboot loop → clean timeout | Kernel downloads but won't boot — typically **UEFI Secure Boot** rejecting the unsigned IPA kernel, or BIOS boot-mode drift | On the node's iLO/BMC (see [reaching a node's BMC / iLO](../runbooks/baremetal-bmc-access.md)): **disable Secure Boot** / align BIOS to a working sibling; confirm `deploy_boot_mode`. Watch the serial/iLO console for the exact error |
| Same iPXE kernel-loop **but Secure Boot is already off** — VSP POST loops at *"Starting required devices"* with a UEFI error (e.g. `C40000002:V…`) and **System Health → `PCI scan failed`** | **PCI enumeration failure** at boot: a faulting/needs-reseating PCI device (NIC or storage controller) stops the firmware bringing up boot devices, so the IPA kernel never runs (IML may still read `HealthRollup: OK`) | Watch via VSP; confirm Secure Boot off + scan IML/Storage health; capture the **AHS log** and escalate to **HPE/DC** + the Ironic owner. Park the node (`maintenance set`). *(Demo-verified 2026-06-18: `CZ2D47086T` / SOV-1272.)* |
| Cleaning fails at `deploy.erase_devices_metadata` with `dd … oflag=direct → Input/output error` on a **subset** of disks — but iLO/Redfish reports those drives **Health=OK / Unlocked** | **Outdated controller/system firmware** — a SAS-path bug makes writes EIO on healthy drives (looks exactly like "dead disks"). NOT a real disk failure, NOT Opal | **Update firmware to the latest SPP** (controller / System ROM / iLO / SPS — offline via iLO Virtual Media), then `manage`→`provide` and re-clean → drives erase fine. **Do NOT RMA** healthy-reporting disks. ⚠️ First `manage`/`provide` after a flash may hit iLO `UnableToModifyDuringSystemPOST` — wait out the long post-flash POST, retry. *(2026-06-22: SR932i-p `…036`→`…040` + ROM `v2.84` recovered nodes S & W; SOV-1327/1328/1399.)* |
| Clean times out; iPXE fetches `deploy_kernel` repeatedly but **`deploy_ramdisk` never**, no heartbeat — a stray token runs as an iPXE command, e.g. `malicious=evilvalue: command not found` then *"No response, retrying"* | **Malformed / injected `kernel_append_params`** — a value with an embedded **newline** splits the generated iPXE script, so text after `\n` runs as an iPXE command and the script aborts before `initrd`/`boot`. ⚠️ Often a **leftover security-TEST payload** (Ironic CVE-2026 test) whose cleanup didn't run | Inspect `… node show <uuid> -f json \| jq .driver_info.kernel_append_params` for an embedded `\n`/unexpected tokens; sanitize → `… node set <uuid> --driver-info kernel_append_params='console=ttyS0'`; re-clean. Source often `gor-drannou-tools → cve/ironic.2026/…`; if *not* a known test, treat as real injection and scan all nodes. *(2026-06-23: `CZ2D47086T` / SOV-1272 — looked like a PCI fault; silently broke provisioning ~4 weeks.)* |
| Node `available` but Nova won't schedule (`No valid host`) | Wrong `resource_class` (no flavor targets it) **or** a missing required **trait** | Match `resource_class` to a node that deploys. Dedicated pools are enforced by a **trait** the flavor requires (e.g. `CUSTOM_DEDICATED_SCALITY`), **not** the resource_class. Verify `openstack resource provider inventory list <node-uuid>` + `trait list` — RP is keyed by **node UUID, not name** |
| Node `available`/clean in Ironic but Nova `server create` → **`No valid host`**; scheduler log *"Got no allocation candidates from Placement"* | **Stale Nova instance holding a ghost Placement allocation** — node wiped Ironic-side but Nova/Placement never released it | Find the consumer: `openstack resource provider show <node-uuid> --allocations` → `openstack server show <consumer>`; **`openstack server delete <consumer>`** (NOT `resource provider allocation delete`). If blocked by a Neutron **trunk subport**, detach subports **one at a time** first. *(Demo6, 2026-06-24, SOV-1492.)* |
| Deploy aborts at `deploy.switch_to_tenant_network`: *"Could not add public network VIF … No Port found"* | The neutron port the deploy expects is gone — scheduling **already succeeded** (late step), so **not** a flavor/trait problem | Look up the VIF/port from the error (`openstack port show <id>`); repair/recreate the tenant-network port binding, redeploy. A failed deploy can leave the instance in **ERROR** holding an **Ironic node lock** — clear it before retry. *(2026-06-18: `CZ2D47086S` / SOV-1327.)* |
| Cleaning fails in **< 1 s** and the node **never powers on**; conductor logs `The local_link_connection is required for 'neutron' network interface and is not present in the nodes … port <uuid>` (one per port), then `NetworkError: Failed to create neutron ports` | The node's Ironic ports carry **`local_link_connection={}`**. With `network_interface=neutron` that field is mandatory, so Ironic skips every port in its *own* validation, has none left to create, and fails **before** Neutron, PXE or the hardware. Usually follows the ports being deleted and hand-recreated with `port create --address` alone | **Do not guess the values** — they are LLDP-derived. Recover them from the node's own enrollment inspection record: see *[Recovering a port's lost `local_link_connection`](#recovering-a-ports-lost-local_link_connection)* below. *(2026-08-24: demo6 `HXQF3CO280CE` / SOV-2270 — 7 days, 23 failed retries.)* |

## Triage when Ironic runs on Kubernetes

When OpenStack/Ironic is deployed on K8s (e.g. the demo / minint BM-PODs), the logs that explain a clean/deploy
failure live in **pods**, not on a controller host. Namespace is typically `ironic`; OpenStack CLI + `kubectl`
run from the seed node, creds/kubeconfigs in GoPass.

| Pod | Holds | Filter by |
|---|---|---|
| `ironic-conductor` | state-machine transitions + the real clean/deploy error (**authoritative when `last_error` is empty**) | node **UUID** |
| `ironic-api` | agent heartbeats — their *absence* means the ramdisk never came up | node **UUID** |
| `ironic-http` | iPXE boot sequence: `boot.ipxe` → `pxelinux.cfg/<mac>` → `deploy_kernel` → `deploy_ramdisk` | node **IP** (full sequence) or **PXE MAC** |
| `ironic-tftp` | initial bootloader fetch — **often empty** if the NIC runs native iPXE (e.g. Mellanox FlexBoot → straight to HTTP) | node IP |

Cleaning-network **DHCP is usually Neutron's** dnsmasq, not `ironic-dnsmasq` — an empty `ironic-dnsmasq` log does
**not** mean the node got no lease (find the IP it speaks from in the `ironic-http` log).

```bash
NS=ironic
UUID=<node-uuid>
IP=<node cleaning-net IP>    # from the ironic-http access log

# real error + state machine (authoritative when last_error is empty):
kubectl -n $NS logs deploy/ironic-conductor --all-containers --since=2h | grep -i "$UUID"
# did the ramdisk ever heartbeat?  (no hits ⇒ it never booted):
kubectl -n $NS logs deploy/ironic-api --all-containers --since=2h | grep -i "$UUID"
# full boot sequence — a kernel with NO following deploy_ramdisk ⇒ kernel downloads but won't boot:
kubectl -n $NS logs deploy/ironic-http --all-containers --since=2h | grep "$IP"
```

---

## Recovering a port's lost `local_link_connection`

**When to use:** a node fails cleaning or deploy in **under a second, without ever powering on**, and the conductor log says `The local_link_connection is required for 'neutron' network interface`. Typically after someone deleted and hand-recreated the node's ports — `openstack baremetal port create --address <mac> --node <uuid>` produces a port with no switch data, and Ironic will never bind it.

**Key fact:** `local_link_connection` (`switch_id` / `port_id` / `switch_info`) is **LLDP data captured during introspection at enrollment**. It cannot be typed from memory, and it is **not derivable** from a sibling node — breakout indices are not sequential and per-MAC → ToR assignment differs between nodes on the same rack. ⚠️ Guessing binds the node to someone else's switch port, and Ironic accepts it silently.

⚠️ **Re-inspecting the node does not help** — this platform inspects once, at enrollment, and re-inspection is unsupported (SOV-1850, Backlog).

### 1 — Read the LLDP back out of Ironic's stored inspection record

The record survives port deletion, `last_error` clearing, and log rotation. ⚠️ **It contains `plugin_data.ovh_data.bmc_password` in cleartext** — write it to a file with a tight umask, never `cat` it, and shred it afterwards.

```bash
UUID=<broken-node-uuid>
CTRL=<healthy-sibling-uuid>          # control — always validate before trusting
umask 077
openstack baremetal node inventory save $UUID > /tmp/inv.json
openstack baremetal node inventory save $CTRL > /tmp/ctrl.json

for f in /tmp/ctrl.json /tmp/inv.json; do
  echo "=== $f ==="
  jq -r '(.plugin_data.parsed_lldp // {}) as $p
    | (.inventory.interfaces // [])[]
    | [ .name, .mac_address,
        ($p[.name].switch_system_name // "-"),
        ($p[.name].switch_port_id     // "-"),
        ($p[.name].switch_chassis_id  // "-") ] | @tsv' "$f"
done
```

**Validate on the control first.** Its output must match `openstack baremetal port list --node $CTRL --long` exactly, field for field. If it does, the same extraction is trustworthy for the broken node. If it doesn't, stop — the extraction is wrong, not the data.

*(If `parsed_lldp` is absent, the raw TLVs are still in `inventory.interfaces[].lldp` — chassis-ID is type 1, port-ID type 2, system-name type 5.)*

### 2 — Write the values back

⚠️ **`local_link_connection`, `pxe_enabled`, `physical_network` and `portgroup_id` can only be changed while the node is in `enroll`, `inspecting`, `inspect wait`, `manageable` — or in maintenance.** Anywhere else you get **HTTP 409**. Maintenance is preferable on a shared environment: it leaves a visible reason for whoever else is on the box.

```bash
openstack baremetal node maintenance set $UUID --reason "<ticket> — restoring local_link_connection (<name>, <date>)"

# one per port; map MAC -> port UUID from `openstack baremetal port list --node $UUID --long`
openstack baremetal port set <port-uuid>   --local-link-connection switch_id=<switch_chassis_id>   --local-link-connection port_id=<switch_port_id>   --local-link-connection switch_info=<switch_system_name>

openstack baremetal port list --node $UUID --long        # verify all populated
openstack baremetal node maintenance unset $UUID
openstack baremetal node manage  $UUID
openstack baremetal node provide $UUID
```

### 3 — Check the PXE flag while you're there

Hand-created ports frequently flag the wrong NIC. The enrollment inspector recorded which one actually PXE-boots — grep the conductor log for the node's first minute:

```bash
kubectl -n ironic logs deploy/ironic-conductor --all-containers | grep "Port created for MAC.*$UUID"
#   → the one annotated "(PXE booting)" is the correct pxe_enabled port
```

`plugin_data.boot_interface` in the saved inventory carries the same answer.

```bash
openstack baremetal port set <correct-port> --pxe-enabled     # bare flags — no true/false argument
openstack baremetal port set <wrong-port>   --pxe-disabled
```

A wrong PXE flag doesn't cause the fast prepare-stage failure — the risk is the node sitting in `clean wait` until timeout because the boot NIC never receives DHCP/PXE options. ⚠️ It is **not always fatal**: on demo6 the node booted and cleaned green with the flag still on the other NIC of the same `EthernetN/M` pair, so where both NICs sit on the cleaning VLAN either may serve PXE `[Unverified — one observation]`. Align the flag with the enrollment record regardless; if a node does strand in `clean wait`, check this first.

### Verification

```
Adding cleaning network to node …                  ← no "local_link_connection is required" lines
For node … successfully created ports (…)          ← the moment it is fixed
Successfully set node … power state to power on
… moved to provision state "clean wait"
```

Then the normal clean template runs (`psid_reset` → `do_remove_encryption_key` → [`raid.delete_configuration`] → `erase_devices_metadata` → `erase_devices`) and the node lands in `available`. **Budget ~10 minutes** — measured 10 min 22 s on demo6, of which **8 min 56 s was waiting for the IPA agent to call back**; the clean steps themselves took 22 seconds. `raid.delete_configuration` only appears when a RAID configuration is actually present, so a 4-step run is not a sign of trouble.

### Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `HTTP 409 … can not have any connectivity attributes updated unless node is in enroll, inspecting, inspect wait, manageable state or in maintenance mode` | Node is in `clean failed` / `available` / `active` | `maintenance set`, or `manage` to reach `manageable`, then retry |
| `openstack baremetal port set … --pxe-enabled true` → `unrecognized arguments: true` | `--pxe-enabled` / `--pxe-disabled` are **bare flags** | Drop the argument |
| Extraction returns `-` for every switch field | Wrong jq path — `parsed_lldp` lives under `plugin_data`, not under `all_interfaces[].lldp_processed` | Use the query in step 1 |
| Node reaches `clean wait` then times out | PXE flag on the wrong NIC | Step 3 |
| Control node's LLDP does **not** match its own Ironic ports | The record is stale or the node was re-enrolled since | Do not use it — fall back to Netbox or the ToR MAC table |

### Cleanup

```bash
shred -u /tmp/inv.json /tmp/ctrl.json
```

*Provenance: demo6 `HXQF3CO280CE`, 2026-08-24 — SOV-2270 / OFR-26. The node was unusable for 7 days across 23 failed retries by 4 different people and returned to `available` 10 minutes after the fix; the data that fixed it had been in the inspection record since enrollment on 2026-07-23. Root-cause class: [SOV-1847 Enrollment & Day-0 Validation](../../../../generic/root-cause-collection/enrollment-day0-validation-SOV-1847.md).*

---
*Source: `kb/runbooks/baremetal-node-recovery.md` (Triage · Common failures · Ironic-on-K8s). Keep this page in sync with that runbook.*
