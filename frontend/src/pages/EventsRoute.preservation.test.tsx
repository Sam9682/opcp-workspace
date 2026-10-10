/**
 * Preservation property tests — Property 2: Preservation, Existing Routes and
 * Admin Behavior Unchanged.
 * Spec: .kiro/specs/member-events-route-missing
 *
 * Property 2 (Preservation): for any input where the bug condition does NOT
 * hold (navigation to any path other than `/events`, or an unauthenticated
 * request to an already-protected route), the fixed application SHALL produce
 * the same result as the original application — preserving `/admin/events`
 * admin management, `ProtectedRoute` authentication enforcement, all other
 * route mappings, and the admin "Manage events" dropdown link.
 *
 * OBSERVATION-FIRST METHODOLOGY: the assertions below encode behavior OBSERVED
 * on the CURRENT (UNFIXED) code, so they MUST PASS today and lock the baseline
 * the fix must preserve. To exercise the REAL routing table verbatim, this test
 * reconstructs the layout's inner <Routes> from App.tsx (the same page
 * components, the same ProtectedRoute wrapping, in the same order) — following
 * the reconstruction pattern in prerequisitesRoutes.test.tsx. The `/events`
 * path is deliberately EXCLUDED from the existing-routes set: it is the path
 * being fixed and has no route on unfixed code.
 *
 * The unauthenticated-redirect property is scoped to routes that are ALREADY
 * protected on the unfixed code (every member/admin route except `/` and
 * `/events`). Per the task, `/events` is added to that set only AFTER the fix
 * wraps it in ProtectedRoute.
 *
 * EXPECTED OUTCOME ON UNFIXED CODE: PASS (baseline behavior to preserve).
 *
 * Validates: Requirements 3.1, 3.2, 3.3, 3.4
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
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
// isolating route/guard behavior. This mirrors prerequisitesRoutes.test.tsx.
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
 * `/events` path (which does not exist on unfixed code and is the path under
 * fix). A recognizable /login placeholder detects the ProtectedRoute redirect.
 * Rendering happens inside <Layout> so the real nav (and its admin dropdown) is
 * present, matching how App.tsx mounts these routes.
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
// `/events` is deliberately EXCLUDED — it is the path being fixed.
// `level` pins the page's own top-level heading (the <h1>/<h2> the page root
// renders), disambiguating it from same-named sub-section headings (e.g.
// DocumentsPage renders an <h1>Documents</h1> title plus per-category <h2>
// section headings, one of which can also read "Documents").
const INSTALL_ID = '11111111-1111-1111-1111-111111111111';
const EXISTING_ROUTES: Array<{ path: string; heading: RegExp | string; level: number }> = [
  { path: '/', heading: 'AI Shai Web OPCP Workspace', level: 1 },
  { path: '/forum', heading: 'Forum', level: 1 },
  { path: '/forum/new', heading: 'Nouveau sujet', level: 1 },
  { path: '/documents', heading: 'Documents', level: 1 },
  { path: '/oracle', heading: 'Oracle IA', level: 1 },
  { path: '/admin/users', heading: 'Gestion des utilisateurs', level: 1 },
  { path: '/admin/events', heading: 'Gestion des événements', level: 1 },
  { path: '/admin/tasks', heading: 'Gérer les tâches', level: 1 },
  { path: '/admin/configuration', heading: 'Configuration', level: 1 },
  { path: '/prerequisites/how-to-use', heading: 'Comment utiliser', level: 1 },
  { path: '/prerequisites/installations', heading: 'Installations', level: 1 },
  { path: `/prerequisites/installations/${INSTALL_ID}/basics`, heading: 'Basics', level: 1 },
  { path: '/account/security', heading: /S[ée]curit[ée] du Compte/, level: 2 },
];

// Routes protected by ProtectedRoute (everything except the public `/`). The
// fix (task 3.3) wires `/events` under ProtectedRoute, so it is now part of the
// auth-enforcement set alongside the pre-existing protected routes. These are
// the inputs for the unauthenticated-redirect property.
const PROTECTED_ROUTES: string[] = [
  ...EXISTING_ROUTES.map((r) => r.path).filter((p) => p !== '/'),
  '/events',
];

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
// Requirement 3.1 — /admin/events renders AdminEventsPage with create/edit/
// cancel controls (admin management preserved).
// ---------------------------------------------------------------------------
describe('Preservation: /admin/events keeps full admin management (Requirement 3.1)', () => {
  it('renders AdminEventsPage with create control, and edit/cancel controls per event', async () => {
    // One event so the per-card edit/cancel controls render.
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
      },
    ]);
    signIn('administrator');

    renderAppRoutes('/admin/events');

    // The admin management heading renders (not the login redirect).
    expect(await screen.findByRole('heading', { name: 'Gestion des événements' })).toBeInTheDocument();
    expect(screen.queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument();

    // Full management controls are present: create + per-event edit/cancel.
    expect(await screen.findByRole('button', { name: 'Nouvel événement' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Modifier' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Annuler' })).toBeInTheDocument();

    // AdminEventsPage fetched its data on mount.
    await waitFor(() => expect(eventService.listEvents).toHaveBeenCalled());
  });
});

// ---------------------------------------------------------------------------
// Requirement 3.2 — ProtectedRoute enforcement is unchanged: unauthenticated
// access to an already-protected route redirects to /login.
// ---------------------------------------------------------------------------
describe('Preservation: auth enforcement on already-protected routes (Requirement 3.2)', () => {
  it('redirects an unauthenticated /admin/events to /login', () => {
    // No access_token: authService.isAuthenticated() is false.
    renderAppRoutes('/admin/events');
    expect(screen.getByText(LOGIN_PLACEHOLDER)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Gestion des événements' })).not.toBeInTheDocument();
  });

  it('lets an authenticated admin through to /admin/events', async () => {
    signIn('administrator');
    renderAppRoutes('/admin/events');
    expect(await screen.findByRole('heading', { name: 'Gestion des événements' })).toBeInTheDocument();
    expect(screen.queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Requirement 3.3 — every existing path renders its same page component.
// (Example checks; the property below generalizes this over the whole set.)
// ---------------------------------------------------------------------------
describe('Preservation: existing routes render their same page component (Requirement 3.3)', () => {
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
// Requirement 3.4 — the admin "Events" dropdown shows the "Manage events" link
// to /admin/events.
// ---------------------------------------------------------------------------
describe('Preservation: admin "Manage events" dropdown link (Requirement 3.4)', () => {
  it('reveals a "Gérer les événements" link pointing to /admin/events on hover', async () => {
    const user = userEvent.setup();
    signIn('administrator');
    renderAppRoutes('/');

    // The admin Events nav link carries a " ▾" caret in its accessible name.
    const eventsLink = screen.getAllByRole('link', { name: /^Événements\s*▾$/ })[0];
    expect(eventsLink).toHaveAttribute('href', '/events');

    // The dropdown entry is hidden until the Events item is hovered.
    expect(screen.queryAllByRole('link', { name: 'Gérer les événements' })).toHaveLength(0);

    await user.hover(eventsLink);
    const manage = await screen.findByRole('link', { name: 'Gérer les événements' });
    expect(manage).toHaveAttribute('href', '/admin/events');
  });
});

// ---------------------------------------------------------------------------
// Property (preservation over existing routes): for a randomly drawn
// pre-existing path, the mapped page component (identified by its heading) is
// unchanged versus the original routing table (Requirement 3.3).
// ---------------------------------------------------------------------------
describe('Property — existing route -> page-component mapping is unchanged (Requirement 3.3)', () => {
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
// not (Requirement 3.2).
// ---------------------------------------------------------------------------
describe('Property — auth enforcement matches other protected routes (Requirement 3.2)', () => {
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
              // (The specific page content is covered by the mapping property;
              // here we only assert the guard decision.)
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
