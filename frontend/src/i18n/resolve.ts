import type { Language, TranslationDictionary } from './translations';
import { SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE } from './translations';

/**
 * Resolve a UI_String key for a language. Returns the localized text when
 * present; otherwise returns the key itself so the interface stays readable.
 *
 * (Requirements 2.1, 2.2, 2.5)
 */
export function resolve(
  dicts: Record<Language, TranslationDictionary>,
  language: Language,
  key: string,
): string {
  const text = dicts[language]?.[key];
  return text ?? key;
}

/**
 * Normalize an arbitrary stored value to a Supported_Language, defaulting to
 * French for absent/invalid input (including `null`, empty string, and stale
 * or unknown codes).
 *
 * (Requirements 4.3, 4.4)
 */
export function normalizeLanguage(raw: unknown): Language {
  return SUPPORTED_LANGUAGES.includes(raw as Language)
    ? (raw as Language)
    : DEFAULT_LANGUAGE;
}
