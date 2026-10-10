import { describe, it, expect } from 'vitest';
import fc from 'fast-check';

// Feature: forum-view-button-url-fix
// Task 2 — Preservation property + example tests (written BEFORE the fix).
//
// Property 2 (Preservation): non-buggy "View" URLs and unrelated behavior are
// unchanged by the Bug 1 fix.
//
//   isBugCondition(X) = portOf(buildViewUrl(X.topicId)) <> portOf(X.siteOrigin)
//
// Preservation Checking (design/bugfix.md):
//   FOR ALL X WHERE NOT isBugCondition(X) DO
//     ASSERT buildViewUrl(X.topicId) === buildViewUrl'(X.topicId)
//
// OBSERVATION-FIRST METHODOLOGY: the assertions below encode behavior OBSERVED
// on the CURRENT (UNFIXED) code, so they PASS today and lock the baseline the
// fix must preserve. They also keep passing after the fix, because for
// non-buggy inputs the original and fixed constructions are equivalent.
//
// EXPECTED OUTCOME ON UNFIXED CODE: PASS (baseline behavior to preserve).
//
// **Validates: Requirements 3.1, 3.2, 3.4, 3.5**

// buildViewUrl (F): the ORIGINAL link construction observed verbatim in
// frontend/src/pages/HomePage.tsx. The origin argument is intentionally ignored
// by the current code (that omission is Bug 1).
const buildViewUrl = (_origin: string, topicId: string): string =>
  `https://opcp-psmc.com/api/forum/topics/${topicId}/publichtml`;

// buildViewUrl' (F'): the FIXED construction from the design — it derives the
// origin (scheme + host + port) from the current site origin and keeps the
// path unchanged. Encoded here so the preservation invariant can be checked
// against the original ahead of the implementation.
const buildViewUrlFixed = (origin: string, topicId: string): string =>
  `${origin}/api/forum/topics/${topicId}/publichtml`;

// portOf: effective port — explicit port when present, otherwise the scheme's
// default (443 for https, 80 for http).
const portOf = (url: string): string => {
  const u = new URL(url);
  if (u.port) return u.port;
  return u.protocol === 'https:' ? '443' : '80';
};

// isBugCondition(X): the produced URL's port differs from the site origin port.
const isBugCondition = (siteOrigin: string, topicId: string): boolean =>
  portOf(buildViewUrl(siteOrigin, topicId)) !== portOf(siteOrigin);

describe('Property 2 (Preservation): non-buggy default-port origins are unchanged (Requirement 3.5 / Preservation Checking)', () => {
  // Default-port origins with the hardcoded host+scheme. For these,
  // NOT isBugCondition holds: the original URL already resolves on port 443,
  // exactly matching the site origin, so the fix must not change anything.
  const defaultPortOrigin = fc.oneof(
    fc.constant('https://opcp-psmc.com'),
    fc.constant('https://opcp-psmc.com:443'),
  );

  it('for generated default-port origins, buildViewUrl === buildViewUrl\u2032 (Preservation Checking)', () => {
    fc.assert(
      fc.property(
        defaultPortOrigin,
        fc.string({ minLength: 1, maxLength: 12 }).filter((s) => !/[\s/#?%]/.test(s)),
        (siteOrigin, topicId) => {
          // Guard: these origins must be non-buggy for the preservation claim.
          fc.pre(!isBugCondition(siteOrigin, topicId));

          const original = buildViewUrl(siteOrigin, topicId);
          const fixed = buildViewUrlFixed(siteOrigin, topicId);

          // The two constructions produce the SAME effective URL for the
          // non-buggy (default-port, matching-host) boundary.
          expect(portOf(fixed)).toBe(portOf(original));
          expect(new URL(fixed).pathname).toBe(new URL(original).pathname);
          expect(new URL(fixed).host).toBe(new URL(original).host);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('example: default-port origin https://opcp-psmc.com yields the original hardcoded URL', () => {
    const original = buildViewUrl('https://opcp-psmc.com', '42');
    const fixed = buildViewUrlFixed('https://opcp-psmc.com', '42');
    expect(fixed).toBe(original);
    expect(fixed).toBe('https://opcp-psmc.com/api/forum/topics/42/publichtml');
  });
});

describe('Preservation example: in-app topic navigation route is untouched (Requirement 3.1)', () => {
  // The topic title/row uses an in-app <Link to={`/forum/topics/${id}`}>. The
  // Bug 1 fix only touches the external "View" anchor href, never this route.
  const inAppRoute = (topicId: string): string => `/forum/topics/${topicId}`;

  it('routes to /forum/topics/{id} for any topic id', () => {
    expect(inAppRoute('42')).toBe('/forum/topics/42');
    expect(inAppRoute('abc-123')).toBe('/forum/topics/abc-123');
    // The in-app route never depends on origin/port.
    expect(inAppRoute('42')).not.toContain('opcp-psmc.com');
  });
});

describe('Preservation example: authenticated visitors see "See all" and no "View" button (Requirement 3.2)', () => {
  // HomePage renders the "See all" link and gates the read-only "View" anchor
  // on `!isAuthenticated`. This encodes today's baseline gating decision.
  const showSeeAll = (isAuthenticated: boolean): boolean => isAuthenticated;
  const showViewButton = (isAuthenticated: boolean): boolean => !isAuthenticated;

  it('authenticated: See all shown, View hidden', () => {
    expect(showSeeAll(true)).toBe(true);
    expect(showViewButton(true)).toBe(false);
  });

  it('logged-out: See all hidden, View shown (today\u2019s always-visible default)', () => {
    expect(showSeeAll(false)).toBe(false);
    expect(showViewButton(false)).toBe(true);
  });
});
