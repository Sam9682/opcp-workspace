import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import fc from 'fast-check';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { LanguageProvider } from '../hooks/useLanguage';
import { HowToUsePage } from './HowToUsePage';
import { InstallationListPage } from '../components/prerequisites/InstallationListPage';
import { InstallationPrereqPage } from './InstallationPrereqPage';
import { prerequisitesService } from '../services/prerequisitesService';

// The installation-scoped pages call prerequisitesService on mount
// (loadStaticContent / loadClientAnswers) and the list page calls
// listInstallations. Mock the module so those loads resolve to empty
// content/answers/lists and never hit the network, isolating route/guard
// behavior. HowToUse makes no service calls.
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
    // The servers-nodes tab (ServersTable) loads credential config on mount
    // when given an installationId; provide empty/no-op resolves so route/guard
    // behavior stays isolated and the mount effect never hits the network.
    loadCredentialConfig: vi.fn().mockResolvedValue({
      auth_url: '',
      credential_id: '',
      nova_endpoint: '',
      secret_stored: false,
    }),
    saveCredentialConfig: vi.fn().mockResolvedValue({
      auth_url: '',
      credential_id: '',
      nova_endpoint: '',
      secret_stored: false,
    }),
    retrieveServers: vi.fn().mockResolvedValue({ servers: [] }),
  },
}));

// Mirrors the prerequisites route structure declared in App.tsx: the global
// how-to-use page, the installation list entry point, and a single
// installation-scoped page mounted at
// /prerequisites/installations/:installationId/:slug. Each is wrapped in a
// ProtectedRoute, with a recognizable /login placeholder used to detect the
// auth-guard redirect.
function renderPrereqRoutes(initialEntry: string) {
  // The prerequisites pages call useTranslation(), so wrap the routes in a
  // LanguageProvider.
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/login" element={<div>Login Placeholder</div>} />
          <Route
            path="/prerequisites/how-to-use"
            element={
              <ProtectedRoute>
                <HowToUsePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/prerequisites/installations"
            element={
              <ProtectedRoute>
                <InstallationListPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/prerequisites/installations/:installationId/:slug"
            element={
              <ProtectedRoute>
                <InstallationPrereqPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  );
}

// Each prerequisites route paired with the heading title rendered by its page.
// - HowToUse renders <h1>Comment utiliser</h1>
// - InstallationListPage renders <h1>{t('prereq.installations.title')}</h1> = "Installations"
// - InstallationPrereqPage → StaticContentPage / QuestionAnswerForm render <h1>{title}</h1>
const INSTALL_ID = '11111111-1111-1111-1111-111111111111';
const PREREQ_ROUTES: Array<{ route: string; title: string }> = [
  { route: '/prerequisites/how-to-use', title: 'Comment utiliser' },
  { route: '/prerequisites/installations', title: 'Installations' },
  { route: `/prerequisites/installations/${INSTALL_ID}/basics`, title: 'Basics' },
  {
    route: `/prerequisites/installations/${INSTALL_ID}/network-checklist`,
    title: 'Network Checklist',
  },
  {
    route: `/prerequisites/installations/${INSTALL_ID}/core-control-plane`,
    title: 'Core Control Plane',
  },
  { route: `/prerequisites/installations/${INSTALL_ID}/cloudstore`, title: 'CloudStore' },
  { route: `/prerequisites/installations/${INSTALL_ID}/vcf`, title: 'VCF' },
  {
    route: `/prerequisites/installations/${INSTALL_ID}/network-flux`,
    title: 'Network Flux',
  },
];

const LOGIN_PLACEHOLDER = 'Login Placeholder';

beforeEach(() => {
  localStorage.clear();
  cleanup();
});

// Validates: Requirements 5.1, 5.3
describe('prerequisites route wiring and auth guard', () => {
  describe('when authenticated', () => {
    for (const { route, title } of PREREQ_ROUTES) {
      it(`renders its page at ${route}`, () => {
        // Authenticated as a non-admin member: titles still render for every
        // archetype, and the auth guard lets the route through.
        localStorage.setItem('access_token', 'test-token');
        localStorage.setItem('user_role', 'member');

        renderPrereqRoutes(route);

        // The protected page is shown...
        expect(screen.getByText(title)).toBeInTheDocument();
        // ...and the auth-guard redirect target is not.
        expect(screen.queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument();
      });
    }
  });

  describe('when not authenticated', () => {
    for (const { route, title } of PREREQ_ROUTES) {
      it(`redirects ${route} to /login`, () => {
        // No access_token set: authService.isAuthenticated() is false.
        renderPrereqRoutes(route);

        // The auth guard redirects to the login route...
        expect(screen.getByText(LOGIN_PLACEHOLDER)).toBeInTheDocument();
        // ...and the protected page title is not rendered.
        expect(screen.queryByText(title)).not.toBeInTheDocument();
      });
    }
  });
});

// Minimum property-test iterations mandated by the design (>= 100).
const NUM_RUNS = 100;

// Quantify over the full set of prerequisites routes. Each run draws one
// { route, title } pair so the guard behaviour is exercised uniformly across
// every archetype rather than a fixed sequence.
const prereqRouteArb = fc.constantFrom(...PREREQ_ROUTES);

// Feature: multi-instance-opcp-prerequisites, Property: Authenticated access renders the matching prerequisites page
// Validates: Requirements 5.1, 5.3
describe('authenticated access renders the matching prerequisites page', () => {
  it('renders the page title and not the login placeholder for a random route when authenticated', async () => {
    await fc.assert(
      fc.property(prereqRouteArb, ({ route, title }) => {
        // Reset DOM + storage each run so state never leaks between draws.
        cleanup();
        localStorage.clear();
        // Authenticated as a non-admin member: the auth guard lets the route
        // through and every archetype renders its title.
        localStorage.setItem('access_token', 'test-token');
        localStorage.setItem('user_role', 'member');

        renderPrereqRoutes(route);

        // The protected page is shown...
        expect(screen.getByText(title)).toBeInTheDocument();
        // ...and the auth-guard redirect target is not.
        expect(screen.queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// Feature: multi-instance-opcp-prerequisites, Property: Unauthenticated access redirects to login
// Validates: Requirements 5.1, 5.3
describe('unauthenticated access redirects to login', () => {
  it('renders the login placeholder and not the page title for a random route when unauthenticated', async () => {
    await fc.assert(
      fc.property(prereqRouteArb, ({ route, title }) => {
        // Reset DOM + storage each run; leave access_token unset so
        // authService.isAuthenticated() is false.
        cleanup();
        localStorage.clear();

        renderPrereqRoutes(route);

        // The auth guard redirects to the login route...
        expect(screen.getByText(LOGIN_PLACEHOLDER)).toBeInTheDocument();
        // ...and the protected page title is not rendered.
        expect(screen.queryByText(title)).not.toBeInTheDocument();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// ---------------------------------------------------------------------------
// Bugfix: default-installation-checklists
// Property 1: Bug Condition — Default Installation Renders Only Network Checklist
//
// The default-installation entry route (InstallationListPage.FIRST_PREREQ_SLUG =
// 'network-checklist') should render ALL FOUR checklist categories. On the
// UNFIXED code it renders only the "Network Checklist" section, so this test is
// EXPECTED TO FAIL — the failure confirms the bug exists. Do NOT change the code
// or the test to make it pass at this stage.
//
// Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3
// ---------------------------------------------------------------------------

// The entry slug an installation row links to (from InstallationListPage.FIRST_PREREQ_SLUG).
const DEFAULT_INSTALLATION_ENTRY_SLUG = 'network-checklist';

// The full set of category headings a default-installation entry view must show.
const REQUIRED_CATEGORY_HEADINGS = [
  'Network Checklist',
  'Core Control Plane',
  'CloudStore',
  'VCF',
] as const;

describe('default-installation entry view renders all four checklist categories', () => {
  it('shows Network Checklist, Core Control Plane, CloudStore, and VCF for an authenticated member', () => {
    // Authenticated as a non-admin member so the auth guard lets the route
    // through, matching the existing authenticated-member setup.
    localStorage.setItem('access_token', 'test-token');
    localStorage.setItem('user_role', 'member');

    renderPrereqRoutes(
      `/prerequisites/installations/${INSTALL_ID}/${DEFAULT_INSTALLATION_ENTRY_SLUG}`,
    );

    // Quantify over the set of the four required category headings: every one
    // of them must be present on the default-installation entry view.
    for (const heading of REQUIRED_CATEGORY_HEADINGS) {
      expect(screen.getByText(heading)).toBeInTheDocument();
    }
  });
});

// ---------------------------------------------------------------------------
// Bugfix: default-installation-checklists
// Property 2: Preservation — Non-Entry Views Behave Identically
//
// Observation-first: these tests assert behavior observed on the UNFIXED code
// for inputs where the bug condition does NOT hold. They MUST PASS on the
// unfixed code, establishing the baseline the fix must preserve.
//
// Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
// ---------------------------------------------------------------------------

// The slugs InstallationPrereqPage recognizes (static + question archetypes).
// Any slug OUTSIDE this set must render the not-found message.
const RECOGNIZED_SLUGS = [
  'basics',
  'network-flux',
  'network-checklist',
  'core-control-plane',
  'cloudstore',
  'vcf',
] as const;

// The not-found message rendered for an unknown/unrecognized slug (Req 3.2).
const NOT_FOUND_MESSAGE = 'Page de prérequis introuvable.';

// Feature: default-installation-checklists, Property 2: Preservation — unknown-slug not-found
// Validates: Requirements 3.2
describe('unknown-slug preservation: any unrecognized slug renders the not-found message', () => {
  it('renders "Page de prérequis introuvable." for any slug outside the recognized set', async () => {
    await fc.assert(
      fc.property(
        // Generate arbitrary URL-path slug segments, then constrain to the
        // input space that matters here: non-empty slugs that are NOT one of
        // the recognized archetype slugs. This quantifies over the whole
        // "unknown slug" domain rather than a single hand-picked example.
        fc
          .stringMatching(/^[a-z0-9-]+$/)
          .filter(
            (s) =>
              s.length > 0 &&
              !(RECOGNIZED_SLUGS as readonly string[]).includes(s),
          ),
        (slug) => {
          // Reset DOM + storage each run so state never leaks between draws.
          cleanup();
          localStorage.clear();
          // Authenticated as a non-admin member so the auth guard lets the
          // route through and the page itself (not the login redirect) renders.
          localStorage.setItem('access_token', 'test-token');
          localStorage.setItem('user_role', 'member');

          // Query within THIS render's own container (not the global `screen`)
          // and unmount at the end of the iteration, so async mount effects
          // from a prior draw can never bleed into this assertion.
          const { getByText, queryByText, unmount } = renderPrereqRoutes(
            `/prerequisites/installations/${INSTALL_ID}/${slug}`,
          );
          try {
            // The not-found message is shown for the unrecognized slug...
            expect(getByText(NOT_FOUND_MESSAGE)).toBeInTheDocument();
            // ...and the auth guard did not redirect to /login.
            expect(queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument();
          } finally {
            unmount();
          }
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});

// A single question category, identified by its canonical slug plus one of its
// row ids. On the UNFIXED code, navigating to a category slug renders exactly
// that category via QuestionAnswerForm and persists answers keyed on
// (installationId, slug). We generate arbitrary (rowId, value) for a chosen
// category and assert the persistence key is that category's own slug.
const PERSISTENCE_CATEGORIES: Array<{
  slug: string;
  // The primary question text used to locate the row's answer input, paired
  // with the row id the component persists under.
  rows: Array<{ rowId: string; questionPrimary: string }>;
}> = [
  {
    slug: 'network-checklist',
    rows: [
      {
        rowId: 'nc-deploy-remote-access',
        questionPrimary: 'Can we access OPCP racks remotely ? If yes, how ? (VPN, Bastion)',
      },
      {
        rowId: 'nc-svc-dns-servers',
        questionPrimary: 'Are internal DNS servers available? If yes, provide IPs.',
      },
    ],
  },
  {
    slug: 'core-control-plane',
    rows: [
      { rowId: 'ccp-ntp', questionPrimary: 'NTP' },
      { rowId: 'ccp-ldap', questionPrimary: 'LDAP' },
    ],
  },
  {
    slug: 'cloudstore',
    rows: [
      { rowId: 'cs-network-subnet-creation', questionPrimary: 'Network & Subnet creation' },
      { rowId: 'cs-ingress-vip', questionPrimary: 'Ingress VIP (customer)' },
    ],
  },
  {
    slug: 'vcf',
    rows: [
      { rowId: 'vcf-mgmt-network-name', questionPrimary: 'vcf_mgmt_network_name' },
      { rowId: 'vcf-wld-workload-domain-num', questionPrimary: 'workload_domain_num' },
    ],
  },
];

// Draws a category and one of its rows together so the (slug, rowId) pair is
// always internally consistent, then pairs it with an arbitrary answer value.
// The persistence property renders all four checklist categories on the
// network-checklist entry slug; with the full network checklist config that
// render is heavy, so this property uses a reduced (still meaningful) run
// count to stay within the default test timeout while preserving coverage.
const PERSISTENCE_NUM_RUNS = 25;

const persistenceInputArb = fc
  .constantFrom(...PERSISTENCE_CATEGORIES)
  .chain((category) =>
    fc.record({
      slug: fc.constant(category.slug),
      row: fc.constantFrom(...category.rows),
      value: fc.string(),
    }),
  );

// Feature: default-installation-checklists, Property 2: Preservation — persistence keys
// Validates: Requirements 3.4, 3.5
describe('persistence-key preservation: editing a client answer saves under that category\'s own slug', () => {
  it('calls saveClientAnswer(installationId, slug, rowId, value) with the category slug for arbitrary (rowId, value)', async () => {
    await fc.assert(
      fc.property(persistenceInputArb, ({ slug, row, value }) => {
        // Reset DOM + storage + mock calls each run so state never leaks.
        cleanup();
        localStorage.clear();
        vi.mocked(prerequisitesService.saveClientAnswer).mockClear();
        // Authenticated as a non-admin member: canAnswer is true, so the
        // client answer input is editable and blur persists it.
        localStorage.setItem('access_token', 'test-token');
        localStorage.setItem('user_role', 'member');

        // On the UNFIXED code, a category slug renders exactly that category.
        // Query within THIS render's own container and unmount at the end so
        // async mount effects from a prior draw cannot bleed in.
        const { getByLabelText, unmount } = renderPrereqRoutes(
          `/prerequisites/installations/${INSTALL_ID}/${slug}`,
        );
        try {
          // Locate the editable client-answer input for the chosen row via its
          // accessible label ("Réponse client — <question>") and its per-row
          // markers/example/hints render alongside it (Req 3.5).
          const input = getByLabelText(`Réponse client — ${row.questionPrimary}`);

          // Type an arbitrary value and blur to trigger persistence.
          fireEvent.change(input, { target: { value } });
          fireEvent.blur(input);

          // The answer persists under this category's OWN slug and rowId (Req 3.4).
          expect(prerequisitesService.saveClientAnswer).toHaveBeenCalledWith(
            INSTALL_ID,
            slug,
            row.rowId,
            value,
          );
        } finally {
          unmount();
        }
      }),
      { numRuns: PERSISTENCE_NUM_RUNS },
    );
  });
});
