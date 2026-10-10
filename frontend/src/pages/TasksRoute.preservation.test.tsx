/**
 * Preservation property tests — Property 2: Preservation, Non-`/tasks`
 * Navigation Behavior Unchanged.
 * Spec: .kiro/specs/assigned-events-tasks-empty-fix
 *
 * Property 2 (Preservation): for any input where the bug condition does NOT
 * hold (any navigation that is not authenticated navigation to `/tasks`), the
 * fixed application SHALL produce the same result as the original application —
 * preserving the `/events` -> EventsPage mapping (and its listEvents() fetch),
 * the `/admin/tasks` -> AdminTasksPage and `/admin/events` -> AdminEventsPage
 * mappings with their full management controls, the ProtectedRoute redirect to
 * `/login` for unauthenticated users, every other existing route-to-component
 * mapping, and the nav bar links.
 *
 * OBSERVATION-FIRST METHODOLOGY: the assertions below encode behavior OBSERVED
 * on the CURRENT (UNFIXED) code, so they MUST PASS today and lock the baseline
 * the fix must preserve. To exercise the REAL routing table verbatim, this test
 * reconstructs the layout's inner <Routes> from App.tsx (the same page
 * components, the same ProtectedRoute wrapping, in the same order) — following
 * the reconstruction pattern in EventsRoute.preservation.test.tsx.
 *
 * The `/tasks` path is deliberately EXCLUDED from the existing-routes set and
 * from the protected-routes set: it is the path being fixed and has NO route on
 * unfixed code. On unfixed code, navigating to `/tasks` inside <Layout> matches
 * nothing (blank content area) rather than redirecting to /login, so it is not
 * part of the baseline being preserved here. (Its correct fixed behavior is
 * covered by Property 1 in the bug-condition exploration test.)
 *
 * EXPECTED OUTCOME ON UNFIXED CODE: PASS (baseline behavior to preserve).
 *
 * Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import fc from 'fast-check';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { LanguageProvider } from '../hooks/useLanguage';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { Layout } from '../components/Layout';

// The real page components wired by App.tsx's inner <Routes>.
import { HomePage } from './HomePage';
import { ForumPage } from './ForumPage';
import { NewTopicPage } from './NewTopicPage';
import { TopicDetailPage } from './TopicDetailPage';
import { AdminUsersPage } from './AdminUsersPage';
import { AdminEventsPage } from './AdminEventsPage';
import { AdminTasksPage } from './AdminTasksPage';
import { AdminConfigPage } from './AdminConfigPage';
import { OraclePage } from './OraclePage';
import { HowToUsePage } from './HowToUsePage';
import { InstallationListPage } from '../components/prerequisites/InstallationListPage';
import { InstallationPrereqPage } from './InstallationPrereqPage';
import { DocumentsPage } from './DocumentsPage';
import { EventsPage } from './EventsPage';
import { SecurityPage } from './SecurityPage';

// -----------------------------------------------------------------------------
// Service mocks. Every page component fetches on mount; mock the service modules
// so each page renders its own content deterministically without network access,
// isolating route/guard behavior. This mirrors EventsRoute.preservation.test.tsx.
// -----------------------------------------------------------------------------
vi.mock('../services/eventService', () => ({
  eventService: {
    listEvents: vi.fn().mockResolvedValue([]),
    createEvent: vi.fn().mockResolvedValue(undefined),
    updateEvent: vi.fn().mockResolvedValue(undefined),
    deleteEvent: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock('../services/taskService', () => ({
  taskService: {
    listTasks: vi.fn().mockResolvedValue([]),
    createTask: vi.fn().mockResolvedValue(undefined),
    updateTask: vi.fn().mockResolvedValue(undefined),
    deleteTask: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock('../services/adminService', () => ({
  adminService: {
    listUsers: vi.fn().mockResolvedValue({ members: [] }),
    getLoginLogs: vi.fn().mockResolvedValue({ entries: [], total: 0, page: 1, page_size: 20 }),
    getAIProviderConfig: vi.fn().mockResolvedValue({ providers: [] }),
    getForumConfig: vi.fn().mockResolvedValue({ view_button_enabled: false }),
    updateAIProviderConfig: vi.fn().mockResolvedValue({ providers: [] }),
    updateForumConfig: vi.fn().mockResolvedValue({ view_button_enabled: false }),
    updateUserRole: vi.fn().mockResolvedValue(undefined),
    updateMembershipStatus: vi.fn().mockResolvedValue(undefined),
    updateEmailVerification: vi.fn().mockResolvedValue(undefined),
    createUser: vi.fn().mockResolvedValue(undefined),
    deleteUser: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock('../services/forumService', () => ({
  forumService: {
    getTopics: vi.fn().mockResolvedValue([]),
    getTopicsPublic: vi.fn().mockResolvedValue([]),
    getTopic: vi.fn().mockResolvedValue({ id: 't1', title: 'T', posts: [] }),
    getTopicPublic: vi.fn().mockResolvedValue({ id: 't1', title: 'T', posts: [] }),
    createTopic: vi.fn().mockResolvedValue({}),
    createPost: vi.fn().mockResolvedValue({}),
    updatePost: vi.fn().mockResolvedValue({}),
    deletePost: vi.fn().mockResolvedValue(undefined),
    getForumConfig: vi.fn().mockResolvedValue({ view_button_enabled: false }),
  },
}));

vi.mock('../services/infoService', () => ({
  infoService: {
    getStats: vi.fn().mockResolvedValue({ members: 0, topics: 0, posts: 0 }),
  },
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    listDocuments: vi.fn().mockResolvedValue({ documents: [] }),
    uploadDocument: vi.fn().mockResolvedValue({}),
    downloadDocument: vi.fn().mockResolvedValue(undefined),
    deleteDocument: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock('../services/securityService', () => ({
  securityService: {
    getTwoFactorStatus: vi.fn().mockResolvedValue({
      totp_enabled: false,
      email_2fa_enabled: false,
      methods: [],
    }),
    changePassword: vi.fn().mockResolvedValue(undefined),
    startTotpSetup: vi.fn().mockResolvedValue({}),
    confirmTotp: vi.fn().mockResolvedValue(undefined),
    disableTotp: vi.fn().mockResolvedValue(undefined),
    enableEmail2fa: vi.fn().mockResolvedValue(undefined),
    disableEmail2fa: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock('../services/oracleService', () => ({
  oracleService: {
    getHistory: vi.fn().mockResolvedValue([]),
    askOracle: vi.fn().mockResolvedValue({ answer: '', sources: [] }),
    askOracleStream: vi.fn().mockResolvedValue(undefined),
    analyzeForumMessages: vi.fn().mockResolvedValue({}),
    getAvailableProviders: vi.fn().mockResolvedValue({ providers: [] }),
  },
}));

vi.mock('../services/prerequisitesService', () => ({
  prerequisitesService: {
    listInstallations: vi.fn().mockResolvedValue([]),
    createInstallation: vi.fn().mockResolvedValue({}),
    updateInstallation: vi.fn().mockResolvedValue({}),
    deleteInstallation: vi.fn().mockResolvedValue(undefined),
    loadStaticContent: vi.fn().mockResolvedValue({ slug: '', content: '' }),
    saveStaticContent: vi.fn().mockResolvedValue(undefined),
    loadClientAnswers: vi.fn().mockResolvedValue({ slug: '', answers: {} }),
    saveClientAnswer: vi.fn().mockResolvedValue(undefined),
    loadCredentialConfig: vi.fn().mockResolvedValue({
      auth_url: '', credential_id: '', nova_endpoint: '', secret_stored: false,
    }),
    saveCredentialConfig: vi.fn().mockResolvedValue({
      auth_url: '', credential_id: '', nova_endpoint: '', secret_stored: false,
    }),
    retrieveServers: vi.fn().mockResolvedValue({ servers: [] }),
  },
}));

import { eventService } from '../services/eventService';
import { taskService } from '../services/taskService';

const TOKEN_KEY = 'access_token';
const ROLE_KEY = 'user_role';
const USER_KEY = 'user';
const LOGIN_PLACEHOLDER = 'Login Placeholder';

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

/**
 * Reconstructs the layout's inner <Routes> from App.tsx VERBATIM, minus the
 * `/tasks` path (which does not exist on unfixed code and is the path under
 * fix). A recognizable /login placeholder detects the ProtectedRoute redirect.
 * Rendering happens inside <Layout> so the real nav (and its admin dropdowns) is
 * present, matching how App.tsx mounts these routes.
 *
 * NOTE: `/events` and `/admin/tasks` ARE present on unfixed code (unlike the
 * earlier member-events / admin-tasks fixes, which are already merged), so they
 * are part of the baseline preserved here.
 */
function renderAppRoutes(initialEntry: string) {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/login" element={<div>{LOGIN_PLACEHOLDER}</div>} />
          <Route
            path="/*"
            element={
              <Layout>
                <Routes>
                  <Route path="/" element={<HomePage />} />
                  <Route path="/forum" element={<ProtectedRoute><ForumPage /></ProtectedRoute>} />
                  <Route path="/forum/new" element={<ProtectedRoute><NewTopicPage /></ProtectedRoute>} />
                  <Route path="/forum/topics/:topicId" element={<ProtectedRoute><TopicDetailPage /></ProtectedRoute>} />
                  <Route path="/admin/users" element={<ProtectedRoute><AdminUsersPage /></ProtectedRoute>} />
                  <Route path="/admin/events" element={<ProtectedRoute><AdminEventsPage /></ProtectedRoute>} />
                  <Route path="/admin/tasks" element={<ProtectedRoute><AdminTasksPage /></ProtectedRoute>} />
                  <Route path="/admin/configuration" element={<ProtectedRoute><AdminConfigPage /></ProtectedRoute>} />
                  <Route path="/oracle" element={<ProtectedRoute><OraclePage /></ProtectedRoute>} />
                  <Route path="/prerequisites/how-to-use" element={<ProtectedRoute><HowToUsePage /></ProtectedRoute>} />
                  <Route path="/prerequisites/installations" element={<ProtectedRoute><InstallationListPage /></ProtectedRoute>} />
                  <Route path="/prerequisites/installations/:installationId/:slug" element={<ProtectedRoute><InstallationPrereqPage /></ProtectedRoute>} />
                  <Route path="/documents" element={<ProtectedRoute><DocumentsPage /></ProtectedRoute>} />
                  <Route path="/events" element={<ProtectedRoute><EventsPage /></ProtectedRoute>} />
                  <Route path="/account/security" element={<ProtectedRoute><SecurityPage /></ProtectedRoute>} />
                </Routes>
              </Layout>
            }
          />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  );
}

// The pre-existing route paths (from App.tsx) paired with a stable heading each
// page renders, used to assert the route -> page-component mapping is unchanged.
// The default Active_Language is French, so headings use their FR labels.
// `/tasks` is deliberately EXCLUDED — it is the path being fixed (no route yet).
// `level` pins the page's own top-level heading (the <h1>/<h2> the page root
// renders), disambiguating it from same-named sub-section headings.
const INSTALL_ID = '11111111-1111-1111-1111-111111111111';
const EXISTING_ROUTES: Array<{ path: string; heading: RegExp | string; level: number }> = [
  { path: '/', heading: 'AI Shai Web OPCP Workspace', level: 1 },
  { path: '/forum', heading: 'Forum', level: 1 },
  { path: '/forum/new', heading: 'Nouveau sujet', level: 1 },
  { path: '/documents', heading: 'Documents', level: 1 },
  { path: '/oracle', heading: 'Oracle IA', level: 1 },
  { path: '/events', heading: 'Événements', level: 1 },
  { path: '/admin/users', heading: 'Gestion des utilisateurs', level: 1 },
  { path: '/admin/events', heading: 'Gestion des événements', level: 1 },
  { path: '/admin/tasks', heading: 'Gérer les tâches', level: 1 },
  { path: '/admin/configuration', heading: 'Configuration', level: 1 },
  { path: '/prerequisites/how-to-use', heading: 'Comment utiliser', level: 1 },
  { path: '/prerequisites/installations', heading: 'Installations', level: 1 },
  { path: `/prerequisites/installations/${INSTALL_ID}/basics`, heading: 'Basics', level: 1 },
  { path: '/account/security', heading: /S[ée]curit[ée] du Compte/, level: 2 },
];

// Routes protected by ProtectedRoute on the UNFIXED code (everything except the
// public `/`). `/tasks` is deliberately EXCLUDED: it has no route yet, so it is
// NOT part of the auth-enforcement baseline (navigating there renders a blank
// content area, not a /login redirect). These are the inputs for the
// unauthenticated-redirect property.
const PROTECTED_ROUTES: string[] = EXISTING_ROUTES.map((r) => r.path).filter((p) => p !== '/');

const NUM_RUNS = 100;

// jsdom does not implement scrollIntoView, which OraclePage calls in a mount
// effect. Stub it so mounting OraclePage under its route does not throw (this
// is an environment shim, not a behavior change).
beforeEach(() => {
  localStorage.clear();
  cleanup();
  vi.clearAllMocks();
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});

// ---------------------------------------------------------------------------
// Requirement 3.1 — /events renders EventsPage and calls listEvents() (Events
// feature preserved unchanged).
// ---------------------------------------------------------------------------
describe('Preservation: /events keeps EventsPage + listEvents() (Requirement 3.1)', () => {
  it('renders EventsPage and fetches via eventService.listEvents()', async () => {
    signIn('member');

    renderAppRoutes('/events');

    expect(await screen.findByRole('heading', { name: 'Événements', level: 1 })).toBeInTheDocument();
    expect(screen.queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument();
    await waitFor(() => expect(eventService.listEvents).toHaveBeenCalled());
  });
});

// ---------------------------------------------------------------------------
// Requirement 3.2 — /admin/tasks renders AdminTasksPage with create + per-task
// edit/cancel controls (admin task management preserved).
// ---------------------------------------------------------------------------
describe('Preservation: /admin/tasks keeps full admin task management (Requirement 3.2)', () => {
  it('renders AdminTasksPage with create control and per-task edit/cancel controls', async () => {
    // One task so the per-card edit/cancel controls render.
    vi.mocked(taskService.listTasks).mockResolvedValueOnce([
      {
        id: 'task-1',
        title: 'Préparer le dossier',
        description: 'desc',
        start_date: '2030-01-01T10:00:00Z',
        end_date: '2030-01-01T12:00:00Z',
        location: 'Salle B',
        owner_id: 'u1',
        assigned_user_ids: [],
        status: 'scheduled',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      } as unknown as Awaited<ReturnType<typeof taskService.listTasks>>[number],
    ]);
    signIn('administrator');

    renderAppRoutes('/admin/tasks');

    // The admin task-management heading renders (not the login redirect).
    expect(await screen.findByRole('heading', { name: 'Gérer les tâches', level: 1 })).toBeInTheDocument();
    expect(screen.queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument();

    // Full management controls: create (a button, not the nav link) + per-task
    // edit/cancel.
    expect(await screen.findByRole('button', { name: 'Tâches' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Modifier' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Annuler' })).toBeInTheDocument();

    // AdminTasksPage fetched its data on mount.
    await waitFor(() => expect(taskService.listTasks).toHaveBeenCalled());
  });
});

// ---------------------------------------------------------------------------
// Requirement 3.3 — /admin/events renders AdminEventsPage with its full event-
// management controls (admin event management preserved).
// ---------------------------------------------------------------------------
describe('Preservation: /admin/events keeps full admin event management (Requirement 3.3)', () => {
  it('renders AdminEventsPage with create control and per-event edit/cancel controls', async () => {
    vi.mocked(eventService.listEvents).mockResolvedValueOnce([
      {
        id: 'evt-1',
        title: 'Assemblée générale',
        description: 'desc',
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
      } as unknown as Awaited<ReturnType<typeof eventService.listEvents>>[number],
    ]);
    signIn('administrator');

    renderAppRoutes('/admin/events');

    expect(await screen.findByRole('heading', { name: 'Gestion des événements', level: 1 })).toBeInTheDocument();
    expect(screen.queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument();

    expect(await screen.findByRole('button', { name: 'Nouvel événement' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Modifier' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Annuler' })).toBeInTheDocument();

    await waitFor(() => expect(eventService.listEvents).toHaveBeenCalled());
  });
});

// ---------------------------------------------------------------------------
// Requirement 3.4 — ProtectedRoute enforcement is unchanged: unauthenticated
// access to an already-protected route redirects to /login.
// ---------------------------------------------------------------------------
describe('Preservation: auth enforcement on already-protected routes (Requirement 3.4)', () => {
  it('redirects an unauthenticated /admin/tasks to /login', () => {
    // No access_token: authService.isAuthenticated() is false.
    renderAppRoutes('/admin/tasks');
    expect(screen.getByText(LOGIN_PLACEHOLDER)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Gérer les tâches' })).not.toBeInTheDocument();
  });

  it('redirects an unauthenticated /events to /login', () => {
    renderAppRoutes('/events');
    expect(screen.getByText(LOGIN_PLACEHOLDER)).toBeInTheDocument();
  });

  it('lets an authenticated admin through to /admin/tasks', async () => {
    signIn('administrator');
    renderAppRoutes('/admin/tasks');
    expect(await screen.findByRole('heading', { name: 'Gérer les tâches', level: 1 })).toBeInTheDocument();
    expect(screen.queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Requirement 3.5 — every existing path renders its same page component.
// (Example checks; the property below generalizes this over the whole set.)
// ---------------------------------------------------------------------------
describe('Preservation: existing routes render their same page component (Requirement 3.5)', () => {
  for (const { path, heading, level } of EXISTING_ROUTES) {
    it(`maps ${path} to its page component`, async () => {
      signIn('administrator');
      renderAppRoutes(path);
      const found = await screen.findByRole('heading', { name: heading, level });
      expect(found).toBeInTheDocument();
      expect(screen.queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument();
    });
  }
});

// ---------------------------------------------------------------------------
// Requirement 3.6 — the nav bar shows the "Tasks" -> /tasks link, and for
// admins the "Manage tasks" -> /admin/tasks dropdown link.
// ---------------------------------------------------------------------------
describe('Preservation: nav bar Tasks + admin "Manage tasks" links (Requirement 3.6)', () => {
  it('shows the "Tâches" link to /tasks for an authenticated member', async () => {
    signIn('member');
    renderAppRoutes('/');

    // A member sees a plain "Tâches" link (no admin caret) pointing to /tasks.
    const tasksLink = screen.getAllByRole('link', { name: /^T[aâ]ches$/ })[0];
    expect(tasksLink).toHaveAttribute('href', '/tasks');
  });

  it('reveals a "Gérer les tâches" link pointing to /admin/tasks on hover (admin)', async () => {
    const user = userEvent.setup();
    signIn('administrator');
    renderAppRoutes('/');

    // The admin Tasks nav link carries a " ▾" caret in its accessible name and
    // points to /tasks.
    const tasksLink = screen.getAllByRole('link', { name: /^T[aâ]ches\s*▾$/ })[0];
    expect(tasksLink).toHaveAttribute('href', '/tasks');

    // The dropdown entry is hidden until the Tasks item is hovered.
    expect(screen.queryAllByRole('link', { name: 'Gérer les tâches' })).toHaveLength(0);

    await user.hover(tasksLink);
    const manage = await screen.findByRole('link', { name: 'Gérer les tâches' });
    expect(manage).toHaveAttribute('href', '/admin/tasks');
  });
});

// ---------------------------------------------------------------------------
// Property (preservation over existing routes): for a randomly drawn
// pre-existing path, the mapped page component (identified by its heading) is
// unchanged versus the original routing table (Requirement 3.5).
// ---------------------------------------------------------------------------
describe('Property — existing route -> page-component mapping is unchanged (Requirement 3.5)', () => {
  it('renders the expected page heading for a random pre-existing path (authenticated)', async () => {
    await fc.assert(
      fc.asyncProperty(fc.constantFrom(...EXISTING_ROUTES), async ({ path, heading, level }) => {
        cleanup();
        localStorage.clear();
        vi.clearAllMocks();
        // Authenticated admin: the guard lets every route through and admin
        // pages render (superset of the member-visible set).
        signIn('administrator');

        const { findByRole, queryByText, unmount } = renderAppRoutes(path);
        try {
          const found = await findByRole('heading', { name: heading, level });
          expect(found).toBeInTheDocument();
          // The auth guard did not redirect.
          expect(queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument();
        } finally {
          unmount();
        }
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// ---------------------------------------------------------------------------
// Property (auth enforcement): for a randomly drawn already-protected route and
// a random authenticated/unauthenticated state, enforcement matches the shared
// ProtectedRoute rule — unauthenticated redirects to /login, authenticated does
// not (Requirement 3.4).
// ---------------------------------------------------------------------------
describe('Property — auth enforcement matches other protected routes (Requirement 3.4)', () => {
  it('unauthenticated protected routes redirect to /login; authenticated do not', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.constantFrom(...PROTECTED_ROUTES),
        fc.boolean(),
        async (path, isAuthenticated) => {
          cleanup();
          localStorage.clear();
          vi.clearAllMocks();
          if (isAuthenticated) {
            signIn('administrator');
          }

          const { queryByText, findByText, unmount } = renderAppRoutes(path);
          try {
            if (isAuthenticated) {
              // Authenticated: the guard does NOT redirect to the login route.
              await waitFor(() =>
                expect(queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument(),
              );
            } else {
              // Unauthenticated: the guard redirects to the login route.
              expect(await findByText(LOGIN_PLACEHOLDER)).toBeInTheDocument();
            }
          } finally {
            unmount();
          }
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});
