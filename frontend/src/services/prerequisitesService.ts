import api from './api';

export interface StaticContentResponse {
  slug: string;
  content: string;
  updated_at?: string;
  installation_id?: string;
}

export interface ClientAnswersResponse {
  slug: string;
  answers: Record<string, string>;
}

/** A named OPCP prerequisites Installation (multi-instance scoping). */
export interface Installation {
  id: string;
  project_name: string;
  created_at: string;
  updated_at: string;
}

/**
 * OpenStack credential configuration for the `servers-nodes` tab. The secret is
 * never returned by the backend; `secret_stored` only reports whether one exists.
 * `ca_certificate` is non-secret and is always returned (empty when unset).
 */
export interface CredentialConfig {
  auth_url: string;
  credential_id: string;
  nova_endpoint: string;
  ca_certificate: string;
  secret_stored: boolean;
}

/**
 * Payload to save credentials. `credential_secret` is omitted when reusing the
 * secret already stored server-side.
 */
export interface SaveCredentialConfigRequest {
  auth_url: string;
  credential_id: string;
  nova_endpoint: string;
  credential_secret?: string;
  // Optional; omitted/empty means the backend uses the system default trust store.
  ca_certificate?: string;
}

/** A single Nova server as returned by the OpenStack proxy. */
export interface NovaServer {
  id: string;
  name: string;
  status: string;
}

export interface RetrieveServersResponse {
  servers: NovaServer[];
}

/**
 * A stored per-installation node override (snake_case wire shape). Keyed by
 * `node_uuid`; the remaining fields carry the edited values for that row.
 */
export interface ServerNodeOverridePayload {
  node_uuid: string;
  serial_number: string;
  instance_uuid: string;
  power_state: string;
  provision_state: string;
  remark: string;
}

export interface ServerNodesResponse {
  nodes: ServerNodeOverridePayload[];
}

/** Prerequisites slug for the OpenStack servers/nodes tab. */
export const SERVERS_SLUG = 'servers-nodes';

export const prerequisitesService = {
  // Installations (multi-instance CRUD)
  async listInstallations(): Promise<Installation[]> {
    const response = await api.get('/prerequisites/installations');
    // Backend returns { installations: Installation[] }.
    return response.data?.installations ?? [];
  },

  async createInstallation(projectName: string): Promise<Installation> {
    const response = await api.post('/prerequisites/installations', {
      project_name: projectName,
    });
    return response.data;
  },

  async updateInstallation(id: string, projectName: string): Promise<Installation> {
    const response = await api.put(`/prerequisites/installations/${id}`, {
      project_name: projectName,
    });
    return response.data;
  },

  async deleteInstallation(id: string): Promise<void> {
    await api.delete(`/prerequisites/installations/${id}`);
  },

  // Static content (Basics, Network Flux) — scoped to an Installation.
  async loadStaticContent(
    installationId: string,
    slug: string,
  ): Promise<StaticContentResponse> {
    const response = await api.get(
      `/prerequisites/installations/${installationId}/${slug}/content`,
    );
    return response.data;
  },

  async saveStaticContent(
    installationId: string,
    slug: string,
    content: string,
  ): Promise<void> {
    await api.put(
      `/prerequisites/installations/${installationId}/${slug}/content`,
      { content },
    );
  },

  // Client answers (Network Checklist, Core Control Plane, CloudStore, VCF) —
  // scoped to an Installation.
  async loadClientAnswers(
    installationId: string,
    slug: string,
  ): Promise<ClientAnswersResponse> {
    const response = await api.get(
      `/prerequisites/installations/${installationId}/${slug}/answers`,
    );
    return response.data;
  },

  async saveClientAnswer(
    installationId: string,
    slug: string,
    rowId: string,
    answer: string,
  ): Promise<void> {
    await api.put(
      `/prerequisites/installations/${installationId}/${slug}/answers/${rowId}`,
      { answer },
    );
  },

  // OpenStack credentials + live server retrieval (servers-nodes tab) —
  // scoped to an Installation.
  async loadCredentialConfig(installationId: string): Promise<CredentialConfig> {
    const response = await api.get(
      `/prerequisites/installations/${installationId}/${SERVERS_SLUG}/credentials`,
    );
    return response.data;
  },

  async saveCredentialConfig(
    installationId: string,
    cfg: SaveCredentialConfigRequest,
  ): Promise<CredentialConfig> {
    const response = await api.put(
      `/prerequisites/installations/${installationId}/${SERVERS_SLUG}/credentials`,
      cfg,
    );
    return response.data;
  },

  async retrieveServers(
    installationId: string,
    cfg: SaveCredentialConfigRequest,
  ): Promise<RetrieveServersResponse> {
    const response = await api.post(
      `/prerequisites/installations/${installationId}/${SERVERS_SLUG}/servers/retrieve`,
      cfg,
    );
    return response.data;
  },

  // Per-installation node overrides (servers-nodes tab). The backend is a pure
  // override store keyed by `node_uuid`; defaults define row existence.
  async loadServerNodes(installationId: string): Promise<ServerNodesResponse> {
    const response = await api.get(
      `/prerequisites/installations/${installationId}/${SERVERS_SLUG}/nodes`,
    );
    return response.data;
  },

  async saveServerNodes(
    installationId: string,
    nodes: ServerNodeOverridePayload[],
  ): Promise<ServerNodesResponse> {
    const response = await api.put(
      `/prerequisites/installations/${installationId}/${SERVERS_SLUG}/nodes`,
      { nodes },
    );
    return response.data;
  },
};
