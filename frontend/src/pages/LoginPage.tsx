import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService, isLogin2FAChallenge } from '../services/authService';
import { validateEmail } from '../utils/validation';
import { useTranslation } from '../hooks/useLanguage';

export const LoginPage = () => {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  // When set, the primary credentials were validated but a second 2FA step is required.
  const [challengeToken, setChallengeToken] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const navigate = useNavigate();

  // How long an error message stays on screen before auto-dismissing (ms).
  const ERROR_VISIBLE_MS = 6000;
  const errorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Show an error and keep it visible long enough for the user to read it.
  const showError = (message: string) => {
    if (errorTimerRef.current) {
      clearTimeout(errorTimerRef.current);
    }
    setError(message);
    errorTimerRef.current = setTimeout(() => {
      setError('');
      errorTimerRef.current = null;
    }, ERROR_VISIBLE_MS);
  };

  const clearError = () => {
    if (errorTimerRef.current) {
      clearTimeout(errorTimerRef.current);
      errorTimerRef.current = null;
    }
    setError('');
  };

  // Clean up any pending timer on unmount.
  useEffect(() => {
    return () => {
      if (errorTimerRef.current) {
        clearTimeout(errorTimerRef.current);
      }
    };
  }, []);

  // Build a user-facing message from a thrown request error. A missing
  // `response` means the request never reached the server (network down,
  // DNS failure, timeout, CORS), i.e. the connection could not be established.
  const resolveLoginError = (err: any): string => {
    if (!err?.response) {
      return t('page.login.error.connection');
    }
    return (
      err.response?.data?.detail?.message
      || err.response?.data?.detail
      || err.response?.data?.error?.message
      || t('page.login.error.failed')
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    if (!validateEmail(email)) {
      showError(t('page.login.error.invalidEmail'));
      return;
    }

    setLoading(true);
    try {
      const result = await authService.login({ email, password });
      if (isLogin2FAChallenge(result)) {
        // Do not navigate: switch to the verification-code step.
        setChallengeToken(result.challenge_token);
        setCode('');
        return;
      }
      navigate('/');
    } catch (err: any) {
      console.error('Login error:', err);
      showError(resolveLoginError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    if (!challengeToken) {
      return;
    }

    setLoading(true);
    try {
      await authService.verifyLogin2fa(challengeToken, code.trim());
      navigate('/');
    } catch (err: any) {
      console.error('2FA verification error:', err);
      // A missing response means the server was unreachable; otherwise the
      // code was rejected.
      showError(err?.response ? t('page.login.error.invalidCode') : t('page.login.error.connection'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center py-12 px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-6">
          <h2 className="text-3xl font-bold text-[#000E9C]">{t('page.login.title')}</h2>
          <p className="mt-1 text-sm text-gray-600">
            {challengeToken ? t('page.login.subtitle.twoFactor') : t('page.login.subtitle.default')}
          </p>
        </div>
        <div className="card p-8">
          {challengeToken ? (
            <form className="space-y-5" onSubmit={handleVerifySubmit}>
              {error && (
                <div role="alert" aria-live="assertive" className="rounded bg-red-100 border border-red-400 p-3">
                  <p className="text-sm font-semibold text-red-700">{error}</p>
                </div>
              )}
              <p className="text-sm text-gray-600">
                {t('page.login.twoFactor.instruction')}
              </p>
              <div>
                <label htmlFor="code" className="block text-sm font-medium text-gray-700 mb-1">
                  {t('page.login.field.code')}
                </label>
                <input
                  id="code"
                  name="code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  required
                  className="w-full px-3 py-2.5 border border-gray-300 text-gray-900 rounded focus:outline-none focus:ring-2 focus:ring-[#4949FF] focus:border-transparent transition-all text-sm"
                  placeholder="123456"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 text-sm font-semibold rounded text-white bg-[#000E9C] hover:bg-[#4949FF] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#4949FF] disabled:opacity-50 transition-colors"
              >
                {loading ? t('page.login.submitting.verify') : t('page.login.submit.verify')}
              </button>

              <button
                type="button"
                onClick={() => {
                  setChallengeToken(null);
                  setCode('');
                  clearError();
                }}
                className="w-full text-sm text-[#4949FF] hover:underline"
              >
                {t('page.login.back')}
              </button>
            </form>
          ) : (
            <form className="space-y-5" onSubmit={handleSubmit}>
              {error && (
                <div role="alert" aria-live="assertive" className="rounded bg-red-100 border border-red-400 p-3">
                  <p className="text-sm font-semibold text-red-700">{error}</p>
                </div>
              )}
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                  {t('page.login.field.email')}
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  className="w-full px-3 py-2.5 border border-gray-300 text-gray-900 rounded focus:outline-none focus:ring-2 focus:ring-[#4949FF] focus:border-transparent transition-all text-sm"
                  placeholder="votre@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                  {t('page.login.field.password')}
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  className="w-full px-3 py-2.5 border border-gray-300 text-gray-900 rounded focus:outline-none focus:ring-2 focus:ring-[#4949FF] focus:border-transparent transition-all text-sm"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 text-sm font-semibold rounded text-white bg-[#000E9C] hover:bg-[#4949FF] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#4949FF] disabled:opacity-50 transition-colors"
              >
                {loading ? t('page.login.submitting') : t('page.login.submit')}
              </button>
            </form>
          )}
          {!challengeToken && (
            <div className="mt-5 space-y-2 text-center">
              <a href="/forgot-password" className="text-sm text-[#4949FF] hover:underline">
                {t('page.login.forgotPassword')}
              </a>
              <p className="text-sm text-gray-600">
                {t('page.login.notMember')}{' '}
                <a href="/register" className="font-medium text-[#4949FF] hover:underline">
                  {t('page.login.registerHere')}
                </a>
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
