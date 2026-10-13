// Per-installation override layer for the Servers nodes inventory.
//
// Server-node rows are driven by the per-installation data persisted/retrieved
// from the backend (`prerequisitesService.loadServerNodes`), not by a fixed
// defaults list. Each stored row is an override keyed by `nodeUuid`;
// `mergeNodeOverrides` returns the row set driven by those overrides so a fresh
// database (no stored rows) renders an empty table.

import type { ServerNode } from './serversData';

/** A stored per-installation override of a node row, keyed by nodeUuid. */
export interface ServerNodeOverride {
  nodeUuid: string;
  serialNumber: string;
  instanceUuid: string;
  powerState: string;
  provisionState: string;
  remark: string;
}

/**
 * Merge per-installation overrides with an optional defaults list, with the
 * stored overrides driving which rows exist.
 *
 * For each default row, if an override with the same `nodeUuid` exists its
 * field values replace the defaults (the merged row's `nodeUuid` is pinned to
 * the default's join key). Overrides whose `nodeUuid` matches no default are
 * additionally included as full `ServerNode` rows (all six fields come from the
 * override). With an empty `defaults` list the result is therefore exactly the
 * overrides — so a fresh database (zero stored rows) yields an empty table.
 */
export function mergeNodeOverrides(
  defaults: ReadonlyArray<ServerNode>,
  overrides: ReadonlyArray<ServerNodeOverride>,
): ServerNode[] {
  const byUuid = new Map(overrides.map((o) => [o.nodeUuid, o]));
  const matched = new Set<string>();

  const merged = defaults.map((d) => {
    const o = byUuid.get(d.nodeUuid);
    if (o) {
      matched.add(d.nodeUuid);
      return { ...d, ...o, nodeUuid: d.nodeUuid };
    }
    return { ...d };
  });

  // Override rows with no matching default become full rows of their own, so
  // the stored data is authoritative for row existence.
  const extra = overrides
    .filter((o) => !matched.has(o.nodeUuid))
    .map(
      (o): ServerNode => ({
        nodeUuid: o.nodeUuid,
        serialNumber: o.serialNumber,
        instanceUuid: o.instanceUuid,
        powerState: o.powerState,
        provisionState: o.provisionState,
        remark: o.remark,
      }),
    );

  return [...merged, ...extra];
}
