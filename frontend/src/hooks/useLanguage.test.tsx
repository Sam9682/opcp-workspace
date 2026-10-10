import { describe, it, expect, beforeEach } from 'vitest';
import { render, renderHook, act, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import fc from 'fast-check';
import { LanguageProvider, useTranslation } from './useLanguage';
import { dictionaries, SUPPORTED_LANGUAGES } from '../i18n/translations';
import type { Language } from '../i18n/translations';

// Minimum property-test iterations mandated by the design (>= 100).
const NUM_RUNS = 100;

// localStorage key under which the Active_Language persists (Language_Store).
const STORAGE_KEY = 'opcp.language';

// Wrapper that provides the LanguageProvider to the hook under test.
const wrapper = ({ children }: { children: ReactNode }) => (
  <LanguageProvider>{children}</LanguageProvider>
);

beforeEach(() => {
  localStorage.clear();
});

// Feature: bilingual-language-support, Property 1: Language switch sets the active language
// For any Supported_Language L, calling setLanguage(L) makes the Active_Language exactly L.
// Validates: Requirements 1.3, 1.4, 6.1
describe('Property 1: language switch sets the active language', () => {
  it('after setLanguage(L), the active language is exactly L', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...(SUPPORTED_LANGUAGES as readonly Language[])),
        (language) => {
          localStorage.clear();
          const { result } = renderHook(() => useTranslation(), { wrapper });

          act(() => {
            result.current.setLanguage(language);
          });

          expect(result.current.language).toBe(language);
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});

// Feature: bilingual-language-support, Property 4: Language selection round-trips through the store
// For any Supported_Language L, setting the language writes L to localStorage
// (opcp.language) and re-initializing a fresh provider yields L.
// Validates: Requirements 4.1, 4.2, 6.3
describe('Property 4: language selection round-trips through the store', () => {
  it('setting the language persists it and a fresh provider re-initializes to it', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...(SUPPORTED_LANGUAGES as readonly Language[])),
        (language) => {
          localStorage.clear();

          // First provider instance: switch the language, which persists to store.
          const first = renderHook(() => useTranslation(), { wrapper });
          act(() => {
            first.result.current.setLanguage(language);
          });

          // The Active_Language is written to the Language_Store.
          expect(localStorage.getItem(STORAGE_KEY)).toBe(language);

          // A fresh provider re-initializes from the store to the same language.
          const second = renderHook(() => useTranslation(), { wrapper });
          expect(second.result.current.language).toBe(language);
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});

// Example tests for provider behavior.
// Requirements: 4.3, 5.1, 5.2, 6.2, 6.4
describe('LanguageProvider example behavior', () => {
  it('initializes a New_Visitor (empty store) to French', () => {
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();

    const { result } = renderHook(() => useTranslation(), { wrapper });

    expect(result.current.language).toBe('fr');
  });

  it('exposes language, setLanguage, and t to a consumer', () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });

    expect(result.current.language).toBe('fr');
    expect(typeof result.current.setLanguage).toBe('function');
    expect(typeof result.current.t).toBe('function');
  });

  it('resolves a UI_String to French under fr and English under en', () => {
    // Consumer component that renders a keyed UI_String and a switch control.
    function Consumer() {
      const { setLanguage, t } = useTranslation();
      return (
        <div>
          <span data-testid="home-label">{t('nav.home')}</span>
          <button onClick={() => setLanguage('en')}>to-en</button>
          <button onClick={() => setLanguage('fr')}>to-fr</button>
        </div>
      );
    }

    render(
      <LanguageProvider>
        <Consumer />
      </LanguageProvider>,
    );

    // Default (French) resolves to the French text.
    expect(screen.getByTestId('home-label').textContent).toBe(
      dictionaries.fr['nav.home'],
    );
    expect(screen.getByTestId('home-label').textContent).toBe('Accueil');

    // Switching to English re-renders the consumer with English text.
    act(() => {
      screen.getByText('to-en').click();
    });
    expect(screen.getByTestId('home-label').textContent).toBe(
      dictionaries.en['nav.home'],
    );
    expect(screen.getByTestId('home-label').textContent).toBe('Home');

    // Switching back to French restores the French text.
    act(() => {
      screen.getByText('to-fr').click();
    });
    expect(screen.getByTestId('home-label').textContent).toBe('Accueil');
  });
});
