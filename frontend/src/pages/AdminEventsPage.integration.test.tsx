/**
 * Integration test for the full create flow on the AdminEventsPage.
 *
 * Spec: .kiro/specs/event-creation-failure/ (Task 4, frontend part)
 *
 * These tests exercise the FIXED create wiring end-to-end at the component
 * level, matching the established AdminEventsPage / DocumentsPage pattern
 * (full render inside LanguageProvider, service module mocked with vi.fn()s):
 *
 *  - A create submission whose request fails validation renders the SPECIFIC
 *    message ("End date must be after start date.") in the create-modal alert,
 *    NOT the generic "Échec de la création de l'événement." banner. The modal
 *    stays open and the list is not refreshed.
 *  - A valid create submission closes the modal and refreshes the list (a
 *    second listEvents call that now includes the created event).
 *
 * The backend returns a Pydantic-style 422 detail array for the validation
 * failure; the fixed `extractApiError` cleans the "Value error, " prefix and
 * prefers that specific message over the fallback, and `handleCreate` places it
 * into `createError` which the modal renders in its role="alert" region.
 *
 * Validates: Requirements 2.3, 3.1, 3.6
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, within, waitFor, fireEvent } from '@testing-library/react';
import { AdminEventsPage } from './AdminEventsPage';
import { eventService, type Event } from '../services/eventService';
import { adminService } from '../services/adminService';
import { LanguageProvider } from '../hooks/useLanguage';

// AdminEventsPage consumes the translation context; render it inside the
// provider. The default Active_Language is French, so the fallback banner text
// is the French "Échec de la création de l'événement."
function renderPage() {
  return render(
    <LanguageProvider>
      <AdminEventsPage />
    </LanguageProvider>,
  );
}

// Mock the service modules: methods are vi.fn()s configured per test.
vi.mock('../services/eventService', () => ({
  eventService: {
    listEvents: vi.fn(),
    createEvent: vi.fn(),
    updateEvent: vi.fn(),
    deleteEvent: vi.fn(),
  },
}));

vi.mock('../services/adminService', () => ({
  adminService: {
    listUsers: vi.fn(),
  },
}));

const mockedListEvents = vi.mocked(eventService.listEvents);
const mockedCreateEvent = vi.mocked(eventService.createEvent);
const mockedListUsers = vi.mocked(adminService.listUsers);

const CREATE_FALLBACK = 'Échec de la création de l\'événement.';
const SPECIFIC_MESSAGE = 'End date must be after start date.';

/** Axios-shaped 422 error carrying a Pydantic validation detail array. */
function axios422(msg: string) {
  return { response: { data: { detail: [{ msg }] } } };
}

function makeEvent(id: string, title: string): Event {
  return {
    id,
    title,
    description: null,
    start_date: '2030-01-01T10:00:00Z',
    end_date: '2030-01-01T12:00:00Z',
    location: null,
    max_participants: null,
    created_by: 'admin-id',
    assigned_user_id: null,
    assigned_user_ids: [],
    status: 'scheduled',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    participant_count: 0,
  };
}

// Wait until the initial load resolves and the page shows the "New event" button.
async function waitForLoaded(): Promise<HTMLElement> {
  return screen.findByRole('button', { name: 'Nouvel événement' });
}

// Open the create modal and return its dialog container (the modal panel).
async function openCreateModal(): Promise<HTMLElement> {
  const newEventBtn = await waitForLoaded();
  fireEvent.click(newEventBtn);
  // The create modal heading identifies the panel.
  const heading = await screen.findByRole('heading', { name: 'Nouvel événement' });
  return heading.closest('div.bg-white') as HTMLElement;
}

beforeEach(() => {
  mockedListUsers.mockResolvedValue({ members: [] } as unknown as Awaited<
    ReturnType<typeof adminService.listUsers>
  >);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('AdminEventsPage create flow (integration)', () => {
  it('renders the specific validation message in the create-modal alert on failure', async () => {
    mockedListEvents.mockResolvedValue([]);
    // Backend rejects the create with a Pydantic 422 for equal dates.
    mockedCreateEvent.mockRejectedValue(
      axios422(`Value error, ${SPECIFIC_MESSAGE}`),
    );

    renderPage();
    const modal = await openCreateModal();

    fireEvent.click(within(modal).getByRole('button', { name: 'Créer' }));

    // The specific message appears in the modal's alert region...
    const alert = await within(modal).findByRole('alert');
    expect(alert).toHaveTextContent(SPECIFIC_MESSAGE);
    // ...and it is NOT the generic fallback banner, with no leaked prefix.
    expect(alert).not.toHaveTextContent(CREATE_FALLBACK);
    expect(alert.textContent ?? '').not.toContain('Value error,');

    // The modal stays open (create heading still present) and the list was not
    // refreshed (only the single initial load happened).
    expect(screen.getByRole('heading', { name: 'Nouvel événement' })).toBeInTheDocument();
    expect(mockedListEvents).toHaveBeenCalledTimes(1);
  });

  it('closes the modal and refreshes the list on a valid submission', async () => {
    const created = makeEvent('evt-1', 'Naive future event');
    // Initial load empty; after a successful create the reload returns the event.
    mockedListEvents.mockResolvedValueOnce([]).mockResolvedValueOnce([created]);
    mockedCreateEvent.mockResolvedValue(undefined);

    renderPage();
    await openCreateModal();

    fireEvent.click(screen.getByRole('button', { name: 'Créer' }));

    // createEvent was invoked and the list refreshed (second listEvents call).
    await waitFor(() => expect(mockedCreateEvent).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mockedListEvents).toHaveBeenCalledTimes(2));

    // The create modal closed (heading gone) and no error alert is shown.
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: 'Nouvel événement' })).not.toBeInTheDocument(),
    );
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();

    // The newly created event appears in the refreshed list.
    expect(await screen.findByText('Naive future event')).toBeInTheDocument();
  });
});
