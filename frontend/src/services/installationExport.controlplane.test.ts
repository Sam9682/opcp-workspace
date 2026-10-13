import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import {
  CLOUDSTORE_VCF_CONTROLPLANE_FILENAME,
  CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE,
  CLOUDSTORE_VCF_DATAPLANE_FILENAME,
  CLOUDSTORE_VCF_DATAPLANE_TEMPLATE,
  CONTROLPLANE_KEY_TO_ROW_ID,
  DATAPLANE_KEY_TO_ROW_ID,
  applyAnswersToTemplate,
  generateCloudStoreVcfControlPlane,
  generateCloudStoreVcfDataPlane,
} from './installationExport';
import { prerequisitesService, type Installation } from './prerequisitesService';

// ---------------------------------------------------------------------------
// BUG 2 — "Generate control plane file" must export the installation's RECORDED
// answers, overriding the static template defaults, not the fixed template.
//
// The generators start from the service template (preserving its exact key set,
// ordering, and the two-space-indent + trailing-newline formatting + filename)
// and override each mapped key with the recorded VCF answer when the user
// provided a non-empty value; template defaults are kept where no answer maps
// or the answer is empty.
// ---------------------------------------------------------------------------

const INSTALLATION: Installation = {
  id: '55555555-5555-5555-5555-555555555555',
  project_name: 'CP Project',
  created_at: '2026-02-01T00:00:00.000Z',
  updated_at: '2026-02-01T00:00:00.000Z',
};

/**
 * Capture the single downloaded file (filename + text content) produced by the
 * generator under test. `downloadFile` builds a Blob, calls
 * `URL.createObjectURL`, and clicks a synthetic anchor; we neutralize the DOM
 * side effects and read the Blob's text.
 */
async function captureDownload(
  run: () => Promise<void>,
): Promise<{ filename: string; content: string }> {
  let capturedBlob: Blob | null = null;
  let capturedFilename = '';

  const originalCreate = URL.createObjectURL;
  const originalRevoke = URL.revokeObjectURL;
  (URL as unknown as { createObjectURL: (b: Blob) => string }).createObjectURL = (
    blob: Blob,
  ) => {
    capturedBlob = blob;
    return 'blob:mock';
  };
  (URL as unknown as { revokeObjectURL: () => void }).revokeObjectURL = () => {};

  const realCreateElement = document.createElement.bind(document);
  const spy = vi
    .spyOn(document, 'createElement')
    .mockImplementation((tag: string) => {
      const el = realCreateElement(tag) as HTMLElement;
      if (tag === 'a') {
        Object.defineProperty(el, 'download', {
          configurable: true,
          set(v: string) {
            capturedFilename = v;
          },
          get() {
            return capturedFilename;
          },
        });
        (el as HTMLAnchorElement).click = () => {};
      }
      return el;
    });

  try {
    await run();
  } finally {
    spy.mockRestore();
    URL.createObjectURL = originalCreate;
    URL.revokeObjectURL = originalRevoke;
  }

  if (!capturedBlob) throw new Error('no file was downloaded');
  const content = await (capturedBlob as Blob).text();
  return { filename: capturedFilename, content };
}

beforeEach(() => {
  vi.restoreAllMocks();
  // No credential config needed for these descriptors; let it reject so the
  // export builder degrades gracefully.
  vi.spyOn(prerequisitesService, 'loadCredentialConfig').mockRejectedValue(
    new Error('no config'),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

/** Stub loadClientAnswers so only the `vcf` tab returns the given answers. */
function mockVcfAnswers(answers: Record<string, string>) {
  vi.spyOn(prerequisitesService, 'loadClientAnswers').mockImplementation(
    async (_installationId: string, slug: string) =>
      ({ slug, answers: slug === 'vcf' ? answers : {} }) as never,
  );
}

describe('applyAnswersToTemplate', () => {
  it('overrides mapped keys with non-empty answers and keeps defaults otherwise', () => {
    const template = { a: 'default-a', b: 'default-b', c: true };
    const keyMap = { a: 'row-a', b: 'row-b' };
    const answers = { 'row-a': 'answered-a', 'row-b': '   ' };

    const output = applyAnswersToTemplate(template, keyMap, answers);

    // Mapped key with a non-empty answer is overridden.
    expect(output.a).toBe('answered-a');
    // Mapped key whose answer is whitespace-only keeps the template default.
    expect(output.b).toBe('default-b');
    // Unmapped key keeps its typed default.
    expect(output.c).toBe(true);
    // Key set and ordering preserved.
    expect(Object.keys(output)).toEqual(['a', 'b', 'c']);
  });
});

describe('generateCloudStoreVcfControlPlane — real recorded data overrides the template', () => {
  it('overrides mapped keys with stored answers and falls back to template defaults', async () => {
    mockVcfAnswers({
      'vcf-mgmt-dns-server': '10.0.0.9',
      'vcf-mgmt-appliance-password': 'Sup3rSecret',
    });

    const { filename, content } = await captureDownload(() =>
      generateCloudStoreVcfControlPlane(INSTALLATION),
    );

    // Filename unchanged.
    expect(filename).toBe(CLOUDSTORE_VCF_CONTROLPLANE_FILENAME);
    // Two-space indent + trailing newline formatting unchanged.
    expect(content.endsWith('\n')).toBe(true);
    expect(content).toContain('\n  "appliance_password"');

    const parsed = JSON.parse(content) as Record<string, unknown>;

    // Stored answers override the template defaults at the mapped keys.
    expect(parsed.dns_server).toBe('10.0.0.9');
    expect(parsed.appliance_password).toBe('Sup3rSecret');
    // A mapped key with no stored answer keeps the template default.
    expect(parsed.ntp_server).toBe(CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE.ntp_server);
    // An unmapped key keeps the template default (and its original type).
    expect(parsed.pairing_source).toBe(CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE.pairing_source);
    expect(parsed.debug).toBe(CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE.debug);

    // The full template key set and ordering are preserved.
    expect(Object.keys(parsed)).toEqual(
      Object.keys(CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE),
    );
  });

  it('reproduces the template verbatim when no answers are stored', async () => {
    mockVcfAnswers({});

    const { content } = await captureDownload(() =>
      generateCloudStoreVcfControlPlane(INSTALLATION),
    );

    expect(content).toBe(
      `${JSON.stringify(CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE, null, 2)}\n`,
    );
  });
});

describe('generateCloudStoreVcfDataPlane — real recorded data overrides the template', () => {
  it('overrides mapped keys with stored answers and falls back to template defaults', async () => {
    mockVcfAnswers({
      'vcf-wld-workload-domain-num': '3',
      'vcf-wld-overlay-vlan-id': '2222',
    });

    const { filename, content } = await captureDownload(() =>
      generateCloudStoreVcfDataPlane(INSTALLATION),
    );

    expect(filename).toBe(CLOUDSTORE_VCF_DATAPLANE_FILENAME);
    expect(content.endsWith('\n')).toBe(true);

    const parsed = JSON.parse(content) as Record<string, unknown>;

    expect(parsed.workload_domain_num).toBe('3');
    expect(parsed.overlay_vlan_id).toBe('2222');
    // Unmapped key keeps the template default.
    expect(parsed.pairing_source).toBe(CLOUDSTORE_VCF_DATAPLANE_TEMPLATE.pairing_source);
    expect(parsed.lacp).toBe(CLOUDSTORE_VCF_DATAPLANE_TEMPLATE.lacp);

    expect(Object.keys(parsed)).toEqual(
      Object.keys(CLOUDSTORE_VCF_DATAPLANE_TEMPLATE),
    );
  });
});

describe('mapping tables only reference real template keys', () => {
  it('every control-plane mapping key exists in the control-plane template', () => {
    for (const key of Object.keys(CONTROLPLANE_KEY_TO_ROW_ID)) {
      expect(CLOUDSTORE_VCF_CONTROLPLANE_TEMPLATE).toHaveProperty(key);
    }
  });

  it('every data-plane mapping key exists in the data-plane template', () => {
    for (const key of Object.keys(DATAPLANE_KEY_TO_ROW_ID)) {
      expect(CLOUDSTORE_VCF_DATAPLANE_TEMPLATE).toHaveProperty(key);
    }
  });
});
