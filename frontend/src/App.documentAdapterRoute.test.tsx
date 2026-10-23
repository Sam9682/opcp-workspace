/**
 * Tests — Document Adapter navigation presence and protected-route redirect.
 * Spec: .kiro/specs/document-audience-adapter (Task 13.3)
 *
 * These tests render the REAL `App` (its own BrowserRouter + LanguageProvider)
 * and exercise the Document Adapter wiring added in tasks 13.1 (route) and
 * 13.2 (nav item):
 *
 *  - Nav presence (Requirement 1.1): an authenticated member sees the
 *    Document Adapter nav item (label `nav.documentAdapter`) and it links to
 *    `/document-adapter`.
 *  - Protected-route redirect (Requirements 1.2, 1.3): an unauthenticated
 *    request to `/document-adapter` is redirected by ProtectedRoute to the
 *    login page, and the DocumentAdapterPage never mounts (its on-mount service
 *    calls never fire).
 *
 * Setup mirrors the established conventions (App.memberTasksNav.integration.test.tsx /
 * EventsPage.test.tsx): localStorage auth seeding, the real App's BrowserRouter
 * driven via the history API, and the services DocumentAdapterPage calls on
 * mount (documentService.listDocuments, oracleService.getAvailableProviders)
 * mocked with vi.fn()s so no network is hit and the redirect case can assert
 * the page did NOT mount.
 *
 * The nav label text is resolved from the i18n dictionary
 * (`nav.documentAdapter`): "Document Adapter" (EN) / "Adaptateur de documents"
 * (FR). We seed EN so the heading/label assertions match English copy.
 *
 * Validates: Requirements 1.1, 1.2, 1.3
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import App from './App';

// DocumentAdapterPage fetches on mount via documentService.listDocuments() and
// oracleService.getAvailableProviders(). Mock these modules so the page (when
// it mounts) renders deterministically without network access, and so the
// redirect test can assert the page never mounted (the calls never fire).
vi.mock('./services/documentService', () => ({
  documentService: {
    listDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    downloadDocument: vi.fn(),
  },
}));

vi.mock('./services/oracleService', () => ({
  oracleService: {
    getAvailableProviders: vi.fn(),
  },
}));

import { documentService } from './services/documentService';
import { oracleService } from './services/oracleService';

const mockedListDocuments = vi.mocked(documentService.listDocuments);
const mockedGetProviders = vi.mocked(oracleService.getAvailableProviders);

// localStorage keys read by authService for auth/admin gating.
const TOKEN_KEY = 'access_token';
const ROLE_KEY = 'user_role';
const USER_KEY = 'user';
// localStorage key under which the active language persists (Language_Store).
const LANG_KEY = 'opcp.language';

/** Sign in as an authenticated member. */
function signInAsMember() {
  localStorage.setItem(TOKEN_KEY, 'test-token');
  localStorage.setItem(ROLE_KEY, 'member');
  localStorage.setItem(
    USER_KEY,
    JSON.stringify({ id: 'u1', email: 'member@opcp.test', first_name: 'Us', last_name: 'Er', role: 'member' }),
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

beforeEach(() => {
  localStorage.clear();
  goto('/');
  mockedListDocuments.mockReset();
  mockedGetProviders.mockReset();
  mockedListDocuments.mockResolvedValue([] as never);
  mockedGetProviders.mockResolvedValue([] as never);
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  goto('/');
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Nav presence — an authenticated member sees the Document Adapter nav item
// linking to /document-adapter. (Requirement 1.1)
// ---------------------------------------------------------------------------
describe('Document Adapter nav presence (Requirement 1.1)', () => {
  it('renders the Document Adapter nav item linking to /document-adapter for a member', () => {
    signInAsMember();
    setLanguage('en');
    goto('/');

    render(<App />);

    // The nav renders the Document Adapter item (desktop + mobile), each with
    // the nav.documentAdapter label pointing to /document-adapter.
    const links = screen.getAllByRole('link', { name: 'Document Adapter' });
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      expect(link).toHaveAttribute('href', '/document-adapter');
    }
  });
});

// ---------------------------------------------------------------------------
// Protected-route redirect — an unauthenticated request to /document-adapter is
// redirected to /login and the page never mounts. (Requirements 1.2, 1.3)
// ---------------------------------------------------------------------------
describe('Document Adapter protected-route redirect (Requirements 1.2, 1.3)', () => {
  it('redirects an unauthenticated visitor at /document-adapter to /login', async () => {
    // No auth seeded: ProtectedRoute redirects to /login.
    setLanguage('en');
    goto('/document-adapter');

    render(<App />);

    await waitFor(() => expect(window.location.pathname).toBe('/login'));

    // The login page rendered (page.login.title -> EN "Log in" heading)...
    expect(await screen.findByRole('heading', { name: /log\s*in|connexion/i })).toBeInTheDocument();

    // ...and the DocumentAdapterPage did NOT mount, so its on-mount service
    // calls never fired.
    expect(mockedListDocuments).not.toHaveBeenCalled();
    expect(mockedGetProviders).not.toHaveBeenCalled();
  });
});
