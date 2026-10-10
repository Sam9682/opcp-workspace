import { useEffect, useMemo, useState } from 'react';
import { SERVER_NODES, type ServerNode } from './serversData';
import {
  mergeNodeOverrides,
  type ServerNodeOverride,
} from './serverNodeOverrides';
import { useTranslation } from '../../hooks/useLanguage';
import { authService } from '../../services/authService';
import { prerequisitesService } from '../../services/prerequisitesService';
import type {
  NovaServer,
  SaveCredentialConfigRequest,
  ServerNodeOverridePayload,
} from '../../services/prerequisitesService';

interface ServersTableProps {
  title: string;
  /**
   * `card` (default) renders the standalone card wrapper and page heading.
   * `embedded` drops the outer card and `<h1>` so the table can be hosted
   * inside a tab panel that already provides both.
   */
  variant?: 'card' | 'embedded';
  /** Server rows to display. Defaults to the built-in inventory. */
  nodes?: ReadonlyArray<ServerNode>;
  /**
   * When present, enables the OpenStack live-retrieval credentials form (and,
   * from task 9.2, the live results section) above the unchanged static table.
   */
  installationId?: string;
}

const PLACEHOLDER = '—';

/** Map a snake_case wire payload to the camelCase override shape. */
const toServerNodeOverride = (
  payload: ServerNodeOverridePayload,
): ServerNodeOverride => ({
  nodeUuid: payload.node_uuid,
  serialNumber: payload.serial_number,
  instanceUuid: payload.instance_uuid,
  powerState: payload.power_state,
  provisionState: payload.provision_state,
  remark: payload.remark,
});

/**
 * Inverse of `toServerNodeOverride`: map a camelCase `ServerNode` row to the
 * snake_case wire payload sent to the backend. Used when persisting the full
 * merged node list on an edit confirm.
 */
const toServerNodeOverridePayload = (
  node: ServerNode,
): ServerNodeOverridePayload => ({
  node_uuid: node.nodeUuid,
  serial_number: node.serialNumber,
  instance_uuid: node.instanceUuid,
  power_state: node.powerState,
  provision_state: node.provisionState,
  remark: node.remark,
});

const HEAD_CELL =
  'px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-[#000E9C] border-b border-gray-200 whitespace-nowrap';

const BODY_CELL = 'px-3 py-2 text-sm text-gray-700 border-b border-gray-100 align-top';

/** Tailwind classes for a small status pill, keyed on the normalized state. */
const powerStateClass = (state: string): string => {
  const normalized = state.trim().toLowerCase();
  if (normalized === 'power on') return 'bg-green-100 text-green-800';
  if (normalized === 'power off') return 'bg-gray-200 text-gray-700';
  return 'bg-amber-100 text-amber-800';
};

const provisionStateClass = (state: string): string => {
  const normalized = state.trim().toLowerCase();
  if (normalized === 'active') return 'bg-green-100 text-green-800';
  if (normalized === 'available') return 'bg-blue-100 text-blue-800';
  return 'bg-amber-100 text-amber-800';
};

const StatePill = ({ value, className }: { value: string; className: string }) =>
  value.trim() ? (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${className}`}
    >
      {value}
    </span>
  ) : (
    <span className="text-gray-400">{PLACEHOLDER}</span>
  );

const MonoCell = ({ value }: { value: string }) =>
  value.trim() ? (
    <span className="font-mono text-xs">{value}</span>
  ) : (
    <span className="text-gray-400">{PLACEHOLDER}</span>
  );

const NODE_CELL_INPUT_CLASS =
  'w-full min-w-[8rem] px-2 py-1 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent';

/**
 * Free-text editor for a single node cell (used for all six columns when the
 * current user is a member or administrator). Bound to the row's edit state via
 * `onChange`; the actual persistence (save on blur/Enter) is wired in a later
 * task.
 */
const EditableCell = ({
  value,
  label,
  onChange,
  onConfirm,
}: {
  value: string;
  label: string;
  onChange: (next: string) => void;
  /** Commit the edit (persist to the backend) on blur or Enter. */
  onConfirm: () => void;
}) => (
  <input
    type="text"
    aria-label={label}
    value={value}
    onChange={(e) => onChange(e.target.value)}
    onBlur={onConfirm}
    onKeyDown={(e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        onConfirm();
      }
    }}
    className={NODE_CELL_INPUT_CLASS}
  />
);

const CRED_FIELD_CLASS =
  'w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent';

/** Which required field failed client-side validation, keyed to its i18n message. */
type CredentialsValidationKey =
  | 'prereq.servers.validation.authUrlRequired'
  | 'prereq.servers.validation.credentialIdRequired'
  | 'prereq.servers.validation.novaEndpointRequired'
  | 'prereq.servers.validation.secretRequired';

interface CredentialsFormState {
  authUrl: string;
  credentialId: string;
  credentialSecret: string;
  novaEndpoint: string;
  caCertificate: string;
}

/**
 * Validate the credentials form before a retrieval is attempted.
 *
 * Retrieval is gated when any required non-secret field (auth URL, credential
 * id, Nova endpoint) is empty, or when the secret is empty while none is stored
 * server-side (`secretStored === false`). Returns the i18n key of the first
 * failing rule, or `null` when the form is valid.
 */
export const validateCredentialsForm = (
  state: CredentialsFormState,
  secretStored: boolean,
): CredentialsValidationKey | null => {
  if (!state.authUrl.trim()) return 'prereq.servers.validation.authUrlRequired';
  if (!state.credentialId.trim()) return 'prereq.servers.validation.credentialIdRequired';
  if (!state.novaEndpoint.trim()) return 'prereq.servers.validation.novaEndpointRequired';
  if (!state.credentialSecret.trim() && !secretStored) {
    return 'prereq.servers.validation.secretRequired';
  }
  return null;
};

/**
 * Build the save/retrieve payload from the current form state. The secret is
 * only included when the operator typed one; an empty secret is omitted so the
 * backend reuses the stored value.
 */
const toSaveRequest = (state: CredentialsFormState): SaveCredentialConfigRequest => {
  const request: SaveCredentialConfigRequest = {
    auth_url: state.authUrl.trim(),
    credential_id: state.credentialId.trim(),
    nova_endpoint: state.novaEndpoint.trim(),
    ca_certificate: state.caCertificate.trim(),
  };
  if (state.credentialSecret.trim()) {
    request.credential_secret = state.credentialSecret;
  }
  return request;
};

/** i18n keys for the error banner, keyed by the backend error code. */
type ErrorMessageKey =
  | 'prereq.servers.error.invalidCredentials'
  | 'prereq.servers.error.connection'
  | 'prereq.servers.error.openstack'
  | 'prereq.servers.error.invalidCaCertificate'
  | 'prereq.servers.error.generic';

/** Map a backend `ErrorResponse` code to the localized message key. */
const ERROR_CODE_TO_KEY: Record<string, ErrorMessageKey> = {
  AUTH_FAILED: 'prereq.servers.error.invalidCredentials',
  CONNECTION_FAILED: 'prereq.servers.error.connection',
  OPENSTACK_ERROR: 'prereq.servers.error.openstack',
  INVALID_CA_CERTIFICATE: 'prereq.servers.error.invalidCaCertificate',
};

/**
 * Extract the backend error code from an axios error. Router errors use the
 * shared `ErrorResponse.create(code, message, details)` contract, which the
 * app's exception handler unwraps to a top-level `{ error: { code } }` body;
 * the raw `{ detail: { error: { code } } }` shape is the fallback when the
 * handler is not applied. Returns `null` when no code can be found.
 */
const extractErrorCode = (error: unknown): string | null => {
  const data = (
    error as { response?: { data?: unknown } } | undefined
  )?.response?.data;
  if (!data || typeof data !== 'object') return null;
  const record = data as {
    error?: { code?: unknown };
    detail?: { error?: { code?: unknown } };
  };
  const topLevel = record.error?.code;
  if (typeof topLevel === 'string') return topLevel;
  const nested = record.detail?.error?.code;
  if (typeof nested === 'string') return nested;
  return null;
};

/** Resolve a backend error into the localized message key (with fallback). */
const toErrorMessageKey = (error: unknown): ErrorMessageKey => {
  const code = extractErrorCode(error);
  if (code && code in ERROR_CODE_TO_KEY) return ERROR_CODE_TO_KEY[code];
  return 'prereq.servers.error.generic';
};

/** i18n keys for the node-save error banner. */
type NodeErrorMessageKey =
  | 'prereq.servers.nodes.error.save'
  | 'prereq.servers.nodes.error.notFound';

/**
 * Map a backend error code to the node-save message key. `INSTALLATION_NOT_FOUND`
 * surfaces the not-found message; `DATABASE_ERROR` and any unknown/absent code
 * fall back to the generic save-failure message.
 */
const NODE_ERROR_CODE_TO_KEY: Record<string, NodeErrorMessageKey> = {
  INSTALLATION_NOT_FOUND: 'prereq.servers.nodes.error.notFound',
  DATABASE_ERROR: 'prereq.servers.nodes.error.save',
};

/** Resolve a node-save rejection into the localized message key (with fallback). */
const toNodeErrorMessageKey = (error: unknown): NodeErrorMessageKey => {
  const code = extractErrorCode(error);
  if (code && code in NODE_ERROR_CODE_TO_KEY) return NODE_ERROR_CODE_TO_KEY[code];
  return 'prereq.servers.nodes.error.save';
};

interface CredentialsFormProps {
  installationId: string;
}

/**
 * OpenStack credentials form shown above the static inventory when an
 * `installationId` is supplied. Collects the Keystone auth URL, credential id,
 * a masked write-only secret, and the Nova endpoint, and exposes a RETRIEVE
 * INFO button gated by client-side validation.
 *
 * On mount it prefills the non-secret fields from the stored config and records
 * whether a secret is already stored (so the secret field can stay optional).
 * The actual retrieval flow + live results are wired in task 9.2; this task
 * establishes the form, prefill, and validation, and leaves a clear hook for
 * that follow-up.
 */
const CredentialsForm = ({ installationId }: CredentialsFormProps) => {
  const { t } = useTranslation();
  const [form, setForm] = useState<CredentialsFormState>({
    authUrl: '',
    credentialId: '',
    credentialSecret: '',
    novaEndpoint: '',
    caCertificate: '',
  });
  const [secretStored, setSecretStored] = useState(false);
  const [validationKey, setValidationKey] = useState<CredentialsValidationKey | null>(
    null,
  );
  // Live-retrieval state. `servers` is null until the first successful
  // retrieve so the results table stays hidden while nothing has been fetched.
  const [loading, setLoading] = useState(false);
  const [errorKey, setErrorKey] = useState<ErrorMessageKey | null>(null);
  const [servers, setServers] = useState<NovaServer[] | null>(null);

  // Prefill non-secret fields on mount (and whenever the installation changes).
  // The secret is never returned by the backend; only `secret_stored` reports
  // whether one exists.
  useEffect(() => {
    let cancelled = false;
    prerequisitesService
      .loadCredentialConfig(installationId)
      .then((cfg) => {
        if (cancelled) return;
        setForm((prev) => ({
          ...prev,
          authUrl: cfg.auth_url ?? '',
          credentialId: cfg.credential_id ?? '',
          novaEndpoint: cfg.nova_endpoint ?? '',
          caCertificate: cfg.ca_certificate ?? '',
        }));
        setSecretStored(Boolean(cfg.secret_stored));
      })
      .catch(() => {
        // No stored config yet (or load failed): leave fields empty and treat
        // the secret as not stored so validation still requires one.
        if (!cancelled) setSecretStored(false);
      });
    return () => {
      cancelled = true;
    };
  }, [installationId]);

  const setField = (field: keyof CredentialsFormState) => (value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    // Clear a stale validation message as soon as the operator edits a field.
    setValidationKey(null);
  };

  const handleRetrieve = () => {
    const failure = validateCredentialsForm(form, secretStored);
    if (failure) {
      setValidationKey(failure);
      return;
    }
    if (loading) return; // Ignore re-clicks while a request is in flight.
    setValidationKey(null);
    setErrorKey(null);
    setLoading(true);

    // A single call persists the config (+ optional secret) and retrieves the
    // live server list; a successful response replaces any prior rows.
    prerequisitesService
      .retrieveServers(installationId, toSaveRequest(form))
      .then((result) => {
        setServers(result.servers ?? []);
        // The secret (if any) was just persisted server-side, so future
        // retrievals no longer require it.
        if (form.credentialSecret.trim()) setSecretStored(true);
      })
      .catch((error) => {
        setErrorKey(toErrorMessageKey(error));
      })
      .finally(() => {
        setLoading(false);
      });
  };

  const fields = useMemo(
    () =>
      [
        {
          id: 'openstack-auth-url',
          label: t('prereq.servers.credentials.authUrl'),
          key: 'authUrl' as const,
          type: 'text',
        },
        {
          id: 'openstack-credential-id',
          label: t('prereq.servers.credentials.credentialId'),
          key: 'credentialId' as const,
          type: 'text',
        },
        {
          id: 'openstack-credential-secret',
          label: t('prereq.servers.credentials.credentialSecret'),
          key: 'credentialSecret' as const,
          type: 'password',
        },
        {
          id: 'openstack-nova-endpoint',
          label: t('prereq.servers.credentials.novaEndpoint'),
          key: 'novaEndpoint' as const,
          type: 'text',
        },
      ] as const,
    [t],
  );

  return (
    <section className="mb-8 rounded border border-gray-200 bg-gray-50 p-4">
      <h3 className="mb-4 text-lg font-semibold text-[#000E9C]">
        {t('prereq.servers.credentials.title')}
      </h3>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {fields.map((field) => (
          <div key={field.id}>
            <label
              htmlFor={field.id}
              className="mb-1 block text-xs font-medium text-gray-500"
            >
              {field.label}
            </label>
            <input
              id={field.id}
              type={field.type}
              value={form[field.key]}
              onChange={(e) => setField(field.key)(e.target.value)}
              className={CRED_FIELD_CLASS}
            />
            {field.key === 'credentialSecret' && secretStored && (
              <p className="mt-1 text-xs text-green-700">
                {t('prereq.servers.credentials.secretStored')}
              </p>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4">
        <label
          htmlFor="openstack-ca-certificate"
          className="mb-1 block text-xs font-medium text-gray-500"
        >
          {t('prereq.servers.credentials.caCertificate')}
        </label>
        <textarea
          id="openstack-ca-certificate"
          rows={6}
          value={form.caCertificate}
          onChange={(e) => setField('caCertificate')(e.target.value)}
          className={`${CRED_FIELD_CLASS} font-mono`}
        />
      </div>

      {validationKey && (
        <p role="alert" className="mt-3 text-sm text-red-600">
          {t(validationKey)}
        </p>
      )}

      <div className="mt-4">
        <button
          type="button"
          onClick={handleRetrieve}
          disabled={loading}
          className="rounded bg-[#000E9C] px-4 py-2 text-sm font-semibold text-white hover:bg-[#000B7A] focus:outline-none focus:ring-2 focus:ring-[#4949FF] focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {t('prereq.servers.retrieve')}
        </button>
      </div>

      <LiveResultsSection loading={loading} errorKey={errorKey} servers={servers} />
    </section>
  );
};

interface LiveResultsSectionProps {
  loading: boolean;
  errorKey: ErrorMessageKey | null;
  /** `null` before the first retrieve; an array (possibly empty) afterwards. */
  servers: NovaServer[] | null;
}

/**
 * Live server-status output shown below the credentials form: a loading
 * indicator while a retrieve is pending, an error banner keyed by the backend
 * error code, or a table of `{ id, name, status }` rows once a retrieve
 * succeeds. Nothing renders before the first retrieval attempt.
 */
const LiveResultsSection = ({ loading, errorKey, servers }: LiveResultsSectionProps) => {
  const { t } = useTranslation();

  if (loading) {
    return (
      <p role="status" className="mt-4 text-sm text-gray-600">
        {t('prereq.servers.retrieving')}
      </p>
    );
  }

  if (errorKey) {
    return (
      <p role="alert" className="mt-4 rounded bg-red-50 px-3 py-2 text-sm text-red-700">
        {t(errorKey)}
      </p>
    );
  }

  if (servers === null) return null;

  return (
    <div className="mt-6">
      <h4 className="mb-3 text-base font-semibold text-[#000E9C]">
        {t('prereq.servers.results.title')}
      </h4>
      {servers.length === 0 ? (
        <p className="text-sm text-gray-500">{t('prereq.servers.results.empty')}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead>
              <tr>
                <th scope="col" className={HEAD_CELL}>
                  {t('prereq.servers.results.colId')}
                </th>
                <th scope="col" className={HEAD_CELL}>
                  {t('prereq.servers.results.colName')}
                </th>
                <th scope="col" className={HEAD_CELL}>
                  {t('prereq.servers.results.colStatus')}
                </th>
              </tr>
            </thead>
            <tbody>
              {servers.map((server) => (
                <tr key={server.id} className="hover:bg-gray-50">
                  <td className={BODY_CELL}>
                    <MonoCell value={server.id} />
                  </td>
                  <td className={BODY_CELL}>{server.name.trim() || PLACEHOLDER}</td>
                  <td className={BODY_CELL}>
                    <StatePill
                      value={server.status}
                      className={provisionStateClass(server.status)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

/**
 * Read-only inventory of server nodes for the "Servers nodes" prerequisites
 * tab. Coordinators consult it to pick an available Node UUID when filling in
 * the CloudStore / Core Control Plane forms.
 */
export const ServersTable = ({
  title,
  variant = 'card',
  nodes = SERVER_NODES,
  installationId,
}: ServersTableProps) => {
  const { t } = useTranslation();
  const embedded = variant === 'embedded';

  // Per-installation overrides layered over the default inventory. Loaded on
  // mount when an installation is in context; a load failure leaves the table
  // on defaults with no blocking error (defaults remain authoritative).
  const [nodesOverrides, setNodesOverrides] = useState<ServerNodeOverride[]>([]);

  // Node-save error banner key. Set on a rejected `saveServerNodes`, cleared on
  // the next successful save or the next edit.
  const [saveErrorKey, setSaveErrorKey] = useState<NodeErrorMessageKey | null>(
    null,
  );

  useEffect(() => {
    if (!installationId) {
      setNodesOverrides([]);
      return;
    }
    let cancelled = false;
    prerequisitesService
      .loadServerNodes(installationId)
      .then((response) => {
        if (cancelled) return;
        setNodesOverrides(response.nodes.map(toServerNodeOverride));
      })
      .catch(() => {
        // No stored overrides yet (or load failed): render the defaults.
        if (!cancelled) setNodesOverrides([]);
      });
    return () => {
      cancelled = true;
    };
  }, [installationId]);

  const mergedNodes = useMemo(
    () => mergeNodeOverrides(nodes, nodesOverrides),
    [nodes, nodesOverrides],
  );

  // Editing is enabled for members and administrators; visitors and
  // unauthenticated users get the read-only renderers. Resolved once from
  // `authService`: administrator via `isAdmin()`, member via the stored role.
  const isEditable =
    authService.isAdmin() || authService.getCurrentUser()?.role === 'member';

  // Per-row edit state, keyed by the row's default `nodeUuid` (the merge join
  // key, which is stable across edits). Kept in sync with the merged node
  // values so members/administrators start from the currently displayed data
  // and can edit any of the six fields as free text. The save call and
  // error banner are wired in a later task.
  const [editState, setEditState] = useState<Record<string, ServerNode>>({});

  useEffect(() => {
    const next: Record<string, ServerNode> = {};
    for (const node of mergedNodes) {
      next[node.nodeUuid] = { ...node };
    }
    setEditState(next);
  }, [mergedNodes]);

  const handleFieldChange = (
    rowKey: string,
    field: keyof ServerNode,
    value: string,
  ) => {
    // A fresh edit clears any stale save-failure banner.
    setSaveErrorKey(null);
    setEditState((prev) => {
      const current = prev[rowKey];
      if (!current) return prev;
      return { ...prev, [rowKey]: { ...current, [field]: value } };
    });
  };

  // Confirm an edit (blur/Enter): persist the full merged node list (with the
  // current edits applied) to the backend, scoped to the installation. On
  // success, store the returned overrides and clear the error banner; on
  // rejection, surface the mapped error key. No-op without an installation.
  const handleConfirm = () => {
    if (!installationId) return;
    const rows = mergedNodes.map((node) => editState[node.nodeUuid] ?? node);
    const payload = rows.map(toServerNodeOverridePayload);
    prerequisitesService
      .saveServerNodes(installationId, payload)
      .then((response) => {
        setNodesOverrides(response.nodes.map(toServerNodeOverride));
        setSaveErrorKey(null);
      })
      .catch((error) => {
        setSaveErrorKey(toNodeErrorMessageKey(error));
      });
  };

  const body = (
    <>
      {embedded ? (
        <h2 className="text-2xl font-bold text-[#000E9C] mb-5">{title}</h2>
      ) : (
        <h1 className="text-2xl font-bold text-[#000E9C] mb-5">{title}</h1>
      )}

      {saveErrorKey && (
        <p
          role="alert"
          className="mb-4 rounded bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {t(saveErrorKey)}
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr>
              <th scope="col" className={HEAD_CELL}>
                Node UUID
              </th>
              <th scope="col" className={HEAD_CELL}>
                Serial Number
              </th>
              <th scope="col" className={HEAD_CELL}>
                Instance UUID
              </th>
              <th scope="col" className={HEAD_CELL}>
                Power State
              </th>
              <th scope="col" className={HEAD_CELL}>
                Provision State
              </th>
              <th scope="col" className={HEAD_CELL}>
                Remark
              </th>
            </tr>
          </thead>
          <tbody>
            {mergedNodes.map((node) => {
              // For editable rows, read from edit state (falls back to the
              // merged node until the sync effect populates it).
              const row = editState[node.nodeUuid] ?? node;
              return (
                <tr key={node.nodeUuid} className="hover:bg-gray-50">
                  {isEditable ? (
                    <>
                      <td className={BODY_CELL}>
                        <EditableCell
                          label="Node UUID"
                          value={row.nodeUuid}
                          onChange={(v) =>
                            handleFieldChange(node.nodeUuid, 'nodeUuid', v)
                          }
                          onConfirm={handleConfirm}
                        />
                      </td>
                      <td className={BODY_CELL}>
                        <EditableCell
                          label="Serial Number"
                          value={row.serialNumber}
                          onChange={(v) =>
                            handleFieldChange(node.nodeUuid, 'serialNumber', v)
                          }
                          onConfirm={handleConfirm}
                        />
                      </td>
                      <td className={BODY_CELL}>
                        <EditableCell
                          label="Instance UUID"
                          value={row.instanceUuid}
                          onChange={(v) =>
                            handleFieldChange(node.nodeUuid, 'instanceUuid', v)
                          }
                          onConfirm={handleConfirm}
                        />
                      </td>
                      <td className={BODY_CELL}>
                        <EditableCell
                          label="Power State"
                          value={row.powerState}
                          onChange={(v) =>
                            handleFieldChange(node.nodeUuid, 'powerState', v)
                          }
                          onConfirm={handleConfirm}
                        />
                      </td>
                      <td className={BODY_CELL}>
                        <EditableCell
                          label="Provision State"
                          value={row.provisionState}
                          onChange={(v) =>
                            handleFieldChange(node.nodeUuid, 'provisionState', v)
                          }
                          onConfirm={handleConfirm}
                        />
                      </td>
                      <td className={BODY_CELL}>
                        <EditableCell
                          label="Remark"
                          value={row.remark}
                          onChange={(v) =>
                            handleFieldChange(node.nodeUuid, 'remark', v)
                          }
                          onConfirm={handleConfirm}
                        />
                      </td>
                    </>
                  ) : (
                    <>
                      <td className={BODY_CELL}>
                        <MonoCell value={node.nodeUuid} />
                      </td>
                      <td className={BODY_CELL}>
                        <MonoCell value={node.serialNumber} />
                      </td>
                      <td className={BODY_CELL}>
                        <MonoCell value={node.instanceUuid} />
                      </td>
                      <td className={BODY_CELL}>
                        <StatePill
                          value={node.powerState}
                          className={powerStateClass(node.powerState)}
                        />
                      </td>
                      <td className={BODY_CELL}>
                        <StatePill
                          value={node.provisionState}
                          className={provisionStateClass(node.provisionState)}
                        />
                      </td>
                      <td className={BODY_CELL}>
                        {node.remark.trim() ? (
                          node.remark
                        ) : (
                          <span className="text-gray-400">{PLACEHOLDER}</span>
                        )}
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {installationId && <CredentialsForm installationId={installationId} />}
    </>
  );

  if (embedded) {
    return body;
  }

  return <div className="card p-6">{body}</div>;
};
