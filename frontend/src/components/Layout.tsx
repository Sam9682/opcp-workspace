import type { ReactNode } from 'react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { authService } from '../services/authService';
import type { CurrentUser } from '../services/authService';
import { PREREQ_NAV_ITEMS } from './prerequisites/types';
import { useTranslation } from '../hooks/useLanguage';

interface LayoutProps {
  children: ReactNode;
}

/**
 * Pure precedence rule for the shared top banner "OPCP" label:
 *   email present (non-empty, trimmed) -> "OPCP (email)"        (Requirement 1.1)
 *   else full name present             -> "OPCP (First Last)"   (Requirement 1.2)
 *   else / no user                     -> "OPCP"                (Requirement 2.1)
 * Missing/empty fields are guarded with `??` and `.trim()` so an empty user
 * renders "OPCP" rather than "OPCP ()".
 */
export function computeHeaderLabel(user: CurrentUser | null): string {
  if (!user) {
    return 'OPCP'; // Requirement 2.1
  }

  const email = (user.email ?? '').trim();
  if (email.length > 0) {
    return `OPCP (${email})`; // Requirement 1.1
  }

  const fullName = `${(user.first_name ?? '').trim()} ${(user.last_name ?? '').trim()}`.trim();
  if (fullName.length > 0) {
    return `OPCP (${fullName})`; // Requirement 1.2
  }

  return 'OPCP'; // fallback: no usable identifier
}

export const Layout = ({ children }: LayoutProps) => {
  const isAuthenticated = authService.isAuthenticated();
  const isAdmin = authService.isAdmin();
  const headerLabel = computeHeaderLabel(authService.getCurrentUser());
  const { language, setLanguage, t } = useTranslation();
  const [showEventsMenu, setShowEventsMenu] = useState(false);
  const [showTasksMenu, setShowTasksMenu] = useState(false);
  const [showPrereqMenu, setShowPrereqMenu] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = async () => {
    try {
      await authService.logout();
      window.location.href = '/';
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <nav className="sticky top-0 z-50 bg-[#000E9C] text-white h-14 flex items-center px-4 sm:px-6">
        <div className="max-w-7xl w-full mx-auto flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link to="/" className="text-lg font-bold text-white hover:no-underline">
              {headerLabel}
            </Link>
            {/* Desktop Menu */}
            <div className="hidden sm:flex items-center gap-1">
              <Link to="/" className="px-3 py-1.5 text-sm font-medium text-white/90 hover:text-white hover:bg-white/10 rounded transition-colors hover:no-underline">
                {t('nav.home')}
              </Link>
              {isAuthenticated && (
                <>
                  <Link to="/forum" className="px-3 py-1.5 text-sm font-medium text-white/90 hover:text-white hover:bg-white/10 rounded transition-colors hover:no-underline">
                    {t('nav.forum')}
                  </Link>
                  <div className="relative" onMouseEnter={() => setShowEventsMenu(true)} onMouseLeave={() => setShowEventsMenu(false)}>
                    <Link to="/events" className="px-3 py-1.5 text-sm font-medium text-white/90 hover:text-white hover:bg-white/10 rounded transition-colors hover:no-underline">
                      {t('nav.events')} {isAdmin && <span className="ml-0.5 text-xs">▾</span>}
                    </Link>
                    {isAdmin && showEventsMenu && (
                      <div className="absolute top-full left-0 mt-1 w-48 bg-white rounded shadow-lg border border-gray-200 py-1 z-50">
                        <Link to="/admin/events" className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 hover:no-underline">
                          {t('nav.events.manage')}
                        </Link>
                      </div>
                    )}
                  </div>
                  <div className="relative" onMouseEnter={() => setShowTasksMenu(true)} onMouseLeave={() => setShowTasksMenu(false)}>
                    <Link to="/tasks" className="px-3 py-1.5 text-sm font-medium text-white/90 hover:text-white hover:bg-white/10 rounded transition-colors hover:no-underline">
                      {t('nav.tasks')} {isAdmin && <span className="ml-0.5 text-xs">▾</span>}
                    </Link>
                    {isAdmin && showTasksMenu && (
                      <div className="absolute top-full left-0 mt-1 w-48 bg-white rounded shadow-lg border border-gray-200 py-1 z-50">
                        <Link to="/admin/tasks" className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 hover:no-underline">
                          {t('nav.tasks.manage')}
                        </Link>
                      </div>
                    )}
                  </div>
                  <Link to="/documents" className="px-3 py-1.5 text-sm font-medium text-white/90 hover:text-white hover:bg-white/10 rounded transition-colors hover:no-underline">
                    {t('nav.documents')}
                  </Link>
                  <Link to="/oracle" className="px-3 py-1.5 text-sm font-medium text-white/90 hover:text-white hover:bg-white/10 rounded transition-colors hover:no-underline">
                    {t('nav.oracle')}
                  </Link>
                  <div className="relative" onMouseEnter={() => setShowPrereqMenu(true)} onMouseLeave={() => setShowPrereqMenu(false)}>
                    <span className="px-3 py-1.5 text-sm font-medium text-white/90 hover:text-white hover:bg-white/10 rounded transition-colors cursor-pointer">
                      {t('nav.prerequisites')} <span className="ml-0.5 text-xs">▾</span>
                    </span>
                    {showPrereqMenu && (
                      <div className="absolute top-full left-0 mt-1 w-56 bg-white rounded shadow-lg border border-gray-200 py-1 z-50">
                        {PREREQ_NAV_ITEMS.map((item) => (
                          <Link key={item.route} to={item.route} className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 hover:no-underline">
                            {t(item.labelKey)}
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                  {isAdmin && (
                    <Link to="/admin/users" className="px-3 py-1.5 text-sm font-medium text-white/90 hover:text-white hover:bg-white/10 rounded transition-colors hover:no-underline">
                      {t('nav.users')}
                    </Link>
                  )}
                  {isAdmin && (
                    <Link to="/admin/configuration" className="px-3 py-1.5 text-sm font-medium text-white/90 hover:text-white hover:bg-white/10 rounded transition-colors hover:no-underline">
                      {t('nav.config')}
                    </Link>
                  )}
                </>
              )}
            </div>
          </div>
          {/* Desktop Auth */}
          <div className="hidden sm:flex items-center gap-2">
            <div className="flex items-center gap-1" role="group" aria-label="Language">
              {(['fr', 'en'] as const).map((lng) => (
                <button
                  key={lng}
                  type="button"
                  onClick={() => setLanguage(lng)}
                  aria-pressed={language === lng}
                  className={
                    language === lng
                      ? 'px-2 py-1 text-xs font-semibold rounded bg-white text-[#000E9C]'
                      : 'px-2 py-1 text-xs font-medium rounded text-white/80 hover:bg-white/10'
                  }
                >
                  {t(`lang.${lng}`)}
                </button>
              ))}
            </div>
            {isAuthenticated ? (
              <>
                <Link
                  to="/account/security"
                  aria-label={t('auth.accountSecurity')}
                  className="inline-flex items-center justify-center p-1.5 bg-white/15 border border-white/30 text-white rounded hover:bg-white/25 transition-colors hover:no-underline"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4" aria-hidden="true">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                </Link>
                <button
                  onClick={handleLogout}
                  className="px-4 py-1.5 text-sm font-medium bg-white/15 border border-white/30 text-white rounded hover:bg-white/25 transition-colors"
                >
                  {t('auth.logout')}
                </button>
              </>
            ) : (
              <div className="flex gap-2">
                <Link
                  to="/login"
                  className="px-4 py-1.5 text-sm font-medium bg-white/15 border border-white/30 text-white rounded hover:bg-white/25 transition-colors hover:no-underline"
                >
                  {t('auth.login')}
                </Link>
                <Link
                  to="/register"
                  className="px-4 py-1.5 text-sm font-medium bg-white text-[#000E9C] rounded hover:bg-gray-100 transition-colors hover:no-underline"
                >
                  {t('auth.register')}
                </Link>
              </div>
            )}
          </div>
          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="sm:hidden text-white text-xl p-1"
            aria-label="Menu"
          >
            {mobileMenuOpen ? '✕' : '☰'}
          </button>
        </div>
      </nav>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="sm:hidden bg-white border-b border-gray-200 shadow-md">
          <div className="px-4 py-3 space-y-1">
            <div className="flex items-center gap-1 pb-2 mb-2 border-b border-gray-200" role="group" aria-label="Language">
              {(['fr', 'en'] as const).map((lng) => (
                <button
                  key={lng}
                  type="button"
                  onClick={() => setLanguage(lng)}
                  aria-pressed={language === lng}
                  className={
                    language === lng
                      ? 'px-3 py-1 text-sm font-semibold rounded bg-[#000E9C] text-white'
                      : 'px-3 py-1 text-sm font-medium rounded text-[#000E9C] hover:bg-gray-50'
                  }
                >
                  {t(`lang.${lng}`)}
                </button>
              ))}
            </div>
            <Link to="/" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded hover:no-underline">
              {t('nav.home')}
            </Link>
            {isAuthenticated && (
              <>
                <Link to="/forum" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded hover:no-underline">
                  {t('nav.forum')}
                </Link>
                <Link to="/events" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded hover:no-underline">
                  {t('nav.events')}
                </Link>
                {isAdmin && (
                  <Link to="/admin/events" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2 pl-6 text-sm text-gray-600 hover:bg-gray-50 rounded hover:no-underline">
                    {t('nav.events.manage')}
                  </Link>
                )}
                <Link to="/tasks" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded hover:no-underline">
                  {t('nav.tasks')}
                </Link>
                {isAdmin && (
                  <Link to="/admin/tasks" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2 pl-6 text-sm text-gray-600 hover:bg-gray-50 rounded hover:no-underline">
                    {t('nav.tasks.manage')}
                  </Link>
                )}
                <Link to="/documents" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded hover:no-underline">
                  {t('nav.documents')}
                </Link>
                <Link to="/oracle" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded hover:no-underline">
                  {t('nav.oracle')}
                </Link>
                <div className="px-3 py-2 text-sm font-medium text-gray-700">{t('nav.prerequisites')}</div>
                {PREREQ_NAV_ITEMS.map((item) => (
                  <Link
                    key={item.route}
                    to={item.route}
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 pl-6 text-sm text-gray-600 hover:bg-gray-50 rounded hover:no-underline"
                  >
                    {t(item.labelKey)}
                  </Link>
                ))}
                {isAdmin && (
                  <Link to="/admin/users" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded hover:no-underline">
                    {t('nav.users')}
                  </Link>
                )}
                {isAdmin && (
                  <Link to="/admin/configuration" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded hover:no-underline">
                    {t('nav.config')}
                  </Link>
                )}
              </>
            )}
            <div className="pt-3 mt-3 border-t border-gray-200">
              {isAuthenticated ? (
                <>
                  <Link
                    to="/account/security"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded hover:no-underline"
                  >
                    {t('auth.accountSecurity')}
                  </Link>
                  <button
                    onClick={() => { setMobileMenuOpen(false); handleLogout(); }}
                    className="w-full text-left px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 rounded"
                  >
                    {t('auth.logout')}
                  </button>
                </>
              ) : (
                <div className="space-y-2">
                  <Link to="/login" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2 text-sm font-medium text-[#000E9C] hover:bg-gray-50 rounded hover:no-underline">
                    {t('auth.login')}
                  </Link>
                  <Link to="/register" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2 text-sm font-medium text-white bg-[#000E9C] rounded text-center hover:no-underline">
                    {t('auth.register')}
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto py-8 px-4 sm:px-6 lg:px-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <p className="text-sm text-gray-500">© 2026 OPCP — opcp-psmc.com</p>
        </div>
      </footer>
    </div>
  );
};
