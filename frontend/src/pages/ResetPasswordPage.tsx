import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authService } from '../services/authService';
import { useTranslation } from '../hooks/useLanguage';

export const ResetPasswordPage = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const token = searchParams.get('token');

  useEffect(() => {
    if (!token) {
      setError(t('page.resetPassword.error.invalidLink'));
    }
  }, [token, t]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!token) {
      setError(t('page.resetPassword.error.invalidLink'));
      return;
    }

    if (password.length < 8) {
      setError(t('page.resetPassword.error.minLength'));
      return;
    }

    if (!/[A-Z]/.test(password)) {
      setError(t('page.resetPassword.error.uppercase'));
      return;
    }

    if (!/[a-z]/.test(password)) {
      setError(t('page.resetPassword.error.lowercase'));
      return;
    }

    if (!/\d/.test(password)) {
      setError(t('page.resetPassword.error.digit'));
      return;
    }

    if (password !== confirmPassword) {
      setError(t('page.resetPassword.error.mismatch'));
      return;
    }

    setLoading(true);
    try {
      await authService.resetPassword(token, password);
      setSuccess(true);
      setTimeout(() => navigate('/login'), 3000);
    } catch (err: any) {
      const errorMessage = err.response?.data?.error?.message 
        || err.response?.data?.detail 
        || t('page.resetPassword.error.failed');
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center py-12 px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-6">
          <h2 className="text-3xl font-bold text-[#000E9C]">{t('page.resetPassword.title')}</h2>
          <p className="mt-1 text-sm text-gray-600">{t('page.resetPassword.subtitle')}</p>
        </div>
        <div className="card p-8">
          {success ? (
            <div className="text-center">
              <div className="rounded bg-green-50 border border-green-200 p-4">
                <p className="text-sm text-green-800">
                  {t('page.resetPassword.success.title')}
                </p>
                <p className="text-sm text-green-700 mt-1">
                  {t('page.resetPassword.success.redirect')}
                </p>
              </div>
            </div>
          ) : (
            <form className="space-y-5" onSubmit={handleSubmit}>
              {error && (
                <div className="rounded bg-red-50 border border-red-200 p-3">
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                  {t('page.resetPassword.field.newPassword')}
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
                <p className="mt-1 text-xs text-gray-500">
                  {t('page.resetPassword.password.hint')}
                </p>
              </div>
              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
                  {t('page.resetPassword.field.confirmPassword')}
                </label>
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  required
                  className="w-full px-3 py-2.5 border border-gray-300 text-gray-900 rounded focus:outline-none focus:ring-2 focus:ring-[#4949FF] focus:border-transparent transition-all text-sm"
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>

              <button
                type="submit"
                disabled={loading || !token}
                className="w-full py-2.5 text-sm font-semibold rounded text-white bg-[#000E9C] hover:bg-[#4949FF] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#4949FF] disabled:opacity-50 transition-colors"
              >
                {loading ? t('page.resetPassword.submitting') : t('page.resetPassword.submit')}
              </button>

              <div className="text-center">
                <a href="/login" className="text-sm font-medium text-[#4949FF] hover:underline">
                  {t('page.resetPassword.backToLogin')}
                </a>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
