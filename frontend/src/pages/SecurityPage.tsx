import { useEffect, useState } from 'react';
import { securityService, type TwoFactorStatus, type TotpSetup } from '../services/securityService';
import { authService } from '../services/authService';
import { useTranslation } from '../hooks/useLanguage';

/** Read the current user's email from the persisted session in localStorage. */
function getCurrentUserEmail(): string {
  try {
    const raw = localStorage.getItem('user');
    if (!raw) return '';
    const parsed = JSON.parse(raw);
    return typeof parsed?.email === 'string' ? parsed.email : '';
  } catch {
    return '';
  }
}

/** Extract a human-readable message from an Axios-style error, falling back to a French default. */
function extractError(err: any, fallback: string): string {
  return (
    err?.response?.data?.detail?.error?.message ||
    err?.response?.data?.detail ||
    err?.response?.data?.message ||
    fallback
  );
}

const inputClass =
  'w-full px-3 py-2.5 border border-gray-300 text-gray-900 rounded focus:outline-none focus:ring-2 focus:ring-[#4949FF] focus:border-transparent transition-all text-sm';
const primaryButtonClass =
  'w-full py-2.5 text-sm font-semibold rounded text-white bg-[#000E9C] hover:bg-[#4949FF] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#4949FF] disabled:opacity-50 transition-colors';
const secondaryButtonClass =
  'w-full py-2.5 text-sm font-semibold rounded text-[#000E9C] bg-white border border-[#000E9C] hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#4949FF] disabled:opacity-50 transition-colors';

function SuccessBanner({ message }: { message: string }) {
  return (
    <div className="rounded bg-green-50 border border-green-200 p-3" role="status">
      <p className="text-sm text-green-800">{message}</p>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded bg-red-50 border border-red-200 p-3" role="alert">
      <p className="text-sm text-red-800">{message}</p>
    </div>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  const { t } = useTranslation();
  return active ? (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
      {t('page.security.status.enabled')}
    </span>
  ) : (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
      {t('page.security.status.disabled')}
    </span>
  );
}

function PasswordSection() {
  const { t } = useTranslation();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const [resetError, setResetError] = useState('');
  const [resetSuccess, setResetSuccess] = useState('');
  const [resetLoading, setResetLoading] = useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      await securityService.changePassword(currentPassword, newPassword);
      setSuccess(t('page.security.password.success'));
      setCurrentPassword('');
      setNewPassword('');
    } catch (err: any) {
      setError(extractError(err, t('page.security.password.error.change')));
    } finally {
      setLoading(false);
    }
  };

  const handleResetByEmail = async () => {
    setResetError('');
    setResetSuccess('');
    const email = getCurrentUserEmail();
    if (!email) {
      setResetError(t('page.security.password.error.noEmail'));
      return;
    }
    setResetLoading(true);
    try {
      await authService.requestPasswordReset(email);
      setResetSuccess(t('page.security.password.reset.success'));
    } catch (err: any) {
      setResetError(extractError(err, t('page.security.password.reset.error')));
    } finally {
      setResetLoading(false);
    }
  };

  return (
    <section className="card p-6 sm:p-8">
      <h3 className="text-xl font-bold text-[#000E9C] mb-1">{t('page.security.password.title')}</h3>
      <p className="text-sm text-gray-600 mb-5">
        {t('page.security.password.subtitle')}
      </p>

      <form className="space-y-4" onSubmit={handleChangePassword}>
        {error && <ErrorBanner message={error} />}
        {success && <SuccessBanner message={success} />}

        <div>
          <label htmlFor="current-password" className="block text-sm font-medium text-gray-700 mb-1">
            {t('page.security.password.current')}
          </label>
          <input
            id="current-password"
            name="current-password"
            type="password"
            autoComplete="current-password"
            required
            className={inputClass}
            placeholder="••••••••"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
          />
        </div>

        <div>
          <label htmlFor="new-password" className="block text-sm font-medium text-gray-700 mb-1">
            {t('page.security.password.new')}
          </label>
          <input
            id="new-password"
            name="new-password"
            type="password"
            autoComplete="new-password"
            required
            className={inputClass}
            placeholder="••••••••"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
          <p className="mt-1 text-xs text-gray-500">
            {t('page.security.password.hint')}
          </p>
        </div>

        <button type="submit" disabled={loading} className={primaryButtonClass}>
          {loading ? t('page.security.password.submitting') : t('page.security.password.submit')}
        </button>
      </form>

      <div className="mt-6 pt-6 border-t border-gray-200 space-y-3">
        {resetError && <ErrorBanner message={resetError} />}
        {resetSuccess && <SuccessBanner message={resetSuccess} />}
        <p className="text-sm text-gray-600">
          {t('page.security.password.resetPrompt')}
        </p>
        <button
          type="button"
          onClick={handleResetByEmail}
          disabled={resetLoading}
          className={secondaryButtonClass}
        >
          {resetLoading ? t('page.security.password.resetSubmitting') : t('page.security.password.resetSubmit')}
        </button>
      </div>
    </section>
  );
}

function TwoFactorSection() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<TwoFactorStatus | null>(null);
  const [statusError, setStatusError] = useState('');
  const [statusLoading, setStatusLoading] = useState(true);

  // TOTP setup flow state
  const [totpSetup, setTotpSetup] = useState<TotpSetup | null>(null);
  const [totpCode, setTotpCode] = useState('');
  const [totpError, setTotpError] = useState('');
  const [totpSuccess, setTotpSuccess] = useState('');
  const [totpBusy, setTotpBusy] = useState(false);

  // Email 2FA state
  const [emailError, setEmailError] = useState('');
  const [emailSuccess, setEmailSuccess] = useState('');
  const [emailBusy, setEmailBusy] = useState(false);

  const loadStatus = async () => {
    setStatusLoading(true);
    setStatusError('');
    try {
      const result = await securityService.getTwoFactorStatus();
      setStatus(result);
    } catch {
      setStatusError(t('page.security.twoFactor.statusError'));
    } finally {
      setStatusLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleStartTotpSetup = async () => {
    setTotpError('');
    setTotpSuccess('');
    setTotpBusy(true);
    try {
      const setup = await securityService.startTotpSetup();
      setTotpSetup(setup);
    } catch (err: any) {
      setTotpError(extractError(err, t('page.security.totp.error.start')));
    } finally {
      setTotpBusy(false);
    }
  };

  const handleConfirmTotp = async (e: React.FormEvent) => {
    e.preventDefault();
    setTotpError('');
    setTotpSuccess('');
    setTotpBusy(true);
    try {
      await securityService.confirmTotp(totpCode.trim());
      setTotpSuccess(t('page.security.totp.success.enabled'));
      setTotpSetup(null);
      setTotpCode('');
      await loadStatus();
    } catch (err: any) {
      setTotpError(extractError(err, t('page.security.totp.error.invalidCode')));
    } finally {
      setTotpBusy(false);
    }
  };

  const handleDisableTotp = async () => {
    setTotpError('');
    setTotpSuccess('');
    setTotpBusy(true);
    try {
      await securityService.disableTotp();
      setTotpSuccess(t('page.security.totp.success.disabled'));
      await loadStatus();
    } catch (err: any) {
      setTotpError(extractError(err, t('page.security.totp.error.disable')));
    } finally {
      setTotpBusy(false);
    }
  };

  const handleToggleEmail2fa = async () => {
    setEmailError('');
    setEmailSuccess('');
    setEmailBusy(true);
    const enabling = !status?.email_2fa_enabled;
    try {
      if (enabling) {
        await securityService.enableEmail2fa();
        setEmailSuccess(t('page.security.email2fa.success.enabled'));
      } else {
        await securityService.disableEmail2fa();
        setEmailSuccess(t('page.security.email2fa.success.disabled'));
      }
      await loadStatus();
    } catch (err: any) {
      setEmailError(
        extractError(
          err,
          enabling
            ? t('page.security.email2fa.error.enable')
            : t('page.security.email2fa.error.disable')
        )
      );
    } finally {
      setEmailBusy(false);
    }
  };

  const cancelTotpSetup = () => {
    setTotpSetup(null);
    setTotpCode('');
    setTotpError('');
  };

  return (
    <section className="card p-6 sm:p-8">
      <h3 className="text-xl font-bold text-[#000E9C] mb-1">
        {t('page.security.twoFactor.title')}
      </h3>
      <p className="text-sm text-gray-600 mb-5">
        {t('page.security.twoFactor.subtitle')}
      </p>

      {statusError && <ErrorBanner message={statusError} />}
      {statusLoading && <p className="text-sm text-gray-500">{t('page.security.twoFactor.statusLoading')}</p>}

      {!statusLoading && !statusError && status && (
        <div className="space-y-6">
          {/* TOTP method */}
          <div className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="text-base font-semibold text-gray-900">
                  {t('page.security.totp.title')}
                </h4>
                <p className="mt-1 text-sm text-gray-600">
                  {t('page.security.totp.description')}
                </p>
              </div>
              <StatusBadge active={status.totp_enabled} />
            </div>

            <div className="mt-4 space-y-3">
              {totpError && <ErrorBanner message={totpError} />}
              {totpSuccess && <SuccessBanner message={totpSuccess} />}

              {status.totp_enabled ? (
                <button
                  type="button"
                  onClick={handleDisableTotp}
                  disabled={totpBusy}
                  className={secondaryButtonClass}
                >
                  {totpBusy ? t('page.security.totp.processing') : t('page.security.totp.disable')}
                </button>
              ) : totpSetup ? (
                <div className="space-y-4">
                  <div className="rounded bg-blue-50 border border-blue-200 p-4 space-y-3">
                    <p className="text-sm text-gray-700">
                      {t('page.security.totp.setupInstruction')}
                    </p>
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">
                        {t('page.security.totp.secretLabel')}
                      </p>
                      <code className="block w-full break-all rounded bg-white border border-gray-200 px-3 py-2 text-sm font-mono text-gray-900">
                        {totpSetup.secret}
                      </code>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">{t('page.security.totp.uriLabel')}</p>
                      <code className="block w-full break-all rounded bg-white border border-gray-200 px-3 py-2 text-xs font-mono text-gray-700">
                        {totpSetup.otpauth_uri}
                      </code>
                      <p className="mt-1 text-xs text-gray-500">
                        {t('page.security.totp.uriHint')}
                      </p>
                    </div>
                  </div>

                  <form className="space-y-3" onSubmit={handleConfirmTotp}>
                    <div>
                      <label htmlFor="totp-code" className="block text-sm font-medium text-gray-700 mb-1">
                        {t('page.security.totp.codeLabel')}
                      </label>
                      <input
                        id="totp-code"
                        name="totp-code"
                        type="text"
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        required
                        className={inputClass}
                        placeholder="123456"
                        value={totpCode}
                        onChange={(e) => setTotpCode(e.target.value)}
                      />
                    </div>
                    <div className="flex gap-3">
                      <button type="submit" disabled={totpBusy} className={primaryButtonClass}>
                        {totpBusy ? t('page.security.totp.verifying') : t('page.security.totp.confirm')}
                      </button>
                      <button
                        type="button"
                        onClick={cancelTotpSetup}
                        disabled={totpBusy}
                        className={secondaryButtonClass}
                      >
                        {t('page.security.totp.cancel')}
                      </button>
                    </div>
                  </form>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={handleStartTotpSetup}
                  disabled={totpBusy}
                  className={primaryButtonClass}
                >
                  {totpBusy ? t('page.security.totp.loading') : t('page.security.totp.setup')}
                </button>
              )}
            </div>
          </div>

          {/* Email 2FA method */}
          <div className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="text-base font-semibold text-gray-900">{t('page.security.email2fa.title')}</h4>
                <p className="mt-1 text-sm text-gray-600">
                  {t('page.security.email2fa.description')}
                </p>
              </div>
              <StatusBadge active={status.email_2fa_enabled} />
            </div>

            <div className="mt-4 space-y-3">
              {emailError && <ErrorBanner message={emailError} />}
              {emailSuccess && <SuccessBanner message={emailSuccess} />}

              <button
                type="button"
                onClick={handleToggleEmail2fa}
                disabled={emailBusy}
                className={status.email_2fa_enabled ? secondaryButtonClass : primaryButtonClass}
              >
                {emailBusy
                  ? t('page.security.email2fa.processing')
                  : status.email_2fa_enabled
                  ? t('page.security.email2fa.disable')
                  : t('page.security.email2fa.enable')}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function SecurityPage() {
  const { t } = useTranslation();
  return (
    <div className="max-w-2xl mx-auto py-8 px-4 space-y-6">
      <div>
        <h2 className="text-3xl font-bold text-[#000E9C]">{t('page.security.title')}</h2>
        <p className="mt-1 text-sm text-gray-600">
          {t('page.security.subtitle')}
        </p>
      </div>

      <PasswordSection />
      <TwoFactorSection />
    </div>
  );
}

export { SecurityPage };
export default SecurityPage;
