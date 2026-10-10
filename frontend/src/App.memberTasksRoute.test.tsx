/**
 * Bug condition exploration test — Property 1: Bug Condition, Member Tasks Route
 * Renders and Fetches.
 * Spec: .kiro/specs/assigned-events-tasks-empty-fix
 *
 * CRITICAL BUGFIX SEMANTICS: every assertion below encodes the EXPECTED (fixed)
 * behavior for the member-facing `/tasks` route. It MUST FAIL on the current
 * (unfixed) code — that failure CONFIRMS the bug: `App.tsx` has no
 * `<Route path="/tasks">` and there is no member-facing `TasksPage`, so
 * navigating to `/tasks` matches nothing inside `Layout`, mounts no component,
 * and `taskService.listTasks()` is never called (blank content area).
 *
 * This is the exact analog of the previously fixed Events defect (`/events` ->
 * `EventsPage`). The test will PASS once the fix registers
 * `/tasks -> TasksPage` under `ProtectedRoute` and the page calls
 * `taskService.listTasks()` on mount, mirroring `EventsPage`.
 *
 * DO NOT fix the code or weaken these assertions to make this pass — a FAILING
 * run here is the SUCCESS outcome for this task.
 *
 * Setup mirrors the established conventions (App.tasksRoute.test.tsx /
 * App.tasksNav.integration.test.tsx): localStorage auth seeding, BrowserRouter
 * driven via the history API, and the taskService module mocked with vi.fn()s.
 *
 * Validates: Requirements 1.1, 1.2, 1.3 (bug), 2.1-2.5 (expected behavior)
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import App from './App';

// The member Tasks page fetches on mount via taskService.listTasks(). Mock the
// module so the (fixed) page renders deterministically without network access,
// and so we can assert the fetch fires. On unfixed code no component mounts, so
// this mock is simply never called — which is precisely what we assert against.
vi.mock('./services/taskService', () => ({
  taskService: {
    listTasks: vi.fn(),
    createTask: vi.fn(),
    updateTask: vi.fn(),
    deleteTask: vi.fn(),
  },
}));

import { taskService } from './services/taskService';

const mockedListTasks = vi.mocked(taskService.listTasks);

// localStorage keys read by authService for auth/admin gating.
const TOKEN_KEY = 'access_token';
const ROLE_KEY = 'user_role';
const USER_KEY = 'user';

/** Sign in as an authenticated user of the given role. */
function signIn(role: 'member' | 'administrator') {
  localStorage.setItem(TOKEN_KEY, 'test-token');
  localStorage.setItem(ROLE_KEY, role);
  localStorage.setItem(
    USER_KEY,
    JSON.stringify({
      id: 'u1',
      email: `${role}@opcp.test`,
      first_name: 'Us',
      last_name: 'Er',
      role,
    }),
  );
}

/** Drive the initial BrowserRouter location via the history API. */
function goto(path: string) {
  window.history.pushState({}, '', path);
}

/** A sample task shaped like the taskService `Task` type. */
function sampleTask(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 't-1',
    title: 'Préparer le rapport trimestriel',
    description: 'Compiler les chiffres du trimestre',
    start_date: '2030-03-01T09:00:00Z',
    // Use a distinct end-date DAY so the start-date day/month/year fragment
    // ("01/03/2030") is unique in the rendered card and findByText resolves to
    // a single element (the start date), not two overlapping date lines.
    end_date: '2030-03-02T17:00:00Z',
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
  goto('/tasks');
  mockedListTasks.mockReset();
  mockedListTasks.mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  goto('/');
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Test case 1 — Member navigates to /tasks: a member-facing Tasks page renders
// and taskService.listTasks() is called on mount. (Requirements 2.1, 2.2)
// On unfixed code: no route matches /tasks, nothing mounts, listTasks() is
// never called, and no Tasks heading is found -> this test FAILS (expected).
// ---------------------------------------------------------------------------
describe('Bug Condition — member at /tasks renders the page and fetches (Req 2.1, 2.2)', () => {
  it('mounts a member Tasks page and calls listTasks() on mount', async () => {
    signIn('member');
    render(<App />);

    // The authenticated member is not redirected to /login and stays at /tasks.
    await waitFor(() => expect(window.location.pathname).toBe('/tasks'));

    // A member-facing Tasks heading renders (title key page.tasks.title ->
    // "Tâches" in FR / "Tasks" in EN). On unfixed code nothing mounts here.
    const heading = await screen.findByRole(
      'heading',
      { name: /t[aâ]ches|tasks/i },
      { timeout: 3000 },
    );
    expect(heading).toBeInTheDocument();

    // The page fetched its data on mount (proves a real page mounted, not a
    // fallthrough). On unfixed code this call never happens.
    await waitFor(() => expect(mockedListTasks).toHaveBeenCalled());
  });
});

// ---------------------------------------------------------------------------
// Test case 2 — Admin navigates to /tasks: the read-only member Tasks page
// renders (not a redirect, not the admin management page). (Requirement 2.1)
// ---------------------------------------------------------------------------
describe('Bug Condition — admin at /tasks renders the read-only member page (Req 2.1)', () => {
  it('mounts the member Tasks page for an admin and calls listTasks()', async () => {
    signIn('administrator');
    render(<App />);

    await waitFor(() => expect(window.location.pathname).toBe('/tasks'));

    const heading = await screen.findByRole(
      'heading',
      { name: /t[aâ]ches|tasks/i },
      { timeout: 3000 },
    );
    expect(heading).toBeInTheDocument();
    await waitFor(() => expect(mockedListTasks).toHaveBeenCalled());
  });
});

// ---------------------------------------------------------------------------
// Test case 3 — Tasks displayed: with listTasks() mocked to return a sample
// task, the page shows the task's title, dates, and status. (Requirement 2.3)
// ---------------------------------------------------------------------------
describe('Bug Condition — mocked tasks display title/dates/status (Req 2.3)', () => {
  it('renders a card with the task title, formatted dates, and status', async () => {
    mockedListTasks.mockResolvedValue([sampleTask()] as never);
    signIn('member');
    render(<App />);

    // Title of the task appears.
    expect(
      await screen.findByText('Préparer le rapport trimestriel', undefined, { timeout: 3000 }),
    ).toBeInTheDocument();

    // The start date formatted with toLocaleString('fr-FR') is present. Match a
    // day/month/year fragment rather than the exact locale string (timezone).
    const formatted = new Date('2030-03-01T09:00:00Z').toLocaleString('fr-FR');
    const dayMonthYear = formatted.split(' ')[0]; // e.g. "01/03/2030"
    expect(await screen.findByText(new RegExp(dayMonthYear.replace(/\//g, '\\/')))).toBeInTheDocument();

    // The status badge text is shown.
    expect(await screen.findByText(/scheduled/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Test case 4 — Empty state: with listTasks() mocked to return [], an empty
// state message renders rather than a blank content area. (Requirement 2.4)
// ---------------------------------------------------------------------------
describe('Bug Condition — empty list shows an empty-state message (Req 2.4)', () => {
  it('renders a non-blank empty-state message when there are no tasks', async () => {
    mockedListTasks.mockResolvedValue([] as never);
    signIn('member');
    render(<App />);

    // The page mounted and fetched (empty) tasks.
    await waitFor(() => expect(mockedListTasks).toHaveBeenCalled());

    // The Tasks page heading is present even with an empty list...
    const heading = await screen.findByRole(
      'heading',
      { name: /t[aâ]ches|tasks/i },
      { timeout: 3000 },
    );
    expect(heading).toBeInTheDocument();

    // ...and an empty-state message renders (page.tasks.empty), NOT a blank
    // area. The FR empty text mirrors page.events.empty ("Aucun ..."); match a
    // permissive empty-state phrasing so the assertion is robust to wording.
    const emptyState = await screen.findByText(/aucune?\s+t[aâ]che|no\s+tasks?|aucune?\s+donn/i);
    expect(emptyState).toBeInTheDocument();
  });
});
