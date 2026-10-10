import { describe, it, expect, vi, beforeEach } from 'vitest';
import fc from 'fast-check';

// buildInstallationExport pulls per-tab answers and the servers-nodes credential
// config from prerequisitesService. We replace that module with a stub so the
// export runs without a live backend: loadClientAnswers resolves to an empty
// answer map for every QA tab, and loadCredentialConfig returns a config whose
// `ca_certificate` is the generated value under test.
vi.mock('./prerequisitesService', () => ({
  prerequisitesService: {
    loadClientAnswers: vi.fn(),
    loadCredentialConfig: vi.fn(),
  },
}));

import { prerequisitesService, type Installation } from './prerequisitesService';
import { buildInstallationExport } from './installationExport';

const mockedService = prerequisitesService as unknown as {
  loadClientAnswers: ReturnType<typeof vi.fn>;
  loadCredentialConfig: ReturnType<typeof vi.fn>;
};

const INSTALLATION: Installation = {
  id: '99999999-9999-9999-9999-999999999999',
  project_name: 'Prop7 Project',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

beforeEach(() => {
  mockedService.loadClientAnswers.mockReset();
  mockedService.loadCredentialConfig.mockReset();
  // Every QA tab load degrades to an empty answer map; irrelevant to this property.
  mockedService.loadClientAnswers.mockResolvedValue({ answers: {} });
});

// Feature: openstack-ca-certificate, Property 7: Export includes the stored CA certificate
//
// For any stored credential configuration, the installation export document's
// `servers.credentials.ca_certificate` SHALL equal the loaded configuration's
// CA certificate value.
//
// **Validates: Requirements 4.1**
describe('Property 7: export includes the stored CA certificate (Requirements 4.1)', () => {
  it('export ca_certificate equals the loaded config ca_certificate for any value', async () => {
    await fc.assert(
      fc.asyncProperty(fc.string(), async (caCertificate) => {
        mockedService.loadCredentialConfig.mockResolvedValue({
          auth_url: 'https://keystone.example/v3',
          credential_id: 'cred-1',
          nova_endpoint: 'https://nova.example/v2.1',
          ca_certificate: caCertificate,
          secret_stored: true,
        });

        const doc = await buildInstallationExport(INSTALLATION);

        expect(doc.servers.credentials).not.toBeNull();
        expect(doc.servers.credentials?.ca_certificate).toBe(caCertificate);
      }),
      { numRuns: 100 },
    );
  });
});
