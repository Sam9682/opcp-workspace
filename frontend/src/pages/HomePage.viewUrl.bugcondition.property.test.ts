import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { buildPublicHtmlUrl } from '../utils/forumLinks';

// Feature: forum-view-button-url-fix
// Task 1 / Task 3.4 — Bug condition exploration test for the "View" button URL (Bug 1).
//
// Property 1 (Bug Condition / Fix Checking): the "View" URL preserves the
// site origin's port and keeps the path /api/forum/topics/{topicId}/publichtml.
//
// This test encodes the EXPECTED behavior. On the original (unfixed) code it
// FAILED because the href was built from a hardcoded host WITHOUT a port:
//
//     `https://opcp-psmc.com/api/forum/topics/${topic.id}/publichtml`
//
// so when the app is served on a non-default port the produced URL dropped that
// port and resolved against the default HTTPS port (443) -> "page not found".
//
// Task 3.4: the fix now lives in frontend/src/utils/forumLinks.ts as the exported
// `buildPublicHtmlUrl(origin, topicId)` helper, which derives scheme + host + port
// from the passed origin. The test now exercises that real fixed helper so it
// VALIDATES the fix — it PASSES because the port is preserved and the path is exact.
//
// **Validates: Requirements 1.1, 1.2, 2.1, 2.2**

// buildViewUrl (F'): the FIXED link construction. The exploration test now
// exercises the real helper used by HomePage.tsx (`buildPublicHtmlUrl`), which
// derives the origin (scheme + host + port) from its `origin` argument.
const buildViewUrl = (origin: string, topicId: string): string =>
  buildPublicHtmlUrl(origin, topicId);

// portOf: effective port of a URL — explicit port when present, otherwise the
// scheme's default (443 for https, 80 for http).
const portOf = (url: string): string => {
  const u = new URL(url);
  if (u.port) return u.port;
  return u.protocol === 'https:' ? '443' : '80';
};

const pathOf = (url: string): string => new URL(url).pathname;

describe('Property 1 (Bug Condition): View URL preserves the site origin port (Requirements 1.1, 1.2, 2.1, 2.2)', () => {
  // Scoped PBT: concrete failing origins from the design's exploration plan.
  const failingCases: { siteOrigin: string; topicId: string }[] = [
    { siteOrigin: 'https://opcp-psmc.com:8443', topicId: '42' },
    { siteOrigin: 'https://staging.example.com:9000', topicId: '42' },
  ];

  it('produced URL port equals the site origin port and path is exact (PASSES on fixed code — validates Bug 1 fix)', () => {
    fc.assert(
      fc.property(fc.constantFrom(...failingCases), ({ siteOrigin, topicId }) => {
        const result = buildViewUrl(siteOrigin, topicId);

        // Fix Checking assertions from design/bugfix.md:
        //   portOf(result) === portOf(siteOrigin)
        //   pathOf(result) === "/api/forum/topics/" + topicId + "/publichtml"
        expect(portOf(result)).toBe(portOf(siteOrigin));
        expect(pathOf(result)).toBe(`/api/forum/topics/${topicId}/publichtml`);
      }),
      { numRuns: 100 },
    );
  });

  it('path integrity holds regardless of origin (guards against regressions in the fix)', () => {
    // The path segment has always been correct; this documents the non-buggy
    // boundary of the path segment and guards against regressions in the fix.
    const result = buildViewUrl('https://opcp-psmc.com:8443', '42');
    expect(pathOf(result)).toBe('/api/forum/topics/42/publichtml');
  });
});
