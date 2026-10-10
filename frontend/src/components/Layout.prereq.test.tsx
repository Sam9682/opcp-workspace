import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, cleanup, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import fc from 'fast-check';
import { Layout } from './Layout';
import { PREREQ_NAV_ITEMS } from './prerequisites/types';
import { LanguageProvider } from '../hooks/useLanguage';
import { fr } from '../i18n/translations';

// Minimum property-test iterations mandated by the design (>= 100).
const NUM_RUNS = 100;

const PREREQ_TRIGGER_LABEL = 'OPCP installations';

// Nav entries carry a translation key (labelKey); links render their resolved
// text via t(labelKey). Under the default French language the accessible name
// of each link equals the French dictionary value for that key.
function navLabel(item: (typeof PREREQ_NAV_ITEMS)[number]): string {
  return fr[item.labelKey];
}

// Layout uses <Link>, so it must render inside a Router. Auth is read at render
// time via authService.isAuthenticated() (!!localStorage 'access_token') and
// authService.isAdmin() (localStorage 'user_role' === 'administrator'). We drive
// auth by seeding localStorage before render.
function renderLayout() {
  // Layout now calls useTranslation(), so wrap it in a LanguageProvider.
  // localStorage is cleared in beforeEach, so the default French language is
  // active and labels resolve to their French copy.
  return render(
    <LanguageProvider>
      <MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter>
    </LanguageProvider>,
  );
}

function authenticate() {
  localStorage.setItem('access_token', 'test-token');
}

beforeEach(() => {
  localStorage.clear();
  cleanup();
});

// Property 1: Navigation entries map to their configured routes.
// For any entry in PREREQ_NAV_ITEMS, the rendered navigation link targets
// exactly the route configured for that entry.
// Validates: Requirements 1.5, 1.6
describe('Property 1: navigation entries map to their configured routes', () => {
  it('renders a desktop dropdown link whose href equals each configured route', () => {
    // Render the authenticated Layout once and reveal the desktop dropdown; the
    // fast-check property then universally quantifies over PREREQ_NAV_ITEMS,
    // asserting each entry's link targets exactly its configured route. Rendering
    // once (rather than per-run) keeps this pure DOM property fast while still
    // covering every navigation entry.
    authenticate();
    renderLayout();

    // The desktop dropdown links live in the DOM only while hovered
    // (showPrereqMenu). Reveal them by entering the dropdown container. The
    // desktop trigger is the <span> carrying the menu label; its relative
    // container is the element wired with onMouseEnter.
    const triggers = screen.getAllByText(PREREQ_TRIGGER_LABEL);
    const desktopTrigger = triggers.find((el) => el.tagName === 'SPAN');
    expect(desktopTrigger).toBeDefined();
    const dropdownContainer = desktopTrigger!.parentElement as HTMLElement;
    fireEvent.mouseEnter(dropdownContainer);

    fc.assert(
      fc.property(fc.constantFrom(...PREREQ_NAV_ITEMS), (item) => {
        // Within the revealed dropdown, the link for this entry targets exactly
        // its configured route.
        const link = within(dropdownContainer).getByRole('link', {
          name: navLabel(item),
        }) as HTMLAnchorElement;
        expect(link.getAttribute('href')).toBe(item.route);
      }),
      { numRuns: NUM_RUNS },
    );
  });

  it('renders every configured entry as a link to its route (all entries)', () => {
    authenticate();
    renderLayout();

    const triggers = screen.getAllByText(PREREQ_TRIGGER_LABEL);
    const desktopTrigger = triggers.find((el) => el.tagName === 'SPAN');
    const dropdownContainer = desktopTrigger!.parentElement as HTMLElement;
    fireEvent.mouseEnter(dropdownContainer);

    for (const item of PREREQ_NAV_ITEMS) {
      const link = within(dropdownContainer).getByRole('link', {
        name: navLabel(item),
      }) as HTMLAnchorElement;
      expect(link.getAttribute('href')).toBe(item.route);
    }
  });

  it('reveals the dropdown links via user hover as well (user-event)', async () => {
    const user = userEvent.setup();
    authenticate();
    renderLayout();

    const triggers = screen.getAllByText(PREREQ_TRIGGER_LABEL);
    const desktopTrigger = triggers.find((el) => el.tagName === 'SPAN') as HTMLElement;
    await user.hover(desktopTrigger);

    const dropdownContainer = desktopTrigger.parentElement as HTMLElement;
    for (const item of PREREQ_NAV_ITEMS) {
      const link = within(dropdownContainer).getByRole('link', {
        name: navLabel(item),
      }) as HTMLAnchorElement;
      expect(link.getAttribute('href')).toBe(item.route);
    }
  });

  it('renders a mobile menu link whose href equals each configured route', async () => {
    // Mobile counterpart of the desktop property: open the mobile menu once for
    // an authenticated user, then universally quantify over PREREQ_NAV_ITEMS to
    // assert each entry's mobile link targets exactly its configured route.
    const user = userEvent.setup();
    authenticate();
    renderLayout();

    // Reveal the mobile navigation (the section + entry links render only once
    // the mobile menu is open).
    await user.click(screen.getByLabelText('Menu'));

    fc.assert(
      fc.property(fc.constantFrom(...PREREQ_NAV_ITEMS), (item) => {
        // Every mobile link carrying this entry's label targets exactly its route.
        const links = screen.getAllByRole('link', {
          name: navLabel(item),
        }) as HTMLAnchorElement[];
        expect(links.length).toBeGreaterThan(0);
        expect(links.every((l) => l.getAttribute('href') === item.route)).toBe(true);
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// Unit tests for auth-gated visibility of the prerequisites menu.
// Validates: Requirements 1.1, 1.2, 2.1, 2.2
describe('prerequisites menu auth-gated visibility', () => {
  describe('when authenticated', () => {
    it('shows the desktop prerequisites trigger', () => {
      authenticate();
      renderLayout();

      // The desktop trigger (a <span>) is present.
      const triggers = screen.getAllByText(PREREQ_TRIGGER_LABEL);
      expect(triggers.some((el) => el.tagName === 'SPAN')).toBe(true);
    });

    it('shows the prerequisites section and its entries in the mobile menu when opened', async () => {
      const user = userEvent.setup();
      authenticate();
      renderLayout();

      // Open the mobile menu.
      await user.click(screen.getByLabelText('Menu'));

      // The mobile section heading is present...
      const mobileHeadings = screen
        .getAllByText(PREREQ_TRIGGER_LABEL)
        .filter((el) => el.tagName === 'DIV');
      expect(mobileHeadings.length).toBeGreaterThan(0);

      // ...along with a link for each configured entry pointing at its route.
      for (const item of PREREQ_NAV_ITEMS) {
        const links = screen.getAllByRole('link', {
          name: navLabel(item),
        }) as HTMLAnchorElement[];
        expect(links.length).toBeGreaterThan(0);
        expect(links.every((l) => l.getAttribute('href') === item.route)).toBe(true);
      }
    });
  });

  describe('when not authenticated', () => {
    it('hides the desktop prerequisites trigger', () => {
      // localStorage cleared in beforeEach: not authenticated.
      renderLayout();

      expect(screen.queryByText(PREREQ_TRIGGER_LABEL)).toBeNull();
      for (const item of PREREQ_NAV_ITEMS) {
        expect(screen.queryByRole('link', { name: navLabel(item) })).toBeNull();
      }
    });

    it('hides the prerequisites section from the mobile menu even when opened', async () => {
      const user = userEvent.setup();
      renderLayout();

      // Open the mobile menu.
      await user.click(screen.getByLabelText('Menu'));

      // Neither the section heading nor any entry link is present.
      expect(screen.queryByText(PREREQ_TRIGGER_LABEL)).toBeNull();
      for (const item of PREREQ_NAV_ITEMS) {
        expect(screen.queryByRole('link', { name: navLabel(item) })).toBeNull();
      }
    });
  });
});
