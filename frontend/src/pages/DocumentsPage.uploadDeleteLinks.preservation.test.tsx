/**
 * Preservation property tests for the
 * "documents-page-upload-delete-per-category" bugfix.
 *
 * Property 2 (Preservation) — Non-Buggy Inputs Behave Identically. For any
 * input where the bug condition does NOT hold (isBugCondition returns false),
 * the fixed DocumentsPage must produce the same result as the original.
 *
 * Methodology: observation-first. These assertions were derived by observing
 * the actual behaviour of the UNFIXED DocumentsPage and encoding it, so they
 * PASS on unfixed code (confirming the baseline to preserve) and must continue
 * to pass after the fix.
 *
 * Observed non-buggy behaviours captured here:
 *   - Non-admin (isAdmin === false): no upload control and no Delete control
 *     render for any item, over arbitrary document lists. Validates 2.3, 3.1
 *   - Every non-`links` item renders exactly one Download button wired to
 *     downloadDocument(id, original_name), over arbitrary lists. Validates 3.4
 *   - A `links` item with missing/null/empty target_url renders the Download
 *     fallback and no hyperlink. Validates 3.5
 *   - A successful upload refreshes the list and the item appears under its
 *     server-derived category; a failed upload (unmapped extension) shows the
 *     existing upload error banner and sends no client category param (only the
 *     File is passed to uploadDocument). Validates 3.2, 3.3
 *   - Sections render in CATEGORY_ORDER first, then any remaining present
 *     categories (grouping is a partition by category). Validates 3.6
 *   - Case-insensitive substring filter on original_name, all docs on an empty
 *     query, and the empty-state message when nothing matches. Validates 3.7
 *
 * Conventions reused from DocumentsPage.test.tsx /
 * DocumentsPage.uploadDeleteLinks.bug.test.tsx: mock documentService (extended
 * with deleteDocument) / authService, render inside a LanguageProvider (default
 * French), the makeDocument helper (extended with target_url), fast-check with
 * NUM_RUNS = 100, and window.confirm stubbed via vi.spyOn.
 *
 * Validates: Requirements 2.3, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, within, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import fc from 'fast-check';
import { DocumentsPage, formatSize } from './DocumentsPage';
import { documentService, type Document, type DocumentCategory } from '../services/documentService';
import { authService } from '../services/authService';
import { LanguageProvider } from '../hooks/useLanguage';

function renderPage() {
  return render(
    <LanguageProvider>
      <DocumentsPage />
    </LanguageProvider>,
  );
}

// Mock the service module. Extended with a `deleteDocument` mock so this suite
// shares the same factory shape as the fix/bug suites; on unfixed code the page
// never invokes it.
vi.mock('../services/documentService', () => ({
  documentService: {
    listDocuments: vi.fn(),
    downloadDocument: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
  },
}));

vi.mock('../services/authService', () => ({
  authService: {
    isAdmin: vi.fn(),
  },
}));

const mockedListDocuments = vi.mocked(documentService.listDocuments);
const mockedDownloadDocument = vi.mocked(documentService.downloadDocument);
const mockedUploadDocument = vi.mocked(documentService.uploadDocument);
// deleteDocument is added by the fix; cast so this test compiles before then.
const mockedDeleteDocument = vi.mocked(
  (documentService as unknown as { deleteDocument: (id: string) => Promise<void> }).deleteDocument,
);
const mockedIsAdmin = vi.mocked(authService.isAdmin);

// Minimum property-test iterations mandated by the design (>= 100).
const NUM_RUNS = 100;

// CATEGORY_ORDER from DocumentsPage: known subfolder sections render first, then
// any remaining present categories (e.g. a legacy `documents` row) afterwards.
const CATEGORY_ORDER: DocumentCategory[] = ['docs', 'links', 'scripts', 'trainings'];

// French category labels (default Active_Language).
const CATEGORY_LABELS: Record<DocumentCategory, string> = {
  documents: 'Documents',
  scripts: 'Scripts',
  links: 'Liens',
  docs: 'Documentation',
  trainings: 'Formations',
};

// Base upload label / button text (FR) from translations.
const UPLOAD_LABEL = 'Téléverser un document';
const UPLOAD_BUTTON = 'Téléverser';
const DOWNLOAD_LABEL = 'Télécharger';
const EMPTY_MESSAGE = 'Aucun document disponible.';
const UPLOAD_ERROR = 'Échec du téléversement du document.';

// Build a full Document record. target_url is optional so `links` fixtures can
// carry (or omit) a URL; cast keeps this compilable regardless of whether the
// type declares target_url yet.
function makeDocument(
  id: string,
  original_name: string,
  size: number,
  category: DocumentCategory,
  target_url?: string | null,
): Document {
  return {
    id,
    filename: `${id}.bin`,
    original_name,
    mime_type: 'application/octet-stream',
    size,
    category,
    access_level: 'members',
    uploaded_by: 'admin-id',
    download_count: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...(target_url !== undefined ? { target_url } : {}),
  } as Document;
}

// Visible, non-whitespace name characters so getByText matching stays stable
// (the browser collapses/trims whitespace). Mixed case exercises the
// case-insensitive search filter.
const nameCharArb = fc.constantFrom(...'abcdefghijABCDEFGHIJ0123456789-_.'.split(''));
const nameArb: fc.Arbitrary<string> = fc
  .array(nameCharArb, { minLength: 1, maxLength: 12 })
  .map((chars) => chars.join(''));

// Non-`links` categories only — used for the Download-preservation property so
// no item takes the hyperlink branch.
const NON_LINK_CATEGORIES: DocumentCategory[] = ['documents', 'scripts', 'docs', 'trainings'];

// Arbitrary list of non-`links` documents with UNIQUE ids.
const nonLinkDocumentsArb: fc.Arbitrary<Document[]> = fc
  .array(
    fc.record({
      original_name: nameArb,
      size: fc.integer({ min: 0, max: 5_000_000 }),
      category: fc.constantFrom(...NON_LINK_CATEGORIES),
    }),
    { minLength: 0, maxLength: 5 },
  )
  .map((rows) =>
    rows.map((row, i) => makeDocument(`doc-${i}`, row.original_name, row.size, row.category)),
  );

// Arbitrary list across all categories (links carry a usable URL so they are
// non-buggy only via the plain-link branch — excluded from control-preservation
// counts below where relevant).
const allCategoriesArb: fc.Arbitrary<DocumentCategory> = fc.constantFrom(
  'documents',
  'scripts',
  'links',
  'docs',
  'trainings',
);

// Search queries: same visible characters plus spaces, and the empty string, to
// exercise the substring-match and empty-query paths.
const queryArb: fc.Arbitrary<string> = fc.oneof(
  fc.constant(''),
  fc
    .array(fc.constantFrom(...'abcdEFGH01-_. '.split('')), { minLength: 1, maxLength: 6 })
    .map((chars) => chars.join('')),
);

async function waitForLoaded(): Promise<void> {
  await screen.findByLabelText('Rechercher un document');
}

function sectionForCategory(category: DocumentCategory): HTMLElement | null {
  const heading = screen.queryByRole('heading', { level: 2, name: CATEGORY_LABELS[category] });
  if (!heading) return null;
  return heading.closest('section');
}

let confirmSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  vi.clearAllMocks();
  cleanup();
  mockedListDocuments.mockResolvedValue({ documents: [], total: 0 });
  mockedDownloadDocument.mockResolvedValue(undefined);
  mockedUploadDocument.mockResolvedValue(makeDocument('uploaded', 'uploaded.pdf', 1, 'documents'));
  mockedDeleteDocument.mockResolvedValue(undefined);
  // Stub confirmation to accept by default (kept for parity with the fix suite).
  confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
  // Default: non-admin unless a test opts in.
  mockedIsAdmin.mockReturnValue(false);
});

afterEach(() => {
  confirmSpy.mockRestore();
  cleanup();
});

// -----------------------------------------------------------------------------
// Preservation (1): Non-admin viewers see no upload control and no Delete
// control for any item, over arbitrary document lists.
// Validates: Requirements 2.3, 3.1
// -----------------------------------------------------------------------------
describe('Preservation: non-admin sees no upload and no delete controls', () => {
  it('renders no upload control and no delete control when isAdmin() is false', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(
          fc.record({
            original_name: nameArb,
            category: fc.constantFrom<DocumentCategory>('documents', 'scripts', 'docs', 'trainings'),
          }),
          { minLength: 0, maxLength: 5 },
        ),
        async (rows) => {
          cleanup();
          mockedIsAdmin.mockReturnValue(false);
          const docs = rows.map((r, i) => makeDocument(`doc-${i}`, r.original_name, 100, r.category));
          mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

          renderPage();
          await waitForLoaded();

          // No upload control of any kind (global or per-section).
          expect(screen.queryByLabelText(UPLOAD_LABEL)).toBeNull();
          expect(screen.queryByRole('button', { name: UPLOAD_BUTTON })).toBeNull();
          // No Delete control anywhere.
          expect(screen.queryAllByRole('button', { name: /supprimer/i })).toHaveLength(0);
          cleanup();
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});

// -----------------------------------------------------------------------------
// Preservation (2): every non-`links` item renders exactly one Download button,
// wired to downloadDocument(id, original_name).
// Validates: Requirements 3.4
// -----------------------------------------------------------------------------
describe('Preservation: non-links items keep the Download button', () => {
  it('renders exactly one Download button per non-links item', async () => {
    await fc.assert(
      fc.asyncProperty(nonLinkDocumentsArb, async (docs) => {
        cleanup();
        mockedIsAdmin.mockReturnValue(false);
        mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

        renderPage();
        await waitForLoaded();

        const downloadButtons = screen.queryAllByRole('button', { name: DOWNLOAD_LABEL });
        expect(downloadButtons).toHaveLength(docs.length);
        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });

  it('wires the Download button to downloadDocument(id, original_name)', async () => {
    mockedIsAdmin.mockReturnValue(false);
    const doc = makeDocument('doc-42', 'rapport.pdf', 1024, 'documents');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

    renderPage();
    await waitForLoaded();

    const button = await screen.findByRole('button', { name: DOWNLOAD_LABEL });
    await userEvent.click(button);

    expect(mockedDownloadDocument).toHaveBeenCalledTimes(1);
    expect(mockedDownloadDocument).toHaveBeenCalledWith('doc-42', 'rapport.pdf');
  });
});

// -----------------------------------------------------------------------------
// Preservation (3): a `links` item with missing/null/empty target_url renders
// the Download fallback and no hyperlink.
// Validates: Requirements 3.5
// -----------------------------------------------------------------------------
describe('Preservation: links item without a usable target_url falls back to Download', () => {
  it('renders the Download button and no link for missing/null/empty target_url', async () => {
    const targetUrlArb = fc.constantFrom<string | null | undefined>(undefined, null, '');

    await fc.assert(
      fc.asyncProperty(nameArb, targetUrlArb, async (name, target_url) => {
        cleanup();
        mockedIsAdmin.mockReturnValue(false);
        const doc = makeDocument('link-x', name, 50, 'links', target_url);
        mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

        renderPage();
        await waitForLoaded();

        // Download fallback present; no hyperlink rendered.
        expect(screen.getAllByRole('button', { name: DOWNLOAD_LABEL })).toHaveLength(1);
        expect(screen.queryByRole('link')).toBeNull();
        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// -----------------------------------------------------------------------------
// Preservation (4): upload category derivation on success / rejection on
// failure. A successful upload refreshes the list and the item appears under
// its server-derived category; a failed upload shows the existing upload error
// banner. In both cases only the File is passed to uploadDocument (no client
// category param).
// Validates: Requirements 3.2, 3.3
// -----------------------------------------------------------------------------
describe('Preservation: upload category derivation and unmapped-extension rejection', () => {
  it('refreshes the list on success and shows the item under its server-derived category, passing only the File', async () => {
    mockedIsAdmin.mockReturnValue(true);
    // Server derives the category (documents) from the extension; the page does
    // not send any category param.
    const uploaded = makeDocument('new-1', 'guide.md', 100, 'documents');
    mockedListDocuments
      .mockResolvedValueOnce({ documents: [], total: 0 })
      .mockResolvedValueOnce({ documents: [uploaded], total: 1 });
    mockedUploadDocument.mockResolvedValue(uploaded);

    renderPage();
    await waitForLoaded();

    const file = new File(['# hello'], 'guide.md', { type: 'text/markdown' });
    const input = screen.getByLabelText(UPLOAD_LABEL) as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(mockedUploadDocument).toHaveBeenCalledTimes(1);
      // Only the File is passed — no client-supplied category argument.
      expect(mockedUploadDocument).toHaveBeenCalledWith(file);
      expect(mockedUploadDocument.mock.calls[0]).toHaveLength(1);
    });

    // List refreshed twice: initial mount + post-upload.
    await waitFor(() => expect(mockedListDocuments).toHaveBeenCalledTimes(2));

    // The uploaded item appears under its server-derived category (Documents).
    const section = sectionForCategory('documents');
    expect(section).not.toBeNull();
    expect(within(section as HTMLElement).getByText('guide.md')).toBeInTheDocument();
  });

  it('shows the upload error banner when the upload is rejected (unmapped extension), passing only the File', async () => {
    mockedIsAdmin.mockReturnValue(true);
    mockedListDocuments.mockResolvedValue({ documents: [], total: 0 });
    mockedUploadDocument.mockRejectedValue(new Error('unmapped extension'));

    renderPage();
    await waitForLoaded();

    const file = new File(['x'], 'bad.exe', { type: 'application/octet-stream' });
    const input = screen.getByLabelText(UPLOAD_LABEL) as HTMLInputElement;
    await userEvent.upload(input, file);

    expect(await screen.findByText(UPLOAD_ERROR)).toBeInTheDocument();
    // Only the File is passed — no client-supplied category argument.
    expect(mockedUploadDocument).toHaveBeenCalledWith(file);
    expect(mockedUploadDocument.mock.calls[0]).toHaveLength(1);
  });
});

// -----------------------------------------------------------------------------
// Preservation (5): sections render in CATEGORY_ORDER first, then any remaining
// present categories — grouping is a partition by category.
// Validates: Requirements 3.6
// -----------------------------------------------------------------------------
describe('Preservation: category grouping and ordering', () => {
  it('renders present sections in CATEGORY_ORDER then remaining categories, partitioning all items', async () => {
    const docsArb = fc
      .array(
        fc.record({
          original_name: nameArb,
          category: allCategoriesArb,
        }),
        { minLength: 0, maxLength: 6 },
      )
      .map((rows) =>
        rows.map((row, i) =>
          // Give links a usable URL so they still render (link branch); category
          // grouping is independent of the download-vs-link branch.
          makeDocument(
            `doc-${i}`,
            row.original_name,
            100,
            row.category,
            row.category === 'links' ? `https://ex${i}.example.com` : undefined,
          ),
        ),
      );

    await fc.assert(
      fc.asyncProperty(docsArb, async (docs) => {
        cleanup();
        mockedIsAdmin.mockReturnValue(false);
        mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

        renderPage();
        await waitForLoaded();

        // Present categories in the observed rendering order.
        const presentSet = new Set(docs.map((d) => d.category));
        const expectedOrder: DocumentCategory[] = [
          ...CATEGORY_ORDER.filter((c) => presentSet.has(c)),
          ...[...presentSet].filter((c) => !CATEGORY_ORDER.includes(c)),
        ];
        const expectedHeadings = expectedOrder.map((c) => CATEGORY_LABELS[c]);

        const headings = screen.queryAllByRole('heading', { level: 2 }).map((h) => h.textContent);
        expect(headings).toEqual(expectedHeadings);

        // Partition: each present category section holds exactly its items.
        for (const category of expectedOrder) {
          const expectedCount = docs.filter((d) => d.category === category).length;
          const section = sectionForCategory(category);
          expect(section).not.toBeNull();
          const items = within(section as HTMLElement).getAllByRole('listitem');
          expect(items).toHaveLength(expectedCount);
        }
        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// -----------------------------------------------------------------------------
// Preservation (6): case-insensitive substring filter on original_name, all
// docs on an empty query, and the empty-state message when nothing matches.
// Validates: Requirements 3.7
// -----------------------------------------------------------------------------
describe('Preservation: search filtering and empty state', () => {
  it('shows the case-insensitive substring matches, all docs on empty query', async () => {
    const docsArb = fc
      .array(
        fc.record({ original_name: nameArb, category: fc.constantFrom<DocumentCategory>('documents', 'scripts') }),
        { minLength: 0, maxLength: 5 },
      )
      .map((rows) => rows.map((r, i) => makeDocument(`doc-${i}`, r.original_name, 100, r.category)));

    await fc.assert(
      fc.asyncProperty(docsArb, queryArb, async (docs, query) => {
        cleanup();
        mockedIsAdmin.mockReturnValue(false);
        mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

        renderPage();
        const input = await screen.findByLabelText('Rechercher un document');

        fireEvent.change(input, { target: { value: query } });

        const normalized = query.trim().toLowerCase();
        const expected =
          normalized === ''
            ? docs
            : docs.filter((d) => d.original_name.toLowerCase().includes(normalized));

        await waitFor(() => {
          const buttons = screen.queryAllByRole('button', { name: DOWNLOAD_LABEL });
          expect(buttons).toHaveLength(expected.length);
        });
        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });

  it('shows the empty-state message when no item matches the query', async () => {
    mockedIsAdmin.mockReturnValue(false);
    const docs = [
      makeDocument('d1', 'alpha.pdf', 100, 'documents'),
      makeDocument('d2', 'beta.sh', 200, 'scripts'),
    ];
    mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

    renderPage();
    const input = await screen.findByLabelText('Rechercher un document');

    fireEvent.change(input, { target: { value: 'no-such-name-zzz' } });

    expect(await screen.findByText(EMPTY_MESSAGE)).toBeInTheDocument();
  });

  it('shows the empty-state message when the list is empty', async () => {
    mockedIsAdmin.mockReturnValue(false);
    mockedListDocuments.mockResolvedValue({ documents: [], total: 0 });

    renderPage();
    await waitForLoaded();

    expect(screen.getByText(EMPTY_MESSAGE)).toBeInTheDocument();
  });
});

// Keep formatSize referenced so a helper import mismatch surfaces at compile
// time (mirrors the existing suite's dependency on the shared export).
void formatSize;
