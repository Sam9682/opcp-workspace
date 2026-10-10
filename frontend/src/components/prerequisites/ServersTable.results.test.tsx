import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  render,
  screen,
  cleanup,
  act,
  fireEvent,
  within,
  waitFor,
} from '@testing-library/react';
import type React from 'react';
import { ServersTable } from './ServersTable';
import { LanguageProvider } from '../../hooks/useLanguage';
import { prerequisitesService } from '../../services/prerequisitesService';
import type { NovaServer } from '../../services/prerequisitesService';

// ===========================================================================
// Feature spec: openstack-node-status (task 9.4)
// Property 5: Live results reflect the retrieved server list.
// Property 6: Error responses map to the correct client message.
//
// Successful retrieval renders one row per server with its id/name/status; a
// loading indicator shows while the request is pending; a second retrieve
// replaces the prior rows. Each backend error code (AUTH_FAILED,
// CONNECTION_FAILED, OPENSTACK_ERROR, and an unknown code -> generic) renders
// its mapped message.
//
// Validates: Requirements 6.2, 7.1, 7.2, 7.3, 8.1, 8.2, 8.3
// ===========================================================================

vi.mock('../../services/prerequisitesService', () => ({
  SERVERS_SLUG: 'servers-nodes',
  prerequisitesService: {
    loadCredentialConfig: vi.fn(),
    saveCredentialConfig: vi.fn(),
    retrieveServers: vi.fn(),
    // ServersTable's mount effect loads per-installation node overrides;
    // default to an empty override set so these credential-focused tests are
    // unaffected by the nodes table. saveServerNodes is unused here.
    loadServerNodes: vi.fn().mockResolvedValue({ nodes: [] }),
    saveServerNodes: vi.fn().mockResolvedValue({ nodes: [] }),
  },
}));

const mockedPrereq = vi.mocked(prerequisitesService);

const INSTALL_ID = '22222222-2222-2222-2222-222222222222';

const LABEL_AUTH_URL = "URL d'authentification (Keystone)";
const LABEL_CREDENTIAL_ID = 'Identifiant de la credential';
const LABEL_CREDENTIAL_SECRET = 'Secret de la credential';
const LABEL_NOVA_ENDPOINT = "Point d'accès Nova";
const RETRIEVE_LABEL = 'RÉCUPÉRER LES INFOS';
const RETRIEVING_LABEL = 'Récupération en cours…';
const RESULTS_TITLE = 'Serveurs';

// French error messages (default language) keyed by backend error code.
const MSG_INVALID_CREDENTIALS = 'Identifiants invalides. Vérifiez la credential et son secret.';
const MSG_CONNECTION = 'Impossible de contacter OpenStack. Vérifiez le réseau et les URL.';
const MSG_OPENSTACK = 'OpenStack a renvoyé une erreur. Veuillez réessayer plus tard.';
const MSG_GENERIC = 'Une erreur est survenue lors de la récupération des serveurs.';

function renderTable(ui: React.ReactElement) {
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

// Fill the form with a complete, valid credential set so validation passes and
// the click proceeds to a retrieval request.
function fillValidForm() {
  fireEvent.change(screen.getByLabelText(LABEL_AUTH_URL), {
    target: { value: 'https://keystone.example.com/v3' },
  });
  fireEvent.change(screen.getByLabelText(LABEL_CREDENTIAL_ID), {
    target: { value: 'cred-123' },
  });
  fireEvent.change(screen.getByLabelText(LABEL_CREDENTIAL_SECRET), {
    target: { value: 's3cr3t' },
  });
  fireEvent.change(screen.getByLabelText(LABEL_NOVA_ENDPOINT), {
    target: { value: 'https://nova.example.com/v2.1' },
  });
}

// Build an axios-like error whose backend code lives under the app's unwrapped
// `{ error: { code } }` body (the shape the exception handler produces).
function axiosError(code: string) {
  return { response: { data: { error: { code, message: 'boom' } } } };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  mockedPrereq.loadCredentialConfig.mockResolvedValue({
    auth_url: '',
    credential_id: '',
    nova_endpoint: '',
    ca_certificate: '',
    secret_stored: false,
  });
});

afterEach(() => {
  cleanup();
});

async function mountForm() {
  renderTable(<ServersTable title="Servers nodes" installationId={INSTALL_ID} />);
  await act(async () => {
    await Promise.resolve();
  });
}

// The live results table is the only table with the "Serveurs" heading; anchor
// on that heading's following table to disambiguate from the static inventory.
function getResultsTable(): HTMLElement {
  const heading = screen.getByRole('heading', { name: RESULTS_TITLE });
  const section = heading.parentElement as HTMLElement;
  return within(section).getByRole('table');
}

describe('Property 5: live results reflect the retrieved server list', () => {
  it('renders one row per server with its id, name, and status', async () => {
    const servers: NovaServer[] = [
      { id: 'srv-1', name: 'controller-0', status: 'ACTIVE' },
      { id: 'srv-2', name: 'compute-1', status: 'SHUTOFF' },
      { id: 'srv-3', name: 'compute-2', status: 'ERROR' },
    ];
    mockedPrereq.retrieveServers.mockResolvedValue({ servers });

    await mountForm();
    fillValidForm();
    fireEvent.click(screen.getByText(RETRIEVE_LABEL));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: RESULTS_TITLE })).toBeInTheDocument();
    });

    const table = getResultsTable();
    const bodyRows = within(table).getAllByRole('row').slice(1); // drop header row
    expect(bodyRows).toHaveLength(servers.length);

    servers.forEach((server, i) => {
      const cells = within(bodyRows[i]).getAllByRole('cell');
      expect(cells[0]).toHaveTextContent(server.id);
      expect(cells[1]).toHaveTextContent(server.name);
      expect(cells[2]).toHaveTextContent(server.status);
    });
  });

  it('shows the loading indicator while the request is pending, then the results', async () => {
    // A deferred promise keeps the request pending so the loading state is
    // observable before resolution.
    let resolveRetrieve!: (value: { servers: NovaServer[] }) => void;
    mockedPrereq.retrieveServers.mockReturnValue(
      new Promise((resolve) => {
        resolveRetrieve = resolve;
      }),
    );

    await mountForm();
    fillValidForm();
    fireEvent.click(screen.getByText(RETRIEVE_LABEL));

    // Loading indicator (role="status") appears while pending.
    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(RETRIEVING_LABEL);
    });
    expect(screen.queryByRole('heading', { name: RESULTS_TITLE })).toBeNull();

    // Resolve the request; the loading indicator gives way to the results table.
    await act(async () => {
      resolveRetrieve({ servers: [{ id: 'srv-1', name: 'node', status: 'ACTIVE' }] });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: RESULTS_TITLE })).toBeInTheDocument();
    });
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('replaces prior rows when a subsequent retrieval succeeds', async () => {
    mockedPrereq.retrieveServers
      .mockResolvedValueOnce({
        servers: [
          { id: 'old-1', name: 'old-node-1', status: 'ACTIVE' },
          { id: 'old-2', name: 'old-node-2', status: 'ACTIVE' },
        ],
      })
      .mockResolvedValueOnce({
        servers: [{ id: 'new-1', name: 'new-node', status: 'SHUTOFF' }],
      });

    await mountForm();
    fillValidForm();

    // First retrieve: two rows.
    fireEvent.click(screen.getByText(RETRIEVE_LABEL));
    await waitFor(() => {
      expect(within(getResultsTable()).getAllByRole('row')).toHaveLength(3); // 1 header + 2
    });
    expect(screen.getByText('old-node-1')).toBeInTheDocument();

    // Second retrieve: a single row that replaces the previous two.
    fireEvent.click(screen.getByText(RETRIEVE_LABEL));
    await waitFor(() => {
      expect(within(getResultsTable()).getAllByRole('row')).toHaveLength(2); // 1 header + 1
    });
    expect(screen.getByText('new-node')).toBeInTheDocument();
    expect(screen.queryByText('old-node-1')).toBeNull();
    expect(screen.queryByText('old-node-2')).toBeNull();
  });
});

describe('Property 6: error responses map to the correct client message', () => {
  const ERROR_CASES = [
    { code: 'AUTH_FAILED', message: MSG_INVALID_CREDENTIALS },
    { code: 'CONNECTION_FAILED', message: MSG_CONNECTION },
    { code: 'OPENSTACK_ERROR', message: MSG_OPENSTACK },
    { code: 'SOMETHING_UNKNOWN', message: MSG_GENERIC },
  ] as const;

  it.each(ERROR_CASES)(
    'renders the mapped message for backend code $code',
    async ({ code, message }) => {
      mockedPrereq.retrieveServers.mockRejectedValue(axiosError(code));

      await mountForm();
      fillValidForm();
      fireEvent.click(screen.getByText(RETRIEVE_LABEL));

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent(message);

      // No results table renders on an error.
      expect(screen.queryByRole('heading', { name: RESULTS_TITLE })).toBeNull();
    },
  );

  it('maps the nested detail.error.code error shape to its message', async () => {
    // The raw FastAPI shape `{ detail: { error: { code } } }` is the fallback
    // when the app's exception handler is not applied; it must map identically.
    mockedPrereq.retrieveServers.mockRejectedValue({
      response: { data: { detail: { error: { code: 'CONNECTION_FAILED' } } } },
    });

    await mountForm();
    fillValidForm();
    fireEvent.click(screen.getByText(RETRIEVE_LABEL));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(MSG_CONNECTION);
  });
});
