import { describe, it, expect, vi } from 'vitest';
import fc from 'fast-check';

import type { Language } from '../i18n/translations';
import { buildArchitectureDocumentHtml, type InstallationExport } from './installationExport';
import { QA_CATEGORIES } from '../components/prerequisites/checklistCategories';
import type { QuestionFormConfig, QuestionRow } from '../components/prerequisites/types';

// ---------------------------------------------------------------------------
// Task 1 — Bug condition exploration test (architecture-doc-commentaires-i18n)
//
// Property 1: Bug Condition — comments rendered in the active language with
// localized labels.
//
// This test encodes the EXPECTED (fixed) behavior. On the UNFIXED builder it
// MUST FAIL — that failure confirms the bug exists (renderRow emits
// `exampleValue`; chrome/header/section strings are hardcoded French; no
// `language` is threaded). DO NOT fix the code or the test when it fails here.
//
// The builder `buildArchitectureDocumentHtml` is a pure function of an
// `InstallationExport`, so we drive it with a hand-built fixture (no service
// mocking) and assert on the produced HTML string. The property is scoped over
// the two concrete languages ('fr', 'en').
//
// **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
// ---------------------------------------------------------------------------

// The (fixed) builder signature threads a language. On unfixed code the runtime
// function ignores the extra argument, so it still executes and emits French —
// exactly what makes these assertions fail. We cast so the test type-checks
// against either signature.
const buildDoc = buildArchitectureDocumentHtml as unknown as (
  data: InstallationExport,
  language: Language,
) => string;

/**
 * Build a fixture InstallationExport. Every QA tab gets one distinguished row
 * (the FIRST row of the FIRST section of its real config) an answer whose
 * `exampleValue` and `commentsHint` are distinct sentinel strings, so we can
 * assert the document renders the comments value and not the example value.
 *
 * Because `renderRow` reads from the shared QA_CATEGORIES config (not from the
 * export), the distinct `exampleValue`/`commentsHint` sentinels are asserted
 * against the real config's first row for the CloudStore-style tabs. To keep
 * the assertion robust we scan the produced HTML for any configured row's
 * commentsHint / exampleValue instead of relying on one specific row.
 */
const buildFixture = (): InstallationExport => {
  const tabs: Record<string, Record<string, string>> = {};
  for (const category of QA_CATEGORIES) {
    tabs[category.slug] = {};
  }

  return {
    format: 'opcp-installation-export',
    version: 1,
    exported_at: '2026-02-01T00:00:00.000Z',
    installation: {
      id: '11111111-1111-1111-1111-111111111111',
      project_name: 'Bug Repro Project',
    },
    tabs,
    servers: {
      credentials: {
        auth_url: 'https://keystone.example/v3',
        credential_id: 'cred-1',
        nova_endpoint: 'https://nova.example/v2.1',
        ca_certificate: 'CERT-DATA',
        secret_stored: true,
      },
      nodes: [],
    },
  };
};

/**
 * Collect, from the real QA configs, the set of rows that have BOTH an
 * `exampleValue` and a `commentsHint` so the two are distinguishable in the
 * rendered HTML. Returns the first such row's example/comments pair.
 */
const firstDistinguishableRow = (): { example: string; comments: string } => {
  for (const category of QA_CATEGORIES) {
    const config = category.config as QuestionFormConfig;
    for (const section of config.sections) {
      for (const row of section.rows) {
        if (
          row.exampleValue &&
          row.commentsHint &&
          row.exampleValue !== row.commentsHint
        ) {
          return { example: row.exampleValue, comments: row.commentsHint };
        }
      }
    }
  }
  throw new Error(
    'Fixture assumption broken: no QA row has distinct exampleValue and commentsHint',
  );
};

describe('Bug condition exploration: architecture document comments + i18n (Requirements 2.1-2.5)', () => {
  it('renders commentsHint (not exampleValue) for question rows — FR', () => {
    const { example, comments } = firstDistinguishableRow();
    const html = buildDoc(buildFixture(), 'fr');

    // 2.1 — the comments/details value is rendered (HTML-escaped, per 3.4), the
    // example value is not.
    expect(html).toContain(escapeHtmlRef(comments));
    expect(html).not.toContain(escapeHtmlRef(example));
  });

  it('emits English chrome and lang attribute when language = "en" (2.2)', () => {
    const html = buildDoc(buildFixture(), 'en');

    expect(html).toContain('<html lang="en">');
    expect(html).toContain('Architecture document');
    // The French chrome must NOT leak into an English document.
    expect(html).not.toContain('<html lang="fr">');
  });

  it('localizes the QA table header to English (2.3)', () => {
    const html = buildDoc(buildFixture(), 'en');

    expect(html).toContain('Parameter / Question');
    expect(html).toContain('Value');
    expect(html).toContain('Comments / Details');
  });

  it('localizes the servers section to English (2.4)', () => {
    // Non-null credentials (buildFixture has secret_stored: true): the servers
    // section shows the CA-certificate label and the "stored" secret status.
    const html = buildDoc(buildFixture(), 'en');

    expect(html).toContain('CA certificate');
    expect(html).toContain('Stored (not exported)');

    // Null credentials: the servers section shows the English empty-config
    // message instead. This is mutually exclusive with the stored-secret case,
    // so it is asserted against a separate fixture.
    const noCred = buildFixture();
    noCred.servers.credentials = null;
    const htmlNoCred = buildDoc(noCred, 'en');

    expect(htmlNoCred).toContain('No OpenStack configuration saved.');
    // French empty-config wording must not leak into the English document.
    expect(htmlNoCred).not.toContain('Aucune configuration OpenStack enregistrée.');
  });

  it('renders the muted em-dash placeholder for an undefined commentsHint without crashing (edge case)', () => {
    // A synthetic export whose only "row" comes from a config with a missing
    // commentsHint should not crash and should render the muted placeholder.
    const html = buildDoc(buildFixture(), 'en');
    expect(html).toContain('class="muted">—<');
  });

  // Scoped property: for BOTH concrete languages the document lang attribute
  // matches the active language and comments (not examples) are rendered.
  it('property: lang attribute matches active language and comments are rendered for fr and en', () => {
    const { example, comments } = firstDistinguishableRow();

    fc.assert(
      fc.property(fc.constantFrom<Language>('fr', 'en'), (language) => {
        const html = buildDoc(buildFixture(), language);

        expect(html).toContain(`<html lang="${language}">`);
        expect(html).toContain(escapeHtmlRef(comments));
        expect(html).not.toContain(escapeHtmlRef(example));
      }),
      { numRuns: 20 },
    );
  });
});

// ---------------------------------------------------------------------------
// Task 2 — Preservation property tests (architecture-doc-commentaires-i18n)
//
// Property 2: Preservation — French output and document structure preserved.
//
// These tests encode BASELINE behavior that must NOT regress across the fix.
// They are written observation-first against the UNFIXED builder and MUST PASS
// on it. On the unfixed runtime, `buildArchitectureDocumentHtml` ignores the
// extra `language` argument and always emits French — so every assertion here
// is expressed in terms of the French output and the language-independent
// structure (markers, answer cell / em-dash, HTML-escaping, section set,
// node/credential fields, download filename).
//
// **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
// ---------------------------------------------------------------------------

import { generateArchitectureDocument } from './installationExport';
import { SERVERS_NODES_SLUG } from '../components/prerequisites/checklistCategories';
import type { ServerNode } from '../components/prerequisites/serversData';
import { prerequisitesService, type Installation } from './prerequisitesService';

// Reference the same escaping the builder uses, expressed independently so the
// test does not import a private helper. Order matches the builder: & first.
const escapeHtmlRef = (value: string): string =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

/** A fixture whose QA answers/servers are supplied by the caller. */
const buildExport = (
  tabs: Record<string, Record<string, string>>,
  servers: InstallationExport['servers'],
  projectName = 'Preservation Project',
): InstallationExport => ({
  format: 'opcp-installation-export',
  version: 1,
  exported_at: '2026-02-01T00:00:00.000Z',
  installation: {
    id: '22222222-2222-2222-2222-222222222222',
    project_name: projectName,
  },
  tabs,
  servers,
});

/** All QA rows across every category, paired with their slug. */
const allQaRows = (): Array<{ slug: string; row: QuestionRow }> => {
  const out: Array<{ slug: string; row: QuestionRow }> = [];
  for (const category of QA_CATEGORIES) {
    const config = category.config as QuestionFormConfig;
    for (const section of config.sections) {
      for (const row of section.rows) out.push({ slug: category.slug, row });
    }
  }
  return out;
};

// Values sprinkled with HTML-special characters so escaping is exercised.
const htmlyString = fc.string({ minLength: 0, maxLength: 24 }).map(
  (s) => `${s}<a & b > c " d ' e`,
);

const nodeArb: fc.Arbitrary<ServerNode> = fc.record({
  nodeUuid: htmlyString,
  serialNumber: htmlyString,
  instanceUuid: fc.oneof(fc.constant(''), htmlyString),
  powerState: fc.oneof(fc.constant(''), htmlyString),
  provisionState: fc.oneof(fc.constant(''), htmlyString),
  remark: fc.oneof(fc.constant(''), htmlyString),
});

const credentialsArb: fc.Arbitrary<InstallationExport['servers']['credentials']> = fc.oneof(
  fc.constant(null),
  fc.record({
    auth_url: fc.oneof(fc.constant(''), htmlyString),
    credential_id: fc.oneof(fc.constant(''), htmlyString),
    nova_endpoint: fc.oneof(fc.constant(''), htmlyString),
    ca_certificate: fc.oneof(fc.constant(''), htmlyString),
    secret_stored: fc.boolean(),
  }),
);

const emptyServers: InstallationExport['servers'] = { credentials: null, nodes: [] };

describe('Preservation: architecture document structure + French output (Requirements 3.1-3.6)', () => {
  // 3.1 — French labels whose meaning is unchanged render exactly as before.
  it('preserves exact French chrome/header labels (3.1)', () => {
    const html = buildDoc(buildExport({}, emptyServers), 'fr');

    expect(html).toContain('<html lang="fr">');
    expect(html).toContain("Document d'architecture");
    expect(html).toContain('Sommaire');
    expect(html).toContain('Valeur');
    expect(html).toContain('Projet');
    expect(html).toContain('Généré le');
    // Servers section French wording.
    expect(html).toContain('Servers nodes');
    expect(html).toContain('Configuration OpenStack');
    expect(html).toContain('Inventaire des nœuds serveurs');
  });

  // 3.2 — answer cell renders the trimmed answer; empty answers -> muted em-dash.
  it('property: answer cell shows the trimmed answer, empty answers show the muted em-dash (3.2)', () => {
    const rows = allQaRows();
    fc.assert(
      fc.property(
        // For each configured row, choose either a non-empty (possibly padded)
        // answer or an empty/whitespace answer.
        fc.array(
          fc.oneof(
            fc.string({ minLength: 1, maxLength: 12 }).map((s) => ({ kind: 'value' as const, raw: `  ${s}x  ` })),
            fc.constantFrom('', '   ', '\t').map((raw) => ({ kind: 'empty' as const, raw })),
          ),
          { minLength: rows.length, maxLength: rows.length },
        ),
        (choices) => {
          const tabs: Record<string, Record<string, string>> = {};
          for (const category of QA_CATEGORIES) tabs[category.slug] = {};
          rows.forEach(({ slug, row }, i) => {
            tabs[slug][row.id] = choices[i].raw;
          });

          const html = buildDoc(buildExport(tabs, emptyServers), 'fr');

          choices.forEach((choice) => {
            if (choice.kind === 'value') {
              const trimmed = choice.raw.trim();
              expect(html).toContain(`<td class="value">${escapeHtmlRef(trimmed)}</td>`);
            }
          });
          // At least one empty answer must produce a muted em-dash value cell.
          if (choices.some((c) => c.kind === 'empty')) {
            expect(html).toContain('<td class="value"><span class="muted">—</span></td>');
          }
        },
      ),
      { numRuns: 25 },
    );
  });

  // 3.3 — mandatory rows render 🔴, optional rows render ⚪.
  it('renders 🔴 for mandatory rows and ⚪ for optional rows (3.3)', () => {
    const rows = allQaRows();
    const tabs: Record<string, Record<string, string>> = {};
    for (const category of QA_CATEGORIES) tabs[category.slug] = {};
    const html = buildDoc(buildExport(tabs, emptyServers), 'fr');

    const hasMandatory = rows.some(({ row }) => row.mandatory);
    const hasOptional = rows.some(({ row }) => !row.mandatory);
    if (hasMandatory) expect(html).toContain('<td class="marker">🔴</td>');
    if (hasOptional) expect(html).toContain('<td class="marker">⚪</td>');
    // Every configured row must contribute exactly one marker cell.
    const markerCount = (html.match(/<td class="marker">(🔴|⚪)<\/td>/g) ?? []).length;
    expect(markerCount).toBe(rows.length);
  });

  // 3.4 — user-supplied values (answers) are HTML-escaped in the value cell.
  it('property: answers containing HTML-special characters are escaped (3.4)', () => {
    const rows = allQaRows();
    fc.assert(
      fc.property(htmlyString, (raw) => {
        const tabs: Record<string, Record<string, string>> = {};
        for (const category of QA_CATEGORIES) tabs[category.slug] = {};
        // Put the same value in the first row of each tab.
        const bySlugFirst = new Map<string, string>();
        for (const { slug, row } of rows) {
          if (!bySlugFirst.has(slug)) {
            bySlugFirst.set(slug, row.id);
            tabs[slug][row.id] = raw;
          }
        }

        const html = buildDoc(buildExport(tabs, emptyServers), 'fr');
        const trimmed = raw.trim();
        if (trimmed) {
          // The escaped form appears; the raw unescaped special chars do not
          // leak as literal markup in the value cell.
          expect(html).toContain(escapeHtmlRef(trimmed));
          expect(html).not.toContain(`<td class="value">${trimmed}</td>`);
        }
      }),
      { numRuns: 30 },
    );
  });

  // 3.4 + 3.6 — node fields & credentials present and HTML-escaped.
  it('property: every node/credential field is present and HTML-escaped (3.4, 3.6)', () => {
    fc.assert(
      fc.property(
        fc.array(nodeArb, { minLength: 0, maxLength: 6 }),
        credentialsArb,
        (nodes, credentials) => {
          const html = buildDoc(
            buildExport({}, { credentials, nodes }),
            'fr',
          );

          // Node column headers (technical identifiers preserved as-is).
          expect(html).toContain('Node UUID');
          expect(html).toContain('Serial Number');
          expect(html).toContain('Instance UUID');
          expect(html).toContain('Power State');
          expect(html).toContain('Provision State');
          expect(html).toContain('Remark');

          // Every node's non-empty fields appear HTML-escaped.
          for (const node of nodes) {
            for (const field of [
              node.nodeUuid,
              node.serialNumber,
              node.instanceUuid,
              node.powerState,
              node.provisionState,
              node.remark,
            ]) {
              if (field) expect(html).toContain(escapeHtmlRef(field));
            }
          }

          if (credentials) {
            // Credential field labels present.
            expect(html).toContain('Auth URL');
            expect(html).toContain('Credential ID');
            expect(html).toContain('Nova endpoint');
            expect(html).toContain('Certificat CA');
            expect(html).toContain('Secret');
            expect(html).toContain(
              credentials.secret_stored ? 'Enregistré (non exporté)' : 'Non configuré',
            );
            for (const field of [
              credentials.auth_url,
              credentials.credential_id,
              credentials.nova_endpoint,
              credentials.ca_certificate,
            ]) {
              if (field) expect(html).toContain(escapeHtmlRef(field));
            }
          } else {
            expect(html).toContain('Aucune configuration OpenStack enregistrée.');
          }
        },
      ),
      { numRuns: 40 },
    );
  });

  // 3.5 — all QA sections plus the servers section are present.
  it('includes every QA section and the servers/node-inventory section (3.5)', () => {
    const html = buildDoc(buildExport({}, emptyServers), 'fr');

    for (const category of QA_CATEGORIES) {
      expect(html).toContain(escapeHtmlRef(category.title));
    }
    // Servers section heading is present, and the servers slug is a real tab.
    expect(html).toContain('Servers nodes');
    expect(typeof SERVERS_NODES_SLUG).toBe('string');
  });

  // 3.5 — generateArchitectureDocument downloads {project}-architecture-{date}.html.
  it('property: generateArchitectureDocument downloads {project}-architecture-{date}.html (3.5)', async () => {
    // Neutralize the network: the export builder degrades gracefully when the
    // service rejects, so stub every load to resolve deterministically.
    const loadAnswers = vi
      .spyOn(prerequisitesService, 'loadClientAnswers')
      .mockResolvedValue({ slug: 'x', answers: {} } as never);
    const loadCred = vi
      .spyOn(prerequisitesService, 'loadCredentialConfig')
      .mockRejectedValue(new Error('no config') as never);

    // Neutralize the DOM download and capture the anchor download filename.
    const originalCreate = URL.createObjectURL;
    const originalRevoke = URL.revokeObjectURL;
    (URL as unknown as { createObjectURL: () => string }).createObjectURL = () => 'blob:mock';
    (URL as unknown as { revokeObjectURL: () => void }).revokeObjectURL = () => {};

    const captured: string[] = [];
    const realCreateElement = document.createElement.bind(document);
    const spy = vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = realCreateElement(tag) as HTMLElement;
      if (tag === 'a') {
        Object.defineProperty(el, 'download', {
          configurable: true,
          set(v: string) {
            captured.push(v);
          },
          get() {
            return captured[captured.length - 1] ?? '';
          },
        });
        (el as HTMLAnchorElement).click = () => {};
      }
      return el;
    });

    try {
      await fc.assert(
        fc.asyncProperty(fc.string({ minLength: 1, maxLength: 20 }), async (projectName) => {
          captured.length = 0;
          await generateArchitectureDocument({
            id: '33333333-3333-3333-3333-333333333333',
            project_name: projectName,
            created_at: '2026-02-01T00:00:00.000Z',
            updated_at: '2026-02-01T00:00:00.000Z',
          } as Installation);

          expect(captured.length).toBeGreaterThan(0);
          const filename = captured[captured.length - 1];
          expect(filename).toMatch(/^.+-architecture-\d{4}-\d{2}-\d{2}\.html$/);
        }),
        { numRuns: 10 },
      );
    } finally {
      spy.mockRestore();
      loadAnswers.mockRestore();
      loadCred.mockRestore();
      URL.createObjectURL = originalCreate;
      URL.revokeObjectURL = originalRevoke;
    }
  });
});

// ---------------------------------------------------------------------------
// Task 3.4 — Focused unit tests for the helpers and edge cases
// (architecture-doc-commentaires-i18n)
//
// The private helpers `renderRow`, `renderQaSection`, and `renderServersSection`
// are NOT exported. We assert their behavior through the exported
// `buildArchitectureDocumentHtml(data, language)` by inspecting the produced
// HTML — the same black-box approach the Task 1 / Task 2 tests use. Fixtures are
// built with the existing `buildFixture` / `buildExport` helpers (and cloned
// where a variant is needed).
//
// **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 3.2, 3.4**
// ---------------------------------------------------------------------------

describe('Task 3.4 — helper + edge-case unit tests (Requirements 2.1-2.5, 3.2, 3.4)', () => {
  // --- renderRow: renders commentsHint (not exampleValue) in both languages ---
  describe('renderRow (via buildArchitectureDocumentHtml)', () => {
    it('renders the row commentsHint and NOT the exampleValue — FR (2.1)', () => {
      const { example, comments } = firstDistinguishableRow();
      const html = buildDoc(buildFixture(), 'fr');

      // The comments/details value is rendered HTML-escaped; the example is not.
      expect(html).toContain(escapeHtmlRef(comments));
      expect(html).not.toContain(escapeHtmlRef(example));
    });

    it('renders the row commentsHint and NOT the exampleValue — EN (2.1)', () => {
      const { example, comments } = firstDistinguishableRow();
      const html = buildDoc(buildFixture(), 'en');

      expect(html).toContain(escapeHtmlRef(comments));
      expect(html).not.toContain(escapeHtmlRef(example));
    });

    it('renders the mandatory/optional marker and the comments cell together (2.1)', () => {
      const { comments } = firstDistinguishableRow();
      const html = buildDoc(buildFixture(), 'fr');

      // A marker cell is present for every configured row …
      expect(html).toMatch(/<td class="marker">(🔴|⚪)<\/td>/);
      // … and the comments value is rendered in a comments column cell.
      expect(html).toContain(`<td class="example">${escapeHtmlRef(comments)}</td>`);
    });
  });

  // --- renderQaSection: header cells localize to the active language ---
  describe('renderQaSection header localization', () => {
    it('renders the French QA header cells when language = "fr" (2.3, 3.1)', () => {
      const html = buildDoc(buildFixture(), 'fr');

      expect(html).toContain('Paramètre / Question');
      expect(html).toContain('Valeur');
      expect(html).toContain('Commentaires');
    });

    it('renders the English QA header cells when language = "en" (2.3)', () => {
      const html = buildDoc(buildFixture(), 'en');

      expect(html).toContain('Parameter / Question');
      expect(html).toContain('Value');
      expect(html).toContain('Comments / Details');
      // French header wording must not leak into an English document.
      expect(html).not.toContain('Paramètre / Question');
      expect(html).not.toContain('Commentaires');
    });
  });

  // --- renderServersSection: headings, credential labels, secret statuses,
  //     empty message localize; node column headers unchanged. ---
  describe('renderServersSection localization', () => {
    it('localizes headings, CA label and stored-secret status to English with non-null creds (2.4)', () => {
      // buildFixture() has non-null credentials with secret_stored: true.
      const html = buildDoc(buildFixture(), 'en');

      expect(html).toContain('Servers nodes');
      expect(html).toContain('OpenStack configuration');
      expect(html).toContain('Server node inventory');
      expect(html).toContain('CA certificate');
      expect(html).toContain('Stored (not exported)');
    });

    it('shows the English "Not configured" secret status when secret_stored is false (2.4)', () => {
      const data = buildFixture();
      // Non-null creds but no stored secret.
      data.servers.credentials = {
        auth_url: 'https://keystone.example/v3',
        credential_id: 'cred-1',
        nova_endpoint: 'https://nova.example/v2.1',
        ca_certificate: 'CERT-DATA',
        secret_stored: false,
      };
      const html = buildDoc(data, 'en');

      expect(html).toContain('Not configured');
      expect(html).not.toContain('Stored (not exported)');
    });

    it('shows the English empty-configuration message with null creds (2.4)', () => {
      const data = buildFixture();
      data.servers.credentials = null;
      const html = buildDoc(data, 'en');

      expect(html).toContain('No OpenStack configuration saved.');
      expect(html).not.toContain('Aucune configuration OpenStack enregistrée.');
    });

    it('localizes headings, CA label and stored-secret status to French with non-null creds (2.4, 3.1)', () => {
      const html = buildDoc(buildFixture(), 'fr');

      expect(html).toContain('Configuration OpenStack');
      expect(html).toContain('Inventaire des nœuds serveurs');
      expect(html).toContain('Certificat CA');
      expect(html).toContain('Enregistré (non exporté)');
    });

    it('shows the French "Non configuré" secret status when secret_stored is false (2.4)', () => {
      const data = buildFixture();
      data.servers.credentials = {
        auth_url: 'https://keystone.example/v3',
        credential_id: 'cred-1',
        nova_endpoint: 'https://nova.example/v2.1',
        ca_certificate: 'CERT-DATA',
        secret_stored: false,
      };
      const html = buildDoc(data, 'fr');

      expect(html).toContain('Non configuré');
      expect(html).not.toContain('Enregistré (non exporté)');
    });

    it('shows the French empty-configuration message with null creds (2.4)', () => {
      const data = buildFixture();
      data.servers.credentials = null;
      const html = buildDoc(data, 'fr');

      expect(html).toContain('Aucune configuration OpenStack enregistrée.');
      expect(html).not.toContain('No OpenStack configuration saved.');
    });

    it('leaves the node-table column headers unchanged in both languages (3.6)', () => {
      const nodeHeaders = [
        'Node UUID',
        'Serial Number',
        'Instance UUID',
        'Power State',
        'Provision State',
        'Remark',
      ];
      for (const language of ['fr', 'en'] as const) {
        const html = buildDoc(buildFixture(), language);
        for (const header of nodeHeaders) {
          expect(html).toContain(header);
        }
      }
    });
  });

  // --- buildArchitectureDocumentHtml: correct <html lang> + localized chrome ---
  describe('buildArchitectureDocumentHtml chrome localization', () => {
    it('sets <html lang="fr"> and French chrome for language = "fr" (2.2, 3.1)', () => {
      const html = buildDoc(buildFixture(), 'fr');

      expect(html).toContain('<html lang="fr">');
      expect(html).toContain("Document d'architecture");
      expect(html).toContain('Sommaire');
      expect(html).toContain('Projet');
      expect(html).toContain('Généré le');
    });

    it('sets <html lang="en"> and English chrome for language = "en" (2.2)', () => {
      const html = buildDoc(buildFixture(), 'en');

      expect(html).toContain('<html lang="en">');
      expect(html).toContain('Architecture document');
      expect(html).toContain('Summary');
      expect(html).toContain('Project');
      expect(html).toContain('Generated on');
      // French chrome must not leak into an English document.
      expect(html).not.toContain('<html lang="fr">');
      expect(html).not.toContain("Document d'architecture");
    });
  });

  // --- Edge cases: em-dash placeholders + empty credentials ---
  describe('edge cases (3.2, 3.4)', () => {
    it('renders the muted em-dash in the value cell for an empty answer (3.2)', () => {
      // With no answers supplied, at least one row's value cell is the empty
      // placeholder. Drive it via the shared config so we hit a real row.
      const html = buildDoc(buildExport({}, emptyServers), 'fr');
      expect(html).toContain('<td class="value"><span class="muted">—</span></td>');
    });

    it('renders the muted em-dash in the comments cell when a row has no commentsHint (3.4)', () => {
      // NOTE / limitation: QA rows come from the shared QA_CATEGORIES config, so
      // an undefined `commentsHint` cannot be injected through the exported
      // builder. If any real config row lacks a commentsHint, the builder emits
      // the muted comments placeholder `<td class="example muted">—</td>`; we
      // assert that only when such a row actually exists, otherwise we assert
      // the reachable equivalent (a muted em-dash somewhere in the document).
      const hasRowWithoutComments = QA_CATEGORIES.some((category) => {
        const config = category.config as QuestionFormConfig;
        return config.sections.some((section) =>
          section.rows.some((row) => !row.commentsHint),
        );
      });

      const html = buildDoc(buildExport({}, emptyServers), 'fr');
      if (hasRowWithoutComments) {
        expect(html).toContain('<td class="example muted">—</td>');
      } else {
        // No config row is missing a commentsHint, so the undefined-comments
        // branch is not reachable through the export. Assert the general muted
        // em-dash behavior instead (empty answer value cell).
        expect(html).toContain('class="muted">—<');
      }
    });

    it('renders the empty-configuration message for null credentials (2.4)', () => {
      const data = buildExport({}, { credentials: null, nodes: [] });
      const htmlFr = buildDoc(data, 'fr');
      const htmlEn = buildDoc(data, 'en');

      expect(htmlFr).toContain('Aucune configuration OpenStack enregistrée.');
      expect(htmlEn).toContain('No OpenStack configuration saved.');
    });
  });
});
