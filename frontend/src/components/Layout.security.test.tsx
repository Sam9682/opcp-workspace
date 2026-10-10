import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Layout } from './Layout';
import { LanguageProvider } from '../hooks/useLanguage';

// Accessible name of the icon-only desktop control and the mobile menu label.
const SECURITY_LABEL = 'Sécurité du compte';
const SECURITY_ROUTE = '/account/security';

// Layout uses <Link>, so it must render inside a Router. Auth is read at render
// time via authService.isAuthenticated() (!!localStorage 'access_token'). We
// drive auth by seeding localStorage before render, matching Layout.prereq.test.
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

beforeEach(() => {
  localStorage.clear();
  cleanup();
});

// Header_Security_Link rendering + navigation target.
// Validates: Requirements 1.1, 1.2, 1.4
describe('Header_Security_Link', () => {
  describe('when authenticated', () => {
    it('renders the desktop icon-only link with aria-label targeting /account/security (1.1, 1.4)', () => {
      authenticate();
      renderLayout();

      // The desktop control is icon-only, so it is discoverable by its
      // accessible name (aria-label) and must navigate to the security route.
      const links = screen.getAllByRole('link', {
        name: SECURITY_LABEL,
      }) as HTMLAnchorElement[];

      // Desktop (icon) + mobile (labeled) entries share the same accessible
      // name; at least the desktop one exists and points at the route.
      expect(links.length).toBeGreaterThan(0);
      expect(links.every((l) => l.getAttribute('href') === SECURITY_ROUTE)).toBe(true);
    });

    it('renders a labeled "Sécurité du compte" entry in the mobile menu targeting the route (1.2, 1.4)', async () => {
      const user = userEvent.setup();
      authenticate();
      renderLayout();

      // The mobile entry renders only once the mobile menu is open.
      await user.click(screen.getByLabelText('Menu'));

      const links = screen.getAllByRole('link', {
        name: SECURITY_LABEL,
      }) as HTMLAnchorElement[];

      // A mobile entry carrying the visible label exists and targets the route.
      expect(links.length).toBeGreaterThan(0);
      expect(links.some((l) => l.textContent?.trim() === SECURITY_LABEL)).toBe(true);
      expect(links.every((l) => l.getAttribute('href') === SECURITY_ROUTE)).toBe(true);
    });
  });

  describe('when not authenticated', () => {
    it('does not render the security link in the desktop header', () => {
      // localStorage cleared in beforeEach: not authenticated.
      renderLayout();

      expect(screen.queryByRole('link', { name: SECURITY_LABEL })).toBeNull();
    });

    it('does not render the security link in the mobile menu even when opened', async () => {
      const user = userEvent.setup();
      renderLayout();

      await user.click(screen.getByLabelText('Menu'));

      expect(screen.queryByRole('link', { name: SECURITY_LABEL })).toBeNull();
    });
  });
});
