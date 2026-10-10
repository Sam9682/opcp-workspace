---
id: object-storage-on-cloud-store/architecture-sse-object-copy-move-limitation
type: deep-dive
diataxis: explanation
title: "Known limitation — SSE-encrypted objects cannot be moved/renamed (radosgw)"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

# Known limitation — SSE-encrypted objects cannot be moved/renamed (radosgw)

> **Status:** Open upstream (Ceph). No stable-release fix available yet. · **Ticket:** SOV-1734 · **Captured:** 2026-07-10 (Boris Behrens)
>
> **One-line:** On SNC every object is server-side encrypted, and Ceph RGW cannot server-side *copy* an encrypted object — so **no object can be renamed or moved**. Customers must re-upload under the new name. Upstream fix exists only in the dev branch and is blocked by a regression it introduced.

## What the bug is (plain language)

Object Storage on SNC is backed by **Ceph RADOS Gateway (RGW)**, which speaks the S3 API. S3 has **no native "rename" or "move"** operation — every S3 client and tool implements rename/move as two steps under the hood: **COPY the object to the new name, then DELETE the old one.**

The bug is in the COPY step: **RGW cannot server-side-copy an object that is encrypted with Server-Side Encryption (SSE).** The copy request fails with `501 NotImplemented`. Because rename/move depends on copy, the net customer-visible effect is:

> **An SSE-encrypted object cannot be renamed or moved.** The only way to "rename" it is to re-upload the data under the new name (client-side) and delete the original.

This affects all SSE flavours. **On SNC every object is server-side encrypted** — **SSE-S3** is the platform default, and **SSE-C** (customer-supplied key) is available for customers who bring their own key. There is no unencrypted object.

## Why it matters

- **On SNC every object is server-side encrypted** (SSE-S3 by default, SSE-C on request). There is no unencrypted object, so **every** rename/move is affected — this is not a rare edge case, it is the default behaviour for all data in Object Storage.
- Any customer workflow that reorganises objects — rename, move between prefixes/"folders", or tools that stage-then-rename — breaks.
- The failure is easy to miss until hit: a rename/move looks like a trivial one-line operation but returns `501 NotImplemented`, and the object keeps its original name.

## Why it needs *more upstream work* to be solved

The fix exists but is **not usable by us yet**, for three compounding reasons:

1. **The fix is only in Ceph's development line, not any released stable version.**
   [PR ceph/ceph#63794](https://github.com/ceph/ceph/pull/63794) ("rgw: implement CopyObject for encrypted objects") was merged to `main` on 2025-12-01. `main` is the **Tentacle (v20)** development line. It is **not** in any stable release we would run today (no Reef 18.x or Squid 19.x backport has even been *started*).

2. **The backport is not finished — and it is blocked by a regression the fix itself introduced.**
   The Tentacle backport ([tracker #74034](https://tracker.ceph.com/issues/74034)) is still *"Fix Under Review"*. More importantly it is **blocked by [#75650](https://tracker.ceph.com/issues/75650)**: the new copy-for-encrypted-objects code **corrupts data when an object is both compressed and encrypted** (it passes compressed ciphertext through and re-encrypts/re-compresses it). So the first version of the fix traded a clean `501` error for *silent data corruption* in a sub-case — clearly not shippable. #75650 is now itself fixed in `main` (v21 dev) and *pending backport*.

3. **This is a historically fragile area — a cluster of related correctness bugs.**
   Encrypted-object copy has repeatedly broken in new ways as it is worked on: multipart SSE-C copy corruption ([#23232](https://tracker.ceph.com/issues/23232), fixed 2018), lifecycle transition of SSE-S3 multipart corrupting data ([#76413](https://tracker.ceph.com/issues/76413), pending backport), and the compress+encrypt regression above. Each fix has tended to expose the next edge case (multipart, compression, lifecycle). **All of these need to land and be backported together** before encrypted-object copy is safe in a stable release.

**Bottom line for planning:** the original tracker [#23264](https://tracker.ceph.com/issues/23264) has been open since **2018**. A real fix finally landed in the dev branch in Dec 2025, but between the unfinished backport and the corruption regression it introduced, **there is no stable Ceph release we can deploy that safely supports moving/renaming encrypted objects today.** Until Ceph finishes the backport chain and we pick up a stable release containing it, SNC customers need the documented workaround (re-upload under the new name).

## Customer workaround

Re-upload the object under the new name (a client-side copy that bypasses the broken server-side copy), then delete the original — e.g. `rclone moveto … --disable copy`, or an AWS CLI download/re-upload/delete. Full customer-facing how-to is in the SOV-1734 ticket comment and proposed for the public OVH docs (`ovh/ovhcloud-docs`).

## Sources

- Ceph tracker [#23264 — Server side encryption support for s3 COPY operation](https://tracker.ceph.com/issues/23264) *(the parent bug)*
- [PR #63794 — rgw: implement CopyObject for encrypted objects](https://github.com/ceph/ceph/pull/63794) *(the fix)*
- Ceph tracker [#74034](https://tracker.ceph.com/issues/74034) *(Tentacle backport — Fix Under Review)*
- Ceph tracker [#75650](https://tracker.ceph.com/issues/75650) *(compress+encrypt corruption regression, blocks the backport)*
- Ceph tracker [#45942](https://tracker.ceph.com/issues/45942) *(duplicate — confirms the `501 NotImplemented` symptom for SSE-C)*
- Ceph tracker [#23232](https://tracker.ceph.com/issues/23232) / [#76413](https://tracker.ceph.com/issues/76413) *(related multipart / lifecycle corruption bugs)*

## Cross-references

- SOV-1734 — the tracking ticket (abstract + workaround).
- [Object Storage project](../README.md) — parent project.
- [Architecture index](README.md) — OS architecture docs.
