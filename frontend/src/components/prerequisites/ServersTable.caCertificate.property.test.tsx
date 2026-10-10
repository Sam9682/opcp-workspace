import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, act, fireEvent } from '@testing-library/react';
import type React from 'react';
import fc from 'fast-check';
import { ServersTable } from './ServersTable';
import { LanguageProvider } from '../../hooks/useLanguage';
import { prerequisitesService } from '../../services/prerequisitesService';

// ===========================================================================
// Feature: openstack-ca-certificate, Property 1: CA certificate input
// round-trip in the form
//
// For any text value entered into the CA certificate textarea, the credentials
// form state SHALL retain exactly that value, and the rendered textarea SHALL
// display it (controlled-input round-trip).
//
// Validates: Requirements 1.2
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

const INSTALL_ID = '22222222-2222-2222-2222-222222222222';

// French label (default language) for the CA certificate textarea, keyed to
// `prereq.servers.credentials.caCertificate`.
const LABEL_CA_CERTIFICATE = 'Certificat CA (PEM)';

function renderTable(ui: React.ReactElement) {
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

// Mount the form and let the mount-time loadCredentialConfig promise resolve so
// the prefill settles (to empty) before the test types into the textarea.
async function mountForm() {
  renderTable(<ServersTable title="Servers nodes" installationId={INSTALL_ID} />);
  await act(async () => {
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  // No stored config: the CA certificate starts empty so the textarea round-trip
  // is driven purely by what the test types.
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

describe('Feature: openstack-ca-certificate, Property 1: CA certificate input round-trip in the form', () => {
  it('round-trips any entered value into form state and the rendered textarea', async () => {
    await fc.assert(
      fc.asyncProperty(fc.string(), async (value) => {
        cleanup();
        await mountForm();

        const textarea = screen.getByLabelText(LABEL_CA_CERTIFICATE) as HTMLTextAreaElement;

        // Fire a change with the arbitrary value; the controlled input must
        // reflect exactly that value back.
        fireEvent.change(textarea, { target: { value } });

        const rendered = screen.getByLabelText(LABEL_CA_CERTIFICATE) as HTMLTextAreaElement;
        expect(rendered.value).toBe(value);

        cleanup();
      }),
      { numRuns: 100 },
    );
  });
});
