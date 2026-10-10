/**
 * Unit tests — TasksPage (member-facing, read-only tasks view).
 * Spec: .kiro/specs/assigned-events-tasks-empty-fix (Task 4 — unit coverage)
 *
 * These tests render TasksPage in isolation (wrapped in LanguageProvider, which
 * useTranslation requires) and drive its data loading through a mocked
 * taskService.listTasks(). They cover the four states from the design's Unit
 * Tests section and Requirements 2.3, 2.4, 2.5:
 *
 *  - loading indicator while listTasks() is pending;
 *  - task cards (title, dates, status; description + location when present)
 *    when listTasks() resolves with tasks;
 *  - empty-state message when listTasks() resolves with [];
 *  - no crash when listTasks() rejects (error caught, loading resolves).
 *
 * Conventions mirror App.memberTasksRoute.test.tsx: mock the taskService module
 * with vi.fn()s, seed sample tasks with DISTINCT start/end days so date
 * fragments resolve unambiguously, and match locale date output by a
 * day/month/year fragment (timezone-robust). The default language is French
 * (LanguageProvider defaults to 'fr'), so page.tasks.* resolve to the FR
 * strings ("Tâches", "Chargement...", "Aucune tâche.", "Début :", "Fin :",
 * "Lieu :").
 *
 * Validates: Requirements 2.3, 2.4, 2.5
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';

// TasksPage fetches on mount via taskService.listTasks(). Mock the module so
// the page renders deterministically without network access.
vi.mock('../services/taskService', () => ({
  taskService: {
    listTasks: vi.fn(),
    createTask: vi.fn(),
    updateTask: vi.fn(),
    deleteTask: vi.fn(),
  },
}));

import { taskService, type Task } from '../services/taskService';
import { LanguageProvider } from '../hooks/useLanguage';
import { TasksPage } from './TasksPage';

const mockedListTasks = vi.mocked(taskService.listTasks);

/** Render TasksPage inside the LanguageProvider that useTranslation requires. */
function renderTasksPage() {
  return render(
    <LanguageProvider>
      <TasksPage />
    </LanguageProvider>,
  );
}

/** A sample task shaped like the taskService `Task` type. */
function sampleTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 't-1',
    title: 'Préparer le rapport trimestriel',
    description: 'Compiler les chiffres du trimestre',
    start_date: '2030-03-01T09:00:00Z',
    // Distinct end-date DAY so the start-date fragment ("01/03/2030") stays
    // unique in the rendered card and single-match queries are unambiguous.
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

/** Day/month/year fragment (e.g. "01/03/2030") of a locale-formatted date. */
function dayFragment(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR').split(' ')[0];
}

beforeEach(() => {
  mockedListTasks.mockReset();
  mockedListTasks.mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Loading state — a loading indicator renders while listTasks() is pending,
// before it resolves. (Requirement 2.5)
// ---------------------------------------------------------------------------
describe('TasksPage loading state (Req 2.5)', () => {
  it('renders a loading indicator while listTasks() is pending', async () => {
    // A never-resolving promise keeps the page in its loading state.
    let resolveList: (tasks: Task[]) => void = () => {};
    mockedListTasks.mockImplementation(
      () => new Promise<Task[]>((resolve) => { resolveList = resolve; }),
    );

    renderTasksPage();

    // The FR loading text (page.tasks.loading) is shown while pending.
    expect(screen.getByText('Chargement...')).toBeInTheDocument();
    // The list heading has not rendered yet.
    expect(screen.queryByRole('heading', { name: /t[aâ]ches|tasks/i })).not.toBeInTheDocument();

    // Resolve so the pending promise does not leak into later assertions.
    resolveList([]);
    await waitFor(() => expect(screen.queryByText('Chargement...')).not.toBeInTheDocument());
  });
});

// ---------------------------------------------------------------------------
// Populated state — task cards render with title, dates, status, and the
// optional description + location when present. (Requirement 2.3)
// ---------------------------------------------------------------------------
describe('TasksPage populated state (Req 2.3)', () => {
  it('renders a task card with title, description, location, dates, and status', async () => {
    mockedListTasks.mockResolvedValue([sampleTask()]);

    renderTasksPage();

    // Title.
    expect(
      await screen.findByText('Préparer le rapport trimestriel'),
    ).toBeInTheDocument();
    // Description (present).
    expect(screen.getByText('Compiler les chiffres du trimestre')).toBeInTheDocument();
    // Location (present) — value appears within the "Lieu :" line.
    expect(screen.getByText(/Bureau principal/)).toBeInTheDocument();

    // Start and end dates: distinct days, so each fragment matches its own line.
    const startFrag = dayFragment('2030-03-01T09:00:00Z'); // e.g. "01/03/2030"
    const endFrag = dayFragment('2030-03-05T17:00:00Z');   // e.g. "05/03/2030"
    expect(startFrag).not.toBe(endFrag);
    expect(screen.getByText(new RegExp(startFrag.replace(/\//g, '\\/')))).toBeInTheDocument();
    expect(screen.getByText(new RegExp(endFrag.replace(/\//g, '\\/')))).toBeInTheDocument();

    // Status badge text.
    expect(screen.getByText('scheduled')).toBeInTheDocument();
  });

  it('renders a card without a description or location when those are absent', async () => {
    mockedListTasks.mockResolvedValue([
      sampleTask({ description: undefined, location: undefined, title: 'Tâche minimale' }),
    ]);

    renderTasksPage();

    // The minimal task still renders its title and status.
    expect(await screen.findByText('Tâche minimale')).toBeInTheDocument();
    expect(screen.getByText('scheduled')).toBeInTheDocument();
    // The optional description text is not present.
    expect(screen.queryByText('Compiler les chiffres du trimestre')).not.toBeInTheDocument();
  });

  it('renders one card per task for multiple tasks', async () => {
    mockedListTasks.mockResolvedValue([
      sampleTask({ id: 't-1', title: 'Première tâche' }),
      sampleTask({ id: 't-2', title: 'Deuxième tâche', status: 'cancelled' }),
    ]);

    renderTasksPage();

    expect(await screen.findByText('Première tâche')).toBeInTheDocument();
    expect(screen.getByText('Deuxième tâche')).toBeInTheDocument();
    expect(screen.getByText('scheduled')).toBeInTheDocument();
    expect(screen.getByText('cancelled')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Empty state — a clear empty-state message renders (not a blank area) when
// listTasks() resolves with []. (Requirement 2.4)
// ---------------------------------------------------------------------------
describe('TasksPage empty state (Req 2.4)', () => {
  it('renders the empty-state message when there are no tasks', async () => {
    mockedListTasks.mockResolvedValue([]);

    renderTasksPage();

    // Loading resolves and the FR empty-state text (page.tasks.empty) renders.
    expect(await screen.findByText('Aucune tâche.')).toBeInTheDocument();
    // The heading is present alongside the empty message (not a blank area).
    expect(screen.getByRole('heading', { name: /t[aâ]ches|tasks/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Error state — listTasks() rejects: the error is caught, loading resolves, and
// the page renders (empty) without crashing. (Requirement 2.5)
// ---------------------------------------------------------------------------
describe('TasksPage error state (Req 2.5)', () => {
  it('does not crash when listTasks() rejects; loading resolves to the empty state', async () => {
    // Silence the expected console.error from the page's catch block.
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockedListTasks.mockRejectedValue(new Error('network down'));

    renderTasksPage();

    // Loading resolves (finally block runs) and the page renders its empty
    // state without throwing — the heading is present.
    expect(await screen.findByText('Aucune tâche.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /t[aâ]ches|tasks/i })).toBeInTheDocument();
    // The loading indicator is gone.
    expect(screen.queryByText('Chargement...')).not.toBeInTheDocument();

    errorSpy.mockRestore();
  });
});
