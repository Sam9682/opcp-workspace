/**
 * Bug condition exploration test — Property 1: Bug Condition, NAVIGATE edge case.
 * Spec: .kiro/specs/tasks-menu-not-displayed
 *
 * CRITICAL: This assertion encodes the EXPECTED (fixed) behavior. It MUST FAIL
 * on the current (unfixed) code — that failure confirms there is no
 * /admin/tasks route wired into the App route table (no <Route> and no
 * AdminTasksPage import), so navigating there renders nothing under the Layout.
 * It will PASS once the fix registers /admin/tasks -> AdminTasksPage under
 * ProtectedRoute, exactly like /admin/events -> AdminEventsPage.
 *
 * Validates: Requirement 1.5
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import App from './App';

const TOKEN_KEY = 'access_token';
const ROLE_KEY = 'user_role';
const USER_KEY = 'user';

function signInAsAdmin() {
  localStorage.setItem(TOKEN_KEY, 'test-token');
  localStorage.setItem(ROLE_KEY, 'administrator');
  localStorage.setItem(
    USER_KEY,
    JSON.stringify({ id: '1', email: 'admin@opcp.test', first_name: 'Ad', last_name: 'Min', role: 'administrator' }),
  );
}

beforeEach(() => {
  localStorage.clear();
  // App uses BrowserRouter; drive the initial location via the history API.
  window.history.pushState({}, '', '/admin/tasks');
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  window.history.pushState({}, '', '/');
});

describe('Bug Condition — NAVIGATE: /admin/tasks resolves to the Tasks admin page', () => {
  it('renders the Tasks admin page under ProtectedRoute at /admin/tasks', async () => {
    signInAsAdmin();
    render(<App />);

    // On the fixed code the Tasks admin page renders (and the auth guard, being
    // satisfied for an admin, does not redirect to /login). We assert the route
    // resolved to a real page rather than falling through to nothing: the app
    // must NOT have redirected to the login screen, and some Tasks-admin content
    // must be present.
    expect(window.location.pathname).toBe('/admin/tasks');

    // A defined /admin/tasks route renders task-admin content. On unfixed code
    // no route matches, so no such element exists and this assertion fails.
    const heading = await screen.findByRole(
      'heading',
      { name: /t[aâ]ches|tasks/i },
      { timeout: 3000 },
    );
    expect(heading).toBeInTheDocument();
  });
});
