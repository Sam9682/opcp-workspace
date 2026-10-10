---
id: core/minint-allocate-floating-ip
product: opcp-core
type: runbook
diataxis: how-to
title: "Allocate a floating IP on minint (BGP provider range)"
owner: opcp-core-network
status: draft
last_verified: 2026-08-06
next_review: 2026-11-06
publish_target: confluence
tags: [floating-ip, fip, neutron, bgp, minint, provider-network, first-responder]
---

# Allocate a floating IP on minint (BGP provider range)

> **When to use:** somebody needs one or more floating IPs on `minint` — a demo, a test cluster, an
> MKS/CAPO deployment — and `openstack floating ip create` alone won't do it, because on minint each
> FIP needs its **own `/32` `network:floatingip` subnet** seeded on the `provider` network first.
>
> **Scope:** minint. The same mechanism applies on `demo` and `drannou`, but **the address ranges may
> be shared between those environments** — see Prerequisites.
>
> **Upstream source:** [BGP — Openstack side › Configure IP addresses](https://confluence.ovhcloud.tools/display/GOR/BGP+-+Openstack+side#BGPOpenstackside-ConfigureIPaddresses)
> (Confluence, GOR space). This runbook is the minint-specific distillation plus the failure mode
> below.
>
> **Status:** DRAFT — the 4 steps were **executed successfully on 2026-08-06** allocating
> `5.196.233.5` on minint. Two open questions remain, flagged inline.

---

## ⚠️ Read this before you pick an address

**Never seed a `vm-fip` subnet on a block's `.1` (gateway) address.** A FIP allocated on the block
gateway is **silently unusable**: the BGP border router holds that address as a `scope host` local
address, so return traffic is absorbed locally and the `via <transit-IP>` route is shadowed. The VM
gets no egress, while other FIPs in the same block work fine — which makes it look like a VM problem
rather than an allocation problem.

This has already bitten once (demo-minint, 2026-07-06). Details and recovery:
[`minint-egress-debugging`](../../../cloudstore/misc/network-service-lb-l3-gateways/runbooks/minint-egress-debugging.md)
· incident record [`2026-07-07-fip-gateway-collision`](../../../cloudstore/misc/network-service-lb-l3-gateways/tracking/2026-07-07-fip-gateway-collision.md).

The durable fix — seeding must exclude the gateway address automatically — is **still open** as
[NSQ-032](../../../cloudstore/misc/network-service-lb-l3-gateways/open-questions.md). Until it lands,
**this check is manual and it is on you.** That is why the existing subnets start at `.2`.

---

## TL;DR (the skeleton)

```
1. List what's already allocated in the range   (on minint AND demo AND drannou)
2. Pick a free address — never .1, never one already in use anywhere
3. Create a /32 network:floatingip subnet:      openstack subnet create vm-fipN ...
4. Create the FIP from that subnet:             openstack floating ip create provider --subnet=vm-fipN
5. Verify it appears in the FIP list
```

## Prerequisites

- [ ] `openstack` CLI authenticated against minint (see [env-access-onboarding](../../environments/env-access-onboarding.md)).
- [ ] Permission to create subnets on the `provider` network.
- [ ] **The range you intend to use.** As of 2026-08-06 minint draws from **`5.196.233.0/24`** (croix), added a few weeks earlier.
- [ ] ⚠️ **Check the other environments too.** The ranges are believed to be **shared between `minint`, `demo` and `drannou`** — so an address free on minint may already be in use elsewhere. `[inference — stated by the range owner as "I think", not yet confirmed]` Run Step 1 on all three before allocating.

---

## Step 1 — List what's already allocated

```bash
openstack subnet list --service-type network:floatingip | grep 5.196.233
```

Observed on minint, 2026-08-06 (before the new allocation):

```
| 04409eb9-6355-4605-8528-7b39d4e71d92 | vm-fip11 | 2007bc63-...-d108bf8e7860 | 5.196.233.2/32 |
| 966b03c5-ff22-4d03-8a88-4310833b1f0d | vm-fip12 | 2007bc63-...-d108bf8e7860 | 5.196.233.3/32 |
| 1365ba9f-642a-4605-922b-9fcbb520ce67 | vm-fip13 | 2007bc63-...-d108bf8e7860 | 5.196.233.4/32 |
```

Notes on what you're reading:

- `2007bc63-5c46-4063-b5a5-d108bf8e7860` is the `provider` network.
- The `vm-fipN` **name counter does not track the last octet** — here `vm-fip11 → .2`, `vm-fip12 → .3`, `vm-fip13 → .4`. Don't compute the name from the address; take the next unused **N**.
- **Repeat this command on `demo` and `drannou`** before treating an address as free.

## Step 2 — Pick a free address, and confirm the name is free

Lowest unused address in the range that is **not** a block gateway (`.1`). From the listing above,
`5.196.233.5` was the next free one.

```bash
# confirm the subnet name you intend to use does not already exist
openstack subnet list --service-type network:floatingip | grep -w vm-fip14
```

Expect **no output**. If `vm-fip14` exists, increment.

## Step 3 — Create the `/32` floating-IP subnet

```bash
openstack subnet create vm-fip14 \
  --service-type network:floatingip \
  --subnet-pool provider-subnet-pool \
  --subnet-range 5.196.233.5/32 \
  --network provider \
  --gateway None \
  --no-dhcp
```

Every flag matters: `--service-type network:floatingip` is what makes it a FIP subnet rather than a
tenant subnet, `--gateway None` and `--no-dhcp` keep Neutron from reserving addresses inside a /32.

## Step 4 — Create the floating IP

```bash
openstack floating ip create provider --subnet=vm-fip14
```

## Step 5 — Verify

```bash
openstack floating ip list | grep 5.196.233.5
```

Observed on 2026-08-06:

```
| 14db1ef6-c290-44e6-8d3b-7f07164690b0 | 5.196.233.5 | None | None | 2007bc63-...-d108bf8e7860 | 45011dba6c9b418d99d9348122d85518 |
```

**Expected:** the FIP exists, `Fixed IP Address` and `Port` are `None` (unassigned and ready to
hand out), on the `provider` network.

## Verification (final smoke test)

Associating it and confirming egress is the only proof the address is actually usable — and the only
thing that catches the gateway-collision failure mode above:

```bash
openstack server add floating ip <server_id> 5.196.233.5
# then from inside the VM:
mtr -rwc5 1.1.1.1        # must get past hop 1
```

**Expected:** traffic leaves the VM. If `mtr` dies at hop 1 while other FIPs in the same block work,
go straight to [`minint-egress-debugging`](../../../cloudstore/misc/network-service-lb-l3-gateways/runbooks/minint-egress-debugging.md)
— you have most likely landed on a poisoned address.

## Common failures + fix recipes

| Symptom | Likely cause | Fix |
|---|---|---|
| FIP created, but the VM has no egress; other FIPs in the same block work; `mtr` dies at hop 1 | **The address is a block gateway (`.1`)** — the BGP border router holds it as a `scope host` local address. | The address is unusable as a FIP. Re-home the VM to a healthy address, then **delete the poisoned FIP *and* its `/32` subnet** so it can't be re-allocated. Full procedure in [`minint-egress-debugging`](../../../cloudstore/misc/network-service-lb-l3-gateways/runbooks/minint-egress-debugging.md). |
| `openstack floating ip create provider` fails with no free addresses | No `network:floatingip` subnet exists for a free address yet. | That is the whole point of Step 3 — the subnet must be seeded first. |
| Subnet create fails: name already exists | `vm-fipN` is taken (possibly on another env sharing the range). | Increment N and re-check (Step 2). |
| Address appears free on minint but the FIP misbehaves | Range may be **shared with `demo` / `drannou`** and allocated there. `[inference]` | Re-run Step 1 on the other environments; pick an address free on all of them. |
| A CAPO / MKS `OpenStackFloatingIPPool` keeps re-grabbing a bad address | The pool manages the address and will recreate it after deletion. | Fix the pool definition **before** deleting the FIP/subnet. ⚠️ If the FIP is a k8s `controlPlaneEndpoint`, deleting it rolls the node — coordinate with the cluster owner. |

## Open questions

1. **Is the whole `5.196.233.0/24` allocated to minint, or only part of it?** Raised 2026-08-06 by the range owner; Eric was asked and had not confirmed at time of writing. Determines how many FIPs are actually available before a new range is needed.
2. **Are the ranges genuinely shared across `minint` / `demo` / `drannou`?** Stated as a belief ("I think"), not confirmed. If true, allocation needs a cross-environment check every time — which is fragile and worth automating.

Both are worth resolving before anyone plans a demo that needs several addresses.

## References

- [BGP — Openstack side › Configure IP addresses](https://confluence.ovhcloud.tools/display/GOR/BGP+-+Openstack+side#BGPOpenstackside-ConfigureIPaddresses) — the upstream Confluence procedure this distils.
- [`minint-egress-debugging`](../../../cloudstore/misc/network-service-lb-l3-gateways/runbooks/minint-egress-debugging.md) — the debugging counterpart; read together with this one.
- [`2026-07-07-fip-gateway-collision`](../../../cloudstore/misc/network-service-lb-l3-gateways/tracking/2026-07-07-fip-gateway-collision.md) — the incident that produced the gateway warning.
- [NSQ-032](../../../cloudstore/misc/network-service-lb-l3-gateways/open-questions.md) — durable fix: FIP-subnet seeding must exclude the block gateway. Open.
- Root-cause backlog row *"Floating IP allocated on a block's gateway address"* in [`root-cause-backlog.md`](../../../../generic/root-cause-backlog.md).
- [env-access-onboarding](../../environments/env-access-onboarding.md) — how to reach minint in the first place.
