import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { fr, en, dictionaries } from './translations';
import { resolve } from './resolve';

// Feature: admin-document-upload-categories, Property 8: Category labels resolve in both locales
//
// For each category in CATEGORY_ORDER (documents/scripts/links),
// CATEGORY_LABEL_KEYS[category] resolves to a non-empty display string in both
// the French and English translation tables.
//
// The DocumentsPage constants are not exported, so the expected keys are
// referenced directly here (kept in lock-step with design.md section 6/7).
//
// **Validates: Requirements 1.2, 1.3**

type Category = 'documents' | 'scripts' | 'links';

const CATEGORY_ORDER: Category[] = ['documents', 'scripts', 'links'];
const CATEGORY_LABEL_KEYS: Record<Category, string> = {
  documents: 'page.documents.category.documents',
  scripts: 'page.documents.category.scripts',
  links: 'page.documents.category.links',
};

describe('Property 8: category labels resolve in both locales (Requirements 1.2, 1.3)', () => {
  it('every CATEGORY_ORDER label resolves to a non-empty string in fr and en', () => {
    fc.assert(
      fc.property(fc.constantFrom(...CATEGORY_ORDER), (category) => {
        const key = CATEGORY_LABEL_KEYS[category];

        for (const language of ['fr', 'en'] as const) {
          const label = resolve(dictionaries, language, key);
          // A resolved label must differ from the key itself (the fallback)
          // and be non-empty after trimming.
          expect(label, `${language}["${key}"] should be defined`).not.toBe(key);
          expect(
            label.trim().length,
            `${language}["${key}"] should be non-empty`,
          ).toBeGreaterThan(0);
        }
      }),
      { numRuns: 100 },
    );
  });

  it('the label keys are present directly in both raw dictionaries', () => {
    for (const category of CATEGORY_ORDER) {
      const key = CATEGORY_LABEL_KEYS[category];
      expect(fr[key]?.trim().length ?? 0, `fr["${key}"]`).toBeGreaterThan(0);
      expect(en[key]?.trim().length ?? 0, `en["${key}"]`).toBeGreaterThan(0);
    }
  });
});
