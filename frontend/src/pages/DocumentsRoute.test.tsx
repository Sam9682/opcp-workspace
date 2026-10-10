import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { DocumentsPage } from './DocumentsPage';
import { LanguageProvider } from '../hooks/useLanguage';

// Keep this route test focused on auth gating: stub the document service so the
// page never hits the network. An empty list drives the "Documents" heading +
// empty-state render without any real API dependency.
vi.mock('../services/documentService', () => ({
  documentService: {
    listDocuments: vi.fn().mockResolvedValue({ documents: [], total: 0 }),
    downloadDocument: vi.fn(),
  },
}));

// Mirrors the /documents route structure declared in App.tsx: DocumentsPage is
// wrapped in a ProtectedRoute, with a recognizable /login placeholder used to
// detect the auth-guard redirect.
function renderDocumentsRoutes(initialEntry: string) {
  // The page calls useTranslation(), so wrap the routes in a LanguageProvider.
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/login" element={<div>Login Placeholder</div>} />
          <Route
            path="/documents"
            element={
              <ProtectedRoute>
                <DocumentsPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  );
}

const LOGIN_PLACEHOLDER = 'Login Placeholder';

beforeEach(() => {
  localStorage.clear();
  cleanup();
});

// Validates: Requirements 7.1, 7.2
describe('/documents route wiring and auth guard', () => {
  it('renders the Documents page when authenticated', async () => {
    localStorage.setItem('access_token', 'test-token');

    renderDocumentsRoutes('/documents');

    // The protected page loads asynchronously, then shows its heading...
    expect(await screen.findByText('Documents')).toBeInTheDocument();
    // ...and the auth-guard redirect target is not present.
    expect(screen.queryByText(LOGIN_PLACEHOLDER)).not.toBeInTheDocument();
  });

  it('redirects /documents to /login when not authenticated', () => {
    // No access_token set: authService.isAuthenticated() is false.
    renderDocumentsRoutes('/documents');

    // The auth guard redirects to the login route...
    expect(screen.getByText(LOGIN_PLACEHOLDER)).toBeInTheDocument();
    // ...and the protected page heading is not rendered.
    expect(screen.queryByText('Documents')).not.toBeInTheDocument();
  });
});
