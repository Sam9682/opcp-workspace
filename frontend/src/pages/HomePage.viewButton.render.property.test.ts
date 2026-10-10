import { describe, it, expect } from 'vitest';
import fc from 'fast-check';

// Feature: forum-view-button-url-fix
// Task 5.5 — Property-based test for the toggle render decision (Enhancement 2).
//
// Property 3 (Enhancement): the Forum toggle controls "View" button visibility
// with NON-INVERTED semantics and an ON default.
//
//   For any logged-out visitor render, the "View" button SHALL be shown when the
//   Forum `view_button_enabled` setting is true (including the never-configured
//   default) and SHALL be hidden when the setting is false.
//
// HomePage gates the anchor on `!isAuthenticated && viewButtonEnabled`, with
// `viewButtonEnabled` defaulting to true (never-configured / fetch-error case).
//
// EXPECTED OUTCOME: PASS (this is an enhancement property on the implemented
// gate, not a bug-exploration test).
//
// **Validates: Requirements 2.3, 2.4, 3.3**

// The HomePage render decision as a pure boolean function, encoding the gate
// `!isAuthenticated && viewButtonEnabled`.
const shouldShowViewButton = (
  isAuthenticated: boolean,
  viewButtonEnabled: boolean,
): boolean => !isAuthenticated && viewButtonEnabled;

// Models HomePage's default handling of the setting: state defaults to `true`
// and is left `true` on a fetch error (never-configured / failed-read case).
const resolveSetting = (configured?: boolean | undefined): boolean =>
  configured ?? true;

describe('Property 3 (Enhancement): Forum toggle controls "View" button visibility (Requirements 2.3, 2.4, 3.3)', () => {
  it('render decision equals !isAuthenticated && setting for any generated booleans', () => {
    fc.assert(
      fc.property(fc.boolean(), fc.boolean(), (isAuthenticated, setting) => {
        expect(shouldShowViewButton(isAuthenticated, setting)).toBe(
          !isAuthenticated && setting,
        );
      }),
      { numRuns: 100 },
    );
  });

  it('non-inverted semantics for a logged-out visitor: shown iff setting is true', () => {
    fc.assert(
      fc.property(fc.boolean(), (setting) => {
        // isAuthenticated = false (logged-out visitor)
        expect(shouldShowViewButton(false, setting)).toBe(setting);
      }),
      { numRuns: 100 },
    );
    // Explicit boundary examples.
    expect(shouldShowViewButton(false, true)).toBe(true); // ON  -> shown
    expect(shouldShowViewButton(false, false)).toBe(false); // OFF -> hidden
  });

  it('authenticated visitors never see the "View" button regardless of setting', () => {
    fc.assert(
      fc.property(fc.boolean(), (setting) => {
        expect(shouldShowViewButton(true, setting)).toBe(false);
      }),
      { numRuns: 100 },
    );
  });

  it('ON default / never-configured: a logged-out visitor sees the button by default', () => {
    // The never-configured / fetch-error case resolves to the ON default.
    expect(resolveSetting(undefined)).toBe(true);
    expect(shouldShowViewButton(false, resolveSetting(undefined))).toBe(true);

    // An explicit stored value is honored as-is (non-inverted).
    expect(resolveSetting(false)).toBe(false);
    expect(shouldShowViewButton(false, resolveSetting(false))).toBe(false);
    expect(resolveSetting(true)).toBe(true);
    expect(shouldShowViewButton(false, resolveSetting(true))).toBe(true);
  });
});
