import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { buildPublicHtmlUrl } from './forumLinks';

// Feature: forum-view-button-url-fix
// Task 3.3 — Property-based test for buildPublicHtmlUrl (the design's Fix property).
//
// Fix property (design / Property-Based Tests): for generated origins with
// arbitrary explicit ports, the produced URL's port equals the origin's port and
// the path is exact (/api/forum/topics/{topicId}/publichtml).
//
// **Validates: Requirements 2.1, 2.2**

// portOf: effective port of a URL — explicit port when present, otherwise the
// scheme's default (443 for https, 80 for http).
const portOf = (url: string): string => {
  const u = new URL(url);
  if (u.port) return u.port;
  return u.protocol === 'https:' ? '443' : '80';
};

const pathOf = (url: string): string => new URL(url).pathname;

// Generators constrained to the input space: valid schemes, hosts, explicit
// ports (excluding the scheme defaults so the "arbitrary explicit port" intent
// holds), and numeric topic ids.
const scheme = fc.constantFrom('http', 'https');
const host = fc.constantFrom(
  'opcp-psmc.com',
  'staging.example.com',
  'localhost',
  'app.internal',
);
// Explicit ports in the valid TCP range, avoiding 80/443 so the port is always
// meaningfully explicit and not collapsed to a scheme default.
const explicitPort = fc
  .integer({ min: 1, max: 65535 })
  .filter((p) => p !== 80 && p !== 443);
const topicId = fc.integer({ min: 1, max: 1_000_000 }).map((n) => String(n));

describe('Fix property: buildPublicHtmlUrl preserves the origin port and exact path (Requirements 2.1, 2.2)', () => {
  it('for arbitrary explicit ports, produced port equals origin port and path is exact', () => {
    fc.assert(
      fc.property(scheme, host, explicitPort, topicId, (s, h, port, id) => {
        const origin = `${s}://${h}:${port}`;
        const url = buildPublicHtmlUrl(origin, id);

        // Port is preserved (this is the crux of the Bug 1 fix).
        expect(portOf(url)).toBe(String(port));
        // Path is exactly the forum publichtml path for the given topic id.
        expect(pathOf(url)).toBe(`/api/forum/topics/${id}/publichtml`);
        // Scheme and host are carried through from the origin unchanged.
        const u = new URL(url);
        expect(u.protocol).toBe(`${s}:`);
        expect(u.hostname).toBe(h);
      }),
      { numRuns: 100 },
    );
  });
});
