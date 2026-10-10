import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, act, fireEvent } from '@testing-library/react';
import type React from 'react';
import { ServersTable } from './ServersTable';
import { LanguageProvider } from '../../hooks/useLanguage';
import { prerequisitesService } from '../../services/prerequisitesService';

// ===========================================================================
// Feature spec: openstack-node-status (task 9.3)
// Property 3: Required-field validation gates retrieval.
//
// When any required non-secret field (Auth URL, Credential ID, Nova endpoint)
// is empty — or the secret is empty while none is stored server-side — pressing
// RETRIEVE INFO shows the mapped i18n validation message and sends NO retrieval
// request. This exercises both the pure `validateCredentialsForm` helper and
// the rendered component behavior (retrieveServers is never called).
//
// Validates: Requirements 2.1, 2.2, 2.3, 2.4
// ===========================================================================

// ServersTable's CredentialsForm loads the stored config on mount and, on
// RETRIEVE INFO, persists + retrieves in one call. Mock the service so the
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

const INSTALL_ID = '11111111-1111-1111-1111-111111111111';

// The four credential fields, addressed by their French labels (default lang).
const LABEL_AUTH_URL = "URL d'authentification (Keystone)";
const LABEL_CREDENTIAL_ID = 'Identifiant de la credential';
const LABEL_CREDENTIAL_SECRET = 'Secret de la credential';
const LABEL_NOVA_ENDPOINT = "Point d'accès Nova";
const RETRIEVE_LABEL = 'RÉCUPÉRER LES INFOS';

// French validation messages (default language). Keyed to their i18n keys.
const MSG_AUTH_URL_REQUIRED = "L'URL d'authentification est requise.";
const MSG_CREDENTIAL_ID_REQUIRED = "L'identifiant de la credential est requis.";
const MSG_NOVA_ENDPOINT_REQUIRED = "Le point d'accès Nova est requis.";
const MSG_SECRET_REQUIRED = 'Le secret de la credential est requis.';

// A fully valid form (used as the baseline that each empty-field case perturbs).
const VALID_FORM = {
  authUrl: 'https://keystone.example.com/v3',
  credentialId: 'cred-123',
  credentialSecret: 's3cr3t',
  novaEndpoint: 'https://nova.example.com/v2.1',
};

function renderTable(ui: React.ReactElement) {
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

// Fill the four inputs to the given field values (blank strings clear a field).
function fillForm(values: {
  authUrl: string;
  credentialId: string;
  credentialSecret: string;
  novaEndpoint: string;
}) {
  fireEvent.change(screen.getByLabelText(LABEL_AUTH_URL), {
    target: { value: values.authUrl },
  });
  fireEvent.change(screen.getByLabelText(LABEL_CREDENTIAL_ID), {
    target: { value: values.credentialId },
  });
  fireEvent.change(screen.getByLabelText(LABEL_CREDENTIAL_SECRET), {
    target: { value: values.credentialSecret },
  });
  fireEvent.change(screen.getByLabelText(LABEL_NOVA_ENDPOINT), {
    target: { value: values.novaEndpoint },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  // No stored config: the load resolves to an empty, secret-not-stored config so
  // validation still requires a typed secret. Individual tests override this.
  mockedPrereq.loadCredentialConfig.mockResolvedValue({
    auth_url: '',
    credential_id: '',
    nova_endpoint: '',
    ca_certificate: '',
    secret_stored: false,
  });
  mockedPrereq.retrieveServers.mockResolvedValue({ servers: [] });
});

afterEach(() => {
  cleanup();
});

// Mount the form and let the mount-time loadCredentialConfig promise resolve so
// the "secret stored" flag settles before the test types into the form.
async function mountForm() {
  renderTable(<ServersTable title="Servers nodes" installationId={INSTALL_ID} />);
  await act(async () => {
    await Promise.resolve();
  });
}

// Each empty-field branch: which field is blanked and the message it maps to.
const EMPTY_FIELD_CASES = [
  { field: 'authUrl', message: MSG_AUTH_URL_REQUIRED },
  { field: 'credentialId', message: MSG_CREDENTIAL_ID_REQUIRED },
  { field: 'novaEndpoint', message: MSG_NOVA_ENDPOINT_REQUIRED },
  { field: 'credentialSecret', message: MSG_SECRET_REQUIRED },
] as const;

describe('Property 3: required-field validation gates retrieval', () => {
  it.each(EMPTY_FIELD_CASES)(
    'shows the $field validation message and sends no request when $field is empty',
    async ({ field, message }) => {
      await mountForm();

      // Start from a valid form, then blank exactly the field under test. The
      // secret case relies on the default beforeEach (secret_stored === false).
      fillForm({ ...VALID_FORM, [field]: '' });

      fireEvent.click(screen.getByText(RETRIEVE_LABEL));

      // The mapped validation message renders (role="alert").
      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent(message);

      // Crucially, NO retrieval request was sent.
      expect(mockedPrereq.retrieveServers).not.toHaveBeenCalled();
    },
  );

  it('does not require a typed secret when one is already stored server-side', async () => {
    // A secret is stored, so an empty secret is valid: the other three fields
    // are filled and pressing RETRIEVE INFO proceeds to a request.
    mockedPrereq.loadCredentialConfig.mockResolvedValue({
      auth_url: '',
      credential_id: '',
      nova_endpoint: '',
      ca_certificate: '',
      secret_stored: true,
    });

    await mountForm();

    fillForm({ ...VALID_FORM, credentialSecret: '' });
    fireEvent.click(screen.getByText(RETRIEVE_LABEL));

    await act(async () => {
      await Promise.resolve();
    });

    // No secret-required validation message, and a request WAS sent (the stored
    // secret satisfies the rule).
    expect(screen.queryByText(MSG_SECRET_REQUIRED)).toBeNull();
    expect(mockedPrereq.retrieveServers).toHaveBeenCalledTimes(1);
  });

  it('sends the retrieval request without a secret field when the form is valid but secret was not typed', async () => {
    // Regression guard for 2.4: with a stored secret and no typed secret, the
    // save payload omits credential_secret so the backend reuses the stored one.
    mockedPrereq.loadCredentialConfig.mockResolvedValue({
      auth_url: '',
      credential_id: '',
      nova_endpoint: '',
      ca_certificate: '',
      secret_stored: true,
    });

    await mountForm();

    fillForm({ ...VALID_FORM, credentialSecret: '' });
    fireEvent.click(screen.getByText(RETRIEVE_LABEL));

    await act(async () => {
      await Promise.resolve();
    });

    expect(mockedPrereq.retrieveServers).toHaveBeenCalledWith(
      INSTALL_ID,
      expect.not.objectContaining({ credential_secret: expect.anything() }),
    );
  });
});
