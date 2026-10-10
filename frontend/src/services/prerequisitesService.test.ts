import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// The service imports the default axios instance from './api' and calls
// `.get`/`.put` on it. We replace that module with a stub whose methods we can
// assert against, so these are pure contract tests (HTTP verb, path, body)
// with no live backend.
vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

// Import after the mock is registered so the service binds to the stub.
import api from './api';
import { prerequisitesService } from './prerequisitesService';

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  mockedApi.get.mockReset();
  mockedApi.put.mockReset();
  mockedApi.post.mockReset();
  mockedApi.delete.mockReset();
  // Default resolutions so `response.data` reads don't throw.
  mockedApi.get.mockResolvedValue({ data: {} });
  mockedApi.put.mockResolvedValue({ data: {} });
  mockedApi.post.mockResolvedValue({ data: {} });
  mockedApi.delete.mockResolvedValue({ data: {} });
});

describe('prerequisitesService contract', () => {
  // _Requirements: 6.2 (load through service), 4.4 & 5.7 (save through service)_

  const INSTALL_ID = '11111111-1111-1111-1111-111111111111';

  describe('loadStaticContent', () => {
    it('issues GET /prerequisites/installations/{installationId}/{slug}/content and returns response.data', async () => {
      const payload = { slug: 'basics', content: '<html>x</html>' };
      mockedApi.get.mockResolvedValueOnce({ data: payload });

      const result = await prerequisitesService.loadStaticContent(INSTALL_ID, 'basics');

      expect(mockedApi.get).toHaveBeenCalledTimes(1);
      expect(mockedApi.get).toHaveBeenCalledWith(
        `/prerequisites/installations/${INSTALL_ID}/basics/content`,
      );
      expect(mockedApi.put).not.toHaveBeenCalled();
      expect(result).toEqual(payload);
    });
  });

  describe('saveStaticContent', () => {
    it('issues PUT /prerequisites/installations/{installationId}/{slug}/content with { content } body', async () => {
      await prerequisitesService.saveStaticContent(INSTALL_ID, 'basics', '<html>');

      expect(mockedApi.put).toHaveBeenCalledTimes(1);
      expect(mockedApi.put).toHaveBeenCalledWith(
        `/prerequisites/installations/${INSTALL_ID}/basics/content`,
        { content: '<html>' },
      );
      expect(mockedApi.get).not.toHaveBeenCalled();
    });
  });

  describe('loadClientAnswers', () => {
    it('issues GET /prerequisites/installations/{installationId}/{slug}/answers and returns response.data', async () => {
      const payload = { slug: 'vcf', answers: { 'row-1': 'val' } };
      mockedApi.get.mockResolvedValueOnce({ data: payload });

      const result = await prerequisitesService.loadClientAnswers(INSTALL_ID, 'vcf');

      expect(mockedApi.get).toHaveBeenCalledTimes(1);
      expect(mockedApi.get).toHaveBeenCalledWith(
        `/prerequisites/installations/${INSTALL_ID}/vcf/answers`,
      );
      expect(mockedApi.put).not.toHaveBeenCalled();
      expect(result).toEqual(payload);
    });
  });

  describe('saveClientAnswer', () => {
    it('issues PUT /prerequisites/installations/{installationId}/{slug}/answers/{rowId} with { answer } body', async () => {
      await prerequisitesService.saveClientAnswer(INSTALL_ID, 'vcf', 'row-1', 'val');

      expect(mockedApi.put).toHaveBeenCalledTimes(1);
      expect(mockedApi.put).toHaveBeenCalledWith(
        `/prerequisites/installations/${INSTALL_ID}/vcf/answers/row-1`,
        { answer: 'val' },
      );
      expect(mockedApi.get).not.toHaveBeenCalled();
    });
  });
});

describe('prerequisitesService installations contract', () => {
  // Feature: vcf-prerequisites-update — installation create flow (task 9.1)
  // Validates: Requirements 6.1, 6.2, 9.2

  describe('listInstallations', () => {
    it('issues GET /prerequisites/installations and unwraps { installations }', async () => {
      const installations = [
        {
          id: '11111111-1111-1111-1111-111111111111',
          project_name: 'Alpha',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ];
      mockedApi.get.mockResolvedValueOnce({ data: { installations } });

      const result = await prerequisitesService.listInstallations();

      expect(mockedApi.get).toHaveBeenCalledTimes(1);
      expect(mockedApi.get).toHaveBeenCalledWith('/prerequisites/installations');
      expect(result).toEqual(installations);
    });

    it('returns [] when the response omits the installations field', async () => {
      mockedApi.get.mockResolvedValueOnce({ data: {} });
      await expect(prerequisitesService.listInstallations()).resolves.toEqual([]);
    });
  });

  describe('createInstallation', () => {
    it('issues POST /prerequisites/installations with { project_name } and returns response.data', async () => {
      const created = {
        id: '22222222-2222-2222-2222-222222222222',
        project_name: 'My VCF Project',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      };
      mockedApi.post.mockResolvedValueOnce({ data: created });

      const result = await prerequisitesService.createInstallation('My VCF Project');

      expect(mockedApi.post).toHaveBeenCalledTimes(1);
      expect(mockedApi.post).toHaveBeenCalledWith('/prerequisites/installations', {
        project_name: 'My VCF Project',
      });
      expect(mockedApi.get).not.toHaveBeenCalled();
      expect(result).toEqual(created);
    });
  });

  describe('updateInstallation', () => {
    it('issues PUT /prerequisites/installations/{id} with { project_name }', async () => {
      const id = '33333333-3333-3333-3333-333333333333';
      const updated = {
        id,
        project_name: 'Renamed',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
      };
      mockedApi.put.mockResolvedValueOnce({ data: updated });

      const result = await prerequisitesService.updateInstallation(id, 'Renamed');

      expect(mockedApi.put).toHaveBeenCalledTimes(1);
      expect(mockedApi.put).toHaveBeenCalledWith(
        `/prerequisites/installations/${id}`,
        { project_name: 'Renamed' },
      );
      expect(result).toEqual(updated);
    });
  });

  describe('deleteInstallation', () => {
    it('issues DELETE /prerequisites/installations/{id}', async () => {
      const id = '44444444-4444-4444-4444-444444444444';
      await prerequisitesService.deleteInstallation(id);

      expect(mockedApi.delete).toHaveBeenCalledTimes(1);
      expect(mockedApi.delete).toHaveBeenCalledWith(
        `/prerequisites/installations/${id}`,
      );
    });
  });
});

describe('prerequisitesService OpenStack credentials contract', () => {
  // Feature: openstack-node-status — servers-nodes credentials + retrieval (task 7.2)
  // Validates: Requirements 10.2

  const INSTALL_ID = '55555555-5555-5555-5555-555555555555';
  const SECRET = 'super-secret-value';

  // Helper: no serialized response object should carry a secret field. This
  // guards Req 3.3/5.3 at the service boundary — the client never surfaces one.
  const assertNoSecretField = (value: unknown) => {
    const json = JSON.stringify(value ?? {});
    expect(json).not.toContain('credential_secret');
    expect(json).not.toContain(SECRET);
  };

  describe('loadCredentialConfig', () => {
    it('issues GET .../servers-nodes/credentials and returns a secret-free config', async () => {
      const payload = {
        auth_url: 'https://keystone.example/v3',
        credential_id: 'cred-1',
        nova_endpoint: 'https://nova.example/v2.1',
        secret_stored: true,
      };
      mockedApi.get.mockResolvedValueOnce({ data: payload });

      const result = await prerequisitesService.loadCredentialConfig(INSTALL_ID);

      expect(mockedApi.get).toHaveBeenCalledTimes(1);
      expect(mockedApi.get).toHaveBeenCalledWith(
        `/prerequisites/installations/${INSTALL_ID}/servers-nodes/credentials`,
      );
      expect(mockedApi.put).not.toHaveBeenCalled();
      expect(mockedApi.post).not.toHaveBeenCalled();
      expect(result).toEqual(payload);
      assertNoSecretField(result);
    });
  });

  describe('saveCredentialConfig', () => {
    it('issues PUT .../servers-nodes/credentials with the config body and returns a secret-free config', async () => {
      const cfg = {
        auth_url: 'https://keystone.example/v3',
        credential_id: 'cred-1',
        nova_endpoint: 'https://nova.example/v2.1',
        credential_secret: SECRET,
      };
      const response = {
        auth_url: cfg.auth_url,
        credential_id: cfg.credential_id,
        nova_endpoint: cfg.nova_endpoint,
        secret_stored: true,
      };
      mockedApi.put.mockResolvedValueOnce({ data: response });

      const result = await prerequisitesService.saveCredentialConfig(INSTALL_ID, cfg);

      expect(mockedApi.put).toHaveBeenCalledTimes(1);
      expect(mockedApi.put).toHaveBeenCalledWith(
        `/prerequisites/installations/${INSTALL_ID}/servers-nodes/credentials`,
        cfg,
      );
      expect(mockedApi.get).not.toHaveBeenCalled();
      expect(mockedApi.post).not.toHaveBeenCalled();
      expect(result).toEqual(response);
      // The returned config the client keeps must never echo the secret back.
      assertNoSecretField(result);
    });
  });

  describe('retrieveServers', () => {
    it('issues POST .../servers-nodes/servers/retrieve with the config body and returns a secret-free server list', async () => {
      const cfg = {
        auth_url: 'https://keystone.example/v3',
        credential_id: 'cred-1',
        nova_endpoint: 'https://nova.example/v2.1',
        credential_secret: SECRET,
      };
      const response = {
        servers: [
          { id: 'srv-1', name: 'node-a', status: 'ACTIVE' },
          { id: 'srv-2', name: 'node-b', status: 'SHUTOFF' },
        ],
      };
      mockedApi.post.mockResolvedValueOnce({ data: response });

      const result = await prerequisitesService.retrieveServers(INSTALL_ID, cfg);

      expect(mockedApi.post).toHaveBeenCalledTimes(1);
      expect(mockedApi.post).toHaveBeenCalledWith(
        `/prerequisites/installations/${INSTALL_ID}/servers-nodes/servers/retrieve`,
        cfg,
      );
      expect(mockedApi.get).not.toHaveBeenCalled();
      expect(mockedApi.put).not.toHaveBeenCalled();
      expect(result).toEqual(response);
      assertNoSecretField(result);
    });
  });
});

describe('prerequisitesService does not touch localStorage (Req 6.4)', () => {
  let getItemSpy: ReturnType<typeof vi.spyOn>;
  let setItemSpy: ReturnType<typeof vi.spyOn>;
  let removeItemSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    getItemSpy = vi.spyOn(Storage.prototype, 'getItem');
    setItemSpy = vi.spyOn(Storage.prototype, 'setItem');
    removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem');
  });

  afterEach(() => {
    getItemSpy.mockRestore();
    setItemSpy.mockRestore();
    removeItemSpy.mockRestore();
  });

  it('performs no localStorage reads or writes across every method', async () => {
    const installId = '11111111-1111-1111-1111-111111111111';
    await prerequisitesService.loadStaticContent(installId, 'basics');
    await prerequisitesService.saveStaticContent(installId, 'basics', '<html>');
    await prerequisitesService.loadClientAnswers(installId, 'vcf');
    await prerequisitesService.saveClientAnswer(installId, 'vcf', 'row-1', 'val');

    expect(getItemSpy).not.toHaveBeenCalled();
    expect(setItemSpy).not.toHaveBeenCalled();
    expect(removeItemSpy).not.toHaveBeenCalled();
  });
});
