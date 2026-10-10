import { describe, it, expect, beforeEach } from 'vitest';
import fc from 'fast-check';
import { authService } from './authService';

// Minimum property-test iterations mandated by the design (>= 100).
const NUM_RUNS = 100;

beforeEach(() => {
  localStorage.clear();
});

// Helper: true only when `raw` is NOT parseable as JSON. We use the real
// JSON.parse as the oracle so the generator's filter exactly matches the
// contract under test (a value is "unparseable" iff JSON.parse throws on it).
function isUnparseableJson(raw: string): boolean {
  try {
    JSON.parse(raw);
    return false; // parsed fine -> it IS valid JSON, exclude it
  } catch {
    return true; // threw -> genuinely unparseable
  }
}

// Property 3: getCurrentUser returns null on unparseable input.
// Feature: header-username-display, Property 3: For any string that is not
// valid JSON, storing it under localStorage['user'] and calling
// authService.getCurrentUser() SHALL return null without throwing.
// Validates: Requirements 4.3
describe('Feature: header-username-display, Property 3: getCurrentUser returns null on unparseable input', () => {
  it('returns null (never throws) for any non-JSON string stored under `user`', () => {
    fc.assert(
      fc.property(
        // Arbitrary strings, filtered down to those that are genuinely not
        // valid JSON. This filters out accidentally-valid JSON such as bare
        // numbers ("42"), quoted strings ('"x"'), booleans, "null", or any
        // string that happens to parse (e.g. "[]", "{}").
        fc.string().filter(isUnparseableJson),
        (raw) => {
          localStorage.setItem('user', raw);

          // Must not throw, and must resolve to null.
          let result: unknown;
          expect(() => {
            result = authService.getCurrentUser();
          }).not.toThrow();
          expect(result).toBeNull();
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });

  it('returns null for representative malformed values (examples)', () => {
    const malformed = [
      '',
      '{',
      '{"email":',
      'not json at all',
      "{'email':'x'}", // single quotes are invalid JSON
      '{unquoted: 1}',
      '[1, 2,',
      'undefined',
    ];

    for (const raw of malformed) {
      // Sanity-check that each example is indeed unparseable.
      expect(isUnparseableJson(raw)).toBe(true);
      localStorage.setItem('user', raw);
      expect(() => authService.getCurrentUser()).not.toThrow();
      expect(authService.getCurrentUser()).toBeNull();
    }
  });
});

// Arbitrary producing valid CurrentUser objects. Every field is generated so
// the round-trip (setItem(JSON.stringify(u)) -> getCurrentUser()) is exercised
// across the full shape: all string fields plus the boolean flag. Strings are
// unconstrained (including empty/unicode) since JSON.stringify/parse must
// preserve any string faithfully.
const currentUserArb = fc.record({
  id: fc.string(),
  email: fc.string(),
  first_name: fc.string(),
  last_name: fc.string(),
  role: fc.string(),
  is_email_verified: fc.boolean(),
});

// Property 2: getCurrentUser round-trip preserves the stored user.
// Feature: header-username-display, Property 2: For any valid CurrentUser
// object, writing JSON.stringify(user) to localStorage['user'] and then calling
// authService.getCurrentUser() SHALL return an object equal to the original
// user; and when no value exists under `user`, getCurrentUser() SHALL return
// null.
// Validates: Requirements 4.1, 4.2
describe('Feature: header-username-display, Property 2: getCurrentUser round-trip preserves the stored user', () => {
  it('returns an object deep-equal to the stored user for any CurrentUser', () => {
    fc.assert(
      fc.property(currentUserArb, (user) => {
        localStorage.setItem('user', JSON.stringify(user));
        expect(authService.getCurrentUser()).toEqual(user);
      }),
      { numRuns: NUM_RUNS },
    );
  });

  it('returns null when no value is stored under `user`', () => {
    // beforeEach clears localStorage, so nothing is stored under `user` here.
    expect(authService.getCurrentUser()).toBeNull();
  });
});
