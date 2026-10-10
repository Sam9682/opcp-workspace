// Feature: account-security, Property 5: 2FA status rendering fidelity
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, within } from '@testing-library/react';
import fc from 'fast-check';
import { SecurityPage } from './SecurityPage';
import { LanguageProvider } from '../hooks/useLanguage';

// SecurityPage consumes the translation context, so it must render inside a
// LanguageProvider. The default Active_Language is French, so the existing
// French-label assertions in this file continue to hold.
function renderPage() {
  return render(
    <LanguageProvider>
      <SecurityPage />
    </LanguageProvider>,
  );
}

// SecurityPage reads the 2FA status exclusively through
// securityService.getTwoFactorStatus(). Mock the service so each case can inject
// an arbitrary (totp_enabled, email_2fa_enabled) combination with no network
// access. The other methods are stubbed but unused by these rendering assertions.
vi.mock('../services/securityService', () => ({
  securityService: {
    getTwoFactorStatus: vi.fn(),
    changePassword: vi.fn(),
    startTotpSetup: vi.fn(),
    confirmTotp: vi.fn(),
    disableTotp: vi.fn(),
    enableEmail2fa: vi.fn(),
    disableEmail2fa: vi.fn(),
  },
}));

// The password section calls authService.requestPasswordReset on demand only;
// it never fires during status rendering. Mock it so the page mounts cleanly.
vi.mock('../services/authService', () => ({
  authService: {
    requestPasswordReset: vi.fn(),
  },
}));

import { securityService } from '../services/securityService';

const mockedGetStatus = securityService.getTwoFactorStatus as unknown as ReturnType<typeof vi.fn>;

// The French labels rendered by StatusBadge for each state.
const ACTIVE_LABEL = '✅ Activé';
const INACTIVE_LABEL = '⚪ Désactivé';

// Method section headings, used to scope the badge lookup to the right method.
const TOTP_HEADING = /Application Authenticator \(TOTP\)/;
const EMAIL_HEADING = /Vérification par Email/;

// Return the enclosing method-card element for a heading, so we can assert the
// badge that belongs to that specific method rather than the other one (both
// methods reuse the same active/inactive labels).
function methodCardFor(headingMatcher: RegExp): HTMLElement {
  const heading = screen.getByRole('heading', { name: headingMatcher });
  // Heading -> text/badge flex row -> method card container.
  const card = heading.closest('div.border') as HTMLElement | null;
  expect(card).not.toBeNull();
  return card!;
}

function expectLabelInMethod(headingMatcher: RegExp, enabled: boolean) {
  const card = methodCardFor(headingMatcher);
  const scope = within(card);
  if (enabled) {
    expect(scope.getByText(ACTIVE_LABEL)).toBeInTheDocument();
    expect(scope.queryByText(INACTIVE_LABEL)).toBeNull();
  } else {
    expect(scope.getByText(INACTIVE_LABEL)).toBeInTheDocument();
    expect(scope.queryByText(ACTIVE_LABEL)).toBeNull();
  }
}

beforeEach(() => {
  cleanup();
  mockedGetStatus.mockReset();
  localStorage.clear();
});

// Property 5: 2FA status rendering fidelity
// Validates: Requirements 8.2
// For any combination of (totp_enabled, email_2fa_enabled) returned by the
// status endpoint, the security page renders the matching French active/inactive
// label for each method independently.
describe('Feature: account-security, Property 5: 2FA status rendering fidelity', () => {
  it('renders the matching French label for TOTP and Email 2FA across all combinations', async () => {
    await fc.assert(
      fc.asyncProperty(fc.boolean(), fc.boolean(), async (totp, email) => {
        cleanup();
        mockedGetStatus.mockReset();
        mockedGetStatus.mockResolvedValue({ totp_enabled: totp, email_2fa_enabled: email });

        renderPage();

        // Wait for the async status fetch to resolve and the method cards to render.
        await waitFor(() => {
          expect(screen.getByRole('heading', { name: TOTP_HEADING })).toBeInTheDocument();
        });

        // Each method independently reflects its own flag.
        expectLabelInMethod(TOTP_HEADING, totp);
        expectLabelInMethod(EMAIL_HEADING, email);
      }),
      { numRuns: 100 },
    );
  });

  // Explicit table over all four combinations, complementing the property above
  // with named, easy-to-read cases.
  const combinations: Array<{ totp: boolean; email: boolean }> = [
    { totp: false, email: false },
    { totp: true, email: false },
    { totp: false, email: true },
    { totp: true, email: true },
  ];

  it.each(combinations)(
    'renders correct labels for totp=%s',
    async ({ totp, email }) => {
      mockedGetStatus.mockResolvedValue({ totp_enabled: totp, email_2fa_enabled: email });

      renderPage();

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: TOTP_HEADING })).toBeInTheDocument();
      });

      expectLabelInMethod(TOTP_HEADING, totp);
      expectLabelInMethod(EMAIL_HEADING, email);
    },
  );
});
