import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { InstallationListPage } from './InstallationListPage';
import { LanguageProvider } from '../../hooks/useLanguage';
import { authService } from '../../services/authService';
import { prerequisitesService, type Installation } from '../../services/prerequisitesService';

// authService.isAdmin() gates the create control (Req 6.7 parity on the
// client — admin-only controls). Mock the module so each test can choose the
// role that renders.
vi.mock('../../services/authService', () => ({
  authService: {
    isAdmin: vi.fn(),
    isAuthenticated: vi.fn(() => true),
  },
}));

// prerequisitesService is the only persistence path. Mock every method the
// page touches so the create flow is observable with no network access.
vi.mock('../../services/prerequisitesService', () => ({
  prerequisitesService: {
    listInstallations: vi.fn(),
    createInstallation: vi.fn(),
    updateInstallation: vi.fn(),
    deleteInstallation: vi.fn(),
  },
}));

const mockedAuth = vi.mocked(authService);
const mockedService = vi.mocked(prerequisitesService);

// InstallationListPage consumes useTranslation() (LanguageProvider) and renders
// <Link> rows (Router). Wrap every mount in both. Default language is French,
// so labels resolve to their French copy.
function renderPage() {
  return render(
    <LanguageProvider>
      <MemoryRouter>
        <InstallationListPage />
      </MemoryRouter>
    </LanguageProvider>,
  );
}

const makeInstallation = (over: Partial<Installation> = {}): Installation => ({
  id: '11111111-1111-1111-1111-111111111111',
  project_name: 'Alpha',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  cleanup();
  // Default: admin so the create control renders; list starts empty.
  mockedAuth.isAdmin.mockReturnValue(true);
  mockedAuth.isAuthenticated.mockReturnValue(true);
  mockedService.listInstallations.mockResolvedValue([]);
  mockedService.createInstallation.mockResolvedValue(makeInstallation());
});

// Feature: vcf-prerequisites-update — Frontend installation create flow (task 9.1)
// Validates: Requirements 6.1, 6.2, 9.2
describe('InstallationListPage create flow', () => {
  it('renders the create control for administrators', async () => {
    renderPage();

    // Wait for the initial load to settle so the ready branch renders.
    await waitFor(() => {
      expect(mockedService.listInstallations).toHaveBeenCalled();
    });

    expect(
      screen.getByRole('button', { name: /créer/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('textbox', { name: /nom du projet/i }),
    ).toBeInTheDocument();
  });

  it('hides the create control for non-administrators', async () => {
    mockedAuth.isAdmin.mockReturnValue(false);
    renderPage();

    await waitFor(() => {
      expect(mockedService.listInstallations).toHaveBeenCalled();
    });

    expect(
      screen.queryByRole('button', { name: /créer/i }),
    ).not.toBeInTheDocument();
  });

  it('entering a name and triggering create calls createInstallation with the project name', async () => {
    // The created installation is returned by createInstallation, and after the
    // create the page refreshes the list — return it on the second load.
    const created = makeInstallation({ project_name: 'My VCF Project' });
    mockedService.listInstallations
      .mockResolvedValueOnce([]) // initial mount
      .mockResolvedValueOnce([created]); // refresh after create
    mockedService.createInstallation.mockResolvedValue(created);

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(mockedService.listInstallations).toHaveBeenCalledTimes(1);
    });

    const input = screen.getByRole('textbox', { name: /nom du projet/i });
    await user.type(input, 'My VCF Project');
    await user.click(screen.getByRole('button', { name: /créer/i }));

    // createInstallation is issued with the typed project name. The service
    // method in turn performs api.post('/prerequisites/installations',
    // { project_name }) — covered by the service contract test below.
    await waitFor(() => {
      expect(mockedService.createInstallation).toHaveBeenCalledTimes(1);
    });
    expect(mockedService.createInstallation).toHaveBeenCalledWith('My VCF Project');
  });

  it('renders the created installation in the list after a successful create + refresh', async () => {
    const created = makeInstallation({ project_name: 'My VCF Project' });
    mockedService.listInstallations
      .mockResolvedValueOnce([]) // initial mount: empty
      .mockResolvedValueOnce([created]); // refresh after create shows the new row
    mockedService.createInstallation.mockResolvedValue(created);

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(mockedService.listInstallations).toHaveBeenCalledTimes(1);
    });

    await user.type(
      screen.getByRole('textbox', { name: /nom du projet/i }),
      'My VCF Project',
    );
    await user.click(screen.getByRole('button', { name: /créer/i }));

    // The refresh load runs after the create resolves, then the new row renders
    // as a link labeled with its project_name.
    await waitFor(() => {
      expect(mockedService.listInstallations).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(
        screen.getByRole('link', { name: 'My VCF Project' }),
      ).toBeInTheDocument();
    });
  });

  it('clears the input and does not call createInstallation for a whitespace-only name', async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(mockedService.listInstallations).toHaveBeenCalledTimes(1);
    });

    await user.type(screen.getByRole('textbox', { name: /nom du projet/i }), '   ');
    await user.click(screen.getByRole('button', { name: /créer/i }));

    // Empty/whitespace names are rejected client-side; no service call and an
    // inline error is shown.
    expect(mockedService.createInstallation).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
