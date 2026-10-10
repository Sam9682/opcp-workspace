import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SecurityPage } from './SecurityPage';
import { securityService } from '../services/securityService';
import { authService } from '../services/authService';
import { LanguageProvider } from '../hooks/useLanguage';

// SecurityPage consumes the translation context, so it must render inside a
// LanguageProvider. The default Active_Language is French, so the existing
// French-text assertions in this file continue to hold.
function renderPage() {
  return render(
    <LanguageProvider>
      <SecurityPage />
    </LanguageProvider>,
  );
}

// securityService is the persistence path for 2FA status and management.
// Mock it so status loads resolve/reject deterministically with no network.
vi.mock('../services/securityService', () => ({
  securityService: {
    changePassword: vi.fn(),
    getTwoFactorStatus: vi.fn(),
    startTotpSetup: vi.fn(),
    confirmTotp: vi.fn(),
    disableTotp: vi.fn(),
    enableEmail2fa: vi.fn(),
    disableEmail2fa: vi.fn(),
  },
}));

// authService.requestPasswordReset drives the reset-by-email flow. Mock it so
// the invocation (and its email argument) is observable without a network call.
vi.mock('../services/authService', () => ({
  authService: {
    requestPasswordReset: vi.fn(),
  },
}));

const mockedSecurity = vi.mocked(securityService);
const mockedAuth = vi.mocked(authService);

const DISABLED_STATUS = { totp_enabled: false, email_2fa_enabled: false };

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  cleanup();
  // Default: status loads successfully with both methods disabled.
  mockedSecurity.getTwoFactorStatus.mockResolvedValue(DISABLED_STATUS);
  mockedAuth.requestPasswordReset.mockResolvedValue(undefined);
});

// Requirement 8.1 — the page requests the current 2FA configuration on mount.
describe('2FA status fetch on mount (Req 8.1)', () => {
  it('calls getTwoFactorStatus once when the page loads', async () => {
    renderPage();

    await waitFor(() => {
      expect(mockedSecurity.getTwoFactorStatus).toHaveBeenCalledTimes(1);
    });
  });
});

// Requirement 8.3 — a failed status request shows the French error banner.
describe('2FA status error banner (Req 8.3)', () => {
  it('shows "Impossible de charger le statut 2FA." when the status request fails', async () => {
    mockedSecurity.getTwoFactorStatus.mockRejectedValue(new Error('network down'));

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Impossible de charger le statut 2FA.')).toBeInTheDocument();
    });
  });
});

// Requirements 2.4, 3.1, 5.2 — password and 2FA sections render.
describe('password + 2FA section rendering (Req 2.4, 3.1, 5.2)', () => {
  it('renders current/new password inputs and the change-password submit (Req 3.1)', async () => {
    renderPage();

    // Password section inputs (Req 3.1) and submit control (Req 2.4).
    expect(screen.getByLabelText('Mot de passe actuel')).toBeInTheDocument();
    expect(screen.getByLabelText('Nouveau mot de passe')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Changer le Mot de Passe' })
    ).toBeInTheDocument();

    // Let the on-mount 2FA status fetch settle so state updates are flushed.
    await waitFor(() => {
      expect(mockedSecurity.getTwoFactorStatus).toHaveBeenCalled();
    });
  });

  it('renders the two-factor section with TOTP and email methods (Req 2.4, 5.2)', async () => {
    renderPage();

    // The 2FA section header renders (Req 2.4).
    expect(
      screen.getByRole('heading', { name: /Authentification à Deux Facteurs/i })
    ).toBeInTheDocument();

    // Once the status resolves, both method blocks render (Req 5.2 / 8.2).
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /Application Authenticator/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole('heading', { name: /Vérification par Email/i })
    ).toBeInTheDocument();
  });
});

// Requirement 4.2 — reset-by-email invokes the Password_Reset_Flow for the
// current user's registered email address (read from localStorage `user`).
describe('reset-by-email invocation (Req 4.2)', () => {
  it('calls requestPasswordReset with the email from localStorage', async () => {
    const email = 'user@example.com';
    localStorage.setItem('user', JSON.stringify({ email }));

    const user = userEvent.setup();
    renderPage();

    await user.click(
      screen.getByRole('button', { name: /Réinitialiser par Email/i })
    );

    await waitFor(() => {
      expect(mockedAuth.requestPasswordReset).toHaveBeenCalledWith(email);
    });
    expect(mockedAuth.requestPasswordReset).toHaveBeenCalledTimes(1);
  });

  it('does not call requestPasswordReset when no email is stored', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      screen.getByRole('button', { name: /Réinitialiser par Email/i })
    );

    // A French error banner appears and the reset flow is not invoked.
    expect(
      await screen.findByText('Adresse email introuvable. Veuillez vous reconnecter.')
    ).toBeInTheDocument();
    expect(mockedAuth.requestPasswordReset).not.toHaveBeenCalled();
  });
});
