/**
 * Preservation property tests — Property 2: Preservation.
 * Spec: .kiro/specs/tasks-menu-not-displayed
 *
 * These tests capture the CURRENT (unfixed) baseline behavior of every
 * navigation interaction that does NOT target the Tasks feature
 * (isBugCondition returns false): the Events menu + "Manage events" dropdown,
 * the other nav items (Home, Forum, Documents, AI Oracle, OPCP installations,
 * Users, Configuration) with their routes and admin gating, the FR/EN
 * resolution of every existing nav label, and the hiding of admin-only
 * dropdown entries for non-admin users.
 *
 * They MUST PASS on the unfixed code (confirming the baseline to preserve) and
 * MUST CONTINUE to pass unchanged after the Tasks wiring is added — the fix is
 * purely additive, so none of these observed outputs may change.
 *
 * Observation-first: the expected values below were observed by reading the
 * current Layout.tsx (desktop + mobile markup), translations.ts (fr/en
 * dictionaries) and App.tsx (route table) on the UNFIXED code, then encoded.
 *
 * Property-based coverage (fast-check) generates many combinations of
 * (authenticated, admin, language) and FR/EN toggle sequences to give strong
 * assurance that every non-Tasks item, label, and gate is unchanged.
 *
 * Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, within, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import fc from 'fast-check';
import { Layout } from './Layout';
import { LanguageProvider } from '../hooks/useLanguage';
import { dictionaries } from '../i18n/translations';
import { resolve } from '../i18n/resolve';

// localStorage keys read by authService for auth/admin gating.
const TOKEN_KEY = 'access_token';
const ROLE_KEY = 'user_role';
const USER_KEY = 'user';
// localStorage key under which the active language persists.
const LANG_KEY = 'opcp.language';

type Lang = 'fr' | 'en';

/** Clear all auth state (unauthenticated). */
function signOut() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(USER_KEY);
}

/** Sign in as a plain authenticated (non-admin) user. */
function signInAsUser() {
  localStorage.setItem(TOKEN_KEY, 'test-token');
  localStorage.setItem(ROLE_KEY, 'member');
  localStorage.setItem(
    USER_KEY,
    JSON.stringify({ id: '1', email: 'user@opcp.test', first_name: 'U', last_name: 'Ser', role: 'member' }),
  );
}

/** Sign in as an authenticated administrator. */
function signInAsAdmin() {
  localStorage.setItem(TOKEN_KEY, 'test-token');
  localStorage.setItem(ROLE_KEY, 'administrator');
  localStorage.setItem(
    USER_KEY,
    JSON.stringify({ id: '1', email: 'admin@opcp.test', first_name: 'Ad', last_name: 'Min', role: 'administrator' }),
  );
}

/** Apply the requested auth state to localStorage before rendering. */
function applyAuth(authenticated: boolean, admin: boolean) {
  if (!authenticated) {
    signOut();
  } else if (admin) {
    signInAsAdmin();
  } else {
    signInAsUser();
  }
}

/** Render Layout inside a router + language provider. */
function renderLayout(language: Lang = 'fr') {
  localStorage.setItem(LANG_KEY, language);
  return render(
    <MemoryRouter>
      <LanguageProvider>
        <Layout>
          <div>content</div>
        </Layout>
      </LanguageProvider>
    </MemoryRouter>,
  );
}

/** Find a Link by its accessible text (exact match) within a container. */
function linkByText(container: HTMLElement, text: string): HTMLElement | null {
  const links = within(container).queryAllByRole('link');
  return links.find((el) => el.textContent?.trim() === text) ?? null;
}

/**
 * Observed baseline quirk: in the DESKTOP nav the Events link appends a " ▾"
 * caret only when the user is an admin (`{t('nav.events')} {isAdmin && <span>▾</span>}`),
 * so the accessible name is e.g. "Événements ▾" for admins and "Événements" for
 * non-admins. This helper returns the accessible name to query for the Events
 * desktop link given the admin state, matching the current markup exactly.
 */
function eventsDesktopName(language: Lang, admin: boolean): RegExp {
  const base = OBSERVED_LABELS[language]['nav.events'];
  // Match the base label optionally followed by the admin caret.
  return admin ? new RegExp(`^${base}\\s*▾$`) : new RegExp(`^${base}$`);
}

/** All existing (non-Tasks) nav label keys observed in the current code. */
const EXISTING_NAV_LABEL_KEYS = [
  'nav.home',
  'nav.forum',
  'nav.events',
  'nav.events.manage',
  'nav.documents',
  'nav.oracle',
  'nav.prerequisites',
  'nav.users',
  'nav.config',
  'lang.fr',
  'lang.en',
] as const;

/**
 * Observed FR/EN text for the existing nav labels, recorded from the current
 * translations.ts on the UNFIXED code. Preservation requires these resolve
 * unchanged after the fix. (Requirement 3.3)
 */
const OBSERVED_LABELS: Record<Lang, Record<string, string>> = {
  fr: {
    'nav.home': 'Accueil',
    'nav.forum': 'Forum',
    'nav.events': 'Événements',
    'nav.events.manage': 'Gérer les événements',
    'nav.documents': 'Documents',
    'nav.oracle': 'Oracle IA',
    'nav.prerequisites': 'OPCP installations',
    'nav.users': 'Utilisateurs',
    'nav.config': 'Configuration',
    'lang.fr': 'FR',
    'lang.en': 'EN',
  },
  en: {
    'nav.home': 'Home',
    'nav.forum': 'Forum',
    'nav.events': 'Events',
    'nav.events.manage': 'Manage events',
    'nav.documents': 'Documents',
    'nav.oracle': 'AI Oracle',
    'nav.prerequisites': 'OPCP installations',
    'nav.users': 'Users',
    'nav.config': 'Configuration',
    'lang.fr': 'FR',
    'lang.en': 'EN',
  },
};

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});

// ---------------------------------------------------------------------------
// Preservation — RESOLVE_LABEL: every existing nav label resolves to its
// observed FR/EN text, and FR/EN toggling never changes those resolutions.
// (Requirement 3.3)
// ---------------------------------------------------------------------------
describe('Preservation — existing nav labels resolve to their observed FR/EN text', () => {
  it('every existing nav label resolves to the observed text in FR and EN', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<Lang>('fr', 'en'),
        fc.constantFrom(...EXISTING_NAV_LABEL_KEYS),
        (language, key) => {
          expect(resolve(dictionaries, language, key)).toBe(OBSERVED_LABELS[language][key]);
        },
      ),
    );
  });

  it('any FR/EN toggle sequence leaves every existing label resolving unchanged', () => {
    fc.assert(
      fc.property(
        fc.array(fc.constantFrom<Lang>('fr', 'en'), { minLength: 1, maxLength: 8 }),
        (sequence) => {
          // The active language after the sequence is simply its last element;
          // resolve is pure/stateless, so each key must map to that language's
          // observed text regardless of how we got there.
          const finalLang = sequence[sequence.length - 1];
          for (const key of EXISTING_NAV_LABEL_KEYS) {
            expect(resolve(dictionaries, finalLang, key)).toBe(OBSERVED_LABELS[finalLang][key]);
          }
        },
      ),
    );
  });

  it('the existing nav keys are present in both raw dictionaries (no key removed)', () => {
    for (const key of EXISTING_NAV_LABEL_KEYS) {
      expect(dictionaries.fr[key]).toBe(OBSERVED_LABELS.fr[key]);
      expect(dictionaries.en[key]).toBe(OBSERVED_LABELS.en[key]);
    }
  });
});

// ---------------------------------------------------------------------------
// Preservation — RENDER_DESKTOP_NAV: across all (authenticated, admin,
// language) combinations, the existing desktop nav items render exactly as
// observed, with their existing routes and admin gating. (Requirements 3.1,
// 3.2, 3.5)
// ---------------------------------------------------------------------------
describe('Preservation — desktop nav items, routes, and gating render as observed', () => {
  it('renders exactly the observed desktop items for every auth/admin/language combo', () => {
    fc.assert(
      fc.property(
        fc.boolean(),
        fc.boolean(),
        fc.constantFrom<Lang>('fr', 'en'),
        (authenticated, admin, language) => {
          cleanup();
          localStorage.clear();
          applyAuth(authenticated, admin);
          renderLayout(language);

          const L = OBSERVED_LABELS[language];

          // Home is always present (public), linking to "/".
          const home = screen.getAllByRole('link', { name: L['nav.home'] });
          expect(home.length).toBeGreaterThan(0);
          expect(home[0]).toHaveAttribute('href', '/');

          if (!authenticated) {
            // Unauthenticated: none of the authenticated-only items render.
            expect(screen.queryAllByRole('link', { name: L['nav.forum'] })).toHaveLength(0);
            expect(screen.queryAllByRole('link', { name: L['nav.events'] })).toHaveLength(0);
            expect(screen.queryAllByRole('link', { name: L['nav.documents'] })).toHaveLength(0);
            expect(screen.queryAllByRole('link', { name: L['nav.oracle'] })).toHaveLength(0);
            expect(screen.queryAllByRole('link', { name: L['nav.users'] })).toHaveLength(0);
            expect(screen.queryAllByRole('link', { name: L['nav.config'] })).toHaveLength(0);
            return;
          }

          // Authenticated: Forum, Events, Documents, AI Oracle render with routes.
          const forum = screen.getAllByRole('link', { name: L['nav.forum'] });
          expect(forum[0]).toHaveAttribute('href', '/forum');

          const events = screen.getAllByRole('link', { name: eventsDesktopName(language, admin) });
          expect(events.length).toBeGreaterThan(0);
          expect(events[0]).toHaveAttribute('href', '/events');

          const documents = screen.getAllByRole('link', { name: L['nav.documents'] });
          expect(documents[0]).toHaveAttribute('href', '/documents');

          const oracle = screen.getAllByRole('link', { name: L['nav.oracle'] });
          expect(oracle[0]).toHaveAttribute('href', '/oracle');

          // Admin-gated items: Users and Configuration present only for admins.
          if (admin) {
            const users = screen.getAllByRole('link', { name: L['nav.users'] });
            expect(users[0]).toHaveAttribute('href', '/admin/users');
            const config = screen.getAllByRole('link', { name: L['nav.config'] });
            expect(config[0]).toHaveAttribute('href', '/admin/configuration');
          } else {
            expect(screen.queryAllByRole('link', { name: L['nav.users'] })).toHaveLength(0);
            expect(screen.queryAllByRole('link', { name: L['nav.config'] })).toHaveLength(0);
          }
        },
      ),
    );
  });
});

// ---------------------------------------------------------------------------
// Preservation — Events "Manage events" dropdown gating (desktop). Only an
// authenticated admin, on hover, sees "Manage events" -> /admin/events.
// (Requirements 3.1, 3.5)
// ---------------------------------------------------------------------------
describe('Preservation — Events "Manage events" dropdown gating (desktop)', () => {
  it('admin hovering Events reveals "Manage events" -> /admin/events in both languages', async () => {
    for (const language of ['fr', 'en'] as const) {
      cleanup();
      localStorage.clear();
      const user = userEvent.setup();
      signInAsAdmin();
      renderLayout(language);

      const manageLabel = OBSERVED_LABELS[language]['nav.events.manage'];
      // Dropdown is hidden until hover.
      expect(screen.queryAllByRole('link', { name: manageLabel })).toHaveLength(0);

      // Admin: the Events desktop link carries the " ▾" caret in its name.
      const eventsLinks = screen.getAllByRole('link', { name: eventsDesktopName(language, true) });
      await user.hover(eventsLinks[0]);

      const manage = screen.getAllByRole('link', { name: manageLabel });
      expect(manage.length).toBeGreaterThan(0);
      expect(manage[0]).toHaveAttribute('href', '/admin/events');
    }
  });

  it('non-admin authenticated user never sees "Manage events" (nor "Manage tasks")', async () => {
    for (const language of ['fr', 'en'] as const) {
      cleanup();
      localStorage.clear();
      const user = userEvent.setup();
      signInAsUser();
      renderLayout(language);

      const manageEvents = OBSERVED_LABELS[language]['nav.events.manage'];
      // Hover Events (non-admin: no caret); no admin dropdown should ever appear.
      const eventsLinks = screen.getAllByRole('link', { name: eventsDesktopName(language, false) });
      await user.hover(eventsLinks[0]);

      expect(screen.queryAllByRole('link', { name: manageEvents })).toHaveLength(0);
      // The new Tasks admin entry must be gated identically — absent here too.
      expect(screen.queryAllByRole('link', { name: 'Manage tasks' })).toHaveLength(0);
      expect(screen.queryAllByRole('link', { name: 'Gérer les tâches' })).toHaveLength(0);
    }
  });
});

// ---------------------------------------------------------------------------
// Preservation — RENDER_MOBILE_NAV: the mobile menu renders the existing
// entries and gates the "Manage events" sub-entry to admins. (Requirements
// 3.1, 3.2, 3.5)
// ---------------------------------------------------------------------------
describe('Preservation — mobile nav entries and gating render as observed', () => {
  async function openMobileMenu(): Promise<HTMLElement> {
    const user = userEvent.setup();
    const menuButton = screen.getByRole('button', { name: 'Menu' });
    await user.click(menuButton);
    return document.body;
  }

  it('authenticated user sees Forum/Events/Documents/AI Oracle mobile entries with routes', async () => {
    for (const language of ['fr', 'en'] as const) {
      cleanup();
      localStorage.clear();
      signInAsUser();
      renderLayout(language);
      const container = await openMobileMenu();
      const L = OBSERVED_LABELS[language];

      const forum = linkByText(container, L['nav.forum']);
      expect(forum).not.toBeNull();
      expect(forum).toHaveAttribute('href', '/forum');

      const events = linkByText(container, L['nav.events']);
      expect(events).not.toBeNull();
      expect(events).toHaveAttribute('href', '/events');

      const documents = linkByText(container, L['nav.documents']);
      expect(documents).not.toBeNull();
      expect(documents).toHaveAttribute('href', '/documents');

      const oracle = linkByText(container, L['nav.oracle']);
      expect(oracle).not.toBeNull();
      expect(oracle).toHaveAttribute('href', '/oracle');

      // Non-admin: no admin sub-entries.
      expect(linkByText(container, L['nav.events.manage'])).toBeNull();
      expect(linkByText(container, L['nav.users'])).toBeNull();
      expect(linkByText(container, L['nav.config'])).toBeNull();
    }
  });

  it('admin sees mobile "Manage events" -> /admin/events plus Users/Configuration', async () => {
    for (const language of ['fr', 'en'] as const) {
      cleanup();
      localStorage.clear();
      signInAsAdmin();
      renderLayout(language);
      const container = await openMobileMenu();
      const L = OBSERVED_LABELS[language];

      const manageEvents = linkByText(container, L['nav.events.manage']);
      expect(manageEvents).not.toBeNull();
      expect(manageEvents).toHaveAttribute('href', '/admin/events');

      const users = linkByText(container, L['nav.users']);
      expect(users).not.toBeNull();
      expect(users).toHaveAttribute('href', '/admin/users');

      const config = linkByText(container, L['nav.config']);
      expect(config).not.toBeNull();
      expect(config).toHaveAttribute('href', '/admin/configuration');
    }
  });
});

// ---------------------------------------------------------------------------
// Preservation — admin-gating invariant across random combos: a non-admin
// authenticated user must see neither "Manage events" nor "Manage tasks",
// in either the desktop or mobile nav. (Requirement 3.5)
// ---------------------------------------------------------------------------
describe('Preservation — non-admin never sees admin-only dropdown entries', () => {
  it('non-admin authenticated user sees no "Manage events"/"Manage tasks" for any language', () => {
    fc.assert(
      fc.property(fc.constantFrom<Lang>('fr', 'en'), (language) => {
        cleanup();
        localStorage.clear();
        signInAsUser();
        renderLayout(language);

        const manageEvents = OBSERVED_LABELS[language]['nav.events.manage'];
        expect(screen.queryAllByRole('link', { name: manageEvents })).toHaveLength(0);
        expect(screen.queryAllByRole('link', { name: 'Manage tasks' })).toHaveLength(0);
        expect(screen.queryAllByRole('link', { name: 'Gérer les tâches' })).toHaveLength(0);
      }),
    );
  });
});
