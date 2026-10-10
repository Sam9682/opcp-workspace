import { useState } from 'react';
import { authService } from '../services/authService';
import { validateEmail } from '../utils/validation';
import { useTranslation } from '../hooks/useLanguage';

export const ForgotPasswordPage = () => {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess(false);

    if (!validateEmail(email)) {
      setError(t('page.forgotPassword.error.invalidEmail'));
      return;
    }

    setLoading(true);
    try {
      await authService.requestPasswordReset(email);
      setSuccess(true);
    } catch (err: any) {
      setError(t('page.forgotPassword.error.generic'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center py-12 px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-6">
          <h2 className="text-3xl font-bold text-[#000E9C]">{t('page.forgotPassword.title')}</h2>
          <p className="mt-1 text-sm text-gray-600">{t('page.forgotPassword.subtitle')}</p>
        </div>
        <div className="card p-8">
          {success ? (
            <div className="text-center space-y-4">
              <div className="rounded bg-green-50 border border-green-200 p-4">
                <p className="text-sm text-green-800">
                  {t('page.forgotPassword.success')}
                </p>
              </div>
              <a href="/login" className="text-sm font-medium text-[#4949FF] hover:underline">
                {t('page.forgotPassword.backToLogin')}
              </a>
            </div>
          ) : (
            <form className="space-y-5" onSubmit={handleSubmit}>
              {error && (
                <div className="rounded bg-red-50 border border-red-200 p-3">
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                  {t('page.forgotPassword.field.email')}
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

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 text-sm font-semibold rounded text-white bg-[#000E9C] hover:bg-[#4949FF] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#4949FF] disabled:opacity-50 transition-colors"
              >
                {loading ? t('page.forgotPassword.submitting') : t('page.forgotPassword.submit')}
              </button>

              <div className="text-center">
                <a href="/login" className="text-sm font-medium text-[#4949FF] hover:underline">
                  {t('page.forgotPassword.backToLogin')}
                </a>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
