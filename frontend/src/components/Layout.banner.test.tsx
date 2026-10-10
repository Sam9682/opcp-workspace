import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Layout } from './Layout';
import { LanguageProvider } from '../hooks/useLanguage';
import { authService } from '../services/authService';

// Example / edge-case DOM tests for the shared top-banner "OPCP" link wiring.
// Follows the Layout.prereq.test.tsx pattern: seed localStorage before render,
// render Layout inside MemoryRouter. Auth is read at render time via
// authService.isAuthenticated() (!!localStorage 'access_token'); the displayed
// identifier is read via authService.getCurrentUser() (localStorage 'user').
//
// The OPCP brand label lives in a single <Link to="/"> at the top of the shared
// <nav>. That one element covers both the desktop and mobile presentations, so
// the same computed label must be visible for both. We assert on it directly
// (desktop presentation, always rendered) and again with the mobile menu open
// (mobile presentation state).
//
// Validates: Requirements 3.1, 4.2

function renderLayout() {
  // Layout calls useTranslation(), so wrap it in a LanguageProvider.
  return render(
    <LanguageProvider>
      <MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter>
    </LanguageProvider>,
  );
}

function authenticate() {
  localStorage.setItem('access_token', 'test-token');
}

function seedUser(user: Record<string, unknown>) {
  localStorage.setItem('user', JSON.stringify(user));
}

// Returns the single shared banner OPCP <Link to="/"> whose accessible name is
// exactly `label`. The banner brand link is distinguished from the "Accueil"
// link (which also targets "/") by its text content being the computed label.
function getBannerLink(label: string): HTMLAnchorElement {
  const link = screen.getByRole('link', { name: label }) as HTMLAnchorElement;
  expect(link.getAttribute('href')).toBe('/');
  return link;
}

beforeEach(() => {
  localStorage.clear();
  cleanup();
});

describe('Layout top-banner OPCP label wiring', () => {
  // (a) Authenticated with a non-empty email -> "OPCP (email)".
  describe('authenticated with an email', () => {
    const EMAIL = 'admin@opcp-psmc.com';
    const EXPECTED = `OPCP (${EMAIL})`;

    beforeEach(() => {
      authenticate();
      seedUser({
        id: '1',
        email: EMAIL,
        first_name: 'Ada',
        last_name: 'Lovelace',
        role: 'administrator',
        is_email_verified: true,
      });
    });

    it('renders the email label in the desktop banner presentation', () => {
      renderLayout();
      // The shared banner brand link is present with the email label.
      getBannerLink(EXPECTED);
      // The plain "OPCP" label must NOT appear as the brand link.
      expect(screen.queryByRole('link', { name: 'OPCP' })).toBeNull();
    });

    it('renders the same email label with the mobile menu open (mobile presentation)', async () => {
      const user = userEvent.setup();
      renderLayout();
      // Open the mobile menu; the shared banner brand link is unchanged.
      await user.click(screen.getByLabelText('Menu'));
      getBannerLink(EXPECTED);
    });
  });

  // (b) Authenticated with an empty email but non-empty names -> "OPCP (First Last)".
  describe('authenticated with empty email and names', () => {
    const EXPECTED = 'OPCP (Grace Hopper)';

    beforeEach(() => {
      authenticate();
      seedUser({
        id: '2',
        email: '',
        first_name: 'Grace',
        last_name: 'Hopper',
        role: 'member',
        is_email_verified: false,
      });
    });

    it('renders the full-name label in the desktop banner presentation', () => {
      renderLayout();
      getBannerLink(EXPECTED);
      expect(screen.queryByRole('link', { name: 'OPCP' })).toBeNull();
    });

    it('renders the same full-name label with the mobile menu open (mobile presentation)', async () => {
      const user = userEvent.setup();
      renderLayout();
      await user.click(screen.getByLabelText('Menu'));
      getBannerLink(EXPECTED);
    });
  });

  // (c) Unauthenticated -> plain "OPCP".
  describe('unauthenticated', () => {
    it('renders plain "OPCP" in the desktop banner presentation', () => {
      // localStorage cleared in beforeEach: no access_token, no user.
      renderLayout();
      getBannerLink('OPCP');
      // No parenthesised identifier should be present anywhere in the banner.
      expect(screen.queryByText(/OPCP \(/)).toBeNull();
    });

    it('renders the same plain "OPCP" with the mobile menu open (mobile presentation)', async () => {
      const user = userEvent.setup();
      renderLayout();
      await user.click(screen.getByLabelText('Menu'));
      getBannerLink('OPCP');
      expect(screen.queryByText(/OPCP \(/)).toBeNull();
    });
  });

  // Requirement 4.2 edge case: cleared localStorage -> getCurrentUser() returns
  // null and the banner shows plain "OPCP".
  describe('cleared localStorage', () => {
    it('getCurrentUser() returns null and the banner shows plain "OPCP"', () => {
      // beforeEach already cleared localStorage.
      expect(authService.getCurrentUser()).toBeNull();

      renderLayout();
      getBannerLink('OPCP');
    });
  });
});
