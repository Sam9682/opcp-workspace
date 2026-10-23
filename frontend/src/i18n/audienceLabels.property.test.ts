import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { fr, en, dictionaries, SUPPORTED_LANGUAGES } from './translations';
import type { Language } from './translations';
import { resolve } from './resolve';
import {
  AUDIENCE_LEVELS,
  type AudienceLevel,
} from '../services/documentAdapterService';

// Feature: document-audience-adapter, Property 3: Every audience level has a
// readable label in every language
//
// For every AudienceLevel value (it_beginner, intermediate_a, intermediate_b,
// opcp_expert) and every supported language (fr, en), resolving its audience
// label yields a non-empty string.
//
// The labels live as i18n keys `page.documentAdapter.audience.{level}` in both
// the fr and en dictionaries (frontend/src/i18n/translations.ts), resolved the
// same way the app resolves UI strings (frontend/src/i18n/resolve.ts).
//
// **Validates: Requirements 3.2**

/** Build the i18n key for an audience level's label. */
function audienceLabelKey(level: AudienceLevel): string {
  return `page.documentAdapter.audience.${level}`;
}

describe('Property 3: every audience level has a readable label in every language (Requirements 3.2)', () => {
  it('resolves a non-empty label for every AudienceLevel x language pair', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<AudienceLevel>(...AUDIENCE_LEVELS),
        fc.constantFrom<Language>(...SUPPORTED_LANGUAGES),
        (level, language) => {
          const key = audienceLabelKey(level);
          const label = resolve(dictionaries, language, key);

          // A resolved label must differ from the key itself (the fallback
          // returned when a key is missing) and be non-empty after trimming.
          expect(label, `${language}["${key}"] should be defined`).not.toBe(key);
          expect(
            label.trim().length,
            `${language}["${key}"] should be non-empty`,
          ).toBeGreaterThan(0);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('the audience label keys are present directly in both raw dictionaries', () => {
    // The domain is small and fixed (4 levels x 2 languages = 8 combinations),
    // so this exhaustively enumerates every pair to guarantee full coverage,
    // complementing the generated runs above.
    for (const level of AUDIENCE_LEVELS) {
      const key = audienceLabelKey(level);
      expect(fr[key]?.trim().length ?? 0, `fr["${key}"]`).toBeGreaterThan(0);
      expect(en[key]?.trim().length ?? 0, `en["${key}"]`).toBeGreaterThan(0);
    }
  });
});
