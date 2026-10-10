import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { HowToUse } from './HowToUse';
import { LanguageProvider } from '../../hooks/useLanguage';

// HowToUse is a presentational, no-props component that renders no <Link>s, so
// it does not require a Router. It reads no auth state and exposes no editable
// controls (Req 3.1). It now resolves its marker labels through the
// translation layer, so render it inside a LanguageProvider. Clearing
// localStorage in beforeEach keeps the default French language active, so the
// marker labels resolve to their French copy ('Obligatoire' / 'Optionnel').
beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
});

// Render HowToUse inside a LanguageProvider so useTranslation resolves labels.
function renderHowToUse() {
  return render(
    <LanguageProvider>
      <HowToUse />
    </LanguageProvider>,
  );
}

// Validates: Requirements 3.1, 3.2, 3.3, 3.4
describe('HowToUse (Archetype 1 — read-only)', () => {
  // Req 3.2: the marker legend shows both the Mandatory and Optional markers,
  // sourced from the shared PREREQ_MARKERS constant.
  describe('marker legend', () => {
    it('renders the Mandatory marker label resolved to French', () => {
      renderHowToUse();
      // The marker resolves through t(labelKey); under the default French
      // language prereq.marker.mandatory -> 'Obligatoire'.
      expect(screen.getByText('Obligatoire')).toBeTruthy();
    });

    it('renders the Optional marker label resolved to French', () => {
      renderHowToUse();
      // prereq.marker.optional -> 'Optionnel' under the default French language.
      expect(screen.getByText('Optionnel')).toBeTruthy();
    });
  });

  // Req 3.3: completion tips / example guidance are present.
  describe('completion tips', () => {
    it('renders the tips section heading', () => {
      renderHowToUse();
      expect(
        screen.getByText('Conseils pour compléter les prérequis'),
      ).toBeTruthy();
    });

    it('mentions starting with the Basics page', () => {
      renderHowToUse();
      // A known tip references the "Basics" page.
      expect(screen.getByText(/Basics/)).toBeTruthy();
    });

    it('mentions the "Réponse client" column for mandatory questions', () => {
      renderHowToUse();
      expect(screen.getByText(/Réponse client/)).toBeTruthy();
    });
  });

  // Req 3.4: a visually distinct secrets warning is present.
  describe('secrets warning', () => {
    it('warns against entering secrets / PSK / credentials', () => {
      renderHowToUse();
      expect(
        screen.getByText(/secrets, de clés PSK ou d’identifiants/),
      ).toBeTruthy();
    });

    it('instructs the user to use a secure channel', () => {
      renderHowToUse();
      expect(screen.getByText(/canal sécurisé/)).toBeTruthy();
    });

    it('renders the warning with an alert role for prominence', () => {
      renderHowToUse();
      expect(screen.getByRole('alert')).toBeTruthy();
    });
  });

  // Req 3.1: the component is fully static / read-only for every role — no
  // editable or interactive controls of any kind should render.
  describe('read-only for every role', () => {
    it('renders no textbox controls', () => {
      renderHowToUse();
      expect(screen.queryAllByRole('textbox')).toHaveLength(0);
    });

    it('renders no combobox controls', () => {
      renderHowToUse();
      expect(screen.queryAllByRole('combobox')).toHaveLength(0);
    });

    it('renders no button controls', () => {
      renderHowToUse();
      expect(screen.queryAllByRole('button')).toHaveLength(0);
    });

    it('renders no checkbox controls', () => {
      renderHowToUse();
      expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
    });
  });
});
