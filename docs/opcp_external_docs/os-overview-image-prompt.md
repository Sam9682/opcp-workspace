---
id: object-storage-on-cloud-store/user-stories-visuals-os-overview-image-prompt
type: reference
diataxis: explanation
title: "os overview image prompt"
owner: sov-copilot
status: approved
publish_target: git
product: cloudstore
---

Gemini prompt — Object Storage, project overview (the big picture). Paste the text below verbatim into Gemini (Imagen). No reference image needed. This is the single intro image for the project — same style as the milestone images, but high-level: only the important components, no step badges, no milestone-specific detail.

Generate a single horizontal 16:9 flat 2-D cartoon explainer illustration in the friendly style of a corporate onboarding deck. Use a soft pastel palette, clean rounded shapes with thin light line-art outlines, and simple smiling cartoon characters with minimal facial detail — just dot eyes and a small smile. Flat vector look on a light grey background panel: no 3-D, no isometric perspective, no heavy shading, no photorealism, no real human faces, no third-party brand logos. Keep it clean and uncluttered with generous negative space — this is a big-picture overview, not a detailed diagram, so show only the important components and keep labels short.

Across the very top runs a full-width bright yellow banner (hex #FFD400) with dark text reading "OPCP OBJECT STORAGE — the big picture", and a smaller dark subtitle "S3-compatible storage as a CloudStore package, on a dedicated Ceph cluster".

Below the banner the picture is divided into three equal-height horizontal layer bands stacked top to bottom, each with a small coloured label tab in its upper-left corner. The top band is "LANDING ZONE" with a cream tint (#fffaeb), yellow border and tab, subtitled "what the end user sees". The middle band is "CLOUD STORE — oss-cp" with a light blue tint (#f0f4fc), blue border and tab, subtitled "the control plane (the brain)". The bottom band is "OPCP CORE — CEPH" with a light green tint (#e9f7ec), green border and tab, subtitled "dedicated bare-metal storage".

In the TOP band (LANDING ZONE), on the left draw a friendly L3 End User cartoon in a purple hoodie at a laptop with a small label "End user". In the centre draw one clean browser tile titled "Object Storage" showing a short bucket list and a small "Access Keys" chip — representing self-service buckets, objects and S3 credentials. Keep this band light, end-user only — no admin tile here.

In the MIDDLE band (CLOUD STORE — oss-cp), on the left draw a small L2 IT-Admin figure with a compact "Admin views" tile (cluster health · cross-account · quotas) — the admin surface lives on the L2 layer. In the centre draw one rounded container labelled "oss-cp" holding a single tidy row of five short component chips: "Package runner", "Provisioning engine", "Keystone + S3 credential middleware", "Business Logic (accounts · quota · usage)", and "S3 proxies + observability". Do not over-detail these — just five clean chips in a row.

In the BOTTOM band (OPCP CORE — CEPH), draw a row of four identical coloured server-box cards labelled "Ceph node", each with a small "RGW" sub-chip on it (RGW co-located on the nodes), under a bracket caption "Dedicated Ceph + RGW cluster". From the oss-cp container in the middle band, draw a single thin arrow down into this band labelled "OpenStack API — provisions the hosts only" to show OpenStack is used purely to build the cluster, not as a running service.

Along the right edge, draw one thin vertical ribbon spanning the three bands with the small text "Ceph → RGW → Keystone (oss-cp) → Keycloak (CloudStore BL)" to show the identity chain at a glance.

In a clear area (lower-right of the middle band) float a light-yellow sticky-note callout (slightly rotated, soft drop shadow) titled "Package what SNC has · automate the manual" with three short bullets: "S3 parity with OVH Local Zones", "dedicated Ceph + RGW", "SecNumCloud-ready".

Do not draw any milestone banner, numbered step badges, or sequence legend — this is the overall picture, not a single milestone. Avoid any 3-D or isometric rendering, photorealism, real human faces, cluttered backgrounds, third-party tech logos, and any status or novelty markers such as "NEW", "BEFORE", "AFTER", "IN PROGRESS" or risk flags. Keep it simple, friendly and high-level.
