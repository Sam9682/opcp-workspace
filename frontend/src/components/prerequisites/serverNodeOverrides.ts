// Per-installation override layer for the Servers nodes inventory.
//
// The default inventory (`SERVER_NODES` in `serversData.ts`) is the source of
// truth for which node rows exist. Per-installation edits are stored as a set
// of overrides keyed by `nodeUuid`; `mergeNodeOverrides` layers those overrides
// over the defaults so the row set is always exactly the defaults (edit existing
// rows only, no add/remove — see requirement 2.4).

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
 * Layer per-installation overrides over the default inventory.
 *
 * For each default row, if an override with the same `nodeUuid` exists, its
 * field values replace the defaults; otherwise the default row is kept.
 * Overrides whose `nodeUuid` matches no default are ignored (defaults are
 * authoritative for row existence). The merged row's `nodeUuid` is pinned to
 * the default's `nodeUuid` (the join key), preserving the "edit existing rows
 * only" invariant.
 */
export function mergeNodeOverrides(
  defaults: ReadonlyArray<ServerNode>,
  overrides: ReadonlyArray<ServerNodeOverride>,
): ServerNode[] {
  const byUuid = new Map(overrides.map((o) => [o.nodeUuid, o]));
  return defaults.map((d) => {
    const o = byUuid.get(d.nodeUuid);
    return o ? { ...d, ...o, nodeUuid: d.nodeUuid } : { ...d };
  });
}
