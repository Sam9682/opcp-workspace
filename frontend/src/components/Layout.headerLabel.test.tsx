import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import fc from 'fast-check';
import { Layout, computeHeaderLabel } from './Layout';
import { LanguageProvider } from '../hooks/useLanguage';
import type { CurrentUser } from '../services/authService';

// Minimum property-test iterations mandated by the design (>= 100).
const NUM_RUNS = 100;

// Layout uses <Link>, so it must render inside a Router. The banner OPCP brand
// link is a <Link to="/"> whose visible text is the computed header label. We
// drive the user state by seeding localStorage['user'] before render, matching
// how authService.getCurrentUser() reads it.
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

// Reference implementation of the precedence rule, kept independent from the
// production code so the property genuinely checks behavior rather than echoing
// the same expression. Mirrors Requirements 1.1, 1.2, 2.1.
function expectedLabel(user: CurrentUser | null): string {
  if (!user) return 'OPCP';
  const email = (user.email ?? '').trim();
  if (email.length > 0) return `OPCP (${email})`;
  const fullName = `${(user.first_name ?? '').trim()} ${(user.last_name ?? '').trim()}`.trim();
  if (fullName.length > 0) return `OPCP (${fullName})`;
  return 'OPCP';
}

// Arbitrary producing the three interesting user states plus fully-random users:
//   - null (unauthenticated)                       -> "OPCP"
//   - user with a non-empty email                  -> "OPCP (email)"
//   - user with empty email but a non-empty name   -> "OPCP (First Last)"
//   - user with empty email and empty names        -> "OPCP"
//   - fully arbitrary user (covers whitespace/etc.) -> per precedence rule
// Fields such as email/first_name/last_name include empty and whitespace-only
// strings so the trim()/precedence guards are exercised across the input space.
const identifierString = fc.oneof(
  fc.constant(''),
  fc.constant('   '),
  fc.string(),
  fc.emailAddress(),
);

const userArb: fc.Arbitrary<CurrentUser> = fc.record({
  id: fc.string(),
  email: identifierString,
  first_name: identifierString,
  last_name: identifierString,
  role: fc.string(),
  is_email_verified: fc.boolean(),
});

const userStateArb: fc.Arbitrary<CurrentUser | null> = fc.oneof(
  fc.constant(null),
  userArb,
);

beforeEach(() => {
  localStorage.clear();
  cleanup();
});

// Property 1: Header label follows the identifier precedence rule.
// Feature: header-username-display, Property 1: For any current-user state,
// computeHeaderLabel (and the OPCP banner link that renders it) SHALL produce
// "OPCP (email)" when a non-empty email exists; otherwise "OPCP (First Last)"
// when the email is empty/absent but a non-empty full name exists; otherwise
// plain "OPCP".
// Validates: Requirements 1.1, 1.2, 2.1, 3.1
describe('Feature: header-username-display, Property 1: header label follows the identifier precedence rule', () => {
  it('computeHeaderLabel obeys email > full name > "OPCP" for any user state', () => {
    fc.assert(
      fc.property(userStateArb, (user) => {
        expect(computeHeaderLabel(user)).toBe(expectedLabel(user));
      }),
      { numRuns: NUM_RUNS },
    );
  });

  it('the rendered banner OPCP link text equals computeHeaderLabel(user)', () => {
    fc.assert(
      fc.property(userStateArb, (user) => {
        // Fresh DOM + storage per run so each rendered banner reflects only the
        // user state generated for this iteration.
        cleanup();
        localStorage.clear();
        if (user !== null) {
          localStorage.setItem('user', JSON.stringify(user));
        }

        renderLayout();

        const label = computeHeaderLabel(user);

        // The banner brand link is the single <Link to="/"> whose visible text
        // is the computed label. Locating it by that role+name proves the
        // rendered banner text equals computeHeaderLabel(user) (Requirement
        // 3.1: one label feeds the shared top banner covering desktop+mobile).
        const brandLink = screen.getByRole('link', { name: label });
        expect(brandLink.getAttribute('href')).toBe('/');
        expect(brandLink.textContent).toBe(label);
      }),
      { numRuns: NUM_RUNS },
    );
  });
});
