/**
 * Bug condition exploration test for the frontend error surfacing.
 *
 * Spec: .kiro/specs/event-creation-failure/
 *
 * Property 1 (Bug Condition), frontend part: when the events API returns a 422
 * whose `detail` is a Pydantic error array, `extractApiError` SHALL surface a
 * clean, specific message -- it must strip the leading "Value error, " prefix
 * that Pydantic v2 adds, so the admin sees a natural, actionable reason rather
 * than the raw prefixed string or the generic "Failed to create the event."
 * fallback.
 *
 * This test encodes the EXPECTED (fixed) behavior and is EXPECTED TO FAIL on
 * the unfixed code (which returns `detail[0].msg` verbatim, prefix and all).
 * The failure confirms the missing clean/prefer behavior.
 *
 * Validates: Requirements 1.3 (2.3 after fix)
 *
 * DO NOT "fix" this test when it fails on unfixed code -- the failure IS the
 * expected outcome and documents the bug.
 */
import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { extractApiError } from './AdminEventsPage';

const FALLBACK = 'Failed to create the event.';

/** Build an axios-shaped error carrying a Pydantic 422 detail array. */
function axios422(msg: string) {
  return { response: { data: { detail: [{ msg }] } } };
}

describe('extractApiError bug condition (Pydantic prefix cleaning)', () => {
  it('cleans the "Value error, " prefix from a 422 validation message', () => {
    const err = axios422('Value error, end_date must be after start_date');

    const result = extractApiError(err, FALLBACK);

    // EXPECTED-ON-FIX: prefix stripped -> natural, specific message.
    // On unfixed code, extractApiError returns the raw prefixed string, so
    // this assertion FAILS -> confirms the bug.
    expect(result).not.toContain('Value error,');
    expect(result.toLowerCase()).toContain('end_date must be after start_date');
  });

  it('never returns the raw prefixed string for a 422 detail array', () => {
    const raw = 'Value error, start_date must be in the future';
    const err = axios422(raw);

    const result = extractApiError(err, FALLBACK);

    // On unfixed code result === raw, so this FAILS -> confirms the bug.
    expect(result).not.toBe(raw);
  });

  it('prefers the specific 422 message over the generic fallback', () => {
    const err = axios422('Value error, end_date must be after start_date');

    const result = extractApiError(err, FALLBACK);

    // Must not silently fall back to the generic banner.
    expect(result).not.toBe(FALLBACK);
  });

  // Scoped PBT: for any 422 msg with or without the Pydantic prefix, the output
  // must be the cleaned message and must never leak the "Value error, " prefix.
  it('strips the prefix for arbitrary 422 messages (property)', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 60 }).filter((s) => !s.includes('Value error,')),
        fc.boolean(),
        (core, withPrefix) => {
          const msg = withPrefix ? `Value error, ${core}` : core;
          const result = extractApiError(axios422(msg), FALLBACK);
          // Cleaned output equals the core message and never leaks the prefix.
          expect(result).not.toContain('Value error,');
          expect(result).toBe(core);
        },
      ),
      { numRuns: 50 },
    );
  });
});
