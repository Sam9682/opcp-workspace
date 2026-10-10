import {
  prerequisitesService,
  type CredentialConfig,
  type Installation,
} from './prerequisitesService';
import {
  CHECKLIST_CATEGORIES,
  CONTEXT_CATEGORY,
  QA_CATEGORIES,
  SERVERS_NODES_SLUG,
} from '../components/prerequisites/checklistCategories';
import { SERVER_NODES, type ServerNode } from '../components/prerequisites/serversData';
import type {
  ContextConfig,
  ContextRow,
  QuestionFormConfig,
  QuestionRow,
} from '../components/prerequisites/types';
import type { Language } from '../i18n/translations';

/**
 * Installation export / import + architecture-document generation.
 *
 * The five prerequisites tabs are:
 *   - Network Checklist, Core Control Plane, CloudStore, VCF — question/answer
 *     tabs whose editable values are the per-row "Réponse client" strings,
 *     persisted server-side keyed by (installationId, slug, rowId).
 *   - Servers nodes — reference inventory plus a per-installation OpenStack
 *     credential config (the secret is never returned by the backend).
 *
 * Export gathers every tab's values into one JSON document. Import reads a
 * document in that same shape and writes each answer back. The architecture
 * document renders the tabs, their parameters + values, and the server-node
 * list into a self-contained, downloadable HTML file.
 */

/** Current export schema version. Bumped if the JSON shape changes. */
export const EXPORT_FORMAT_VERSION = 1;

/** JSON shape produced by {@link exportInstallation} and accepted by import. */
export interface InstallationExport {
  format: 'opcp-installation-export';
  version: number;
  exported_at: string;
  installation: {
    id: string;
    project_name: string;
  };
  /** Per-tab client answers: slug -> { rowId -> answer }. */
  tabs: Record<string, Record<string, string>>;
  /**
   * Servers-nodes tab data. Credentials contain no secret (never exported);
   * `nodes` is the reference inventory captured at export time.
   */
  servers: {
    credentials: {
      auth_url: string;
      credential_id: string;
      nova_endpoint: string;
      ca_certificate: string;
      secret_stored: boolean;
    } | null;
    nodes: ReadonlyArray<ServerNode>;
  };
}

/** Result of an import operation, so the caller can report a summary. */
export interface ImportResult {
  /** Number of individual answer values written. */
  written: number;
  /** Number of answer writes that failed. */
  failed: number;
  /** Tab slugs present in the file that are not known tabs (skipped). */
  unknownSlugs: string[];
}

// ---------------------------------------------------------------------------
// Download helper
// ---------------------------------------------------------------------------

/**
 * Trigger a browser download of `content` as `filename`. Uses an object URL +
 * synthetic anchor click — the portable way to offer a client-generated file
 * without a server round-trip.
 */
const downloadFile = (filename: string, content: string, mimeType: string): void => {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};

/** Slugify a project name into a safe filename fragment. */
const safeSlug = (name: string): string =>
  name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'installation';

/** Minimal HTML-escape for text interpolated into the architecture document. */
const escapeHtml = (value: string): string =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

/**
 * Build the export document for an installation by fetching every tab's saved
 * answers plus the servers-nodes credential config. Answer loads are done in
 * parallel; a failed tab load degrades to an empty answer map so the export
 * still succeeds for the remaining tabs.
 */
export const buildInstallationExport = async (
  installation: Installation,
): Promise<InstallationExport> => {
  const tabs: Record<string, Record<string, string>> = {};

  await Promise.all(
    QA_CATEGORIES.map(async (category) => {
      try {
        const response = await prerequisitesService.loadClientAnswers(
          installation.id,
          category.slug,
        );
        tabs[category.slug] = response.answers ?? {};
      } catch {
        tabs[category.slug] = {};
      }
    }),
  );

  // The context tab is answer-backed like the QA tabs but is not in
  // QA_CATEGORIES (its config is a ContextConfig), so load it explicitly.
  try {
    const r = await prerequisitesService.loadClientAnswers(
      installation.id,
      CONTEXT_CATEGORY.slug,
    );
    tabs[CONTEXT_CATEGORY.slug] = r.answers ?? {};
  } catch {
    tabs[CONTEXT_CATEGORY.slug] = {};
  }

  let credentials: InstallationExport['servers']['credentials'] = null;
  try {
    const cfg: CredentialConfig = await prerequisitesService.loadCredentialConfig(
      installation.id,
    );
    credentials = {
      auth_url: cfg.auth_url ?? '',
      credential_id: cfg.credential_id ?? '',
      nova_endpoint: cfg.nova_endpoint ?? '',
      ca_certificate: cfg.ca_certificate ?? '',
      secret_stored: Boolean(cfg.secret_stored),
    };
  } catch {
    // No stored credential config (or load failed) — leave null.
    credentials = null;
  }

  return {
    format: 'opcp-installation-export',
    version: EXPORT_FORMAT_VERSION,
    exported_at: new Date().toISOString(),
    installation: {
      id: installation.id,
      project_name: installation.project_name,
    },
    tabs,
    servers: {
      credentials,
      nodes: SERVER_NODES,
    },
  };
};

/**
 * Export all values across every tab as a downloaded JSON file. The file name
 * embeds the project name and export date.
 */
export const exportInstallation = async (installation: Installation): Promise<void> => {
  const data = await buildInstallationExport(installation);
  const date = data.exported_at.slice(0, 10);
  const filename = `${safeSlug(installation.project_name)}-export-${date}.json`;
  downloadFile(filename, `${JSON.stringify(data, null, 2)}\n`, 'application/json');
};

// ---------------------------------------------------------------------------
// CloudStore service VCF descriptors (control plane / data plane)
// ---------------------------------------------------------------------------

/**
 * Fixed-format "data plane" descriptor downloaded as
 * `cloudstore-service-vcf-9.0.2-dataplane-0.13.3.json`. The shape and default
 * values are defined by the CloudStore VCF service; keys are intentionally
 * ordered to match the reference template.
 */
export const CLOUDSTORE_VCF_DATAPLANE_FILENAME =
  'cloudstore-service-vcf-9.0.2-dataplane-0.13.3.json';

export const CLOUDSTORE_VCF_DATAPLANE_TEMPLATE: Record<string, unknown> = {
  dns_create_records: true,
  esxi_install_timeout: '2100',
  lacp: false,
  openstack_auth_type: 'v3applicationcredential',
  openstack_endpoint_type: 'internal',
  openstack_identity_api_version: '3',
  overlay_subnet_range: '10.105.49.0/24',
  overlay_vlan_id: '2049',
  pairing_source: 'pci',
  vcf_external_network_id: '3f53dd45-0d9b-49d5-bf4d-c274f62e033c',
  vcf_overlay_network_id: '63ed4ef0-6be8-4279-8265-4769ea9f08de',
  vcf_overlay_subnet_id: '6b42d489-d264-4778-8375-4914d7046b7a',
  vcf_vmotion_network_id: '190b5a71-aa7a-4bbb-9687-bfea79d97d4f',
  vcf_vmotion_subnet_id: 'b41e2328-ef80-4692-a5d3-22baea429482',
  vcf_vsan_network_id: '8cb0fee6-9589-42f2-8cf5-7a7e9c206612',
  vcf_vsan_subnet_id: 'f9518eff-c94a-4e19-8eac-f2baf4a54b81',
  vmotion_subnet_range: '10.105.47.0/24',
  vmotion_vlan_id: '2047',
  vsan_subnet_range: '10.105.48.0/24',
  vsan_vlan_id: '2048',
  workload_domain_num: '1',
};

/**
 * Fixed-format "control plane" descriptor downloaded as
 * `cloudstore-service-vcf-9.0.2-controlplane-0.13.3.json`. The shape and
 * default values are defined by the CloudStore VCF service; keys are
 * intentionally ordered to match the reference template.
 */
export const CLOUDSTORE_VCF_CONTROLPLANE_FILENAME =
  'cloudstore-service-vcf-9.0.2-controlplane-0.13.3.json';

export const CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE: Record<string, unknown> = {
  appliance_password: 'ChangeMe',
  appliance_xapikey: 'ChangeMe',
  bootstrap_dns_server: '192.168.220.47',
  customer_network_dhcp_ip: '192.168.220.2',
  customer_network_name: 'customerapi-network',
  debug: true,
  dns_create_records: true,
  dns_server: '10.105.40.3',
  dns_zone: 'internal.cloudstore.ovh',
  esxi_install_timeout: '2100',
  esxi_root_password: 'ChangeMe',
  esxi_setup_script: 'true',
  external_network_id: 'dbe8c824-9b43-47df-a6df-0bfc19fdecf7',
  flavor_name: 'vcf_no_sb',
  image_name: 'esxi-9.0.2-user-data',
  keycloak_clusterissuer: 'customer-issuer',
  keycloak_request_cpu: '500m',
  keycloak_request_memory: '1024Mi',
  lacp: false,
  ntp_server: '10.105.40.3',
  openstack_auth_type: 'v3applicationcredential',
  openstack_endpoint_type: 'internal',
  openstack_identity_api_version: '3',
  overlay_network_id: '966eb2ae-ad79-4d86-baf9-45164a511c2c',
  overlay_subnet_id: 'ee7ffa41-a3cc-48b8-887f-ea7bf4f3b5d8',
  overlay_subnet_range: '10.105.46.0/24',
  overlay_vlan_id: '2046',
  pairing_source: 'pci',
  vcf_deployer_ip: '192.168.220.8',
  vcf_deployer_url:
    'http://vcf-ova.vcf-ova.svc.cluster.local/vcf_deployer-all_in_one-9.0.2.0-v0.1.6.ova',
  vcf_master_password: 'ChangeMe',
  vcf_mgmt_dhcp_ip: '10.105.42.1',
  vcf_mgmt_network_name: 'vcf_network',
  vcf_mgmt_network_vlan_id: '2197',
  vcf_mgmt_subnet_name: 'mgmt',
  vcf_subdomain: 'vcf',
  vmotion_network_id: '2658f685-1517-43ce-8973-e6435505962c',
  vmotion_subnet_id: 'b9b8ea36-13d0-4891-9466-e90bd557d2b0',
  vmotion_subnet_range: '10.105.44.0/24',
  vmotion_vlan_id: '2044',
  vsan_network_id: '9da037a3-6860-4d08-9261-3094b9e299bf',
  vsan_subnet_id: 'be6b78ff-4a96-452b-9821-7071d626e7a8',
  vsan_subnet_range: '10.105.45.0/24',
  vsan_vlan_id: '2045',
};

/**
 * Download the CloudStore VCF data-plane descriptor as a JSON file. The content
 * is the fixed {@link CLOUDSTORE_VCF_DATAPLANE_TEMPLATE} rendered with two-space
 * indentation and a trailing newline, matching the other JSON exports.
 */
export const generateCloudStoreVcfDataPlane = (): void => {
  downloadFile(
    CLOUDSTORE_VCF_DATAPLANE_FILENAME,
    `${JSON.stringify(CLOUDSTORE_VCF_DATAPLANE_TEMPLATE, null, 2)}\n`,
    'application/json',
  );
};

/**
 * Download the CloudStore VCF control-plane descriptor as a JSON file. The
 * content is the fixed {@link CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE} rendered
 * with two-space indentation and a trailing newline.
 */
export const generateCloudStoreVcfControlPlane = (): void => {
  downloadFile(
    CLOUDSTORE_VCF_CONTROLPLANE_FILENAME,
    `${JSON.stringify(CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE, null, 2)}\n`,
    'application/json',
  );
};

// ---------------------------------------------------------------------------
// Import
// ---------------------------------------------------------------------------

/**
 * Parse and validate a raw import-file string into an {@link InstallationExport}.
 * Throws an Error with a stable code-like message when the file is not valid
 * JSON or does not match the expected export shape.
 */
export const parseImportFile = (raw: string): InstallationExport => {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error('INVALID_JSON');
  }

  if (!parsed || typeof parsed !== 'object') {
    throw new Error('INVALID_SHAPE');
  }

  const record = parsed as Partial<InstallationExport>;
  if (record.format !== 'opcp-installation-export') {
    throw new Error('INVALID_FORMAT');
  }
  if (!record.tabs || typeof record.tabs !== 'object') {
    throw new Error('INVALID_SHAPE');
  }

  return parsed as InstallationExport;
};

/**
 * Apply the answers from an imported document to an installation. Writes every
 * `(slug, rowId) -> answer` pair via the prerequisites service, restricting to
 * the known QA tabs and to row ids that exist in each tab's config so a stale
 * or hand-edited file cannot create orphan answers. Unknown slugs are reported
 * back rather than silently ignored.
 *
 * Note: the servers-nodes tab is reference/credential data and is intentionally
 * not written on import (the secret is never present in the file, and the node
 * inventory is read-only).
 */
export const importInstallation = async (
  installationId: string,
  data: InstallationExport,
): Promise<ImportResult> => {
  // Build slug -> Set(validRowIds) from the shared configs so we only write
  // answers that map to a real row.
  const validRowIdsBySlug = new Map<string, Set<string>>();
  for (const category of QA_CATEGORIES) {
    const config = category.config as QuestionFormConfig;
    const ids = new Set<string>();
    for (const section of config.sections) {
      for (const row of section.rows) ids.add(row.id);
    }
    validRowIdsBySlug.set(category.slug, ids);
  }

  // The context tab is not in QA_CATEGORIES, so add its valid row ids
  // explicitly, flattening sections and nested subsections into one id set.
  const contextIds = new Set<string>();
  for (const section of (CONTEXT_CATEGORY.config as ContextConfig).sections) {
    for (const row of section.rows ?? []) contextIds.add(row.id);
    for (const sub of section.subsections ?? [])
      for (const row of sub.rows) contextIds.add(row.id);
  }
  validRowIdsBySlug.set(CONTEXT_CATEGORY.slug, contextIds);

  let written = 0;
  let failed = 0;
  const unknownSlugs: string[] = [];

  for (const [slug, answers] of Object.entries(data.tabs ?? {})) {
    if (slug === SERVERS_NODES_SLUG) continue; // reference tab, nothing to write
    const validIds = validRowIdsBySlug.get(slug);
    if (!validIds) {
      unknownSlugs.push(slug);
      continue;
    }
    if (!answers || typeof answers !== 'object') continue;

    // Write sequentially per tab to keep server write pressure modest and make
    // partial-failure counting deterministic.
    for (const [rowId, answer] of Object.entries(answers)) {
      if (!validIds.has(rowId)) continue;
      const value = answer == null ? '' : String(answer);
      try {
        await prerequisitesService.saveClientAnswer(installationId, slug, rowId, value);
        written += 1;
      } catch {
        failed += 1;
      }
    }
  }

  return { written, failed, unknownSlugs };
};

// ---------------------------------------------------------------------------
// Clear all values
// ---------------------------------------------------------------------------

/** Result of a clear-all-values operation, so the caller can report a summary. */
export interface ClearResult {
  /** Number of individual answer values cleared. */
  cleared: number;
  /** Number of answer clears that failed. */
  failed: number;
}

/**
 * Clear every parameter value across all question/answer tabs (Network
 * Checklist, Core Control Plane, CloudStore, VCF) for an installation by
 * writing an empty answer to every known row. The servers-nodes tab is
 * reference/credential data and is intentionally left untouched, mirroring
 * {@link importInstallation}.
 *
 * Rows are cleared sequentially per tab to keep server write pressure modest
 * and make partial-failure counting deterministic.
 */
export const clearInstallationValues = async (
  installationId: string,
): Promise<ClearResult> => {
  let cleared = 0;
  let failed = 0;

  for (const category of QA_CATEGORIES) {
    const config = category.config as QuestionFormConfig;
    for (const section of config.sections) {
      for (const row of section.rows) {
        try {
          await prerequisitesService.saveClientAnswer(
            installationId,
            category.slug,
            row.id,
            '',
          );
          cleared += 1;
        } catch {
          failed += 1;
        }
      }
    }
  }

  // The context tab is not in QA_CATEGORIES; clear every context row id
  // (across all sections and nested subsections) to '' explicitly.
  for (const section of (CONTEXT_CATEGORY.config as ContextConfig).sections) {
    const rows = [
      ...(section.rows ?? []),
      ...(section.subsections ?? []).flatMap((s) => s.rows),
    ];
    for (const row of rows) {
      try {
        await prerequisitesService.saveClientAnswer(
          installationId,
          CONTEXT_CATEGORY.slug,
          row.id,
          '',
        );
        cleared += 1;
      } catch {
        failed += 1;
      }
    }
  }

  return { cleared, failed };
};

// ---------------------------------------------------------------------------
// Architecture document
// ---------------------------------------------------------------------------

/**
 * Per-language vocabulary for the architecture document's static strings.
 *
 * These are export-document labels, not app UI strings, so they live here in
 * the service (keyed only by the shared {@link Language} type) rather than in
 * the shared i18n dictionaries. That keeps the service pure and unit-testable
 * and avoids coupling it to React/i18n. Node-table column headers (Node UUID,
 * Serial Number, …) are technical identifiers and are intentionally NOT part
 * of this map — they render as-is in both languages.
 */
interface DocLabels {
  // Chrome
  htmlLang: string;
  title: string;
  agent: string;
  summary: string;
  projectLabel: string;
  generatedOnLabel: string;
  footerGeneratedBy: string;
  // QA table header
  paramQuestion: string;
  value: string;
  comments: string;
  // Servers section
  serversNodes: string;
  openstackConfig: string;
  nodeInventory: string;
  authUrl: string;
  credentialId: string;
  novaEndpoint: string;
  caCertificate: string;
  secret: string;
  secretStored: string;
  secretNotConfigured: string;
  noOpenstackConfig: string;
}

/** Document label vocabulary per supported language. */
const DOC_LABELS: Record<Language, DocLabels> = {
  fr: {
    htmlLang: 'fr',
    title: "Document d'architecture",
    agent: 'Export Agent',
    summary: 'Sommaire',
    projectLabel: 'Projet',
    generatedOnLabel: 'Généré le',
    footerGeneratedBy: 'Généré par',
    paramQuestion: 'Paramètre / Question',
    value: 'Valeur',
    comments: 'Commentaires',
    serversNodes: 'Servers nodes',
    openstackConfig: 'Configuration OpenStack',
    nodeInventory: 'Inventaire des nœuds serveurs',
    authUrl: 'Auth URL',
    credentialId: 'Credential ID',
    novaEndpoint: 'Nova endpoint',
    caCertificate: 'Certificat CA',
    secret: 'Secret',
    secretStored: 'Enregistré (non exporté)',
    secretNotConfigured: 'Non configuré',
    noOpenstackConfig: 'Aucune configuration OpenStack enregistrée.',
  },
  en: {
    htmlLang: 'en',
    title: 'Architecture document',
    agent: 'Export Agent',
    summary: 'Summary',
    projectLabel: 'Project',
    generatedOnLabel: 'Generated on',
    footerGeneratedBy: 'Generated by',
    paramQuestion: 'Parameter / Question',
    value: 'Value',
    comments: 'Comments / Details',
    serversNodes: 'Servers nodes',
    openstackConfig: 'OpenStack configuration',
    nodeInventory: 'Server node inventory',
    authUrl: 'Auth URL',
    credentialId: 'Credential ID',
    novaEndpoint: 'Nova endpoint',
    caCertificate: 'CA certificate',
    secret: 'Secret',
    secretStored: 'Stored (not exported)',
    secretNotConfigured: 'Not configured',
    noOpenstackConfig: 'No OpenStack configuration saved.',
  },
};

/** Render one question row into a table row of the architecture document. */
const renderRow = (row: QuestionRow, answer: string | undefined): string => {
  const marker = row.mandatory ? '🔴' : '⚪';
  const value = (answer ?? '').trim();
  const valueCell = value
    ? escapeHtml(value)
    : '<span class="muted">—</span>';
  const comments = row.commentsHint ?? '';
  return `
        <tr>
          <td class="marker">${marker}</td>
          <td>
            <div class="q">${escapeHtml(row.questionPrimary)}</div>
            ${row.questionSecondary ? `<div class="q2">${escapeHtml(row.questionSecondary)}</div>` : ''}
          </td>
          <td class="value">${valueCell}</td>
          ${comments ? `<td class="example">${escapeHtml(comments)}</td>` : '<td class="example muted">—</td>'}
        </tr>`;
};

/** Render one QA tab (config + answers) into a section of the document. */
const renderQaSection = (
  title: string,
  config: QuestionFormConfig,
  answers: Record<string, string>,
  labels: DocLabels,
): string => {
  const sections = config.sections
    .map((section) => {
      const rows = section.rows
        .map((row) => renderRow(row, answers[row.id]))
        .join('');
      return `
      <h3>${escapeHtml(section.title)}</h3>
      <table>
        <thead>
          <tr>
            <th class="marker"></th>
            <th>${labels.paramQuestion}</th>
            <th>${labels.value}</th>
            <th>${labels.comments}</th>
          </tr>
        </thead>
        <tbody>${rows}
        </tbody>
      </table>`;
    })
    .join('');

  return `
    <section>
      <h2>${escapeHtml(title)}</h2>
      ${sections}
    </section>`;
};

/**
 * Render the OPCP Context tab (config + answers) into a section of the
 * document. Each section renders an `<h3>` heading with a two-column
 * (label / value) table for its direct rows, and for each subsection an
 * `<h4>` heading above its own label/value table. Every value cell resolves
 * to `answers[row.id] ?? row.defaultValue`, escaped via {@link escapeHtml}.
 */
const renderContextSection = (
  config: ContextConfig,
  answers: Record<string, string>,
  labels: DocLabels,
): string => {
  const renderRowsTable = (rows: ContextRow[]): string => {
    const body = rows
      .map((row) => {
        const value = answers[row.id] ?? row.defaultValue;
        const valueCell = value
          ? escapeHtml(value)
          : '<span class="muted">—</span>';
        return `
        <tr>
          <td>${escapeHtml(row.label)}</td>
          <td class="value">${valueCell}</td>
        </tr>`;
      })
      .join('');
    return `
      <table>
        <thead>
          <tr>
            <th>${labels.paramQuestion}</th>
            <th>${labels.value}</th>
          </tr>
        </thead>
        <tbody>${body}
        </tbody>
      </table>`;
  };

  const sections = config.sections
    .map((section) => {
      const directRows = section.rows ?? [];
      const directTable = directRows.length ? renderRowsTable(directRows) : '';
      const subsections = (section.subsections ?? [])
        .map(
          (sub) => `
      <h4>${escapeHtml(sub.title)}</h4>
      ${renderRowsTable(sub.rows)}`,
        )
        .join('');
      return `
      <h3>${escapeHtml(section.title)}</h3>
      ${directTable}${subsections}`;
    })
    .join('');

  return `
    <section>
      <h2>${escapeHtml(CONTEXT_CATEGORY.title)}</h2>
      ${sections}
    </section>`;
};

/** Render the server-node inventory into a section of the document. */
const renderServersSection = (
  nodes: ReadonlyArray<ServerNode>,
  credentials: InstallationExport['servers']['credentials'],
  labels: DocLabels,
): string => {
  const rows = nodes
    .map(
      (node) => `
        <tr>
          <td class="mono">${escapeHtml(node.nodeUuid)}</td>
          <td class="mono">${escapeHtml(node.serialNumber)}</td>
          <td class="mono">${node.instanceUuid ? escapeHtml(node.instanceUuid) : '<span class="muted">—</span>'}</td>
          <td>${escapeHtml(node.powerState) || '<span class="muted">—</span>'}</td>
          <td>${escapeHtml(node.provisionState) || '<span class="muted">—</span>'}</td>
          <td>${node.remark ? escapeHtml(node.remark) : '<span class="muted">—</span>'}</td>
        </tr>`,
    )
    .join('');

  const credBlock = credentials
    ? `
      <table class="cred">
        <tbody>
          <tr><th>${labels.authUrl}</th><td class="mono">${escapeHtml(credentials.auth_url) || '<span class="muted">—</span>'}</td></tr>
          <tr><th>${labels.credentialId}</th><td class="mono">${escapeHtml(credentials.credential_id) || '<span class="muted">—</span>'}</td></tr>
          <tr><th>${labels.novaEndpoint}</th><td class="mono">${escapeHtml(credentials.nova_endpoint) || '<span class="muted">—</span>'}</td></tr>
          <tr><th>${labels.caCertificate}</th><td class="mono">${credentials.ca_certificate ? escapeHtml(credentials.ca_certificate) : '<span class="muted">—</span>'}</td></tr>
          <tr><th>${labels.secret}</th><td>${credentials.secret_stored ? labels.secretStored : labels.secretNotConfigured}</td></tr>
        </tbody>
      </table>`
    : `<p class="muted">${labels.noOpenstackConfig}</p>`;

  return `
    <section>
      <h2>${labels.serversNodes}</h2>
      <h3>${labels.openstackConfig}</h3>
      ${credBlock}
      <h3>${labels.nodeInventory}</h3>
      <table>
        <thead>
          <tr>
            <th>Node UUID</th>
            <th>Serial Number</th>
            <th>Instance UUID</th>
            <th>Power State</th>
            <th>Provision State</th>
            <th>Remark</th>
          </tr>
        </thead>
        <tbody>${rows}
        </tbody>
      </table>
    </section>`;
};

/**
 * Assemble the full architecture-document HTML string in the given language.
 * `language` defaults to French so callers (and legacy tests) that omit it get
 * the original French document.
 */
export const buildArchitectureDocumentHtml = (
  data: InstallationExport,
  language: Language = 'fr',
): string => {
  const labels = DOC_LABELS[language];
  const generatedAt = new Date().toLocaleString();
  // The context tab is not in QA_CATEGORIES; render it explicitly, before the
  // QA sections, to match its position as the first checklist category.
  const contextSection = renderContextSection(
    CONTEXT_CATEGORY.config as ContextConfig,
    data.tabs[CONTEXT_CATEGORY.slug] ?? {},
    labels,
  );
  const qaSections = QA_CATEGORIES.map((category) =>
    renderQaSection(
      category.title,
      category.config as QuestionFormConfig,
      data.tabs[category.slug] ?? {},
      labels,
    ),
  ).join('');
  const serversSection = renderServersSection(
    data.servers.nodes,
    data.servers.credentials,
    labels,
  );

  const toc = CHECKLIST_CATEGORIES.map(
    (category) => `<li>${escapeHtml(category.title)}</li>`,
  ).join('');

  return `<!DOCTYPE html>
<html lang="${labels.htmlLang}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${labels.title} — ${escapeHtml(data.installation.project_name)}</title>
<style>
  :root { --brand: #000E9C; --brand2: #4949FF; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1f2937; margin: 0; padding: 0; background: #fff; }
  .wrap { max-width: 960px; margin: 0 auto; padding: 40px 32px; }
  header { border-bottom: 4px solid var(--brand); padding-bottom: 16px; margin-bottom: 24px; }
  .agent { font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--brand2); font-weight: 700; }
  h1 { color: var(--brand); font-size: 28px; margin: 6px 0 4px; }
  .meta { color: #6b7280; font-size: 13px; }
  nav { background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 20px; margin-bottom: 28px; }
  nav h4 { margin: 0 0 6px; color: var(--brand); font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; }
  nav ol { margin: 0; padding-left: 20px; color: #374151; font-size: 14px; }
  section { margin-bottom: 36px; }
  h2 { color: var(--brand); font-size: 20px; border-bottom: 2px solid #e5e7eb; padding-bottom: 6px; margin-top: 32px; }
  h3 { color: #111827; font-size: 15px; margin: 20px 0 8px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 12px; font-size: 13px; }
  th, td { border: 1px solid #e5e7eb; padding: 7px 9px; text-align: left; vertical-align: top; }
  thead th { background: #eef2ff; color: var(--brand); font-size: 12px; text-transform: uppercase; letter-spacing: 0.03em; }
  td.marker, th.marker { width: 28px; text-align: center; }
  td.value { font-weight: 600; color: #111827; width: 24%; }
  td.example { color: #6b7280; width: 26%; }
  .q { font-weight: 600; color: #1f2937; }
  .q2 { color: #6b7280; font-size: 12px; margin-top: 2px; }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; word-break: break-all; }
  .muted { color: #9ca3af; }
  table.cred th { background: #f8fafc; width: 160px; color: #374151; }
  footer { border-top: 1px solid #e5e7eb; margin-top: 40px; padding-top: 14px; color: #9ca3af; font-size: 12px; text-align: center; }
  @media print { .wrap { padding: 0; } nav { break-inside: avoid; } section { break-inside: avoid-page; } }
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="agent">${labels.agent}</div>
      <h1>${labels.title}</h1>
      <div class="meta">
        ${labels.projectLabel} : <strong>${escapeHtml(data.installation.project_name)}</strong><br />
        ${labels.generatedOnLabel} : ${escapeHtml(generatedAt)}
      </div>
    </header>

    <nav>
      <h4>${labels.summary}</h4>
      <ol>${toc}</ol>
    </nav>

    ${contextSection}${qaSections}${serversSection}

    <footer>
      ${labels.footerGeneratedBy} ${labels.agent} · OPCP · ${escapeHtml(data.exported_at.slice(0, 10))}
    </footer>
  </div>
</body>
</html>`;
};

/**
 * Generate and download the "Export Agent" architecture document for
 * an installation. It fetches the current values across every tab (reusing the
 * export builder) and renders them, together with the server-node list, into a
 * self-contained HTML file the browser downloads.
 */
export const generateArchitectureDocument = async (
  installation: Installation,
  language: Language = 'fr',
): Promise<void> => {
  const data = await buildInstallationExport(installation);
  const date = data.exported_at.slice(0, 10);
  const filename = `${safeSlug(installation.project_name)}-architecture-${date}.html`;
  downloadFile(
    filename,
    buildArchitectureDocumentHtml(data, language),
    'text/html;charset=utf-8',
  );
};
