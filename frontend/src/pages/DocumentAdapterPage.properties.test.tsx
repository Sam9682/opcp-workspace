/**
 * Property-based tests for the Document Adapter page.
 * Spec: .kiro/specs/document-audience-adapter (Task 12.4)
 *
 * Feature: document-audience-adapter
 *
 * These tests exercise the five page-level correctness properties that concern
 * the library listing, the provider dropdown, the default-provider preselect,
 * the preview panel, and the copy-to-clipboard action. The three service
 * modules the page depends on (documentService, oracleService,
 * documentAdapterService) are mocked so generated data can be fed directly and
 * the component renders deterministically without network access. The page is
 * wrapped in the real LanguageProvider (language forced to `en`) exactly as the
 * app mounts it, so i18n label resolution is exercised for real.
 *
 * fast-check drives >=100 iterations for every generated-input property.
 */
import {
  describe,
  it,
  expect,
  beforeEach,
  afterEach,
  vi,
} from 'vitest';
import {
  render,
  screen,
  cleanup,
  waitFor,
  within,
  fireEvent,
} from '@testing-library/react';
import fc from 'fast-check';
import type { ReactElement } from 'react';

// ---- Service mocks ---------------------------------------------------------
// The page fetches the documents listing and the providers list on mount, and
// calls the adapter service for generation/copy. Mock all three so each test
// can supply generated data.
vi.mock('../services/documentService', () => ({
  documentService: {
    listDocuments: vi.fn(),
    uploadDocument: vi.fn(),
  },
}));

vi.mock('../services/oracleService', () => ({
  oracleService: {
    getAvailableProviders: vi.fn(),
  },
}));

vi.mock('../services/documentAdapterService', () => ({
  // Re-export the real constants/predicate the page imports alongside the
  // mocked service object, so the page's `AUDIENCE_LEVELS`, `isSupportedSourceType`
  // behave normally while `documentAdapterService.adapt` is a spy.
  AUDIENCE_LEVELS: [
    'it_beginner',
    'intermediate_a',
    'intermediate_b',
    'opcp_expert',
  ],
  isSupportedSourceType: (mimeType: string) =>
    [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ].includes(mimeType),
  documentAdapterService: {
    adapt: vi.fn(),
    exportAdapted: vi.fn(),
  },
}));

import { DocumentAdapterPage } from './DocumentAdapterPage';
import { LanguageProvider } from '../hooks/useLanguage';
import { documentService, type Document } from '../services/documentService';
import { oracleService, type AvailableProvider, type AIProviderId } from '../services/oracleService';
import {
  documentAdapterService,
  type AdaptationResponse,
} from '../services/documentAdapterService';

const mockedListDocuments = vi.mocked(documentService.listDocuments);
const mockedGetProviders = vi.mocked(oracleService.getAvailableProviders);
const mockedAdapt = vi.mocked(documentAdapterService.adapt);

const LANG_KEY = 'opcp.language';
const PROVIDER_IDS: AIProviderId[] = ['shai', 'kiro', 'openai', 'opcp_companion'];
const SUPPORTED_MIME = [
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];

/** Render the page inside the real language provider, forced to English. */
function renderPage(ui: ReactElement = <DocumentAdapterPage />) {
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

/**
 * Run one fast-check iteration body, guaranteeing the rendered tree is always
 * unmounted afterwards. Without this, an assertion failure skips the trailing
 * cleanup and leaves a stale page mounted, so the next iteration finds two
 * copies of every element (e.g. two "From library" selects).
 */
async function withCleanup(body: () => Promise<void>): Promise<void> {
  try {
    await body();
  } finally {
    cleanup();
  }
}

/** Build a Document from a few generated fields, defaulting the rest. */
function makeDocument(
  id: string,
  originalName: string,
  mimeType: string,
): Document {
  return {
    id,
    filename: `${id}.bin`,
    original_name: originalName,
    mime_type: mimeType,
    size: 1024,
    category: 'documents',
    access_level: 'public',
    uploaded_by: 'u1',
    download_count: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };
}

/** Build an AvailableProvider. */
function makeProvider(
  id: AIProviderId,
  enabled: boolean,
  isDefault: boolean,
): AvailableProvider {
  return {
    id,
    name: `Provider ${id}`,
    description: `desc ${id}`,
    default: isDefault,
    enabled,
  };
}

/** Build an AdaptationResponse carrying the given content. */
function makeAdaptResponse(content: string): AdaptationResponse {
  return {
    adapted_content: content,
    audience_level: 'it_beginner',
    ai_provider: 'kiro',
    source_name: 'source.pdf',
    processing_time: 0.1,
  };
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem(LANG_KEY, 'en');
  mockedListDocuments.mockReset();
  mockedGetProviders.mockReset();
  mockedAdapt.mockReset();
  // Sensible empty defaults; individual tests override as needed.
  mockedListDocuments.mockResolvedValue({ documents: [], total: 0 });
  mockedGetProviders.mockResolvedValue({ providers: [] });
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Property 2: Every listed document is selectable.
//
// For any documents listing returned by documentService.listDocuments(),
// every document whose MIME type is a supported source type appears as a
// selectable option in the library select.
//
// Validates: Requirements 2.1
// ---------------------------------------------------------------------------
describe('Feature: document-audience-adapter, Property 2: Every listed document is selectable', () => {
  it('renders every supported listed document as a selectable library option (Validates: Requirements 2.1)', async () => {
    await fc.assert(
      fc.asyncProperty(
        // A listing of documents with unique ids and names; MIME is either a
        // supported source type or some other type (which must be excluded).
        fc.uniqueArray(
          fc.record({
            id: fc.uuid(),
            name: fc
              .string({ minLength: 1, maxLength: 20 })
              .map((s) => `doc ${s.replace(/\s+/g, '_')}`),
            mime: fc.oneof(
              fc.constantFrom(...SUPPORTED_MIME),
              fc.constantFrom('text/plain', 'image/png', 'application/zip'),
            ),
          }),
          { minLength: 1, maxLength: 8, selector: (d) => d.id },
        ),
        (rawDocs) =>
          withCleanup(async () => {
            // Ensure original names are unique so option lookup is unambiguous.
            const docs = rawDocs.map((d, i) =>
              makeDocument(d.id, `${d.name}_${i}`, d.mime),
            );
            mockedListDocuments.mockResolvedValue({
              documents: docs,
              total: docs.length,
            });

            renderPage();

            // The library select is present once the listing resolves.
            const select = await screen.findByRole('combobox', {
              name: 'From library',
            });

            // Every supported document appears as a selectable <option> (by its
            // original name), carrying its id as the option value.
            const supported = docs.filter((d) =>
              SUPPORTED_MIME.includes(d.mime_type),
            );
            const options = within(select).getAllByRole('option');
            for (const doc of supported) {
              const opt = options.find(
                (o) => o.textContent === doc.original_name,
              ) as HTMLOptionElement | undefined;
              expect(opt).toBeTruthy();
              expect(opt?.value).toBe(doc.id);
            }

            // Unsupported documents are NOT offered as options.
            const unsupported = docs.filter(
              (d) => !SUPPORTED_MIME.includes(d.mime_type),
            );
            for (const doc of unsupported) {
              expect(
                options.some((o) => o.textContent === doc.original_name),
              ).toBe(false);
            }
          }),
      ),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 4: The provider dropdown shows exactly the enabled providers.
//
// For any providers response, the set of options in the provider dropdown
// equals the set of providers whose enabled flag is true.
//
// Validates: Requirements 4.2
// ---------------------------------------------------------------------------
describe('Feature: document-audience-adapter, Property 4: The provider dropdown shows exactly the enabled providers', () => {
  it('shows an option for exactly the enabled providers, and no others (Validates: Requirements 4.2)', async () => {
    await fc.assert(
      fc.asyncProperty(
        // For each of the four known provider ids, decide enabled + default.
        fc.record({
          shai: fc.record({ enabled: fc.boolean(), def: fc.boolean() }),
          kiro: fc.record({ enabled: fc.boolean(), def: fc.boolean() }),
          openai: fc.record({ enabled: fc.boolean(), def: fc.boolean() }),
          opcp_companion: fc.record({ enabled: fc.boolean(), def: fc.boolean() }),
        }),
        (spec) =>
          withCleanup(async () => {
            const providers: AvailableProvider[] = PROVIDER_IDS.map((id) =>
              makeProvider(id, spec[id].enabled, spec[id].def),
            );
            mockedGetProviders.mockResolvedValue({ providers });

            renderPage();

            const enabledIds = providers
              .filter((p) => p.enabled)
              .map((p) => p.id);

            if (enabledIds.length === 0) {
              // No enabled provider: the dropdown is absent and the no-provider
              // message is shown instead (Requirement 4.4). The "exactly the
              // enabled providers" set is empty, so there must be no combobox
              // named for the provider section.
              await screen.findByText('No AI provider available.');
              expect(
                screen.queryByRole('combobox', {
                  name: 'Target audience & AI',
                }),
              ).toBeNull();
              return;
            }

            const select = await screen.findByRole('combobox', {
              name: 'Target audience & AI',
            });
            const options = within(select).getAllByRole(
              'option',
            ) as HTMLOptionElement[];
            const optionValues = options.map((o) => o.value).sort();

            // The option value set equals the enabled provider id set — exactly.
            expect(optionValues).toEqual([...enabledIds].sort());
          }),
      ),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 5: The default-flagged enabled provider is preselected.
//
// For any providers response with at least one enabled provider, the
// preselected provider is the enabled provider whose default flag is set; if
// none flagged, the first enabled provider.
//
// Validates: Requirements 4.3
// ---------------------------------------------------------------------------
describe('Feature: document-audience-adapter, Property 5: The default-flagged enabled provider is preselected', () => {
  it('preselects the default-flagged enabled provider, else the first enabled (Validates: Requirements 4.3)', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc
          .record({
            shai: fc.record({ enabled: fc.boolean(), def: fc.boolean() }),
            kiro: fc.record({ enabled: fc.boolean(), def: fc.boolean() }),
            openai: fc.record({ enabled: fc.boolean(), def: fc.boolean() }),
            opcp_companion: fc.record({
              enabled: fc.boolean(),
              def: fc.boolean(),
            }),
          })
          // Constrain to responses with at least one enabled provider.
          .filter((spec) =>
            PROVIDER_IDS.some((id) => spec[id].enabled),
          ),
        (spec) =>
          withCleanup(async () => {
            const providers: AvailableProvider[] = PROVIDER_IDS.map((id) =>
              makeProvider(id, spec[id].enabled, spec[id].def),
            );
            mockedGetProviders.mockResolvedValue({ providers });

            renderPage();

            const select = (await screen.findByRole('combobox', {
              name: 'Target audience & AI',
            })) as HTMLSelectElement;

            const enabled = providers.filter((p) => p.enabled);
            // Expected preselect: first enabled provider whose default flag is
            // set, falling back to the first enabled provider.
            const expected = (enabled.find((p) => p.default) ?? enabled[0]).id;

            expect(select.value).toBe(expected);
          }),
      ),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 7: Returned adapted content is shown in the preview.
//
// For any adapted_content returned by adapt, the preview panel displays that
// exact content.
//
// Validates: Requirements 5.3
// ---------------------------------------------------------------------------
describe('Feature: document-audience-adapter, Property 7: Returned adapted content is shown in the preview', () => {
  it('renders the exact adapted content in the preview panel after Generate (Validates: Requirements 5.3)', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Plain-text content: words of alphanumerics joined by single spaces.
        // Markdown collapses runs of whitespace, so we generate single-space
        // separated words (no leading/trailing/double spaces) to keep the
        // rendered text byte-identical to the input and assert on it directly.
        fc
          .array(fc.stringMatching(/^[A-Za-z0-9]+$/), {
            minLength: 1,
            maxLength: 5,
          })
          .map((words) => words.join(' '))
          .filter((s) => s.length > 0),
        (content) =>
          withCleanup(async () => {
            // A single enabled provider and one supported library document so
            // the Generate prerequisites are satisfied.
            mockedGetProviders.mockResolvedValue({
              providers: [makeProvider('kiro', true, true)],
            });
            const doc = makeDocument(
              'doc-1',
              'Source One.pdf',
              'application/pdf',
            );
            mockedListDocuments.mockResolvedValue({
              documents: [doc],
              total: 1,
            });
            mockedAdapt.mockResolvedValue(makeAdaptResponse(content));

            renderPage();

            // Pick the library document to resolve a source.
            const librarySelect = await screen.findByRole('combobox', {
              name: 'From library',
            });
            fireEvent.change(librarySelect, { target: { value: 'doc-1' } });

            // The Generate button becomes enabled; click it.
            const generate = screen.getByRole('button', { name: 'Generate' });
            await waitFor(() => expect(generate).not.toBeDisabled());
            fireEvent.click(generate);

            // The preview shows the exact adapted content.
            await waitFor(() => expect(mockedAdapt).toHaveBeenCalled());
            expect(await screen.findByText(content)).toBeInTheDocument();
          }),
      ),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 8: Copy places the exact preview content on the clipboard.
//
// For any adapted content present in the preview, invoking copy writes a string
// identical to that content to the clipboard.
//
// Validates: Requirements 5.4
// ---------------------------------------------------------------------------
describe('Feature: document-audience-adapter, Property 8: Copy places the exact preview content on the clipboard', () => {
  it('writes the exact adapted content to the clipboard on Copy (Validates: Requirements 5.4)', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Arbitrary (possibly markdown-rich) content; copy must write it byte
        // for byte regardless of how it renders.
        fc.string({ minLength: 1, maxLength: 80 }),
        (content) =>
          withCleanup(async () => {
            const writeText = vi.fn().mockResolvedValue(undefined);
            Object.defineProperty(navigator, 'clipboard', {
              value: { writeText },
              configurable: true,
            });

            mockedGetProviders.mockResolvedValue({
              providers: [makeProvider('kiro', true, true)],
            });
            const doc = makeDocument(
              'doc-1',
              'Source One.pdf',
              'application/pdf',
            );
            mockedListDocuments.mockResolvedValue({
              documents: [doc],
              total: 1,
            });
            mockedAdapt.mockResolvedValue(makeAdaptResponse(content));

            renderPage();

            const librarySelect = await screen.findByRole('combobox', {
              name: 'From library',
            });
            fireEvent.change(librarySelect, { target: { value: 'doc-1' } });

            const generate = screen.getByRole('button', { name: 'Generate' });
            await waitFor(() => expect(generate).not.toBeDisabled());
            fireEvent.click(generate);

            // Once the preview is up, the Copy button appears.
            const copy = await screen.findByRole('button', { name: 'Copy' });
            fireEvent.click(copy);

            await waitFor(() =>
              expect(writeText).toHaveBeenCalledWith(content),
            );
          }),
      ),
      { numRuns: 100 },
    );
  });
});
