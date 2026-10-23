import { describe, it, expect } from 'vitest';
import fc from 'fast-check';

import {
  isSupportedSourceType,
  SUPPORTED_SOURCE_MIME_TYPES,
} from './documentAdapterService';

// Feature: document-audience-adapter, Property 1: Only PDF and Word source files are accepted
//
// `isSupportedSourceType` returns true if and only if the MIME type is one of
// the three supported values (application/pdf, application/msword,
// application/vnd.openxmlformats-officedocument.wordprocessingml.document).
//
// **Validates: Requirements 2.4**

const SUPPORTED = SUPPORTED_SOURCE_MIME_TYPES as readonly string[];

describe('Property 1: only PDF and Word source files are accepted (Requirements 2.4)', () => {
  it('accepts every supported MIME type', () => {
    fc.assert(
      fc.property(fc.constantFrom(...SUPPORTED), (mimeType) => {
        expect(isSupportedSourceType(mimeType)).toBe(true);
      }),
      { numRuns: 100 },
    );
  });

  it('returns true iff the MIME type is one of the supported values, for arbitrary strings', () => {
    fc.assert(
      fc.property(fc.string(), (mimeType) => {
        // The reference truth is pure set membership against the supported set.
        const expected = SUPPORTED.includes(mimeType);
        expect(isSupportedSourceType(mimeType)).toBe(expected);
      }),
      { numRuns: 100 },
    );
  });

  it('returns true iff the MIME type is one of the supported values, mixing supported and near-miss inputs', () => {
    // Bias the generator toward the supported values and plausible near-misses
    // (casing, whitespace, substrings) so the iff is exercised on both branches.
    const nearMisses = [
      ...SUPPORTED,
      ...SUPPORTED.map((m) => m.toUpperCase()),
      ...SUPPORTED.map((m) => ` ${m}`),
      ...SUPPORTED.map((m) => `${m} `),
      'application/pdf; charset=utf-8',
      'application/octet-stream',
      'text/plain',
      'image/png',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      '',
      'pdf',
      'msword',
    ];

    fc.assert(
      fc.property(
        fc.oneof(fc.constantFrom(...nearMisses), fc.string()),
        (mimeType) => {
          const expected = SUPPORTED.includes(mimeType);
          expect(isSupportedSourceType(mimeType)).toBe(expected);
        },
      ),
      { numRuns: 200 },
    );
  });
});
