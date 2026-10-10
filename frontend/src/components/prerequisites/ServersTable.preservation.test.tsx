import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, within, act } from '@testing-library/react';
import type React from 'react';
import fc from 'fast-check';
import { ServersTable } from './ServersTable';
import type { ServerNode } from './serversData';
import { SERVER_NODES } from './serversData';
import { LanguageProvider } from '../../hooks/useLanguage';
import { prerequisitesService } from '../../services/prerequisitesService';

// ServersTable now uses `useTranslation` (for the node-save error banner), so
// every render must be wrapped in a LanguageProvider. Its mount effect also
// loads per-installation node overrides; mock the service so the table can
// mount without hitting the network and defaults to an empty override set.
vi.mock('../../services/prerequisitesService', () => ({
  SERVERS_SLUG: 'servers-nodes',
  prerequisitesService: {
    loadCredentialConfig: vi.fn(),
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

// ===========================================================================
// Feature spec: servers-nodes-page-layout
//
// This feature intentionally CHANGES the previously strictly-read-only nodes
// inventory: for members and administrators every column becomes an editable
// free-text input; visitors (and unauthenticated users) keep a read-only
// table. These tests pin the new, spec-compliant behavior.
//
// Role is resolved from authService, which reads from localStorage:
//   administrator -> user_role === 'administrator'
//   member        -> user.role === 'member'
//   visitor       -> neither (isAdmin() false, role !== 'member')
//
// Validates: Requirements 2.1, 2.2, 2.3
// ===========================================================================

// Populate localStorage so authService resolves the given role.
function setRole(role: 'administrator' | 'member' | 'visitor') {
  localStorage.setItem('user_role', role);
  localStorage.setItem(
    'user',
    JSON.stringify({
      id: 'u1',
      email: 'u@example.com',
      first_name: 'U',
      last_name: 'Ser',
      role,
      is_email_verified: true,
    }),
  );
}

// Generate arbitrary, well-formed server node inventories so the properties
// hold for any data set, not just the built-in inventory.
const serverNodeArb: fc.Arbitrary<ServerNode> = fc.record({
  nodeUuid: fc.string(),
  serialNumber: fc.string(),
  instanceUuid: fc.string(),
  powerState: fc.constantFrom('power on', 'power off', 'None', ''),
  provisionState: fc.constantFrom('active', 'available', 'enroll', ''),
  remark: fc.string(),
});

// ServersTable keys its rows on `node.nodeUuid`, so give each generated node a
// unique nodeUuid to avoid duplicate-key warnings while still exercising
// arbitrary inventories.
const nodesArb: fc.Arbitrary<ServerNode[]> = fc
  .array(serverNodeArb, { minLength: 1, maxLength: 6 })
  .map((nodes) =>
    nodes.map((node, i) => ({ ...node, nodeUuid: `node-${i}-${node.nodeUuid}` })),
  );

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// Property 1 (Req 2.1, 2.2): editable free-text controls for member/admin.
// ---------------------------------------------------------------------------
describe('Servers nodes table is editable for members and administrators', () => {
  it.each(['member', 'administrator'] as const)(
    'renders six free-text inputs per row for a %s',
    (role) => {
      fc.assert(
        fc.property(nodesArb, (nodes) => {
          cleanup();
          setRole(role);
          renderTable(<ServersTable title="Servers nodes" nodes={nodes} />);

          // Every one of the six columns is an editable text input per row.
          expect(screen.getAllByRole('textbox')).toHaveLength(nodes.length * 6);

          cleanup();
        }),
        { numRuns: 50 },
      );
    },
  );

  it('exposes an editable input for each of the six columns of the built-in inventory', () => {
    setRole('member');
    renderTable(<ServersTable title="Servers nodes" nodes={SERVER_NODES} />);

    // Each column has one editable input per row (addressed by aria-label).
    for (const label of [
      'Node UUID',
      'Serial Number',
      'Instance UUID',
      'Power State',
      'Provision State',
      'Remark',
    ]) {
      expect(screen.getAllByLabelText(label)).toHaveLength(SERVER_NODES.length);
    }
  });
});

// ---------------------------------------------------------------------------
// Property 2 (Req 2.3): read-only table for visitors / unauthenticated users.
// ---------------------------------------------------------------------------
describe('Servers nodes table is read-only for visitors', () => {
  it('renders no editable inputs for any generated inventory (visitor role)', () => {
    fc.assert(
      fc.property(nodesArb, (nodes) => {
        cleanup();
        setRole('visitor');
        renderTable(<ServersTable title="Servers nodes" nodes={nodes} />);

        // No form controls at all: the inventory is display-only.
        expect(screen.queryAllByRole('textbox')).toHaveLength(0);
        expect(document.querySelectorAll('input, textarea, select')).toHaveLength(0);

        cleanup();
      }),
      { numRuns: 100 },
    );
  });

  it('renders no editable inputs when unauthenticated (no stored user)', () => {
    // localStorage cleared in beforeEach -> isAdmin() false, getCurrentUser() null.
    renderTable(<ServersTable title="Servers nodes" nodes={SERVER_NODES} />);
    expect(screen.queryAllByRole('textbox')).toHaveLength(0);
    expect(document.querySelectorAll('input, textarea, select')).toHaveLength(0);
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('renders the inventory as a table with the six columns (read-only presentation)', () => {
    fc.assert(
      fc.property(nodesArb, (nodes) => {
        cleanup();
        setRole('visitor');
        renderTable(<ServersTable title="Servers nodes" nodes={nodes} />);

        const table = screen.getByRole('table');
        expect(table).toBeInTheDocument();
        const headers = within(table).getAllByRole('columnheader');
        expect(headers).toHaveLength(6);

        cleanup();
      }),
      { numRuns: 100 },
    );
  });
});

// ===========================================================================
// Feature spec: servers-nodes-page-layout
// Requirement 1.1 / 1.3 / 1.4: the nodes table renders ABOVE the credentials
// section (credentials fields, RETRIEVE INFO button, and live results move
// below the table). The static six-column inventory table continues to render
// alongside the credentials form. Validates: Requirements 1.1, 1.3, 1.4
// ===========================================================================

const INSTALL_ID = '33333333-3333-3333-3333-333333333333';
const CREDENTIALS_TITLE = 'Identifiants OpenStack';
const RETRIEVE_LABEL = 'RÉCUPÉRER LES INFOS';

describe('Requirement 1: nodes table renders above the credentials section', () => {
  beforeEach(() => {
    mockedPrereq.loadCredentialConfig.mockResolvedValue({
      auth_url: '',
      credential_id: '',
      nova_endpoint: '',
      ca_certificate: '',
      secret_stored: false,
    });
  });

  it('renders the six-column inventory table together with the credentials form', async () => {
    renderTable(
      <ServersTable
        title="Servers nodes"
        nodes={SERVER_NODES}
        installationId={INSTALL_ID}
      />,
    );
    // Let the mount-time load promises resolve.
    await act(async () => {
      await Promise.resolve();
    });

    // The credentials form is present (title + RETRIEVE INFO button).
    expect(
      screen.getByRole('heading', { name: CREDENTIALS_TITLE }),
    ).toBeInTheDocument();
    expect(screen.getByText(RETRIEVE_LABEL)).toBeInTheDocument();

    // The static inventory table renders with its six inventory columns.
    const tables = screen.getAllByRole('table');
    const staticTable = tables.find(
      (table) => within(table).queryByText('Node UUID') !== null,
    );
    expect(staticTable).toBeDefined();

    const headers = within(staticTable as HTMLElement).getAllByRole('columnheader');
    expect(headers).toHaveLength(6);
    expect(
      within(staticTable as HTMLElement).getByText('Serial Number'),
    ).toBeInTheDocument();
    expect(
      within(staticTable as HTMLElement).getByText('Provision State'),
    ).toBeInTheDocument();
  });

  it('orders the nodes table before the credentials section in the DOM', async () => {
    // Visitor role keeps the table read-only, so the built-in Node UUID values
    // are rendered as text and can be located by their content.
    renderTable(
      <ServersTable
        title="Servers nodes"
        nodes={SERVER_NODES}
        installationId={INSTALL_ID}
      />,
    );
    await act(async () => {
      await Promise.resolve();
    });

    const credentialsHeading = screen.getByRole('heading', {
      name: CREDENTIALS_TITLE,
    });
    const tables = screen.getAllByRole('table');
    const staticTable = tables.find(
      (table) => within(table).queryByText('Node UUID') !== null,
    ) as HTMLElement;
    expect(staticTable).toBeDefined();

    // The nodes table appears before the credentials heading in document order.
    const position = staticTable.compareDocumentPosition(credentialsHeading);
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
