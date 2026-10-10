/**
 * Integration tests — member-facing Tasks route, end to end through the real App.
 * Spec: .kiro/specs/assigned-events-tasks-empty-fix (Task 4 — integration coverage)
 *
 * A DISTINCT file from `App.tasksNav.integration.test.tsx`, which belongs to the
 * separate `tasks-menu-not-displayed` spec and exercises the ADMIN "Manage
 * tasks" -> /admin/tasks flow. These tests cover the member-facing `/tasks`
 * route added by THIS bugfix, per the design's Integration Tests section:
 *
 *  - Full nav flow: an authenticated member clicks the "Tasks" nav link, lands
 *    on /tasks, and sees their tasks rendered.
 *  - Context switching: /tasks -> /events -> /admin/tasks each mount their own
 *    correct page without cross-interference.
 *  - Auth flow: unauthenticated /tasks redirects to /login; after signing in,
 *    /tasks reaches the member Tasks page.
 *
 * Conventions mirror App.tasksNav.integration.test.tsx / App.memberTasksRoute
 * .test.tsx: localStorage auth seeding, the App's own BrowserRouter driven via
 * the history API, and the task/event/admin service modules mocked with
 * vi.fn()s so pages render deterministically without network access.
 *
 * A member (non-admin) sees a PLAIN "Tasks" nav link (no " ▾" caret — the caret
 * and the "Manage tasks" dropdown are admin-only), so the link's accessible
 * name is exactly the nav label. The context-switching test uses an admin
 * because /admin/tasks requires one; an admin still gets the read-only member
 * page at /tasks.
 *
 * Validates: Requirements 2.3, 2.4, 2.5, 3.1, 3.4
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import App from './App';

// Pages under exercise fetch on mount. Mock the service modules so every page
// renders cleanly with no network access.
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

// localStorage keys read by authService for auth/admin gating.
const TOKEN_KEY = 'access_token';
const ROLE_KEY = 'user_role';
const USER_KEY = 'user';
// localStorage key under which the active language persists (Language_Store).
const LANG_KEY = 'opcp.language';

/** Sign in as an authenticated user of the given role. */
function signIn(role: 'member' | 'administrator') {
  localStorage.setItem(TOKEN_KEY, 'test-token');
  localStorage.setItem(ROLE_KEY, role);
  localStorage.setItem(
    USER_KEY,
    JSON.stringify({ id: 'u1', email: `${role}@opcp.test`, first_name: 'Us', last_name: 'Er', role }),
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

/** A sample task shaped like the taskService `Task` type. */
function sampleTask(overrides: Record<string, unknown> = {}) {
  return {
    id: 't-1',
    title: 'Préparer le rapport trimestriel',
    description: 'Compiler les chiffres du trimestre',
    start_date: '2030-03-01T09:00:00Z',
    end_date: '2030-03-05T17:00:00Z',
    location: 'Bureau principal',
    owner_id: 'u1',
    assigned_user_ids: ['u1'],
    status: 'scheduled',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

beforeEach(() => {
  localStorage.clear();
  goto('/');
  mockedListTasks.mockReset();
  mockedListEvents.mockReset();
  mockedListUsers.mockReset();
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
// Full nav flow — member clicks the "Tasks" nav link, lands on /tasks, and sees
// their tasks rendered. (Requirements 2.3, 3.4)
// ---------------------------------------------------------------------------
describe('Member Tasks navigation full flow (integration)', () => {
  it('member clicks the Tasks nav link, lands on /tasks, and sees their tasks', async () => {
    mockedListTasks.mockResolvedValue([sampleTask()] as never);
    signIn('member');
    setLanguage('en');
    goto('/');

    render(<App />);

    // A member sees a plain "Tasks" link (no caret) pointing to /tasks. Both the
    // desktop and mobile navs render one, so take the first.
    const tasksLinks = screen.getAllByRole('link', { name: 'Tasks' });
    expect(tasksLinks.length).toBeGreaterThan(0);
    expect(tasksLinks[0]).toHaveAttribute('href', '/tasks');

    fireEvent.click(tasksLinks[0]);

    // The router navigated to /tasks (no redirect to /login for an authed user).
    await waitFor(() => expect(window.location.pathname).toBe('/tasks'));

    // The member Tasks page mounted (heading page.tasks.title -> "Tasks") and
    // fetched its data on mount.
    const heading = await screen.findByRole('heading', { name: 'Tasks' });
    expect(heading).toBeInTheDocument();
    await waitFor(() => expect(mockedListTasks).toHaveBeenCalled());

    // The mocked task is rendered on the page.
    expect(await screen.findByText('Préparer le rapport trimestriel')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Context switching — /tasks -> /events -> /admin/tasks each mount their own
// correct page without cross-interference. (Requirements 2.5, 3.1)
// ---------------------------------------------------------------------------
describe('Member Tasks context switching (integration)', () => {
  it('navigates /tasks -> /events -> /admin/tasks and mounts each correct page', async () => {
    // Admin: has access to /admin/tasks, and still gets the read-only member
    // page at /tasks.
    signIn('administrator');
    setLanguage('en');

    // 1) /tasks -> member TasksPage.
    goto('/tasks');
    render(<App />);
    await waitFor(() => expect(window.location.pathname).toBe('/tasks'));
    expect(await screen.findByRole('heading', { name: 'Tasks' })).toBeInTheDocument();
    await waitFor(() => expect(mockedListTasks).toHaveBeenCalled());
    // The admin management page did NOT mount here.
    expect(screen.queryByRole('heading', { name: 'Manage tasks' })).not.toBeInTheDocument();

    // 2) /events -> EventsPage (unmount then remount the App at the new path).
    cleanup();
    goto('/events');
    render(<App />);
    await waitFor(() => expect(window.location.pathname).toBe('/events'));
    expect(await screen.findByRole('heading', { name: 'Events' })).toBeInTheDocument();
    await waitFor(() => expect(mockedListEvents).toHaveBeenCalled());
    // Neither Tasks page leaked into the Events route.
    expect(screen.queryByRole('heading', { name: 'Tasks' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Manage tasks' })).not.toBeInTheDocument();

    // 3) /admin/tasks -> AdminTasksPage (heading nav.tasks.manage -> "Manage tasks").
    cleanup();
    goto('/admin/tasks');
    render(<App />);
    await waitFor(() => expect(window.location.pathname).toBe('/admin/tasks'));
    expect(await screen.findByRole('heading', { name: 'Manage tasks' })).toBeInTheDocument();
    // The read-only member Tasks heading is not the one that mounted here.
    expect(screen.queryByRole('heading', { name: 'Tasks' })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Auth flow — unauthenticated /tasks redirects to /login; after signing in,
// /tasks reaches the member Tasks page. (Requirement 3.4)
// ---------------------------------------------------------------------------
describe('Member Tasks auth flow (integration)', () => {
  it('redirects an unauthenticated visitor at /tasks to /login', async () => {
    // No auth seeded: ProtectedRoute redirects to /login.
    setLanguage('en');
    goto('/tasks');

    render(<App />);

    await waitFor(() => expect(window.location.pathname).toBe('/login'));
    // The login page rendered (page.login.title -> EN "Log in" heading), and the
    // member Tasks page did NOT mount / fetch.
    expect(await screen.findByRole('heading', { name: /log\s*in|connexion/i })).toBeInTheDocument();
    expect(mockedListTasks).not.toHaveBeenCalled();
  });

  it('after signing in, navigating to /tasks reaches the member Tasks page', async () => {
    mockedListTasks.mockResolvedValue([sampleTask({ title: 'Ma tâche' })] as never);
    setLanguage('en');

    // Start unauthenticated at /tasks -> redirected to /login.
    goto('/tasks');
    render(<App />);
    await waitFor(() => expect(window.location.pathname).toBe('/login'));

    // Simulate a completed sign-in (authService persists a token on success),
    // then navigate to /tasks. Remount the App so the router re-evaluates the
    // now-satisfied ProtectedRoute guard at the new location.
    signIn('member');
    cleanup();
    goto('/tasks');
    render(<App />);

    await waitFor(() => expect(window.location.pathname).toBe('/tasks'));
    expect(await screen.findByRole('heading', { name: 'Tasks' })).toBeInTheDocument();
    await waitFor(() => expect(mockedListTasks).toHaveBeenCalled());
    expect(await screen.findByText('Ma tâche')).toBeInTheDocument();
  });
});
