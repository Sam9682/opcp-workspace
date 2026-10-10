/**
 * Integration test — Tasks navigation flow (end to end through the real App).
 * Spec: .kiro/specs/tasks-menu-not-displayed (Task 4)
 *
 * These tests render the REAL `App` (its own BrowserRouter + LanguageProvider)
 * as an authenticated admin and exercise the Tasks navigation wiring end to
 * end, per the design's Integration Tests section:
 *
 *  - Full flow: an authenticated admin opens the app, sees Tasks alongside
 *    Events in the desktop nav, reveals the Tasks dropdown, clicks "Manage
 *    tasks", and lands on /admin/tasks rendering the Tasks admin page under
 *    ProtectedRoute.
 *  - Context switching: toggling FR/EN via the nav language buttons updates
 *    both the Events and Tasks labels together, while all other existing nav
 *    labels remain correct.
 *  - Regression: navigating to /admin/events (and confirming Home) still
 *    renders the corresponding page unchanged under its existing protection.
 *
 * Setup mirrors the established conventions:
 *  - localStorage auth seeding (access_token / user_role / user), matching
 *    Layout.tasksBug.test.tsx and App.tasksRoute.test.tsx.
 *  - The App uses BrowserRouter, so the initial location is driven via the
 *    history API (window.history.pushState), matching App.tasksRoute.test.tsx.
 *  - The admin desktop Tasks/Events links append a " ▾" caret to their
 *    accessible name, so they are located with a caret-aware regex
 *    (/^Tasks\s*▾$/ etc.), consistent with the preservation/bug-condition tests.
 *  - AdminTasksPage and AdminEventsPage call taskService/eventService and
 *    adminService on mount; those service modules are mocked with vi.fn()s so
 *    the pages render deterministically without network noise.
 *
 * KNOWN GAP (reported, not fixed here): the desktop/mobile Tasks link points to
 * /tasks, but App.tsx registers no /tasks route (only /admin/tasks). This
 * bugfix's scope (design + tasks 3.1-3.3) is the /admin/tasks admin route, and
 * requirements 2.2/2.5 specify landing on /admin/tasks via "Manage tasks".
 * The full flow below therefore exercises the admin path and does NOT rely on
 * a /tasks public route.
 *
 * Validates: Requirements 2.1, 2.2, 2.5, 3.1, 3.3, 3.4
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

// localStorage keys read by authService for auth/admin gating.
const TOKEN_KEY = 'access_token';
const ROLE_KEY = 'user_role';
const USER_KEY = 'user';
// localStorage key under which the active language persists (Language_Store).
const LANG_KEY = 'opcp.language';

// AdminTasksPage loads tasks + members on mount; AdminEventsPage loads events +
// members. Mock the service modules so both admin pages render cleanly with no
// network access. adminService is shared by both pages.
vi.mock('./services/taskService', () => ({
  taskService: {
    listTasks: vi.fn(),
    createTask: vi.fn(),
    updateTask: vi.fn(),
    deleteTask: vi.fn(),
  },
}));

vi.mock('./services/eventService', () => ({
  eventService: {
    listEvents: vi.fn(),
    createEvent: vi.fn(),
    updateEvent: vi.fn(),
    deleteEvent: vi.fn(),
  },
}));

vi.mock('./services/adminService', () => ({
  adminService: {
    listUsers: vi.fn(),
  },
}));

import { taskService } from './services/taskService';
import { eventService } from './services/eventService';
import { adminService } from './services/adminService';

const mockedListTasks = vi.mocked(taskService.listTasks);
const mockedListEvents = vi.mocked(eventService.listEvents);
const mockedListUsers = vi.mocked(adminService.listUsers);

/** Sign in as an authenticated administrator. */
function signInAsAdmin() {
  localStorage.setItem(TOKEN_KEY, 'test-token');
  localStorage.setItem(ROLE_KEY, 'administrator');
  localStorage.setItem(
    USER_KEY,
    JSON.stringify({ id: '1', email: 'admin@opcp.test', first_name: 'Ad', last_name: 'Min', role: 'administrator' }),
  );
}

/** Seed the active language before the App reads it on first render. */
function setLanguage(language: 'fr' | 'en') {
  localStorage.setItem(LANG_KEY, language);
}

/** Drive the initial BrowserRouter location via the history API. */
function goto(path: string) {
  window.history.pushState({}, '', path);
}

beforeEach(() => {
  localStorage.clear();
  goto('/');
  // Default: empty lists so admin pages render their (empty) content quickly.
  mockedListTasks.mockResolvedValue([]);
  mockedListEvents.mockResolvedValue([]);
  mockedListUsers.mockResolvedValue({ members: [] } as unknown as Awaited<
    ReturnType<typeof adminService.listUsers>
  >);
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  goto('/');
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Full flow — admin opens the app, sees Tasks alongside Events, reveals the
// Tasks dropdown, clicks "Manage tasks", and lands on /admin/tasks.
// (Requirements 2.1, 2.2, 2.5)
// ---------------------------------------------------------------------------
describe('Tasks navigation full flow (integration)', () => {
  it('admin sees Tasks next to Events, opens the dropdown, and reaches /admin/tasks', async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    setLanguage('en');
    goto('/');

    render(<App />);

    // Tasks renders alongside Events in the desktop nav. Admin links carry the
    // " ▾" caret, so match with a caret-aware regex.
    const eventsLinks = screen.getAllByRole('link', { name: /^Events\s*▾$/ });
    expect(eventsLinks.length).toBeGreaterThan(0);
    expect(eventsLinks[0]).toHaveAttribute('href', '/events');

    const tasksLinks = screen.getAllByRole('link', { name: /^Tasks\s*▾$/ });
    expect(tasksLinks.length).toBeGreaterThan(0);
    expect(tasksLinks[0]).toHaveAttribute('href', '/tasks');

    // The "Manage tasks" dropdown entry is hidden until the Tasks item is hovered.
    expect(screen.queryAllByRole('link', { name: 'Manage tasks' })).toHaveLength(0);

    // Reveal the dropdown and click "Manage tasks". Use fireEvent.click for the
    // navigation: userEvent.click moves the pointer, which fires onMouseLeave on
    // the Tasks container and unmounts the hover-revealed dropdown before the
    // click lands. fireEvent dispatches the click directly on the resolved link
    // without pointer movement, so the <Link> navigation fires reliably.
    await user.hover(tasksLinks[0]);
    const manage = await screen.findByRole('link', { name: 'Manage tasks' });
    expect(manage).toHaveAttribute('href', '/admin/tasks');

    fireEvent.click(manage);

    // The router navigated to /admin/tasks and the Tasks admin page rendered
    // under ProtectedRoute (no redirect to /login for an admin).
    await waitFor(() => expect(window.location.pathname).toBe('/admin/tasks'));
    const heading = await screen.findByRole('heading', { name: 'Manage tasks' });
    expect(heading).toBeInTheDocument();

    // The Tasks admin page mounted and requested its data (proving the real
    // page rendered, not a fallthrough).
    await waitFor(() => expect(mockedListTasks).toHaveBeenCalled());
  });
});

// ---------------------------------------------------------------------------
// Context switching — toggling FR/EN updates both Events and Tasks labels
// together while all other nav labels remain correct. (Requirement 3.3)
// ---------------------------------------------------------------------------
describe('Tasks navigation language switching (integration)', () => {
  it('toggling EN->FR->EN updates Events + Tasks labels and preserves other nav labels', async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    setLanguage('en');
    goto('/');

    render(<App />);

    // Baseline (EN): Events + Tasks (with admin caret), plus a sample of other
    // existing nav labels resolving in English.
    expect(screen.getAllByRole('link', { name: /^Events\s*▾$/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: /^Tasks\s*▾$/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Home' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Forum' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Users' }).length).toBeGreaterThan(0);

    // Switch to French via the nav language toggle (FR button).
    await user.click(screen.getByRole('button', { name: 'FR', pressed: false }));

    // Both Events and Tasks labels update to French together...
    await waitFor(() =>
      expect(screen.getAllByRole('link', { name: /^Événements\s*▾$/ }).length).toBeGreaterThan(0),
    );
    expect(screen.getAllByRole('link', { name: /^Tâches\s*▾$/ }).length).toBeGreaterThan(0);
    // ...and the English variants are gone.
    expect(screen.queryAllByRole('link', { name: /^Events\s*▾$/ })).toHaveLength(0);
    expect(screen.queryAllByRole('link', { name: /^Tasks\s*▾$/ })).toHaveLength(0);

    // Other existing nav labels resolve correctly in French.
    expect(screen.getAllByRole('link', { name: 'Accueil' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Forum' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Utilisateurs' }).length).toBeGreaterThan(0);

    // Switch back to English; both labels revert together.
    await user.click(screen.getByRole('button', { name: 'EN', pressed: false }));
    await waitFor(() =>
      expect(screen.getAllByRole('link', { name: /^Events\s*▾$/ }).length).toBeGreaterThan(0),
    );
    expect(screen.getAllByRole('link', { name: /^Tasks\s*▾$/ }).length).toBeGreaterThan(0);
    // English labels are back and the French "Accueil" is gone.
    expect(screen.getAllByRole('link', { name: 'Home' }).length).toBeGreaterThan(0);
    expect(screen.queryAllByRole('link', { name: 'Accueil' })).toHaveLength(0);
  });

  it('reveals localized "Manage tasks" / "Gérer les tâches" in the matching language', async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    setLanguage('fr');
    goto('/');

    render(<App />);

    // French: the Tasks item carries the admin caret and its dropdown reads
    // "Gérer les tâches" -> /admin/tasks.
    const tasksLinks = screen.getAllByRole('link', { name: /^Tâches\s*▾$/ });
    expect(tasksLinks.length).toBeGreaterThan(0);
    await user.hover(tasksLinks[0]);

    const manage = await screen.findByRole('link', { name: 'Gérer les tâches' });
    expect(manage).toHaveAttribute('href', '/admin/tasks');
  });
});

// ---------------------------------------------------------------------------
// Regression — existing routes still render under their existing protection
// after the additive Tasks fix. (Requirement 3.4)
// ---------------------------------------------------------------------------
describe('Existing routes regression after Tasks fix (integration)', () => {
  it('/admin/events still renders the Events admin page under ProtectedRoute for an admin', async () => {
    signInAsAdmin();
    setLanguage('fr');
    goto('/admin/events');

    render(<App />);

    // No redirect to /login for an admin, and the Events admin page rendered.
    // AdminEventsPage's heading uses page.adminEvents.title ("Gestion des
    // événements" in FR), distinct from the nav "Gérer les événements" label.
    await waitFor(() => expect(window.location.pathname).toBe('/admin/events'));
    const heading = await screen.findByRole('heading', { name: 'Gestion des événements' });
    expect(heading).toBeInTheDocument();
    await waitFor(() => expect(mockedListEvents).toHaveBeenCalled());
  });

  it('the Home route renders unchanged with Tasks + Events both present in the nav', async () => {
    signInAsAdmin();
    setLanguage('en');
    goto('/');

    render(<App />);

    // Home rendered at "/" and the nav shows both Events and Tasks — the
    // additive fix left the existing structure intact.
    expect(window.location.pathname).toBe('/');
    expect(screen.getAllByRole('link', { name: /^Events\s*▾$/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: /^Tasks\s*▾$/ }).length).toBeGreaterThan(0);
    // Existing Events "Manage events" dropdown wiring is preserved.
    const user = userEvent.setup();
    await user.hover(screen.getAllByRole('link', { name: /^Events\s*▾$/ })[0]);
    const manageEvents = await screen.findByRole('link', { name: 'Manage events' });
    expect(manageEvents).toHaveAttribute('href', '/admin/events');
  });
});
