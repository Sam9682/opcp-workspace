import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';

// Auth is read via authService.isAuthenticated() (!!localStorage 'access_token').
// We drive auth by seeding localStorage before render, matching the other
// Layout/route tests in this suite.
function authenticate() {
  localStorage.setItem('access_token', 'test-token');
}

// Mirrors App.tsx: /account/security is wrapped in <ProtectedRoute>, and the
// login route renders a recognizable marker so we can assert redirects. Using a
// lightweight page stub keeps this test focused on routing/gating rather than
// SecurityPage's data fetching.
function renderAccountSecurityRoute(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/login" element={<div>Page de connexion</div>} />
        <Route
          path="/account/security"
          element={
            <ProtectedRoute>
              <div>Page de sécurité du compte</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  cleanup();
});

// Route registration + unauthenticated redirect.
// Validates: Requirements 2.1, 2.2
describe('/account/security route protection', () => {
  it('renders the protected page when the user is authenticated (2.1)', () => {
    authenticate();
    renderAccountSecurityRoute('/account/security');

    expect(screen.getByText('Page de sécurité du compte')).toBeInTheDocument();
    expect(screen.queryByText('Page de connexion')).toBeNull();
  });

  it('redirects an unauthenticated request to /login (2.2)', () => {
    // localStorage cleared in beforeEach: not authenticated.
    renderAccountSecurityRoute('/account/security');

    expect(screen.getByText('Page de connexion')).toBeInTheDocument();
    expect(screen.queryByText('Page de sécurité du compte')).toBeNull();
  });
});

// Direct behavioral checks on the ProtectedRoute guard used to protect the
// account-security route.
// Validates: Requirements 2.2
describe('ProtectedRoute guard', () => {
  it('renders its children when authenticated', () => {
    authenticate();
    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>contenu protégé</div>
        </ProtectedRoute>
      </MemoryRouter>,
    );

    expect(screen.getByText('contenu protégé')).toBeInTheDocument();
  });

  it('does not render its children when unauthenticated', () => {
    render(
      <MemoryRouter initialEntries={['/account/security']}>
        <Routes>
          <Route path="/login" element={<div>redirigé vers connexion</div>} />
          <Route
            path="/account/security"
            element={
              <ProtectedRoute>
                <div>contenu protégé</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.queryByText('contenu protégé')).toBeNull();
    expect(screen.getByText('redirigé vers connexion')).toBeInTheDocument();
  });
});
