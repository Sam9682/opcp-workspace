/**
 * Integration tests for the member events flow.
 * Spec: .kiro/specs/member-events-route-missing (Task 3.7)
 *
 * These tests exercise the FIXED wiring end-to-end at the app level, matching
 * the established integration style (full <App> render inside its own
 * LanguageProvider/BrowserRouter, service modules mocked with vi.fn()s, initial
 * location driven via window.history.pushState like EventsPage.bugcondition.test.tsx):
 *
 *  - Full flow: an authenticated member clicks the "Events" nav link, lands on
 *    /events, and sees their assigned and public events rendered read-only.
 *  - Context switching: an admin visits /events (read-only member view, no
 *    management controls) and /admin/events (management view with create/edit/
 *    cancel controls). Both behave correctly and independently.
 *  - Visual/state feedback: the loading indicator appears during the fetch and
 *    the list (or the empty state) appears after listEvents() resolves.
 *
 * The member view heading is "Événements" (default French) and it renders NO
 * management controls, while the admin view heading is "Gestion des événements"
 * and it renders the "Nouvel événement" / "Modifier" / "Annuler" controls —
 * these distinguish the two independent views.
 *
 * Validates: Requirements 2.1, 2.2, 3.1
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import App from '../App';
import { eventService, type Event } from '../services/eventService';
import { adminService } from '../services/adminService';

// Mock the events service: listEvents is a vi.fn() configured per test so no
// network is hit and we can assert calls / control resolution timing.
vi.mock('../services/eventService', () => ({
  eventService: {
    listEvents: vi.fn(),
    createEvent: vi.fn(),
    updateEvent: vi.fn(),
    deleteEvent: vi.fn(),
  },
}));

// AdminEventsPage loads members (for its picker) on mount; mock adminService so
// the admin management view renders deterministically without network access.
vi.mock('../services/adminService', () => ({
  adminService: {
    listUsers: vi.fn(),
  },
}));

const mockedListEvents = vi.mocked(eventService.listEvents);
const mockedListUsers = vi.mocked(adminService.listUsers);

const TOKEN_KEY = 'access_token';
const ROLE_KEY = 'user_role';
const USER_KEY = 'user';

function signIn(role: 'member' | 'administrator') {
  localStorage.setItem(TOKEN_KEY, 'test-token');
  localStorage.setItem(ROLE_KEY, role);
  localStorage.setItem(
    USER_KEY,
    JSON.stringify({
      id: `${role}-1`,
      email: `${role}@opcp.test`,
      first_name: 'Us',
      last_name: 'Er',
      role,
    }),
  );
}

function makeEvent(id: string, title: string, overrides: Partial<Event> = {}): Event {
  return {
    id,
    title,
    description: `Description for ${title}`,
    start_date: '2030-01-01T10:00:00Z',
    end_date: '2030-01-01T12:00:00Z',
    location: 'Salle A',
    max_participants: 20,
    created_by: 'admin-id',
    assigned_user_id: null,
    assigned_user_ids: [],
    status: 'scheduled',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    participant_count: 3,
    ...overrides,
  };
}

// Member management controls that MUST NOT appear in the read-only /events view
// but MUST appear in the /admin/events management view.
function queryManagementControls(): HTMLElement[] {
  return [
    ...screen.queryAllByRole('button', { name: /nouvel [ée]v[ée]nement|new event/i }),
    ...screen.queryAllByRole('button', { name: /modifier|edit/i }),
    ...screen.queryAllByRole('button', { name: /annuler|cancel/i }),
  ];
}

beforeEach(() => {
  localStorage.clear();
  cleanup();
  vi.clearAllMocks();
  mockedListUsers.mockResolvedValue({ members: [] } as unknown as Awaited<
    ReturnType<typeof adminService.listUsers>
  >);
  // App uses BrowserRouter; drive the initial location via the history API,
  // matching EventsPage.bugcondition.test.tsx.
  window.history.pushState({}, '', '/');
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  window.history.pushState({}, '', '/');
});

// ---------------------------------------------------------------------------
// Full flow: member clicks the "Events" nav link -> /events -> sees events.
// ---------------------------------------------------------------------------
describe('Member events flow — nav click to /events (Requirements 2.1, 2.2)', () => {
  it('navigates to /events on nav click and renders the member\'s events read-only', async () => {
    const events = [
      makeEvent('evt-1', 'Assemblée générale'), // assigned/private
      makeEvent('evt-2', 'Atelier public'), // public
    ];
    mockedListEvents.mockResolvedValue(events);

    signIn('member');
    render(<App />);

    // Start on the home page.
    expect(window.location.pathname).toBe('/');

    // The desktop nav shows the "Événements" link (member: no admin caret).
    const eventsLink = screen.getAllByRole('link', { name: /^Événements$/ })[0];
    expect(eventsLink).toHaveAttribute('href', '/events');

    fireEvent.click(eventsLink);

    // Navigation lands on /events.
    await waitFor(() => expect(window.location.pathname).toBe('/events'));

    // The member events view mounts, fetches, and renders both events.
    expect(await screen.findByRole('heading', { name: 'Événements' })).toBeInTheDocument();
    await waitFor(() => expect(mockedListEvents).toHaveBeenCalled());
    expect(await screen.findByText('Assemblée générale')).toBeInTheDocument();
    expect(screen.getByText('Atelier public')).toBeInTheDocument();

    // Read-only: the member sees no management controls.
    expect(queryManagementControls()).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Context switching: admin /events (read-only) vs /admin/events (management).
// ---------------------------------------------------------------------------
describe('Context switching — admin /events vs /admin/events (Requirements 2.2, 3.1)', () => {
  it('renders the read-only member view at /events for an admin (no management controls)', async () => {
    mockedListEvents.mockResolvedValue([makeEvent('evt-1', 'Assemblée générale')]);

    signIn('administrator');
    window.history.pushState({}, '', '/events');
    render(<App />);

    // The member read-only view mounts (member title, not the admin title).
    expect(await screen.findByRole('heading', { name: 'Événements' })).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'Gestion des événements' }),
    ).not.toBeInTheDocument();

    expect(await screen.findByText('Assemblée générale')).toBeInTheDocument();

    // Even for an admin, /events is the read-only view — no management controls.
    expect(queryManagementControls()).toHaveLength(0);
    await waitFor(() => expect(mockedListEvents).toHaveBeenCalled());
  });

  it('renders the admin management view at /admin/events with create/edit/cancel controls', async () => {
    mockedListEvents.mockResolvedValue([makeEvent('evt-1', 'Assemblée générale')]);

    signIn('administrator');
    window.history.pushState({}, '', '/admin/events');
    render(<App />);

    // The admin management view mounts (admin title, not the member title).
    expect(
      await screen.findByRole('heading', { name: 'Gestion des événements' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Événements' })).not.toBeInTheDocument();

    // Full management controls are present: create + per-event edit/cancel.
    expect(await screen.findByRole('button', { name: 'Nouvel événement' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Modifier' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Annuler' })).toBeInTheDocument();

    await waitFor(() => expect(mockedListEvents).toHaveBeenCalled());
  });

  it('renders the two views independently: /events read-only then /admin/events management', async () => {
    // The two views are mounted in separate <App> renders (each is its own
    // route mount) and must behave correctly and independently.
    mockedListEvents.mockResolvedValue([makeEvent('evt-1', 'Assemblée générale')]);

    // 1) Read-only member view at /events.
    signIn('administrator');
    window.history.pushState({}, '', '/events');
    const readOnly = render(<App />);
    expect(await screen.findByRole('heading', { name: 'Événements' })).toBeInTheDocument();
    expect(queryManagementControls()).toHaveLength(0);
    readOnly.unmount();
    cleanup();
    vi.clearAllMocks();
    mockedListUsers.mockResolvedValue({ members: [] } as unknown as Awaited<
      ReturnType<typeof adminService.listUsers>
    >);
    mockedListEvents.mockResolvedValue([makeEvent('evt-1', 'Assemblée générale')]);

    // 2) Management view at /admin/events — unaffected by the earlier read-only mount.
    window.history.pushState({}, '', '/admin/events');
    render(<App />);
    expect(
      await screen.findByRole('heading', { name: 'Gestion des événements' }),
    ).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Nouvel événement' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Modifier' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Annuler' })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Visual/state feedback: loading indicator during fetch, then list/empty state.
// ---------------------------------------------------------------------------
describe('Loading feedback on /events (Requirements 2.1, 2.2)', () => {
  it('shows the loading indicator during the fetch, then the resolved list', async () => {
    // Deferred/controlled promise so we can observe the loading state before
    // listEvents() resolves.
    let resolveList: (value: Event[]) => void = () => {};
    const pending = new Promise<Event[]>((resolve) => {
      resolveList = resolve;
    });
    mockedListEvents.mockReturnValue(pending);

    signIn('member');
    window.history.pushState({}, '', '/events');
    render(<App />);

    // The loading indicator appears while the fetch is pending.
    expect(await screen.findByText('Chargement...')).toBeInTheDocument();

    // Resolve the fetch; the list replaces the loading indicator.
    resolveList([makeEvent('evt-1', 'Assemblée générale')]);

    expect(await screen.findByText('Assemblée générale')).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByText('Chargement...')).not.toBeInTheDocument(),
    );
  });

  it('shows the loading indicator, then the empty state when listEvents() resolves with []', async () => {
    let resolveList: (value: Event[]) => void = () => {};
    const pending = new Promise<Event[]>((resolve) => {
      resolveList = resolve;
    });
    mockedListEvents.mockReturnValue(pending);

    signIn('member');
    window.history.pushState({}, '', '/events');
    render(<App />);

    expect(await screen.findByText('Chargement...')).toBeInTheDocument();

    // Resolve empty; the empty-state message replaces the loading indicator.
    resolveList([]);

    expect(await screen.findByText('Aucun événement.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Événements' })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByText('Chargement...')).not.toBeInTheDocument(),
    );
  });
});
