import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, cleanup, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Layout } from './Layout';
import { LanguageProvider } from '../hooks/useLanguage';

// Layout consumes useTranslation(), so it must render inside a LanguageProvider,
// and it uses <Link>, so it must render inside a Router. Auth is read at render
// time via authService (localStorage 'access_token' / 'user_role'); these tests
// exercise the language controls, which render regardless of auth, so we leave
// the store cleared (also anchoring the Active_Language to the French default).
function renderLayout() {
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

beforeEach(() => {
  localStorage.clear();
  cleanup();
});

// Both a desktop and a mobile Language control group exist. The desktop group is
// always in the DOM; the mobile group only renders once the mobile menu opens.
// jsdom ignores CSS, so `hidden sm:flex` elements are still present/queryable.

// Requirement 1.1, 1.2: EN and FR controls render in the Top_Banner.
describe('language controls render in the banner', () => {
  it('renders the desktop Language control group with both FR and EN controls', () => {
    renderLayout();

    // Exactly one Language group exists while the mobile menu is closed.
    const group = screen.getByRole('group', { name: 'Language' });
    expect(within(group).getByRole('button', { name: 'FR' })).toBeInTheDocument();
    expect(within(group).getByRole('button', { name: 'EN' })).toBeInTheDocument();
  });

  it('renders a second (mobile) Language control group with FR and EN once the mobile menu opens', async () => {
    const user = userEvent.setup();
    renderLayout();

    await user.click(screen.getByLabelText('Menu'));

    // Now both the desktop and mobile Language groups are present.
    const groups = screen.getAllByRole('group', { name: 'Language' });
    expect(groups).toHaveLength(2);
    for (const group of groups) {
      expect(within(group).getByRole('button', { name: 'FR' })).toBeInTheDocument();
      expect(within(group).getByRole('button', { name: 'EN' })).toBeInTheDocument();
    }
  });
});

// Requirement 1.5, 2.3: the active control reflects the Active_Language via
// aria-pressed, and the inactive one is not pressed, for each selected language.
describe('active control is indicated with aria-pressed', () => {
  it('marks FR pressed and EN not pressed at the French default', () => {
    renderLayout();

    const group = screen.getByRole('group', { name: 'Language' });
    const fr = within(group).getByRole('button', { name: 'FR' });
    const en = within(group).getByRole('button', { name: 'EN' });

    expect(fr).toHaveAttribute('aria-pressed', 'true');
    expect(en).toHaveAttribute('aria-pressed', 'false');
  });

  it('marks EN pressed and FR not pressed after selecting English', async () => {
    const user = userEvent.setup();
    renderLayout();

    const group = screen.getByRole('group', { name: 'Language' });
    await user.click(within(group).getByRole('button', { name: 'EN' }));

    // Re-query after the state change; the control group re-renders in place.
    const fr = within(group).getByRole('button', { name: 'FR' });
    const en = within(group).getByRole('button', { name: 'EN' });

    expect(en).toHaveAttribute('aria-pressed', 'true');
    expect(fr).toHaveAttribute('aria-pressed', 'false');
  });
});

// Requirement 2.3: switching the Active_Language re-renders consumer text in
// place, with no page reload. The desktop "Accueil"/"Home" nav link is a
// translated consumer (t('nav.home')); keeping the mobile menu closed makes it
// the sole match so the assertion is unambiguous.
describe('switching language re-renders consumer text without reload', () => {
  it('shows English nav text after clicking EN and French nav text after clicking FR', async () => {
    const user = userEvent.setup();
    renderLayout();

    // French default: the home nav link reads "Accueil".
    expect(screen.getByRole('link', { name: 'Accueil' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Home' })).toBeNull();

    // Select English: same component instance re-renders the consumer text.
    const group = screen.getByRole('group', { name: 'Language' });
    await user.click(within(group).getByRole('button', { name: 'EN' }));

    expect(screen.getByRole('link', { name: 'Home' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Accueil' })).toBeNull();

    // Switch back to French: the consumer text reverts in place.
    await user.click(within(group).getByRole('button', { name: 'FR' }));

    expect(screen.getByRole('link', { name: 'Accueil' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Home' })).toBeNull();
  });
});
