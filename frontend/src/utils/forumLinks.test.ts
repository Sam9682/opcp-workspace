import { describe, it, expect } from 'vitest';
import { buildPublicHtmlUrl } from './forumLinks';

// Feature: forum-view-button-url-fix
// Task 3.3 — Unit tests for buildPublicHtmlUrl (the fixed construction, buildViewUrl').
//
// buildPublicHtmlUrl(origin, topicId) derives scheme + host + port from the
// passed origin and appends the fixed path /api/forum/topics/{topicId}/publichtml.
// These example tests exercise scheme/host/port/path assembly across default and
// non-default ports (from the design's Unit Tests section).
//
// **Validates: Requirements 2.1, 2.2**

// portOf: effective port of a URL — explicit port when present, otherwise the
// scheme's default (443 for https, 80 for http). Mirrors the helper used by the
// bug-condition/preservation property tests.
const portOf = (url: string): string => {
  const u = new URL(url);
  if (u.port) return u.port;
  return u.protocol === 'https:' ? '443' : '80';
};

const pathOf = (url: string): string => new URL(url).pathname;

describe('buildPublicHtmlUrl (Requirements 2.1, 2.2)', () => {
  it('assembles scheme + host + path for a default-port https origin', () => {
    expect(buildPublicHtmlUrl('https://opcp-psmc.com', '42')).toBe(
      'https://opcp-psmc.com/api/forum/topics/42/publichtml',
    );
  });

  it('preserves an explicit non-default port (Bug 1 fix — port not dropped)', () => {
    const url = buildPublicHtmlUrl('https://opcp-psmc.com:8443', '42');
    expect(url).toBe('https://opcp-psmc.com:8443/api/forum/topics/42/publichtml');
    expect(portOf(url)).toBe('8443');
  });

  it('preserves a different host together with its explicit port', () => {
    const url = buildPublicHtmlUrl('https://staging.example.com:9000', '42');
    expect(url).toBe(
      'https://staging.example.com:9000/api/forum/topics/42/publichtml',
    );
    expect(new URL(url).hostname).toBe('staging.example.com');
    expect(portOf(url)).toBe('9000');
  });

  it('preserves the http scheme and its explicit port', () => {
    const url = buildPublicHtmlUrl('http://localhost:5173', '7');
    expect(url).toBe('http://localhost:5173/api/forum/topics/7/publichtml');
    expect(new URL(url).protocol).toBe('http:');
    expect(portOf(url)).toBe('5173');
  });

  it('keeps the path exact for the given topic id, independent of origin', () => {
    expect(pathOf(buildPublicHtmlUrl('https://opcp-psmc.com:8443', '123'))).toBe(
      '/api/forum/topics/123/publichtml',
    );
    expect(pathOf(buildPublicHtmlUrl('https://opcp-psmc.com', '999'))).toBe(
      '/api/forum/topics/999/publichtml',
    );
  });
});
