import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, within, act } from '@testing-library/react';
import type React from 'react';
import { ServersTable } from './ServersTable';
import { LanguageProvider } from '../../hooks/useLanguage';
import { prerequisitesService } from '../../services/prerequisitesService';

// ---------------------------------------------------------------------------
// BUG 1 — the Servers-nodes table must render EMPTY on a fresh database.
//
// The table's row set now comes from the per-installation data returned by
// `loadServerNodes`, not from a hard-coded defaults list. With the default
// (empty) `nodes` prop and a backend that returns `{ nodes: [] }`, the table
// renders its six column headers but zero data rows (no seeded reference row
// such as `c6adb16d-...`). When the backend returns one stored row, exactly
// that row renders.
// ---------------------------------------------------------------------------

vi.mock('../../services/prerequisitesService', () => ({
  SERVERS_SLUG: 'servers-nodes',
  prerequisitesService: {
    loadCredentialConfig: vi.fn().mockResolvedValue({
      auth_url: '',
      credential_id: '',
      nova_endpoint: '',
      ca_certificate: '',
      secret_stored: false,
    }),
    saveCredentialConfig: vi.fn(),
    retrieveServers: vi.fn(),
    loadServerNodes: vi.fn().mockResolvedValue({ nodes: [] }),
    saveServerNodes: vi.fn().mockResolvedValue({ nodes: [] }),
  },
}));

const mockedPrereq = vi.mocked(prerequisitesService);

function renderTable(ui: React.ReactElement) {
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

const INSTALL_ID = '44444444-4444-4444-4444-444444444444';
const SEEDED_NODE_UUID = '00000000-0000-0000-0000-000000000000';

// The static reference inventory used to be seeded by default. The table is
// read-only for visitors (no stored user), so rows render as text and the
// absence of the seeded UUID is observable.
function nodeTable(): HTMLElement {
  const tables = screen.getAllByRole('table');
  const table = tables.find(
    (t) => within(t).queryByText('Node UUID') !== null,
  );
  expect(table).toBeDefined();
  return table as HTMLElement;
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  mockedPrereq.loadServerNodes.mockResolvedValue({ nodes: [] });
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

describe('ServersTable renders empty on a fresh database', () => {
  it('renders the six headers but zero data rows when the backend has no stored nodes', async () => {
    renderTable(
      <ServersTable title="Servers nodes" installationId={INSTALL_ID} />,
    );
    await act(async () => {
      await Promise.resolve();
    });

    const table = nodeTable();
    // Six column headers are still present …
    expect(within(table).getAllByRole('columnheader')).toHaveLength(6);
    // … but the body has no data rows.
    const body = table.querySelector('tbody') as HTMLElement;
    expect(within(body).queryAllByRole('row')).toHaveLength(0);
    // The old seeded reference row is gone.
    expect(screen.queryByText(SEEDED_NODE_UUID)).not.toBeInTheDocument();
  });

  it('renders exactly the stored rows returned by the backend', async () => {
    mockedPrereq.loadServerNodes.mockResolvedValue({
      nodes: [
        {
          node_uuid: 'stored-node-1',
          serial_number: 'SN-STORED',
          instance_uuid: 'inst-stored',
          power_state: 'power on',
          provision_state: 'active',
          remark: 'from db',
        },
      ],
    });

    renderTable(
      <ServersTable title="Servers nodes" installationId={INSTALL_ID} />,
    );
    await act(async () => {
      await Promise.resolve();
    });

    const table = nodeTable();
    const body = table.querySelector('tbody') as HTMLElement;
    expect(within(body).getAllByRole('row')).toHaveLength(1);
    expect(within(body).getByText('stored-node-1')).toBeInTheDocument();
    expect(screen.queryByText(SEEDED_NODE_UUID)).not.toBeInTheDocument();
  });
});
