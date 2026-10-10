import { describe, it, expect } from 'vitest';
import type { QuestionFormConfig, QuestionRow } from './types';
import { vcfConfig } from './configs';

// Content assertions for the real VCF customer-input parameters.
// These complement the structural property tests in configs.test.ts by
// pinning down the concrete section ids, the CloudStore-provided params
// (now surfaced as optional, no-customer-input rows), the optional-vs-mandatory
// split, and a handful of known exampleValue/commentsHint mappings from the
// VCF customer workbook.
// _Requirements: 1.1, 1.2, 2.2, 2.3, 2.5, 3.1_

// Collect every row across all sections of a QuestionFormConfig.
const allRows = (config: QuestionFormConfig): QuestionRow[] =>
  config.sections.flatMap((section) => section.rows);

// Find a single row by id across all sections.
const findRow = (config: QuestionFormConfig, rowId: string): QuestionRow | undefined =>
  allRows(config).find((row) => row.id === rowId);

describe('vcfConfig content', () => {
  // Rows are grouped into the Management/Workload sub-sections that reflect
  // the workbook structure (Hosts, Network, DNS, Auth, Secrets, Misc, then the
  // Workload domain General/Network groups).
  it('exposes exactly the expected section ids in order', () => {
    const expectedSectionIds = [
      'vcf-mgmt-hosts',
      'vcf-mgmt-network',
      'vcf-mgmt-dns',
      'vcf-mgmt-auth',
      'vcf-mgmt-secrets',
      'vcf-mgmt-misc',
      'vcf-wld-general',
      'vcf-wld-network',
    ];
    expect(vcfConfig.sections.map((s) => s.id)).toEqual(expectedSectionIds);
  });

  // The CloudStore-provided params (node_uuids / bootstrap_node_uuids) are now
  // surfaced as rows, with the parameter name in questionPrimary. They carry a
  // domain-prefixed row id so they stay unique page-wide.
  it('surfaces the CloudStore-provided params as parameter-named rows', () => {
    expect(findRow(vcfConfig, 'vcf-mgmt-node-uuids')?.questionPrimary).toBe('node_uuids (management)');
    expect(findRow(vcfConfig, 'vcf-mgmt-bootstrap-node-uuids')?.questionPrimary).toBe(
      'bootstrap_node_uuids',
    );
    expect(findRow(vcfConfig, 'vcf-wld-node-uuids')?.questionPrimary).toBe('node_uuids (workload)');
  });

  // mandatory flags reflect whether the deployment requires customer input.
  // Optional rows: the four secrets rows, the ESXi setup script, and the three
  // CloudStore-provided host params (no customer input required). Every other
  // row is mandatory.
  describe('mandatory flags', () => {
    const optionalRowIds = [
      'vcf-mgmt-node-uuids',
      'vcf-mgmt-bootstrap-node-uuids',
      'vcf-mgmt-master-password',
      'vcf-mgmt-esxi-root-password',
      'vcf-mgmt-appliance-password',
      'vcf-mgmt-appliance-xapikey',
      'vcf-mgmt-esxi-setup-script',
      'vcf-wld-node-uuids',
    ];

    it.each(optionalRowIds)('row "%s" is optional (mandatory=false)', (rowId) => {
      const row = findRow(vcfConfig, rowId);
      expect(row, `row ${rowId} should exist`).toBeDefined();
      expect(row!.mandatory).toBe(false);
    });

    it('marks exactly the known optional rows as optional', () => {
      const actualOptional = allRows(vcfConfig)
        .filter((row) => row.mandatory === false)
        .map((row) => row.id)
        .sort();
      expect(actualOptional).toEqual([...optionalRowIds].sort());
    });

    it('marks every other row as mandatory (mandatory=true)', () => {
      const optionalSet = new Set(optionalRowIds);
      const others = allRows(vcfConfig).filter((row) => !optionalSet.has(row.id));
      for (const row of others) {
        expect(row.mandatory, `row ${row.id} should be mandatory`).toBe(true);
      }
    });
  });

  // Spot-check known exampleValue (the workbook "Value") and commentsHint (the
  // "Example:"/notes) mappings drawn from the VCF customer workbook.
  describe('known example/hint mappings', () => {
    it('sets vcf-mgmt-network-name exampleValue to the workbook value', () => {
      expect(findRow(vcfConfig, 'vcf-mgmt-network-name')?.exampleValue).toBe(
        'VCF-MGT (beeb7852-2ae5-47eb-bc87-eaa508c8d49c)',
      );
    });

    it('sets vcf-mgmt-dns-zone exampleValue to the workbook value', () => {
      expect(findRow(vcfConfig, 'vcf-mgmt-dns-zone')?.exampleValue).toBe('cs01.mdc.ma');
    });

    it('sets vcf-mgmt-master-password commentsHint with the @!#$%?^ charset note', () => {
      const hint = findRow(vcfConfig, 'vcf-mgmt-master-password')?.commentsHint;
      expect(hint).toBeDefined();
      expect(hint).toContain('@!#$%?^');
    });

    it('sets vcf-mgmt-esxi-setup-script commentsHint mentioning Broadcom', () => {
      const hint = findRow(vcfConfig, 'vcf-mgmt-esxi-setup-script')?.commentsHint;
      expect(hint).toBeDefined();
      expect(hint).toContain('Broadcom');
    });
  });
});