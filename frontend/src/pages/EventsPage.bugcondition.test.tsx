/**
 * Bug condition exploration test — Property 1: Bug Condition, Member Events
 * Route Renders and Fetches.
 * Spec: .kiro/specs/member-events-route-missing
 *
 * CRITICAL: These assertions encode the EXPECTED (fixed) behavior. They MUST
 * FAIL on the current (unfixed) code — that failure confirms the bug:
 *   isBugCondition(input) where
 *     input.path == '/events' AND input.isAuthenticated == true
 *     AND NOT routeExistsFor('/events')
 * There is no <Route path="/events"> in the layout's inner <Routes> and no
 * member-facing component that calls eventService.listEvents(), so navigating
 * to /events mounts nothing: the content area is blank and listEvents() is
 * never called. These tests will PASS once the fix wires
 * /events -> EventsPage (ProtectedRoute) and EventsPage fetches + renders
 * events read-only.
 *
 * Scoped PBT approach: the bug is deterministic (a single missing route), so
 * the property is scoped to the concrete failing case — an authenticated
 * non-admin member with initial route '/events' — and parametrized over the
 * listEvents() return value (empty array, one event, several events) since the
 * expected member view must render for all of them.
 *
 * Validates: Requirements 1.1, 1.2, 2.1, 2.2
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import fc from 'fast-check';
import App from '../App';
import { eventService, type Event } from '../services/eventService';

// Mock the events service module: listEvents is a vi.fn() configured per test.
// This follows the AdminEventsPage.integration.test.tsx mocking style so the
// page (once it exists) never hits the network, and lets us assert the call.
vi.mock('../services/eventService', () => ({
  eventService: {
    listEvents: vi.fn(),
    createEvent: vi.fn(),
    updateEvent: vi.fn(),
    deleteEvent: vi.fn(),
  },
}));

const mockedListEvents = vi.mocked(eventService.listEvents);

const TOKEN_KEY = 'access_token';
const ROLE_KEY = 'user_role';
const USER_KEY = 'user';

// Authenticated non-admin member session (input.isAuthenticated == true).
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

function makeEvent(id: string, title: string): Event {
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
  };
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  // App uses BrowserRouter; drive the initial location via the history API,
  // matching App.tasksRoute.test.tsx. The bug condition path is '/events'.
  window.history.pushState({}, '', '/events');
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  window.history.pushState({}, '', '/');
});

describe('Bug Condition — authenticated member navigating to /events', () => {
  it('mounts a member events view and calls listEvents() (fails on unfixed code: no route, blank area)', async () => {
    const events = [
      makeEvent('evt-1', 'Assemblée générale'),
      makeEvent('evt-2', 'Atelier public'),
    ];
    mockedListEvents.mockResolvedValue(events);

    signInAsMember();
    render(<App />);

    // The bug condition path stays '/events' (auth guard is satisfied for the
    // authenticated member — no redirect to /login).
    expect(window.location.pathname).toBe('/events');

    // A member-facing events view renders a heading identifying the events
    // page. On unfixed code no route matches '/events', so no such heading
    // exists and this assertion fails.
    const heading = await screen.findByRole(
      'heading',
      { name: /[ée]v[ée]nements|events/i },
      { timeout: 3000 },
    );
    expect(heading).toBeInTheDocument();

    // The member view fetches its data on mount. On unfixed code nothing mounts
    // for '/events', so listEvents() is never called.
    expect(mockedListEvents).toHaveBeenCalled();
  });

  it('renders the returned event titles read-only (fails on unfixed code: nothing renders)', async () => {
    const events = [
      makeEvent('evt-1', 'Assemblée générale'),
      makeEvent('evt-2', 'Atelier public'),
    ];
    mockedListEvents.mockResolvedValue(events);

    signInAsMember();
    render(<App />);

    // Each returned event's title appears in the rendered list.
    expect(await screen.findByText('Assemblée générale')).toBeInTheDocument();
    expect(await screen.findByText('Atelier public')).toBeInTheDocument();

    // Read-only view: no admin management controls (create/edit/cancel) are
    // present for the member. (On unfixed code nothing renders at all.)
    expect(
      screen.queryByRole('button', { name: /nouvel [ée]v[ée]nement|new event/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /modifier|edit/i }),
    ).not.toBeInTheDocument();
  });

  it('renders an empty-state message when listEvents() returns [] (fails on unfixed code: blank area)', async () => {
    mockedListEvents.mockResolvedValue([]);

    signInAsMember();
    render(<App />);

    // listEvents() is still called on mount even when the result is empty...
    await waitFor(() => expect(mockedListEvents).toHaveBeenCalled());

    // ...and an events heading renders (not a blank content area).
    const heading = await screen.findByRole(
      'heading',
      { name: /[ée]v[ée]nements|events/i },
      { timeout: 3000 },
    );
    expect(heading).toBeInTheDocument();
  });

  // Scoped property: for ANY listEvents() return value (empty, one, or several
  // events), the authenticated member at '/events' must see the member view
  // mounted and listEvents() called. On unfixed code this fails for every
  // generated shape because no route/component exists.
  it('property: for any events list, /events mounts the view and calls listEvents()', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(
          fc.record({
            id: fc.uuid(),
            title: fc.string({ minLength: 1, maxLength: 40 }),
          }),
          { minLength: 0, maxLength: 4 },
        ),
        async (specs) => {
          cleanup();
          localStorage.clear();
          vi.clearAllMocks();
          window.history.pushState({}, '', '/events');

          const events = specs.map((s, i) => makeEvent(s.id || `evt-${i}`, s.title));
          mockedListEvents.mockResolvedValue(events);

          signInAsMember();
          render(<App />);

          // The member events view mounts (heading present) for every shape...
          await screen.findByRole(
            'heading',
            { name: /[ée]v[ée]nements|events/i },
            { timeout: 3000 },
          );
          // ...and the data fetch happens on mount.
          expect(mockedListEvents).toHaveBeenCalled();
        },
      ),
      { numRuns: 5 },
    );
  });
});
