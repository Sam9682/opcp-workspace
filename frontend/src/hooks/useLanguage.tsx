import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { LanguageContext } from '../i18n/LanguageContext';
import type { Language } from '../i18n/translations';
import { dictionaries } from '../i18n/translations';
import { normalizeLanguage, resolve } from '../i18n/resolve';

/** localStorage key under which the Active_Language persists (Language_Store). */
const STORAGE_KEY = 'opcp.language';

/**
 * Read the initial Active_Language from the Language_Store, normalizing any
 * absent/invalid value to French. A read failure (localStorage disabled or in
 * privacy mode) also defaults to French. (Requirements 4.2, 4.3, 4.4)
 */
function readInitialLanguage(): Language {
  try {
    return normalizeLanguage(localStorage.getItem(STORAGE_KEY));
  } catch {
    // localStorage unavailable (privacy/disabled): default to French.
    return normalizeLanguage(null);
  }
}

/**
 * Language_Provider: owns the Active_Language, seeds it from the Language_Store,
 * persists changes, and exposes `{ language, setLanguage, t }` to descendants
 * through React Context. (Requirements 4.1, 4.2, 4.3, 4.4, 5.1, 5.2)
 */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(readInitialLanguage);

  // Persist on change; write failures must not break the UI, leaving in-memory
  // state authoritative for the session (mirrors usePersistentForm's defensive
  // try/catch). (Requirement 4.1)
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, language);
    } catch {
      /* ignore quota/unavailable storage */
    }
  }, [language]);

  const setLanguage = useCallback((next: Language) => {
    setLanguageState(normalizeLanguage(next));
  }, []);

  const t = useCallback(
    (key: string) => resolve(dictionaries, language, key),
    [language],
  );

  const value = useMemo(
    () => ({ language, setLanguage, t }),
    [language, setLanguage, t],
  );

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

/**
 * Translation_Hook: returns `{ language, setLanguage, t }` from the
 * Language_Provider. Throws a descriptive error when used outside a provider so
 * wiring mistakes surface during development. (Requirements 5.1, 5.2)
 */
export function useTranslation() {
  const ctx = useContext(LanguageContext);
  if (ctx === null) {
    throw new Error('useTranslation must be used within a LanguageProvider');
  }
  return ctx;
}
