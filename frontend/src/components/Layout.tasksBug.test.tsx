/**
 * Bug condition exploration test — Property 1: Bug Condition.
 * Spec: .kiro/specs/tasks-menu-not-displayed
 *
 * CRITICAL: These assertions encode the EXPECTED (fixed) behavior. They MUST
 * FAIL on the current (unfixed) code — that failure confirms the Tasks
 * navigation wiring is absent (no nav item, no "Manage tasks" dropdown, no
 * translation key, no /admin/tasks route). They will PASS once the fix wires
 * Tasks analogously to Events.
 *
 * The bug is deterministic (wiring present or absent), so per the design the
 * property is scoped to the concrete failing navigation interactions rather
 * than random generation:
 *   RENDER_DESKTOP_NAV, RENDER_DESKTOP_NAV (admin), RENDER_MOBILE_NAV,
 *   RESOLVE_LABEL, NAVIGATE (edge case).
 *
 * Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, within, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Layout } from './Layout';
import { LanguageProvider } from '../hooks/useLanguage';
import { dictionaries } from '../i18n/translations';

// localStorage keys read by authService for auth/admin gating.
const TOKEN_KEY = 'access_token';
const ROLE_KEY = 'user_role';
const USER_KEY = 'user';
// localStorage key under which the active language persists.
const LANG_KEY = 'opcp.language';

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

/** Render Layout inside a router + language provider. */
function renderLayout(language: 'fr' | 'en' = 'fr') {
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

/** Find a Link by its accessible text within a container. */
function linkByText(container: HTMLElement, text: string): HTMLElement | null {
  const links = within(container).queryAllByRole('link');
  return links.find((el) => el.textContent?.trim() === text) ?? null;
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});

// ---------------------------------------------------------------------------
// RESOLVE_LABEL — the translation keys nav.tasks / nav.tasks.manage must exist.
// On unfixed code the keys are absent; resolve() returns the key itself, so
// these assertions fail. (Requirement 1.4)
// ---------------------------------------------------------------------------
describe('Bug Condition — RESOLVE_LABEL: Tasks translation keys resolve in FR and EN', () => {
  it('nav.tasks resolves to "Tâches" (FR) and "Tasks" (EN)', () => {
    expect(dictionaries.fr['nav.tasks']).toBe('Tâches');
    expect(dictionaries.en['nav.tasks']).toBe('Tasks');
  });

  it('nav.tasks.manage resolves to "Gérer les tâches" (FR) and "Manage tasks" (EN)', () => {
    expect(dictionaries.fr['nav.tasks.manage']).toBe('Gérer les tâches');
    expect(dictionaries.en['nav.tasks.manage']).toBe('Manage tasks');
  });
});

// ---------------------------------------------------------------------------
// RENDER_DESKTOP_NAV — a "Tasks" item must render alongside "Events".
// (Requirements 1.1, 1.2)
// ---------------------------------------------------------------------------
describe('Bug Condition — RENDER_DESKTOP_NAV: Tasks item renders alongside Events', () => {
  it('authenticated user sees a "Tasks" nav item next to "Events"', () => {
    signInAsUser();
    renderLayout('en');

    // Sanity: Events is present (the template being mirrored).
    expect(screen.getAllByRole('link', { name: 'Events' }).length).toBeGreaterThan(0);

    // The bug: no "Tasks" nav item exists.
    expect(screen.getAllByRole('link', { name: 'Tasks' }).length).toBeGreaterThan(0);
  });

  it('authenticated admin hovering Tasks reveals a "Manage tasks" link to /admin/tasks', async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    renderLayout('en');

    // Reveal the Tasks dropdown by hovering the Tasks link (mirrors Events).
    // For admins the desktop Tasks link appends a " ▾" caret (identical to the
    // Events link), so its accessible name is "Tasks ▾". Query with a
    // caret-aware regex — the same approach used in Layout.preservation.test.tsx
    // (eventsDesktopName) — because Testing Library's default exact match on
    // 'Tasks' cannot locate "Tasks ▾".
    const tasksLinks = screen.getAllByRole('link', { name: /^Tasks\s*▾$/ });
    await user.hover(tasksLinks[0]);

    const manage = screen.getAllByRole('link', { name: 'Manage tasks' });
    expect(manage.length).toBeGreaterThan(0);
    expect(manage[0]).toHaveAttribute('href', '/admin/tasks');
  });
});

// ---------------------------------------------------------------------------
// RENDER_MOBILE_NAV — the mobile menu must render a "Tasks" entry, and for
// admins a "Manage tasks" sub-entry to /admin/tasks. (Requirement 1.3)
// ---------------------------------------------------------------------------
describe('Bug Condition — RENDER_MOBILE_NAV: Tasks entries render in the mobile menu', () => {
  async function openMobileMenu(): Promise<HTMLElement> {
    const user = userEvent.setup();
    const menuButton = screen.getByRole('button', { name: 'Menu' });
    await user.click(menuButton);
    return document.body;
  }

  it('authenticated user sees a "Tasks" entry in the mobile menu', async () => {
    signInAsUser();
    renderLayout('en');
    const container = await openMobileMenu();

    expect(linkByText(container, 'Tasks')).not.toBeNull();
  });

  it('authenticated admin sees a "Manage tasks" mobile sub-entry to /admin/tasks', async () => {
    signInAsAdmin();
    renderLayout('en');
    const container = await openMobileMenu();

    const manage = linkByText(container, 'Manage tasks');
    expect(manage).not.toBeNull();
    expect(manage).toHaveAttribute('href', '/admin/tasks');
  });
});

// ---------------------------------------------------------------------------
// RENDER — the desktop Tasks link points to /tasks (mirrors Events -> /events).
// ---------------------------------------------------------------------------
describe('Bug Condition — Tasks link targets /tasks', () => {
  it('the "Tasks" nav item links to /tasks', () => {
    signInAsUser();
    renderLayout('en');

    const tasksLinks = screen.getAllByRole('link', { name: 'Tasks' });
    expect(tasksLinks.length).toBeGreaterThan(0);
    expect(tasksLinks[0]).toHaveAttribute('href', '/tasks');
  });
});
