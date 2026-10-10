import { createContext } from 'react';
import type { Language } from './translations';

export interface LanguageContextValue {
  language: Language;
  setLanguage: (next: Language) => void;
  t: (key: string) => string;
}

// Default `null` lets `useTranslation` throw a clear error if used outside a provider.
export const LanguageContext = createContext<LanguageContextValue | null>(null);
