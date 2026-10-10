import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { resolve, normalizeLanguage } from './resolve';
import { dictionaries, SUPPORTED_LANGUAGES } from './translations';
import type { Language } from './translations';

// Minimum property-test iterations mandated by the design (>= 100).
const NUM_RUNS = 100;

// Feature: bilingual-language-support, Property 2: Keys resolve to the active language's text
// For any Supported_Language L and any key present in dictionaries[L],
// resolve(dictionaries, L, key) returns dictionaries[L][key].
// Validates: Requirements 2.1, 2.2, 6.2
describe('Property 2: keys resolve to the active language text', () => {
  it('returns the localized text for any key present in the active dictionary', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...(SUPPORTED_LANGUAGES as readonly Language[])),
        (language) => {
          const keys = Object.keys(dictionaries[language]);
          // Every language dictionary is non-empty, so this generator is safe.
          return fc.assert(
            fc.property(fc.constantFrom(...keys), (key) => {
              expect(resolve(dictionaries, language, key)).toBe(
                dictionaries[language][key],
              );
            }),
            { numRuns: NUM_RUNS },
          );
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});

// Feature: bilingual-language-support, Property 3: Missing keys fall back to the key text
// For any Supported_Language L and any random string key absent from
// dictionaries[L], resolve returns the key unchanged.
// Validates: Requirements 2.5
describe('Property 3: missing keys fall back to the key text', () => {
  it('returns the key unchanged when it is absent from the active dictionary', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...(SUPPORTED_LANGUAGES as readonly Language[])),
        fc.string(),
        (language, key) => {
          // Constrain to keys that are genuinely absent from the dictionary.
          fc.pre(!(key in dictionaries[language]));
          expect(resolve(dictionaries, language, key)).toBe(key);
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});

// Feature: bilingual-language-support, Property 5: Invalid or absent stored values normalize to French
// For any value v not in the Supported_Language set (arbitrary strings, null,
// empty string, non-strings), normalizeLanguage(v) yields French ('fr').
// Validates: Requirements 4.3, 4.4, 6.4
describe('Property 5: invalid or absent stored values normalize to French', () => {
  it('coerces any non-supported value to French', () => {
    const nonSupported = fc.oneof(
      fc.string().filter((s) => !SUPPORTED_LANGUAGES.includes(s as Language)),
      fc.constant(''),
      fc.constant(null),
      fc.constant(undefined),
      fc.integer(),
      fc.boolean(),
      fc.object(),
      fc.array(fc.anything()),
    );

    fc.assert(
      fc.property(nonSupported, (value) => {
        expect(normalizeLanguage(value)).toBe('fr');
      }),
      { numRuns: NUM_RUNS },
    );
  });
});
