/**
 * Preservation property tests for `extractApiError`.
 *
 * Spec: .kiro/specs/event-creation-failure/
 *
 * Property 2 (Preservation): for any input where the bug condition does NOT
 * hold, the fixed code SHALL produce the same result as the original code.
 *
 * Methodology: OBSERVATION-FIRST. These assertions capture the ACTUAL behavior
 * of the UNFIXED `extractApiError`, so they MUST PASS on the unfixed code and
 * establish the baseline the fix must preserve.
 *
 * Observed baseline (unfixed code):
 *   - detail is a string           => returns the string verbatim.
 *   - detail.error.message present => returns that nested business-error message.
 *   - nothing usable present       => returns the generic fallback.
 * The 422 `detail` array cleaning behavior is intentionally NOT asserted here;
 * that is the bug-condition path covered by the exploration test.
 *
 * Validates: Requirements 3.6 (preservation of business-error and fallback
 * handling for extractApiError).
 */
import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { extractApiError } from './AdminEventsPage';

const FALLBACK = 'Failed to create the event.';

/** Axios-shaped error carrying a nested business-error message. */
function axiosBusinessError(message: string) {
  return { response: { data: { detail: { error: { message } } } } };
}

/** Axios-shaped error carrying a plain string detail. */
function axiosStringDetail(detail: string) {
  return { response: { data: { detail } } };
}

describe('extractApiError preservation (non-bug-condition behavior)', () => {
  it('returns the nested error.message for a business error', () => {
    const err = axiosBusinessError('You are already registered for this event');
    expect(extractApiError(err, FALLBACK)).toBe(
      'You are already registered for this event',
    );
  });

  it('returns a plain string detail verbatim', () => {
    const err = axiosStringDetail('Some plain detail');
    expect(extractApiError(err, FALLBACK)).toBe('Some plain detail');
  });

  it('returns the generic fallback when nothing usable is present', () => {
    expect(extractApiError({}, FALLBACK)).toBe(FALLBACK);
    expect(extractApiError({ response: {} }, FALLBACK)).toBe(FALLBACK);
    expect(extractApiError({ response: { data: {} } }, FALLBACK)).toBe(FALLBACK);
    expect(extractApiError(undefined, FALLBACK)).toBe(FALLBACK);
  });

  // Property: any non-empty nested business message is surfaced unchanged.
  it('surfaces arbitrary nested business messages unchanged (property)', () => {
    fc.assert(
      fc.property(fc.string({ minLength: 1, maxLength: 80 }), (message) => {
        const result = extractApiError(axiosBusinessError(message), FALLBACK);
        expect(result).toBe(message);
      }),
      { numRuns: 50 },
    );
  });

  // Property: with no detail whatsoever, the fallback is always returned.
  it('always returns the fallback when no detail is present (property)', () => {
    fc.assert(
      fc.property(fc.string({ minLength: 1, maxLength: 40 }), (fallback) => {
        expect(extractApiError({ response: { data: {} } }, fallback)).toBe(fallback);
      }),
      { numRuns: 50 },
    );
  });
});
