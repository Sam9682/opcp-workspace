import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, act } from '@testing-library/react';
import type React from 'react';
import { ServersTable } from './ServersTable';
import { LanguageProvider } from '../../hooks/useLanguage';
import { prerequisitesService } from '../../services/prerequisitesService';

// ===========================================================================
// Feature: openstack-ca-certificate, Example 1.1: labeled textarea present
//
// The credentials form SHALL display a multi-line text area labeled for the CA
// Certificate alongside the other credential fields. This example asserts the
// element exists, is associated with its label, and is a multi-line <textarea>
// (not a single-line <input>).
//
// Requirements: 1.1
// ===========================================================================

// CredentialsForm loads the stored config on mount. Mock the service so the
// component behavior is driven by the test, not the network.
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

const INSTALL_ID = '33333333-3333-3333-3333-333333333333';

// French label (default language) for the CA certificate textarea, keyed to
// `prereq.servers.credentials.caCertificate`.
const LABEL_CA_CERTIFICATE = 'Certificat CA (PEM)';

function renderTable(ui: React.ReactElement) {
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

// Mount the form and let the mount-time loadCredentialConfig promise resolve so
// the prefill settles before assertions run.
async function mountForm() {
  renderTable(<ServersTable title="Servers nodes" installationId={INSTALL_ID} />);
  await act(async () => {
    await Promise.resolve();
  });
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

describe('Feature: openstack-ca-certificate, Example 1.1: labeled CA certificate textarea present', () => {
  it('renders a labeled multi-line textarea for the CA certificate', async () => {
    await mountForm();

    const field = screen.getByLabelText(LABEL_CA_CERTIFICATE);

    // The labeled element exists and is the CA certificate control.
    expect(field).toBeInTheDocument();
    expect(field).toHaveAttribute('id', 'openstack-ca-certificate');

    // It is a multi-line <textarea>, not a single-line <input>.
    expect(field.tagName).toBe('TEXTAREA');
  });
});
