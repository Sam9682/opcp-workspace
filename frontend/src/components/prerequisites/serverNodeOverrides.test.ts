import { describe, it, expect } from 'vitest';
import { mergeNodeOverrides, type ServerNodeOverride } from './serverNodeOverrides';
import type { ServerNode } from './serversData';

// ---------------------------------------------------------------------------
// BUG 1 — server-node row existence is driven by stored data, not defaults.
//
// `mergeNodeOverrides` is the merge seam the Servers-nodes table uses. With the
// fix, the stored overrides drive which rows exist: an empty defaults list +
// empty overrides must yield an empty table (fresh DB), empty defaults + N
// overrides must yield exactly those N rows, and a non-empty defaults list must
// still support editing existing rows in place.
// ---------------------------------------------------------------------------

const override = (over: Partial<ServerNodeOverride> & { nodeUuid: string }): ServerNodeOverride => ({
  serialNumber: '',
  instanceUuid: '',
  powerState: '',
  provisionState: '',
  remark: '',
  ...over,
});

const defaultNode = (over: Partial<ServerNode> & { nodeUuid: string }): ServerNode => ({
  serialNumber: '',
  instanceUuid: '',
  powerState: '',
  provisionState: '',
  remark: '',
  ...over,
});

describe('mergeNodeOverrides — stored data drives row existence', () => {
  it('returns an empty list for empty defaults and empty overrides (fresh DB)', () => {
    expect(mergeNodeOverrides([], [])).toEqual([]);
  });

  it('returns exactly the overrides as full rows when defaults are empty', () => {
    const overrides: ServerNodeOverride[] = [
      override({
        nodeUuid: 'node-1',
        serialNumber: 'SN-1',
        instanceUuid: 'inst-1',
        powerState: 'power on',
        provisionState: 'active',
        remark: 'first',
      }),
      override({
        nodeUuid: 'node-2',
        serialNumber: 'SN-2',
        powerState: 'power off',
        provisionState: 'available',
      }),
    ];

    const merged = mergeNodeOverrides([], overrides);

    expect(merged).toHaveLength(2);
    expect(merged).toEqual([
      {
        nodeUuid: 'node-1',
        serialNumber: 'SN-1',
        instanceUuid: 'inst-1',
        powerState: 'power on',
        provisionState: 'active',
        remark: 'first',
      },
      {
        nodeUuid: 'node-2',
        serialNumber: 'SN-2',
        instanceUuid: '',
        powerState: 'power off',
        provisionState: 'available',
        remark: '',
      },
    ]);
  });

  it('merges override fields in place over a matching default (edit existing row)', () => {
    const defaults: ServerNode[] = [
      defaultNode({
        nodeUuid: 'node-1',
        serialNumber: 'SN-1',
        powerState: 'power off',
        provisionState: 'available',
      }),
    ];
    const overrides: ServerNodeOverride[] = [
      override({
        nodeUuid: 'node-1',
        serialNumber: 'SN-1-edited',
        powerState: 'power on',
        provisionState: 'active',
        remark: 'edited',
      }),
    ];

    const merged = mergeNodeOverrides(defaults, overrides);

    expect(merged).toHaveLength(1);
    expect(merged[0]).toEqual({
      nodeUuid: 'node-1',
      serialNumber: 'SN-1-edited',
      instanceUuid: '',
      powerState: 'power on',
      provisionState: 'active',
      remark: 'edited',
    });
  });

  it('keeps unmatched defaults and appends overrides that match no default', () => {
    const defaults: ServerNode[] = [
      defaultNode({ nodeUuid: 'node-1', serialNumber: 'SN-1' }),
    ];
    const overrides: ServerNodeOverride[] = [
      override({ nodeUuid: 'node-2', serialNumber: 'SN-2' }),
    ];

    const merged = mergeNodeOverrides(defaults, overrides);

    expect(merged.map((n) => n.nodeUuid)).toEqual(['node-1', 'node-2']);
  });
});
