import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import type { FormConfig, QuestionFormConfig } from './types';
import {
  cloudStoreConfig,
  opcpCoreConfig,
  landingZoneConfig,
  networkChecklistConfig,
  coreControlPlaneConfig,
  cloudStoreQuestionConfig,
  vcfConfig,
} from './configs';

// Both FormConfig and QuestionFormConfig expose row ids at
// `sections[].rows[].id`, so a single union-typed helper can collect ids
// from either shape in document order.
type AnyRowConfig = FormConfig | QuestionFormConfig;

// Collect every row id in a config, in document order.
const allRowIds = (config: AnyRowConfig): string[] =>
  config.sections.flatMap((section) => section.rows.map((row) => row.id));

// Find a single row by id across all sections of a config.
const findRow = (config: FormConfig, rowId: string) =>
  allRowIds(config).includes(rowId)
    ? config.sections.flatMap((s) => s.rows).find((r) => r.id === rowId)
    : undefined;

describe('cloudStoreConfig', () => {
  // The seven reference sub-sections from Requirement 4, with their
  // expected ids and the row ids each must expose.
  // _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_
  const expectedSections: Array<{ id: string; title: string; rowIds: string[] }> = [
    {
      id: 'network-configuration',
      title: 'Configuration réseau',
      rowIds: ['network-name', 'subnet-name', 'subnet-cidr', 'gateway-ip', 'vlan-id', 'dhcp-range'],
    },
    {
      id: 'server-standalone',
      title: 'Serveur (Standalone)',
      rowIds: [
        'server-role',
        'server-hostname',
        'server-ip-address',
        'server-node-uuid',
        'server-ingress-vip',
        'server-cluster-3-nodes',
        'server-cluster-endpoint-vip',
      ],
    },
    {
      id: 'dns-configuration',
      title: 'Configuration DNS',
      rowIds: [
        'dns-zone-name',
        'dns-delegation-target',
        'dns-primary-server-ip',
        'dns-fallback-server-ip',
      ],
    },
    {
      id: 'ntp-configuration',
      title: 'Configuration NTP',
      rowIds: ['ntp-server-1-ip', 'ntp-server-1-dns-name', 'ntp-server-2-ip', 'ntp-server-2-dns-name'],
    },
    {
      id: 'security-certificates',
      title: 'Sécurité & Certificats',
      rowIds: ['root-ca-certificate'],
    },
    {
      id: 'backup-s3',
      title: 'Sauvegarde (S3)',
      rowIds: [
        'backup-enabled',
        'backup-s3-endpoint-url',
        'backup-s3-region',
        'backup-s3-bucket',
        'backup-s3-access-key',
        'backup-s3-secret-key',
        'backup-path',
      ],
    },
    {
      id: 'client-side-actions',
      title: 'Actions côté client',
      rowIds: [
        'client-network-subnet-created',
        'client-networks-wired-rack-edge',
        'client-bastion-host-provisioned',
        'client-bastion-access-provided',
        'client-dns-zone-delegation-configured',
        'client-s3-backup-bucket-reachable',
      ],
    },
  ];

  it('exposes exactly the seven reference sub-sections in order', () => {
    expect(cloudStoreConfig.sections).toHaveLength(7);
    expect(cloudStoreConfig.sections.map((s) => s.id)).toEqual(
      expectedSections.map((s) => s.id),
    );
    expect(cloudStoreConfig.sections.map((s) => s.title)).toEqual(
      expectedSections.map((s) => s.title),
    );
  });

  it.each(expectedSections)('sub-section "$title" exposes the expected row ids', (expected) => {
    const section = cloudStoreConfig.sections.find((s) => s.id === expected.id);
    expect(section, `sub-section ${expected.id} should exist`).toBeDefined();
    expect(section!.rows.map((r) => r.id)).toEqual(expected.rowIds);
  });

  it('sets the S3 backup-path default value to "cs-backups"', () => {
    const backupPath = findRow(cloudStoreConfig, 'backup-path');
    expect(backupPath).toBeDefined();
    expect(backupPath!.defaultValue).toBe('cs-backups');
  });
});

// Feature: opcp-prerequisites-tabs, Property 12: Row ids are unique within each page.
describe('row id uniqueness', () => {
  // Row ids must be unique within each page so persisted state keys never collide.
  // Covers the four new QuestionFormConfig pages plus the legacy FormConfig
  // configs, which still exist in configs.ts and are harmless to keep here.
  const configs: Array<{ name: string; config: AnyRowConfig }> = [
    { name: 'cloudStoreConfig', config: cloudStoreConfig },
    { name: 'opcpCoreConfig', config: opcpCoreConfig },
    { name: 'landingZoneConfig', config: landingZoneConfig },
    { name: 'networkChecklistConfig', config: networkChecklistConfig },
    { name: 'coreControlPlaneConfig', config: coreControlPlaneConfig },
    { name: 'cloudStoreQuestionConfig', config: cloudStoreQuestionConfig },
    { name: 'vcfConfig', config: vcfConfig },
  ];

  it.each(configs)('$name has unique row ids', ({ config }) => {
    const ids = allRowIds(config);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

// Feature: opcp-prerequisites-tabs, Property 12: Row ids are unique within each page.
// fast-check formulation that quantifies over the config objects and asserts,
// for every drawn config, that the set of row ids has the same size as the
// full (document-order) list of row ids. This complements the deterministic
// it.each above (kept for readable per-config diagnostics) with >= 100 runs.
describe('row id uniqueness (property)', () => {
  const allConfigs: AnyRowConfig[] = [
    cloudStoreConfig,
    opcpCoreConfig,
    landingZoneConfig,
    networkChecklistConfig,
    coreControlPlaneConfig,
    cloudStoreQuestionConfig,
    vcfConfig,
  ];

  it('every page has row ids that are unique within that page', () => {
    fc.assert(
      fc.property(fc.constantFrom(...allConfigs), (config) => {
        const ids = allRowIds(config);
        expect(new Set(ids).size).toBe(ids.length);
      }),
      { numRuns: 100 },
    );
  });
});

// Unit tests for the four QuestionFormConfig scaffolds (task 2.3).
// _Requirements: 7.1, 7.2_
describe('question config scaffolding', () => {
  const questionConfigs: Array<{ name: string; config: QuestionFormConfig }> = [
    { name: 'networkChecklistConfig', config: networkChecklistConfig },
    { name: 'coreControlPlaneConfig', config: coreControlPlaneConfig },
    { name: 'cloudStoreQuestionConfig', config: cloudStoreQuestionConfig },
    { name: 'vcfConfig', config: vcfConfig },
  ];

  it.each(questionConfigs)('$name exists and has at least one section', ({ config }) => {
    expect(config).toBeDefined();
    expect(config.sections.length).toBeGreaterThan(0);
  });

  it.each(questionConfigs)('$name has at least one row per section', ({ config }) => {
    for (const section of config.sections) {
      expect(section.rows.length, `section ${section.id} should have rows`).toBeGreaterThan(0);
    }
  });

  it.each(questionConfigs)('$name rows all have non-empty id and questionPrimary', ({ config }) => {
    const rows = config.sections.flatMap((section) => section.rows);
    for (const row of rows) {
      expect(row.id.trim().length, `row id "${row.id}" should be non-empty`).toBeGreaterThan(0);
      expect(
        row.questionPrimary.trim().length,
        `row ${row.id} questionPrimary should be non-empty`,
      ).toBeGreaterThan(0);
    }
  });
});
