# Implementation Plan — OPCP installations bugfixes

Two bugs in the "OPCP installations" menu. Both fixes are **frontend-only**
(React + TypeScript under `frontend/`). The FastAPI backend already behaves
correctly for both cases (verified below), so no `app/` code changes and no
pytest run are required.

Repo root / cwd for all commands: `\\wsl.localhost\Ubuntu-24.04\home\slepetre\workspace\forgejo\opcp-workspace`.
Frontend commands run with cwd = `.../opcp-workspace/frontend`.

---

## Root-cause verification (confirmed against the actual code)

### BUG 1 — fresh DB still shows seeded server-node rows
- `frontend/src/components/prerequisites/serversData.ts` exports
  `SERVER_NODES: ReadonlyArray<ServerNode>` = 9 hard-coded rows, including
  `nodeUuid 'c6adb16d-e6b6-445e-b61a-d1355c6c4abc'`. **Confirmed.**
- `frontend/src/components/prerequisites/ServersTable.tsx` defaults the `nodes`
  prop to `SERVER_NODES` and renders `mergeNodeOverrides(nodes, nodesOverrides)`.
  On mount it calls `prerequisitesService.loadServerNodes(installationId)` and
  stores the result as `nodesOverrides` (empty array on a fresh DB / load
  failure). **Confirmed.**
- `frontend/src/components/prerequisites/serverNodeOverrides.ts`
  `mergeNodeOverrides` maps over `defaults` and only applies an override when its
  `nodeUuid` matches a default; it never adds or removes rows. So the row set is
  always exactly `SERVER_NODES` → the 9 seeded rows always render, even when the
  DB returns zero rows. **Confirmed — this is the bug.**
- Backend: `app/prerequisites/router.py` `get_server_nodes` returns
  `_server_node_response(overrides)` which is `{ nodes: [] }` when no
  `ServerNodeOverride` rows exist for the installation; `save_server_nodes`
  upserts one override row per `node_uuid`. **Confirmed:** the backend is a pure
  per-installation override store and genuinely yields zero rows on a fresh DB.
  The empty-table bug is entirely in the frontend merge/default semantics.

### BUG 2 — "Generate control plane file" exports a static template
- `frontend/src/components/prerequisites/InstallationListPage.tsx`:
  `handleGenerateControlPlane` calls `generateCloudStoreVcfControlPlane()` (no
  args, treated as synchronous); `handleGenerateDataPlane` calls
  `generateCloudStoreVcfDataPlane()`. **Confirmed.**
- `frontend/src/services/installationExport.ts`:
  `generateCloudStoreVcfControlPlane()` downloads the constant
  `CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE` verbatim (placeholders like
  `appliance_password: 'ChangeMe'`, fixed UUIDs); `generateCloudStoreVcfDataPlane()`
  does the same with `CLOUDSTORE_VCF_DATAPLANE_TEMPLATE`. Neither takes an
  installation nor reads the backend. **Confirmed — this is the bug.**
- `buildInstallationExport(installation)` in the same file already fetches real
  per-tab answers (`QA_CATEGORIES` + `CONTEXT_CATEGORY` via
  `prerequisitesService.loadClientAnswers`) into `tabs[slug] = { rowId: answer }`,
  and the credential config. This is the real recorded data to reuse. **Confirmed.**
- The control-plane / data-plane template keys correspond 1:1 (by name) to the
  VCF tab parameters: in `configs.ts` the `vcfConfig` rows carry
  `questionPrimary` strings that are the exact template keys
  (e.g. `vcf_mgmt_network_name`, `dns_server`, `overlay_vlan_id`,
  `vcf_external_network_id`). The persisted answer key is the row `id`
  (e.g. `vcf-mgmt-network-name`). **Confirmed** — this gives the mapping below.

---

## Design decision — BUG 1 (chosen: option a)

**Make persisted/retrieved data the sole source of server-node row existence;
stop seeding fake rows.** On a fresh DB the table renders empty (the existing
empty-`<tbody>` state).

Rationale: the backend is already a pure per-installation override store that
returns `[]` on a fresh DB. The only thing forcing rows to appear is the
frontend treating `SERVER_NODES` as authoritative for row existence. Making
stored data authoritative is the minimal change that satisfies "empty on fresh
DB" while keeping add/edit persistence (`saveServerNodes`) and the live-retrieve
flow intact.

Concretely:
- `ServersTable` `nodes` prop defaults to **`[]`** (empty), not `SERVER_NODES`.
- The rendered row set becomes the **stored overrides** (the data returned by
  `loadServerNodes`), not a fixed defaults list.
- `mergeNodeOverrides` is re-specified so the row set is the union driven by the
  stored data: when `defaults` is empty, the result is exactly the overrides
  (as full `ServerNode` rows). Edits still persist the full displayed list via
  `saveServerNodes` (unchanged wire contract).
- `SERVER_NODES` is **kept only as an optional importable reference constant**
  (not removed, since `installationExport.ts` and the architecture document use
  it and tests import it), but it is **no longer a default** anywhere that drives
  the installations Servers-nodes table. Its continued use inside
  `buildInstallationExport` (export `servers.nodes`) is out of scope for these
  two bugs and left unchanged to avoid altering export JSON shape; note this
  explicitly in the PR.

Edit persistence detail: today `handleConfirm` builds `rows` from `mergedNodes`
and persists all of them. With an empty default and stored-data-driven rows,
`mergedNodes` equals the stored overrides, so editing an existing fetched/entered
row still round-trips correctly. (Add-new-row UI is not part of the current
component and is not introduced here; the live-retrieve flow and manual edit of
fetched rows remain the ways rows come to exist.)

---

## BUG 2 — control-plane / data-plane answer-key → template-key mapping

Both generators start from the template object (to preserve the exact key set
and ordering the CloudStore VCF service expects) and **override each value with
the recorded answer when the user provided a non-empty one**; otherwise the
template default is kept. Answers come from `buildInstallationExport`'s `tabs`
map. For every mapped key the source tab is **`vcf`** (slug `vcf`), i.e.
`tabs['vcf'][<rowId>]`.

### Control plane — `CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE` key → `vcf` answer row id
| template key | answer row id (slug `vcf`) |
|---|---|
| `appliance_password` | `vcf-mgmt-appliance-password` |
| `appliance_xapikey` | `vcf-mgmt-appliance-xapikey` |
| `bootstrap_dns_server` | `vcf-mgmt-bootstrap-dns-server` |
| `customer_network_dhcp_ip` | `vcf-mgmt-customer-network-dhcp-ip` |
| `customer_network_name` | `vcf-mgmt-customer-network-name` |
| `dns_server` | `vcf-mgmt-dns-server` |
| `dns_zone` | `vcf-mgmt-dns-zone` |
| `esxi_root_password` | `vcf-mgmt-esxi-root-password` |
| `esxi_setup_script` | `vcf-mgmt-esxi-setup-script` |
| `external_network_id` | `vcf-mgmt-external-network-id` |
| `flavor_name` | `vcf-mgmt-flavor-name` |
| `image_name` | `vcf-mgmt-image-name` |
| `keycloak_clusterissuer` | `vcf-mgmt-keycloak-clusterissuer` |
| `ntp_server` | `vcf-mgmt-ntp-server` |
| `overlay_network_id` | `vcf-mgmt-overlay-network-id` |
| `overlay_subnet_id` | `vcf-mgmt-overlay-subnet-id` |
| `overlay_subnet_range` | `vcf-mgmt-overlay-subnet-range` |
| `overlay_vlan_id` | `vcf-mgmt-overlay-vlan-id` |
| `vcf_deployer_ip` | `vcf-mgmt-vcf-deployer-ip` |
| `vcf_deployer_url` | `vcf-mgmt-vcf-deployer-url` |
| `vcf_master_password` | `vcf-mgmt-master-password` |
| `vcf_mgmt_dhcp_ip` | `vcf-mgmt-dhcp-ip` |
| `vcf_mgmt_network_name` | `vcf-mgmt-network-name` |
| `vcf_mgmt_network_vlan_id` | `vcf-mgmt-network-vlan-id` |
| `vcf_mgmt_subnet_name` | `vcf-mgmt-subnet-name` |
| `vcf_subdomain` | `vcf-mgmt-vcf-subdomain` |
| `vmotion_network_id` | `vcf-mgmt-vmotion-network-id` |
| `vmotion_subnet_id` | `vcf-mgmt-vmotion-subnet-id` |
| `vmotion_subnet_range` | `vcf-mgmt-vmotion-subnet-range` |
| `vmotion_vlan_id` | `vcf-mgmt-vmotion-vlan-id` |
| `vsan_network_id` | `vcf-mgmt-vsan-network-id` |
| `vsan_subnet_id` | `vcf-mgmt-vsan-subnet-id` |
| `vsan_subnet_range` | `vcf-mgmt-vsan-subnet-range` |
| `vsan_vlan_id` | `vcf-mgmt-vsan-vlan-id` |

No corresponding question — keep template default (document in code comment):
`debug`, `dns_create_records`, `esxi_install_timeout`, `lacp`,
`openstack_auth_type`, `openstack_endpoint_type`, `openstack_identity_api_version`,
`pairing_source`. (`vcf_mgmt_subnet_name` is mapped; the `vcf-mgmt-subnet-id`
concept has no template key.)

### Data plane — `CLOUDSTORE_VCF_DATAPLANE_TEMPLATE` key → `vcf` answer row id (workload-domain rows)
| template key | answer row id (slug `vcf`) |
|---|---|
| `overlay_subnet_range` | `vcf-wld-overlay-subnet-range` |
| `overlay_vlan_id` | `vcf-wld-overlay-vlan-id` |
| `vcf_external_network_id` | `vcf-wld-external-network-id` |
| `vcf_overlay_network_id` | `vcf-wld-overlay-network-id` |
| `vcf_overlay_subnet_id` | `vcf-wld-overlay-subnet-id` |
| `vcf_vmotion_network_id` | `vcf-wld-vmotion-network-id` |
| `vcf_vmotion_subnet_id` | `vcf-wld-vmotion-subnet-id` |
| `vcf_vsan_network_id` | `vcf-wld-vsan-network-id` |
| `vcf_vsan_subnet_id` | `vcf-wld-vsan-subnet-id` |
| `vmotion_subnet_range` | `vcf-wld-vmotion-subnet-range` |
| `vmotion_vlan_id` | `vcf-wld-vmotion-vlan-id` |
| `vsan_subnet_range` | `vcf-wld-vsan-subnet-range` |
| `vsan_vlan_id` | `vcf-wld-vsan-vlan-id` |
| `workload_domain_num` | `vcf-wld-workload-domain-num` |

No corresponding question — keep template default: `dns_create_records`,
`esxi_install_timeout`, `lacp`, `openstack_auth_type`, `openstack_endpoint_type`,
`openstack_identity_api_version`, `pairing_source`.

Implementation note: define the two mappings as explicit
`Record<templateKey, rowId>` constants in `installationExport.ts` so the mapping
is data, not control flow, and is directly unit-testable.

---

## Ordered steps

- [ ] 1. Re-specify the server-node merge so stored data drives row existence.
      In `serverNodeOverrides.ts`, change `mergeNodeOverrides` so the returned
      row set is driven by the overrides (stored data), not a fixed defaults
      list: when a `defaults` row matches an override by `nodeUuid`, merge
      fields as today; **additionally include override rows that have no
      matching default** as full `ServerNode` rows (all six fields come from the
      override). With an empty `defaults` the result is exactly the overrides.
      Keep the existing "edit existing default fields" behavior for the
      non-empty-defaults case so other callers passing `SERVER_NODES` are
      unaffected. Update the function doc comment to state the new "row set
      comes from stored data" semantics.
      Files: `frontend/src/components/prerequisites/serverNodeOverrides.ts`
      Verify: `npm run test -- --run` — all suites pass (serverNodeOverrides is
      covered transitively by ServersTable tests; step 5 adds a direct unit test).

- [ ] 2. Default the Servers-nodes table to empty and render stored data.
      In `ServersTable.tsx`, change the `nodes` prop default from `SERVER_NODES`
      to `[]` (keep the `nodes` prop so explicit callers/tests can still pass a
      list). The component already stores `loadServerNodes` results in
      `nodesOverrides` and computes `mergeNodeOverrides(nodes, nodesOverrides)`;
      with the step-1 change and an empty default this now renders exactly the
      stored rows, and an empty `<tbody>` on a fresh DB. Remove the now-unused
      `SERVER_NODES` import if it is no longer referenced in this file.
      Files: `frontend/src/components/prerequisites/ServersTable.tsx`
      Verify: `npm run test -- --run` — ServersTable suites pass (after the
      step-6 assertion updates); `npm run build` type-checks.

- [ ] 3. Add the two template→answer mapping tables and installation-aware,
      async generators in the export service. In `installationExport.ts`:
      (a) add `CONTROLPLANE_KEY_TO_ROW_ID` and `DATAPLANE_KEY_TO_ROW_ID`
      `Record<string, string>` constants matching the mapping tables above;
      (b) add a private helper `applyAnswersToTemplate(template, keyMap, vcfAnswers)`
      that returns a new object with the template's key set/order preserved and
      each mapped key overridden by `vcfAnswers[rowId]` **only when that answer
      is a non-empty string** (trim check), otherwise the template default;
      (c) change `generateCloudStoreVcfControlPlane` to
      `async (installation: Installation): Promise<void>` that calls
      `buildInstallationExport(installation)`, reads `data.tabs['vcf'] ?? {}`,
      builds the output via `applyAnswersToTemplate(CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE, CONTROLPLANE_KEY_TO_ROW_ID, vcfAnswers)`,
      and downloads with the UNCHANGED `CLOUDSTORE_VCF_CONTROLPLANE_FILENAME` and
      `` `${JSON.stringify(output, null, 2)}\n` `` formatting;
      (d) make `generateCloudStoreVcfDataPlane` the same shape using the data-plane
      template, map, and `CLOUDSTORE_VCF_DATAPLANE_FILENAME`. Keep the template
      constants exported and unchanged. Mirror the style of
      `generateArchitectureDocument` (installation-aware, async, reuses
      `buildInstallationExport`).
      Files: `frontend/src/services/installationExport.ts`
      Verify: `npm run build` type-checks; `npm run test -- --run` passes
      (new assertions added in step 4).

- [ ] 4. Make the InstallationListPage handlers installation-aware and async.
      In `InstallationListPage.tsx`, update `handleGenerateControlPlane` and
      `handleGenerateDataPlane` to be `async`, set/clear `busyId` and `clearStatus`
      like `handleGenerateDoc`, `await generateCloudStoreVcfControlPlane(installation)`
      / `await generateCloudStoreVcfDataPlane(installation)`, and surface the
      existing success/error row status (reuse the current
      `prereq.installations.generateControlPlane.success` /
      `generateDataPlane.success` / `generatePlane.error` i18n keys). Update the
      two button `onClick`s to `() => void handleGenerateControlPlane(installation)`
      / `() => void handleGenerateDataPlane(installation)` (they already pass
      `installation`). Keep the buttons disabled while `busyId === installation.id`.
      Files: `frontend/src/components/prerequisites/InstallationListPage.tsx`
      Verify: `npm run build` type-checks; `npm run test -- --run` passes;
      `npm run lint` clean (no floating promises / unused vars).

- [ ] 5. Add/adjust tests for BUG 1 (empty on fresh DB).
      (a) New direct unit test for `mergeNodeOverrides` asserting: empty defaults
      + empty overrides → `[]`; empty defaults + N overrides → N full rows equal
      to the overrides; non-empty defaults keeps the existing edit-in-place
      behavior. (b) New ServersTable test: with `loadServerNodes` mocked to
      resolve `{ nodes: [] }` and the default `nodes` prop (empty), the table
      body renders zero data rows (no `c6adb16d-...` row) and still shows the six
      column headers; with `{ nodes: [<one override>] }` it renders exactly that
      one row. Mirror the mocking/render setup in
      `ServersTable.preservation.test.tsx` (mock `prerequisitesService`,
      `LanguageProvider` wrapper, `act` for mount effects).
      Files: `frontend/src/components/prerequisites/serverNodeOverrides.test.ts` (new),
      `frontend/src/components/prerequisites/ServersTable.emptyOnFreshDb.test.tsx` (new)
      Verify: `npm run test -- --run` — the new suites pass.

- [ ] 6. Update existing ServersTable tests that encode the old seeded-rows
      behavior. In `ServersTable.preservation.test.tsx`, the two cases that
      currently rely on the `SERVER_NODES` default via `nodes={SERVER_NODES}`
      keep working (they pass `SERVER_NODES` explicitly, so they are unaffected);
      verify this holds and adjust only assertions that implicitly assumed the
      default prop seeds rows (none should break, but confirm). Do not weaken
      coverage — if any assertion encoded "defaults always render", convert it to
      pass `nodes={SERVER_NODES}` explicitly. Audit any other test referencing
      `SERVER_NODES` as the implicit default and make the dependency explicit.
      Files: `frontend/src/components/prerequisites/ServersTable.preservation.test.tsx`
      (and any other `ServersTable.*.test.tsx` that relied on the default)
      Verify: `npm run test -- --run` — full suite green.

- [ ] 7. Add tests for BUG 2 (real data overrides the static template).
      New test for `installationExport.ts` control-plane + data-plane generation:
      mock `prerequisitesService.loadClientAnswers` so `tabs['vcf']` returns
      sentinel values for a few mapped row ids (e.g. `vcf-mgmt-dns-server`,
      `vcf-mgmt-appliance-password`, `vcf-wld-workload-domain-num`), mock the
      `downloadFile` path (spy on `URL.createObjectURL`/`Blob` or extract the
      JSON written) and assert the generated JSON (i) contains the sentinel
      answer values at the correct template keys, (ii) falls back to the template
      default where no answer is provided (e.g. `pairing_source`), and
      (iii) preserves the full template key set and the two-space-indent +
      trailing-newline formatting and the unchanged filename. Follow the
      pure-function/fixture style of `installationExport.test.ts`.
      Files: `frontend/src/services/installationExport.controlplane.test.ts` (new)
      Verify: `npm run test -- --run` — new suite passes.

- [ ] 8. Full verification pass.
      Files: none (verification only)
      Verify (cwd = `.../opcp-workspace/frontend`), all must succeed:
      `npm run test -- --run`; `npm run build`; `npm run lint`.
      No backend code changed, so no pytest run is required.

---

## Files changed (summary)
- `frontend/src/components/prerequisites/serverNodeOverrides.ts` (merge semantics)
- `frontend/src/components/prerequisites/ServersTable.tsx` (empty default)
- `frontend/src/services/installationExport.ts` (installation-aware async generators + mappings)
- `frontend/src/components/prerequisites/InstallationListPage.tsx` (async handlers)
- `frontend/src/components/prerequisites/serverNodeOverrides.test.ts` (new)
- `frontend/src/components/prerequisites/ServersTable.emptyOnFreshDb.test.tsx` (new)
- `frontend/src/components/prerequisites/ServersTable.preservation.test.tsx` (assertion audit)
- `frontend/src/services/installationExport.controlplane.test.ts` (new)

## Verification results (recorded)

Commands run from `frontend/` (via WSL Ubuntu-24.04, non-UNC path):

- `npm run test -- --run` (full Vitest suite): 533 passed, 11 failed
  (87 files). All 11 failures are PRE-EXISTING and unrelated to this change —
  confirmed by stashing the frontend changes and rerunning the six failing
  files on the baseline, where 10/11 reproduce identically (HowToUse "Basics"
  tip, EventsRoute/TasksRoute route-preservation, TopicDetailPage forum-source
  check, and four prerequisitesRoutes route/answer-wiring cases); the 11th
  (TrackingForm property test) is a 30s timeout under parallel worker load in a
  file this change does not touch. The directly relevant suites all pass:
  - `serverNodeOverrides.test.ts` — 4/4
  - `ServersTable.emptyOnFreshDb.test.ts` — 2/2
  - `installationExport.controlplane.test.ts` — 6/6
  - existing `ServersTable.*` and `installationExport.test.ts` — green.
- `npm run build` (`tsc -b && vite build`): SUCCESS (type-check clean, built in
  ~2.8s).
- `npm run lint` (`eslint .`): the repo has 45 pre-existing errors / 4 warnings
  across unrelated files (`no-explicit-any`, `react-refresh/only-export-components`,
  `react-hooks/set-state-in-effect`). Linting only the files this change
  touches + the three new test files yields exactly the 4 PRE-EXISTING errors
  already present in `ServersTable.tsx` / `InstallationListPage.tsx` on the
  baseline (two `only-export-components` on untouched exports, two
  `set-state-in-effect` on the untouched edit-state sync effect) — this change
  introduces ZERO new lint errors. The repo baseline is not lint-clean; making
  it clean is out of scope for these two bugfixes.

Implementation note (BUG 1): the `ServersTable` `nodes` default is a
module-level `EMPTY_NODES` constant rather than an inline `[]`, so the
`mergeNodeOverrides` memo dependency stays stable across renders (an inline
`[]` created a fresh array each render and caused the edit-state sync effect to
re-run every render → render loop in tests).

## Notes / assumptions
- `SERVER_NODES` is intentionally retained (not deleted) because
  `installationExport.ts` (`buildInstallationExport` `servers.nodes` and the
  architecture document) and existing tests import it. The bug fix is to stop
  using it as the Servers-nodes **table** default, not to remove the constant.
  Changing the export JSON's `servers.nodes` content is out of scope for these
  two bugs and left unchanged.
- All mapped answer values are strings (the answer store is `Record<string,string>`);
  the template defaults include booleans/numbers-as-strings. The override only
  replaces values for the mapped keys and only when the user entered a non-empty
  string, so untouched structural keys keep their original typed defaults.
