import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import {
  buildVcfDomainJson,
  MANAGEMENT_DOMAIN_TEMPLATE,
  WORKLOAD_DOMAIN_TEMPLATE,
  MANAGEMENT_KEY_TO_ROW_ID,
  WORKLOAD_KEY_TO_ROW_ID,
  type VcfDomain,
} from './vcfDomainTemplates';

// ===========================================================================
// Bugfix spec: opcp-installations-response-fields-editable (task 2)
// Property 2: Preservation — VCF JSON structure and type coercion are unchanged.
//
// This bugfix only relaxes the frontend/backend authorization gate; it does NOT
// touch buildVcfDomainJson. These property tests pin the VCF overlay behavior
// OBSERVED on the UNFIXED code so it is provably unchanged after the fix.
//
// The properties asserted, for BOTH the management and workload domains and for
// arbitrary generated `answers` maps:
//   1. Key set preserved: output keys == template keys exactly (no key added or
//      dropped by the overlay).
//   2. Non-customer defaults preserved: keys NOT backed by a customer row (e.g.
//      `debug`, `openstack_*`, `pairing_source`, `dns_create_records`, `lacp`)
//      always keep their exact template default regardless of the answers map.
//   3. Overlay of non-empty mapped answers: a mapped key with a non-empty
//      (after trim) answer is overridden by that answer, coerced to the
//      template value's JSON type; an empty/whitespace/absent answer keeps the
//      template default.
//   4. JSON type coercion preserved: boolean template values stay boolean
//      ("true"/"false" -> true/false, other text -> template default);
//      string template values (including quoted numerics like VLAN ids/ranges)
//      stay strings verbatim.
//
// EXPECTED OUTCOME on unfixed code: PASS (baseline to preserve).
//
// Validates: Requirements 3.3, 3.4
// ===========================================================================

const NUM_RUNS = 100;

type JsonValue = string | number | boolean;

const DOMAINS: ReadonlyArray<{
  domain: VcfDomain;
  template: Record<string, JsonValue>;
  keyToRowId: Record<string, string>;
}> = [
  {
    domain: 'management',
    template: MANAGEMENT_DOMAIN_TEMPLATE,
    keyToRowId: MANAGEMENT_KEY_TO_ROW_ID,
  },
  {
    domain: 'workload',
    template: WORKLOAD_DOMAIN_TEMPLATE,
    keyToRowId: WORKLOAD_KEY_TO_ROW_ID,
  },
];

// Reference implementation of the expected overlay + coercion, written
// independently of the production code so the property compares two derivations
// rather than restating the code under test. This mirrors the OBSERVED unfixed
// behavior (empty-after-trim answers are ignored; booleans coerce true/false,
// otherwise keep default; everything else is copied verbatim as a string).
function expectedOverlay(
  template: Record<string, JsonValue>,
  keyToRowId: Record<string, string>,
  answers: Record<string, string>,
): Record<string, JsonValue> {
  const out: Record<string, JsonValue> = { ...template };
  for (const [key, rowId] of Object.entries(keyToRowId)) {
    const raw = answers[rowId];
    if (raw === undefined || raw.trim() === '') continue;
    const templateValue = template[key];
    if (typeof templateValue === 'boolean') {
      const normalized = raw.trim().toLowerCase();
      if (normalized === 'true') out[key] = true;
      else if (normalized === 'false') out[key] = false;
      else out[key] = templateValue;
    } else {
      out[key] = raw;
    }
  }
  return out;
}

// Build a generator that draws an arbitrary `answers` map keyed by the domain's
// real row ids (plus occasional unmapped row ids, which must be ignored). Values
// include empty/whitespace strings, "true"/"false" (mixed case), quoted numeric
// strings, and arbitrary text so both the overlay guard and the boolean/string
// coercion branches are exercised.
function answersArb(keyToRowId: Record<string, string>): fc.Arbitrary<Record<string, string>> {
  const rowIds = Object.values(keyToRowId);
  const valueArb = fc.oneof(
    fc.constantFrom('', '   ', '\t', 'true', 'false', 'TRUE', 'False', 'tRuE'),
    fc.constantFrom('2197', '10.105.46.0/24', '0', '1'),
    fc.string(),
  );
  return fc
    .array(fc.tuple(fc.constantFrom(...rowIds, 'unmapped-row-x', 'unmapped-row-y'), valueArb), {
      maxLength: rowIds.length + 2,
    })
    .map((pairs) => Object.fromEntries(pairs));
}

describe.each(DOMAINS)(
  'Property 2 (preservation): buildVcfDomainJson keeps VCF structure + type coercion — $domain domain',
  ({ domain, template, keyToRowId }) => {
    const templateKeys = Object.keys(template).sort();
    // Keys that are NOT backed by a customer row -> must always keep the default.
    const nonCustomerKeys = templateKeys.filter((k) => !(k in keyToRowId));

    it('emits exactly the template key set for any answers map', () => {
      fc.assert(
        fc.property(answersArb(keyToRowId), (answers) => {
          const out = buildVcfDomainJson(domain, answers);
          expect(Object.keys(out).sort()).toEqual(templateKeys);
        }),
        { numRuns: NUM_RUNS },
      );
    });

    it('keeps non-customer keys (debug, openstack_*, pairing_source, ...) at their template default', () => {
      fc.assert(
        fc.property(answersArb(keyToRowId), (answers) => {
          const out = buildVcfDomainJson(domain, answers);
          for (const key of nonCustomerKeys) {
            expect(out[key]).toBe(template[key]);
          }
        }),
        { numRuns: NUM_RUNS },
      );
    });

    it('overlays non-empty mapped answers and preserves JSON types (equals the reference overlay)', () => {
      fc.assert(
        fc.property(answersArb(keyToRowId), (answers) => {
          const out = buildVcfDomainJson(domain, answers);
          const expected = expectedOverlay(template, keyToRowId, answers);
          expect(out).toEqual(expected);

          // Type coercion is preserved key-by-key: booleans stay boolean, and
          // string template values (including quoted numeric fields) stay string.
          for (const key of templateKeys) {
            if (typeof template[key] === 'boolean') {
              expect(typeof out[key]).toBe('boolean');
            } else if (typeof template[key] === 'string') {
              expect(typeof out[key]).toBe('string');
            }
          }
        }),
        { numRuns: NUM_RUNS },
      );
    });

    it('ignores empty / whitespace-only answers (key stays at template default)', () => {
      const mappedKeys = Object.keys(keyToRowId);
      fc.assert(
        fc.property(
          fc.constantFrom('', ' ', '   ', '\t', '\n'),
          fc.constantFrom(...mappedKeys),
          (blank, key) => {
            const rowId = keyToRowId[key];
            const out = buildVcfDomainJson(domain, { [rowId]: blank });
            expect(out[key]).toBe(template[key]);
          },
        ),
        { numRuns: NUM_RUNS },
      );
    });

    it('overrides a string-typed mapped key verbatim with a non-empty answer', () => {
      const stringMappedKeys = Object.keys(keyToRowId).filter(
        (k) => typeof template[k] === 'string',
      );
      // Some domains may have only string-typed customer rows; guard the sample.
      if (stringMappedKeys.length === 0) return;
      fc.assert(
        fc.property(
          fc.constantFrom(...stringMappedKeys),
          fc.string({ minLength: 1 }).filter((s) => s.trim() !== ''),
          (key, value) => {
            const rowId = keyToRowId[key];
            const out = buildVcfDomainJson(domain, { [rowId]: value });
            expect(out[key]).toBe(value);
            expect(typeof out[key]).toBe('string');
          },
        ),
        { numRuns: NUM_RUNS },
      );
    });

    it('coerces a boolean-typed mapped key: "true"/"false" flip, other text keeps default', () => {
      const boolMappedKeys = Object.keys(keyToRowId).filter(
        (k) => typeof template[k] === 'boolean',
      );
      // Not every domain has a customer-editable boolean row; skip if none.
      if (boolMappedKeys.length === 0) return;
      fc.assert(
        fc.property(
          fc.constantFrom(...boolMappedKeys),
          fc.string(),
          (key, raw) => {
            const rowId = keyToRowId[key];
            const out = buildVcfDomainJson(domain, { [rowId]: raw });
            const normalized = raw.trim().toLowerCase();
            if (normalized === '') {
              expect(out[key]).toBe(template[key]);
            } else if (normalized === 'true') {
              expect(out[key]).toBe(true);
            } else if (normalized === 'false') {
              expect(out[key]).toBe(false);
            } else {
              expect(out[key]).toBe(template[key]);
            }
            expect(typeof out[key]).toBe('boolean');
          },
        ),
        { numRuns: NUM_RUNS },
      );
    });
  },
);
