# Empty server-nodes on a fresh DB, and real-data CloudStore VCF plane export

Two frontend-only bugs in the "OPCP installations" menu. BUG 1: the Servers-nodes table always rendered nine hard-coded reference rows (including `nodeUuid c6adb16d-…`) even on a brand-new database, because the merge layer treated a fixed defaults list as authoritative for row existence. BUG 2: "Generate control plane file" / "Generate data plane file" downloaded a static template verbatim, ignoring the operator's recorded answers. The fix inverts the server-node merge so stored data drives the row set (empty default → empty table), and rewrites the two plane generators to be installation-aware, async, and to override template defaults with the recorded VCF answers. Both fixes are confined to `frontend/` with no backend change.

Watch for: nothing blocking. The backend was already a pure per-installation override store returning `[]` on a fresh DB (confirmed in the plan's root-cause analysis), so BUG 1 was entirely a frontend default/merge issue; the chosen fix is minimal and correct (confirmed). `SERVER_NODES` is retained for the export's `servers.nodes` and the architecture document — intentional, documented, and out of scope (confirmed).

**Verdict**: APPROVED

## High-level view

BUG 1 is fixed at the merge seam. `mergeNodeOverrides` now takes the row set from the stored overrides rather than a fixed defaults list: matching defaults are edited in place, and overrides with no matching default are added as full rows, so an empty `defaults` yields exactly the overrides. `ServersTable` defaults its `nodes` prop to a stable module-level empty array and renders `mergeNodeOverrides(nodes, loadedOverrides)`, so a fresh DB (backend returns `{ nodes: [] }`) renders the six headers and zero data rows. Add/edit persistence and the live-retrieve flow are untouched.

BUG 2 is fixed in the export service. `generateCloudStoreVcfControlPlane` / `generateCloudStoreVcfDataPlane` became `async (installation): Promise<void>`, reuse `buildInstallationExport` to fetch the installation's `vcf`-tab answers, and build the output via `applyAnswersToTemplate`, which walks the template key set in order and overrides each mapped key with the recorded answer only when it is a non-empty trimmed string, otherwise keeping the template default. Filenames and the two-space-indent + trailing-newline formatting are unchanged.

`InstallationListPage` wires the two button handlers as async, awaits the generation, sets/clears `busyId`, and surfaces the existing success/error row-status keys — matching the pattern already used for export and architecture-document generation.

The seeded-row tests were updated rather than deleted: the preservation suite now passes `SERVER_NODES` explicitly, and a new empty-on-fresh suite asserts the table is empty when the backend has no stored nodes. New unit tests cover the merge semantics and the template-override/fallback behavior, including preserved key ordering and formatting.

<details>
<summary>Issues (2)</summary>

1. **`SERVER_NODES` retained for export (informational)** — the reference inventory still backs the export's `servers.nodes` and the architecture document, so exports/docs continue to show the nine reference rows even on a fresh DB. Documented and out of scope for these two bugs; flag only if the export's node list should also become data-driven later.
2. **Recorded suite has 11 pre-existing failures (informational)** — the recorded Vitest run was 533 passed / 11 failed, with the failures attributed to unrelated pre-existing suites and the directly relevant suites green. No action required unless a later pass wants the baseline made clean.

</details>

<details>
<summary>Details</summary>

### Stored data drives server-node row existence

`mergeNodeOverrides` was re-specified so the row set follows the stored overrides, not a fixed defaults list. It indexes overrides by `nodeUuid`, merges each matching default in place (pinning the merged row's `nodeUuid` to the default's join key), and then appends every override that matched no default as a full `ServerNode`. With an empty `defaults` the result is exactly the overrides, so a fresh database (zero stored rows) yields an empty list.

```ts
const byUuid = new Map(overrides.map((o) => [o.nodeUuid, o]));
const matched = new Set<string>();
const merged = defaults.map((d) => {
  const o = byUuid.get(d.nodeUuid);
  if (o) { matched.add(d.nodeUuid); return { ...d, ...o, nodeUuid: d.nodeUuid }; }
  return { ...d };
});
const extra = overrides.filter((o) => !matched.has(o.nodeUuid)).map(/* full ServerNode */);
return [...merged, ...extra];
```

`ServersTable` defaults the `nodes` prop to a module-level `EMPTY_NODES` constant (a stable reference so the `mergeNodeOverrides` memo and the edit-state sync effect don't re-run every render — the plan notes an inline `[]` caused a render loop in tests). On mount it loads `loadServerNodes(installationId)` into `nodesOverrides` ( `[]` on load failure), and renders `mergeNodeOverrides(nodes, nodesOverrides)`. The seeded `SERVER_NODES` import was removed from this component. Edit persistence is preserved: `handleConfirm` builds the payload from the merged rows (which now equal the stored overrides) and calls `saveServerNodes`, and the OpenStack live-retrieve flow is unchanged.

The old seeded-row behavior was not hidden by deleting tests: `ServersTable.preservation.test.tsx` now passes `nodes={SERVER_NODES}` explicitly where it needs the reference rows, and the new `ServersTable.emptyOnFreshDb.test.tsx` asserts six headers with zero data rows and no `c6adb16d-…` row when the backend returns `{ nodes: [] }`, plus exactly one row when it returns one stored node.

### Installation-aware, real-data plane generation

Both generators are now `async (installation: Installation): Promise<void>`. They call `buildInstallationExport(installation)` (which already fetches per-tab answers), read `data.tabs['vcf'] ?? {}`, and build the output through `applyAnswersToTemplate(template, keyMap, vcfAnswers)`. That helper iterates `Object.entries(template)` so the template's exact key set and ordering are preserved, and overrides a mapped key only when the recorded answer is a non-empty trimmed string — otherwise the template default (and its original type) is kept.

```ts
output[key] = typeof answer === 'string' && answer.trim() ? answer : defaultValue;
```

The two mappings (`CONTROLPLANE_KEY_TO_ROW_ID`, `DATAPLANE_KEY_TO_ROW_ID`) are explicit `Record<templateKey, rowId>` data. Spot-checking against `configs.ts` confirms the row ids are real VCF-tab rows whose `questionPrimary` equals the template key (e.g. `vcf-mgmt-dns-server` → `dns_server`, `vcf-wld-workload-domain-num` → `workload_domain_num`), and a parallel pre-existing `MANAGEMENT_KEY_TO_ROW_ID` in `vcfDomainTemplates.ts` mirrors the same pairing. Filenames (`CLOUDSTORE_VCF_CONTROLPLANE_FILENAME` / `…_DATAPLANE_FILENAME`) and the `` `${JSON.stringify(output, null, 2)}\n` `` formatting are unchanged. Test coverage asserts the override, the fallback for unmapped/empty-answer keys, verbatim-template output when no answers exist, preserved key ordering, trailing newline, two-space indent, the unchanged filename, and that every mapping key exists in its template.

### InstallationListPage handlers

`handleGenerateControlPlane` and `handleGenerateDataPlane` are async, set `busyId`, `clearStatus`, `await` the matching generator, and surface row status — success via `prereq.installations.generateControlPlane.success` / `generateDataPlane.success`, failure via the shared `prereq.installations.generatePlane.error`. All three i18n keys exist in both `fr` and `en`. The buttons call `() => void handleGenerate…(installation)` and stay disabled while `busyId === installation.id`, matching the export and architecture-document handlers. No floating-promise or async-handler lint regressions were recorded.

### Verification evidence

Recorded in `.agents/tasks/plan.md` (run from `frontend/` under WSL): `npm run test -- --run` → 533 passed / 11 failed across 87 files, with the 11 failures attributed to pre-existing unrelated suites (verified by stashing the change and reproducing 10/11 on the baseline; the 11th is a parallel-worker timeout in an untouched file). Directly relevant suites all green: `serverNodeOverrides.test.ts` 4/4, `ServersTable.emptyOnFreshDb` 2/2, `installationExport.controlplane.test.ts` 6/6, existing `ServersTable.*` and `installationExport.test.ts` green. `npm run build` (`tsc -b && vite build`) succeeded. `npm run lint` introduced zero new errors (the repo baseline carries 45 pre-existing errors / 4 warnings; the touched files show only the four pre-existing ones). Per the task instructions these suites were not re-run; the recorded evidence is present and specific, and the narrow spot-checks performed here (mapping row ids against `configs.ts`, i18n key existence, absence of the seeded UUID as a table driver) corroborate it.

</details>

<details>
<summary>File map</summary>

- `frontend/src/components/prerequisites/serverNodeOverrides.ts` — merge semantics inverted so stored data drives row existence.
- `frontend/src/components/prerequisites/ServersTable.tsx` — `nodes` prop defaults to a stable empty array; seeded `SERVER_NODES` default/import removed.
- `frontend/src/services/installationExport.ts` — installation-aware async plane generators, `applyAnswersToTemplate`, and the two key→rowId mapping tables.
- `frontend/src/components/prerequisites/InstallationListPage.tsx` — async control/data-plane handlers with busy/row-status wiring.
- `frontend/src/components/prerequisites/serverNodeOverrides.test.ts` (new) — merge-semantics unit tests.
- `frontend/src/components/prerequisites/ServersTable.emptyOnFreshDb.test.tsx` (new) — empty-on-fresh-DB and stored-row rendering.
- `frontend/src/components/prerequisites/ServersTable.preservation.test.tsx` — seeded-row cases pass `SERVER_NODES` explicitly rather than relying on the default.
- `frontend/src/services/installationExport.controlplane.test.ts` (new) — plane override/fallback, formatting, and mapping-key tests.

Full diff: `git diff 4914f31 e316208`
</details>
