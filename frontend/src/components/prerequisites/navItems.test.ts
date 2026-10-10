import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { PREREQ_NAV_ITEMS } from './types';

// Minimum property-test iterations mandated by the design (>= 100).
const NUM_RUNS = 100;

// A well-formed prerequisites route is always `/prerequisites/{slug}` where the
// slug is a lowercase, digit-and-hyphen kebab token.
const WELL_FORMED_ROUTE = /^\/prerequisites\/[a-z0-9-]+$/;

// Feature: opcp-prerequisites-tabs, Property 2: Every navigation route is well-formed
// For any entry in PREREQ_NAV_ITEMS, the labelKey is a non-empty string and the
// route matches `/prerequisites/{slug}`.
// Validates: Requirements 1.2
describe('Property 2: every navigation route is well-formed', () => {
  it('has a non-empty labelKey and a /prerequisites/{slug} route for every entry', () => {
    fc.assert(
      fc.property(fc.constantFrom(...PREREQ_NAV_ITEMS), (item) => {
        expect(typeof item.labelKey).toBe('string');
        expect(item.labelKey.length).toBeGreaterThan(0);
        expect(item.route).toMatch(WELL_FORMED_ROUTE);
      }),
      { numRuns: NUM_RUNS },
    );
  });
});
