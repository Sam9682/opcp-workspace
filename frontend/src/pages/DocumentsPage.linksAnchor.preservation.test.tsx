/**
 * Preservation property tests for the "documents-links-html-link" bugfix.
 *
 * Property 2 (Preservation): Non-links documents render exactly as before.
 *   isBugCondition(doc) === (doc.category === 'links')
 *   For every doc where NOT isBugCondition(doc) (doc.category !== 'links') the
 *   fixed DocumentsPage must produce the SAME result as the original — a
 *   "Download" button wired to documentService.downloadDocument — and the
 *   surrounding grouping, ordering and search/filter behaviour must be
 *   unchanged.
 *
 * Observation-first: these tests are written and run against the UNFIXED code
 * so the baseline behaviour they capture is asserted to hold today. They are
 * re-run after the fix (task 3.4) to confirm no regressions.
 *
 * Conventions reused from DocumentsPage.test.tsx / DocumentsPage.preservation
 * .test.tsx: mock documentService/authService, render inside a LanguageProvider,
 * use a makeDocument helper, and use fast-check with NUM_RUNS = 100. makeDocument
 * accepts an optional target_url so links fixtures can carry a URL; the field is
 * declared on the Document type by the fix, so before the fix it is simply an
 * extra (ignored) property on the object.
 *
 * NOTE: The access-control preservation half of this property is a backend
 * concern and is captured in tests/test_documents_links_target_url_preservation.py.
 *
 * Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, within, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import fc from 'fast-check';
import { DocumentsPage } from './DocumentsPage';
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

vi.mock('../services/documentService', () => ({
  documentService: {
    listDocuments: vi.fn(),
    downloadDocument: vi.fn(),
    uploadDocument: vi.fn(),
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
const mockedIsAdmin = vi.mocked(authService.isAdmin);

// Minimum property-test iterations mandated by the design (>= 100).
const NUM_RUNS = 100;

// Non-`links` categories only — this property is about documents where the bug
// condition does NOT hold (doc.category !== 'links'). CATEGORY_ORDER is
// ['docs','links','scripts','trainings']; 'documents' is an unlisted category
// rendered AFTER the ordered ones.
const NON_LINK_CATEGORIES: DocumentCategory[] = ['docs', 'scripts', 'trainings', 'documents'];

// French labels (the default Active_Language) for every category so DOM lookups
// by heading text are stable.
const CATEGORY_LABELS: Record<DocumentCategory, string> = {
  documents: 'Documents',
  scripts: 'Scripts',
  links: 'Liens',
  docs: 'Documentation',
  trainings: 'Formations',
};

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
    // Cast keeps this test compilable before the fix adds target_url to Document.
    ...(target_url !== undefined ? { target_url } : {}),
  } as Document;
}

// Visible, non-whitespace characters so DOM text matching is stable; mixed case
// so the case-insensitive search filter is meaningfully exercised.
const nameCharArb = fc.constantFrom(...'abcdefghijABCDEFGHIJ0123456789-_.'.split(''));
const nameArb: fc.Arbitrary<string> = fc
  .array(nameCharArb, { minLength: 1, maxLength: 12 })
  .map((chars) => chars.join(''));

// Arbitrary lists of NON-`links` documents with unique ids.
const nonLinkDocumentsArb: fc.Arbitrary<Document[]> = fc
  .array(
    fc.record({
      original_name: nameArb,
      size: fc.integer({ min: 0, max: 5_000_000 }),
      category: fc.constantFrom(...NON_LINK_CATEGORIES),
    }),
    { minLength: 0, maxLength: 6 },
  )
  .map((rows) =>
    rows.map((row, index) => makeDocument(`doc-${index}`, row.original_name, row.size, row.category)),
  );

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

beforeEach(() => {
  vi.clearAllMocks();
  cleanup();
  mockedListDocuments.mockResolvedValue({ documents: [], total: 0 });
  mockedDownloadDocument.mockResolvedValue(undefined);
  mockedUploadDocument.mockResolvedValue(makeDocument('uploaded', 'uploaded.pdf', 1, 'documents'));
  mockedIsAdmin.mockReturnValue(false);
});

afterEach(() => {
  cleanup();
});

// -----------------------------------------------------------------------------
// Download-button preservation. Requirements 3.1, 3.2
// For arbitrary lists of non-`links` documents, every item renders a "Download"
// button, and clicking it calls downloadDocument(doc.id, doc.original_name).
// -----------------------------------------------------------------------------
describe('Preservation: non-links documents render a Download button wired to the download flow', () => {
  it('every non-links item renders exactly one Download button', async () => {
    await fc.assert(
      fc.asyncProperty(nonLinkDocumentsArb, async (documents) => {
        cleanup();
        mockedListDocuments.mockResolvedValue({ documents, total: documents.length });

        renderPage();
        await waitForLoaded();

        const downloadButtons = screen.queryAllByRole('button', { name: 'Télécharger' });
        expect(downloadButtons).toHaveLength(documents.length);

        // No anchors should be rendered for non-links documents.
        for (const doc of documents) {
          expect(screen.queryByRole('link', {
            name: new RegExp(doc.original_name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'),
          })).toBeNull();
        }

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });

  it('clicking a non-links Download button calls downloadDocument(id, original_name)', async () => {
    await fc.assert(
      fc.asyncProperty(
        nameArb,
        fc.integer({ min: 0, max: 5_000_000 }),
        fc.constantFrom(...NON_LINK_CATEGORIES),
        async (name, size, category) => {
          cleanup();
          mockedDownloadDocument.mockClear();
          const doc = makeDocument('only', name, size, category);
          mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

          renderPage();
          await waitForLoaded();

          const button = await screen.findByRole('button', { name: 'Télécharger' });
          await userEvent.click(button);

          expect(mockedDownloadDocument).toHaveBeenCalledTimes(1);
          expect(mockedDownloadDocument).toHaveBeenCalledWith('only', name);

          cleanup();
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});

// -----------------------------------------------------------------------------
// Grouping / ordering preservation. Requirement 3.3
// Section headings follow CATEGORY_ORDER = ['docs','links','scripts','trainings']
// with any remaining present (unlisted) categories rendered after.
// -----------------------------------------------------------------------------
describe('Preservation: section headings follow CATEGORY_ORDER with unlisted categories after', () => {
  it('orders present sections by CATEGORY_ORDER, then remaining categories', async () => {
    await fc.assert(
      fc.asyncProperty(nonLinkDocumentsArb, async (documents) => {
        cleanup();
        mockedListDocuments.mockResolvedValue({ documents, total: documents.length });

        renderPage();
        await waitForLoaded();

        // Categories actually present in the generated list.
        const present = new Set(documents.map((d) => d.category));

        // Expected heading order: CATEGORY_ORDER members present first (excluding
        // 'links', which cannot appear in a non-link list), then unlisted
        // present categories (e.g. 'documents') in first-appearance order.
        const CATEGORY_ORDER: DocumentCategory[] = ['docs', 'links', 'scripts', 'trainings'];
        const ordered = CATEGORY_ORDER.filter((c) => present.has(c));
        const rest: DocumentCategory[] = [];
        for (const doc of documents) {
          if (!CATEGORY_ORDER.includes(doc.category) && !rest.includes(doc.category)) {
            rest.push(doc.category);
          }
        }
        const expectedHeadings = [...ordered, ...rest].map((c) => CATEGORY_LABELS[c]);

        const headings = screen
          .queryAllByRole('heading', { level: 2 })
          .map((h) => h.textContent);

        expect(headings).toEqual(expectedHeadings);

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });

  it('renders a legacy documents category after the ordered subfolder sections (example)', async () => {
    const docs = [
      makeDocument('s1', 'b.sh', 20, 'scripts'),
      makeDocument('t1', 'a.md', 10, 'trainings'),
      makeDocument('d1', 'c.pdf', 30, 'documents'),
      makeDocument('dc1', 'e.pdf', 40, 'docs'),
    ];
    mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

    renderPage();
    await waitForLoaded();

    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    // docs, scripts, trainings are in CATEGORY_ORDER; legacy `documents` renders last.
    expect(headings).toEqual(['Documentation', 'Scripts', 'Formations', 'Documents']);
  });
});

// -----------------------------------------------------------------------------
// Search / filter preservation. Requirement 3.4
// Case-insensitive original_name substring filtering is unchanged.
// -----------------------------------------------------------------------------
describe('Preservation: case-insensitive original_name substring search is unchanged', () => {
  it('displays exactly the substring matches; all docs when the query is empty', async () => {
    await fc.assert(
      fc.asyncProperty(nonLinkDocumentsArb, queryArb, async (documents, query) => {
        cleanup();
        mockedListDocuments.mockResolvedValue({ documents, total: documents.length });

        renderPage();
        const input = await screen.findByLabelText('Rechercher un document');

        fireEvent.change(input, { target: { value: query } });

        const normalized = query.trim().toLowerCase();
        const expected =
          normalized === ''
            ? documents
            : documents.filter((d) => d.original_name.toLowerCase().includes(normalized));

        await waitFor(() => {
          const buttons = screen.queryAllByRole('button', { name: 'Télécharger' });
          expect(buttons).toHaveLength(expected.length);
        });

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// -----------------------------------------------------------------------------
// Grouping partition preservation (example + property): every displayed
// non-links document appears in exactly its category section. Requirement 3.3
// -----------------------------------------------------------------------------
describe('Preservation: grouping is a partition by category', () => {
  it('every displayed document appears in exactly its category section', async () => {
    await fc.assert(
      fc.asyncProperty(nonLinkDocumentsArb, async (documents) => {
        cleanup();
        mockedListDocuments.mockResolvedValue({ documents, total: documents.length });

        renderPage();
        await waitForLoaded();

        const seenIds = new Set<string>();

        for (const category of NON_LINK_CATEGORIES) {
          const expectedDocs = documents.filter((d) => d.category === category);
          const section = sectionForCategory(category);

          if (expectedDocs.length === 0) {
            expect(section).toBeNull();
            continue;
          }

          expect(section).not.toBeNull();
          const items = within(section as HTMLElement).getAllByRole('listitem');
          expect(items).toHaveLength(expectedDocs.length);

          for (const doc of expectedDocs) {
            expect(within(section as HTMLElement).getAllByText(doc.original_name).length).toBeGreaterThan(0);
            expect(seenIds.has(doc.id)).toBe(false);
            seenIds.add(doc.id);
          }
        }

        expect(seenIds.size).toBe(documents.length);
        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});
