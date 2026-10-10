/**
 * Unit tests for the read-only member EventsPage and the /events route mapping.
 * Spec: .kiro/specs/member-events-route-missing (Task 3.4)
 *
 * These tests exercise the FIXED behavior:
 *  - EventsPage calls eventService.listEvents() on mount and renders returned
 *    events read-only.
 *  - EventsPage renders a loading state, then the list, and an empty state when
 *    no events are returned.
 *  - EventsPage renders NO create / edit / cancel management controls.
 *  - App maps /events to a protected EventsPage route.
 *  - Property-based: for any array of events, EventsPage renders exactly one
 *    read-only card per event and no management controls.
 *
 * The component is rendered inside LanguageProvider (matching
 * AdminEventsPage.integration.test.tsx) and the eventService module is mocked
 * with vi.fn()s so no network is hit.
 *
 * Validates: Requirements 2.1, 2.2
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import fc from 'fast-check';
import { EventsPage } from './EventsPage';
import App from '../App';
import { eventService, type Event } from '../services/eventService';
import { LanguageProvider } from '../hooks/useLanguage';

// Mock the events service module: listEvents is a vi.fn() configured per test.
// Matching the AdminEventsPage.integration.test.tsx mocking style so the page
// never hits the network and we can assert the call.
vi.mock('../services/eventService', () => ({
  eventService: {
    listEvents: vi.fn(),
    createEvent: vi.fn(),
    updateEvent: vi.fn(),
    deleteEvent: vi.fn(),
  },
}));

const mockedListEvents = vi.mocked(eventService.listEvents);

// Default Active_Language is French, so headings/labels use the French keys.
function renderPage() {
  return render(
    <LanguageProvider>
      <EventsPage />
    </LanguageProvider>,
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

const TOKEN_KEY = 'access_token';
const ROLE_KEY = 'user_role';
const USER_KEY = 'user';

function signInAsMember() {
  localStorage.setItem(TOKEN_KEY, 'test-token');
  localStorage.setItem(ROLE_KEY, 'member');
  localStorage.setItem(
    USER_KEY,
    JSON.stringify({
      id: 'member-1',
      email: 'member@opcp.test',
      first_name: 'Mem',
      last_name: 'Ber',
      role: 'member',
    }),
  );
}

// Query helpers for management controls that MUST NOT appear in the read-only view.
function queryManagementControls(): HTMLElement[] {
  return [
    ...screen.queryAllByRole('button', { name: /nouvel [ée]v[ée]nement|new event/i }),
    ...screen.queryAllByRole('button', { name: /modifier|edit/i }),
    ...screen.queryAllByRole('button', { name: /annuler|cancel|supprimer|delete/i }),
    ...screen.queryAllByRole('button', { name: /cr[ée]er|create|enregistrer|save/i }),
  ];
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
});

describe('EventsPage (read-only member view)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls eventService.listEvents() on mount and renders returned events read-only', async () => {
    const events = [
      makeEvent('evt-1', 'Assemblée générale'),
      makeEvent('evt-2', 'Atelier public'),
    ];
    mockedListEvents.mockResolvedValue(events);

    renderPage();

    // Fetch happens on mount.
    await waitFor(() => expect(mockedListEvents).toHaveBeenCalledTimes(1));

    // Each returned event title renders.
    expect(await screen.findByText('Assemblée générale')).toBeInTheDocument();
    expect(screen.getByText('Atelier public')).toBeInTheDocument();

    // No management controls in the read-only view.
    expect(queryManagementControls()).toHaveLength(0);
  });

  it('renders a loading state, then the list', async () => {
    let resolveList: (value: Event[]) => void = () => {};
    const pending = new Promise<Event[]>((resolve) => {
      resolveList = resolve;
    });
    mockedListEvents.mockReturnValue(pending);

    renderPage();

    // While the fetch is pending the loading state is shown.
    expect(screen.getByText('Chargement...')).toBeInTheDocument();

    // Resolve the fetch; the list replaces the loading state.
    resolveList([makeEvent('evt-1', 'Assemblée générale')]);

    expect(await screen.findByText('Assemblée générale')).toBeInTheDocument();
    expect(screen.queryByText('Chargement...')).not.toBeInTheDocument();
  });

  it('renders an empty state when no events are returned', async () => {
    mockedListEvents.mockResolvedValue([]);

    renderPage();

    await waitFor(() => expect(mockedListEvents).toHaveBeenCalledTimes(1));

    // Empty-state message renders (French default), and the title heading is present.
    expect(await screen.findByText('Aucun événement.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Événements' })).toBeInTheDocument();
  });

  it('renders NO create, edit, or cancel controls (read-only assertion)', async () => {
    const events = [makeEvent('evt-1', 'Assemblée générale', { status: 'scheduled' })];
    mockedListEvents.mockResolvedValue(events);

    renderPage();

    expect(await screen.findByText('Assemblée générale')).toBeInTheDocument();

    // No buttons at all should be present in the read-only view.
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    expect(queryManagementControls()).toHaveLength(0);
  });
});

describe('App route mapping — /events resolves to a protected EventsPage', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    // App uses BrowserRouter; drive the initial location via the history API.
    window.history.pushState({}, '', '/events');
  });

  afterEach(() => {
    window.history.pushState({}, '', '/');
  });

  it('renders EventsPage under ProtectedRoute for an authenticated member at /events', async () => {
    mockedListEvents.mockResolvedValue([makeEvent('evt-1', 'Assemblée générale')]);

    signInAsMember();
    render(<App />);

    // Auth guard satisfied — no redirect to /login.
    expect(window.location.pathname).toBe('/events');

    // The member events heading renders (route resolved to EventsPage) and the
    // page's mount-time fetch fired.
    expect(await screen.findByRole('heading', { name: 'Événements' })).toBeInTheDocument();
    await waitFor(() => expect(mockedListEvents).toHaveBeenCalled());
    expect(await screen.findByText('Assemblée générale')).toBeInTheDocument();
  });

  it('redirects an unauthenticated visitor away from the protected /events route', async () => {
    mockedListEvents.mockResolvedValue([]);

    // No session set — ProtectedRoute should redirect to /login.
    render(<App />);

    await waitFor(() => expect(window.location.pathname).toBe('/login'));
    // The read-only page never mounts, so no fetch happens.
    expect(mockedListEvents).not.toHaveBeenCalled();
  });
});

describe('Property — EventsPage renders one read-only card per event', () => {
  it('renders exactly one card per event and never any management controls', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(
          fc.record({
            id: fc.uuid(),
            // Trim and collapse internal whitespace so the generated title
            // equals its own Testing Library normalized form, then require at
            // least one non-whitespace character. This keeps the title→card
            // assertion meaningful (getAllByText normalizes whitespace).
            title: fc
              .string({ minLength: 1, maxLength: 40 })
              .map((t) => t.replace(/\s+/g, ' ').trim())
              .filter((t) => t.length > 0),
            status: fc.constantFrom('scheduled', 'cancelled', 'draft'),
          }),
          { minLength: 0, maxLength: 6 },
        ),
        async (specs) => {
          cleanup();
          vi.clearAllMocks();

          // Ensure unique ids so each event maps to a distinct card (React key).
          const events = specs.map((s, i) =>
            makeEvent(`${s.id}-${i}`, s.title, { status: s.status }),
          );
          mockedListEvents.mockResolvedValue(events);

          const { container } = renderPage();

          // Wait for the mount fetch and the loading state to clear.
          await waitFor(() => expect(mockedListEvents).toHaveBeenCalledTimes(1));
          await waitFor(() =>
            expect(screen.queryByText('Chargement...')).not.toBeInTheDocument(),
          );

          if (events.length === 0) {
            // Empty state, no cards.
            expect(screen.getByText('Aucun événement.')).toBeInTheDocument();
            expect(container.querySelectorAll('.card').length).toBe(0);
          } else {
            // Exactly one read-only card per event.
            const cards = container.querySelectorAll('.card');
            expect(cards.length).toBe(events.length);

            // Each event's title renders read-only within a card.
            for (const event of events) {
              expect(screen.getAllByText(event.title).length).toBeGreaterThanOrEqual(1);
            }
          }

          // Read-only invariant: no management controls for any generated shape.
          expect(screen.queryAllByRole('button')).toHaveLength(0);
        },
      ),
      { numRuns: 15 },
    );
  });
});
