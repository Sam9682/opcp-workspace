import { describe, it, expect } from 'vitest';
import { fr, en, dictionaries, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE } from './translations';

// Structural parity test for the fr/en Translation_Dictionaries.
//
// The dictionaries intentionally share an identical key set so a missing
// translation in either language is caught at test time rather than surfacing
// as an untranslated key in the running UI.
// _Requirements: 5.3_

// Sorted key list for stable, order-independent comparison.
const sortedKeys = (dict: Record<string, string>): string[] =>
  Object.keys(dict).sort();

describe('translation dictionary key parity (Requirement 5.3)', () => {
  it('fr and en expose an identical set of keys', () => {
    expect(sortedKeys(fr)).toEqual(sortedKeys(en));
  });

  it('every fr key is present in en', () => {
    const enKeys = new Set(Object.keys(en));
    const missingInEn = Object.keys(fr).filter((key) => !enKeys.has(key));
    expect(missingInEn).toEqual([]);
  });

  it('every en key is present in fr', () => {
    const frKeys = new Set(Object.keys(fr));
    const missingInFr = Object.keys(en).filter((key) => !frKeys.has(key));
    expect(missingInFr).toEqual([]);
  });

  it('both dictionaries have the same number of keys', () => {
    expect(Object.keys(fr).length).toBe(Object.keys(en).length);
  });

  it('has no empty translation values in either dictionary', () => {
    for (const [key, value] of Object.entries(fr)) {
      expect(value.trim().length, `fr["${key}"] should be non-empty`).toBeGreaterThan(0);
    }
    for (const [key, value] of Object.entries(en)) {
      expect(value.trim().length, `en["${key}"] should be non-empty`).toBeGreaterThan(0);
    }
  });

  it('the dictionaries map is keyed by the supported languages and matches fr/en', () => {
    expect(Object.keys(dictionaries).sort()).toEqual([...SUPPORTED_LANGUAGES].sort());
    expect(dictionaries.fr).toBe(fr);
    expect(dictionaries.en).toBe(en);
  });

  it('the default language is one of the supported languages', () => {
    expect(SUPPORTED_LANGUAGES).toContain(DEFAULT_LANGUAGE);
  });

  // Guards the OpenStack CA certificate i18n keys so parity holds for the
  // label and the invalid-certificate error message in both languages.
  // _Requirements: 1.4_
  it.each([
    'prereq.servers.credentials.caCertificate',
    'prereq.servers.error.invalidCaCertificate',
  ])('exposes a non-empty "%s" in both en and fr', (key) => {
    expect(en).toHaveProperty(key);
    expect(fr).toHaveProperty(key);
    expect(en[key].trim().length, `en["${key}"] should be non-empty`).toBeGreaterThan(0);
    expect(fr[key].trim().length, `fr["${key}"] should be non-empty`).toBeGreaterThan(0);
  });
});
