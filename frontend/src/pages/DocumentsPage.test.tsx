import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, within, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import fc from 'fast-check';
import { DocumentsPage, formatSize } from './DocumentsPage';
import { documentService, type Document, type DocumentCategory } from '../services/documentService';
import { authService } from '../services/authService';
import { LanguageProvider } from '../hooks/useLanguage';

// DocumentsPage consumes the translation context, so it must render inside a
// LanguageProvider. The default Active_Language is French, so the existing
// French-text assertions in this file continue to hold.
function renderPage() {
  return render(
    <LanguageProvider>
      <DocumentsPage />
    </LanguageProvider>,
  );
}

// Mock the service module: methods are vi.fn()s whose behaviour is set per test.
vi.mock('../services/documentService', () => ({
  documentService: {
    listDocuments: vi.fn(),
    downloadDocument: vi.fn(),
    uploadDocument: vi.fn(),
  },
}));

// Mock the auth service so we can flip isAdmin() per test.
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

const CATEGORIES: DocumentCategory[] = ['documents', 'scripts', 'links'];

// Full label map for the widened DocumentCategory union (French — the default
// Active_Language). docs -> "Documentation", trainings -> "Formations" per the
// translation keys; the three original entries are unchanged.
const CATEGORY_LABELS: Record<DocumentCategory, string> = {
  documents: 'Documents',
  scripts: 'Scripts',
  links: 'Liens',
  docs: 'Documentation',
  trainings: 'Formations',
};

// Build a full Document record from the fields that matter to the page.
function makeDocument(
  id: string,
  original_name: string,
  size: number,
  category: DocumentCategory,
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
  };
}

// Name characters are restricted to a set of visible, non-whitespace characters
// so that DOM text matching (getByText) is stable — the browser collapses and
// trims whitespace, which would make whitespace-only names unmatchable. The set
// intentionally mixes upper/lower case so the case-insensitive search filter is
// meaningfully exercised.
const nameCharArb = fc.constantFrom(
  ...'abcdefghijABCDEFGHIJ0123456789-_.'.split(''),
);
const nameArb: fc.Arbitrary<string> = fc
  .array(nameCharArb, { minLength: 1, maxLength: 12 })
  .map((chars) => chars.join(''));

// Arbitrary list of documents with UNIQUE ids. Names/sizes/categories are arbitrary.
// ids are made unique via their array index.
const documentsArb: fc.Arbitrary<Document[]> = fc
  .array(
    fc.record({
      original_name: nameArb,
      size: fc.integer({ min: 0, max: 5_000_000 }),
      category: fc.constantFrom(...CATEGORIES),
    }),
    { minLength: 0, maxLength: 5 },
  )
  .map((rows) =>
    rows.map((row, index) => makeDocument(`doc-${index}`, row.original_name, row.size, row.category)),
  );

// Search queries: drawn from the same visible characters plus spaces, and the
// empty string, to exercise both the substring-match and the empty-query paths.
const queryArb: fc.Arbitrary<string> = fc.oneof(
  fc.constant(''),
  fc
    .array(fc.constantFrom(...'abcdEFGH01-_. '.split('')), { minLength: 1, maxLength: 6 })
    .map((chars) => chars.join('')),
);

// Wait until the loading state has resolved (the page shows either sections,
// the empty-state message, or the search box).
async function waitForLoaded(): Promise<void> {
  await screen.findByLabelText('Rechercher un document');
}

// Return the <section> element for a given category, or null if not rendered.
function sectionForCategory(category: DocumentCategory): HTMLElement | null {
  const heading = screen.queryByRole('heading', { level: 2, name: CATEGORY_LABELS[category] });
  if (!heading) return null;
  return heading.closest('section');
}

beforeEach(() => {
  vi.clearAllMocks();
  cleanup();
  // Sensible default so a test that forgets to configure still resolves cleanly.
  mockedListDocuments.mockResolvedValue({ documents: [], total: 0 });
  mockedDownloadDocument.mockResolvedValue(undefined);
  mockedUploadDocument.mockResolvedValue(makeDocument('uploaded', 'uploaded.pdf', 1, 'documents'));
  // Default: non-admin unless a test opts in.
  mockedIsAdmin.mockReturnValue(false);
});

// -----------------------------------------------------------------------------
// Task 7.2 (docs-auto-seed): grouping is a partition by category.
// Validates: Requirements 8.1
// -----------------------------------------------------------------------------
describe('Property 7: grouping is a partition by category', () => {
  it('every displayed document appears in exactly its category section', async () => {
    await fc.assert(
      fc.asyncProperty(documentsArb, async (documents) => {
        cleanup();
        mockedListDocuments.mockResolvedValue({ documents, total: documents.length });

        renderPage();
        await waitForLoaded();

        const seenIds = new Set<string>();

        for (const category of CATEGORIES) {
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

// -----------------------------------------------------------------------------
// Category order drives grouped rendering order.
// Validates: Requirements 2.1, 2.3 (documents-page-categories bugfix)
//
// The documents-page-categories bugfix replaced the old hard-coded
// ['documents','scripts','links'] order with the content-subfolder order
// CATEGORY_ORDER = ['docs','links','scripts','trainings']; any category outside
// that list (e.g. a legacy `documents` row) is rendered AFTER the ordered ones
// so nothing is dropped. This test asserts that new intended ordering.
// -----------------------------------------------------------------------------
describe('category order drives grouped rendering', () => {
  it('renders the four subfolder sections in CATEGORY_ORDER', async () => {
    const docs = [
      makeDocument('t1', 'a.md', 10, 'trainings'),
      makeDocument('s1', 'b.sh', 20, 'scripts'),
      makeDocument('l1', 'c.links', 30, 'links'),
      makeDocument('d1', 'd.pdf', 40, 'docs'),
    ];
    mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

    renderPage();
    await waitForLoaded();

    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    // CATEGORY_ORDER = docs, links, scripts, trainings.
    expect(headings).toEqual(['Documentation', 'Liens', 'Scripts', 'Formations']);
  });

  it('renders a legacy documents category after the ordered subfolder sections', async () => {
    const docs = [
      makeDocument('l1', 'a.links', 10, 'links'),
      makeDocument('s1', 'b.sh', 20, 'scripts'),
      makeDocument('d1', 'c.pdf', 30, 'documents'),
    ];
    mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

    renderPage();
    await waitForLoaded();

    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    // links + scripts are in CATEGORY_ORDER; the legacy `documents` category is
    // not, so it renders last.
    expect(headings).toEqual(['Liens', 'Scripts', 'Documents']);
  });
});

// -----------------------------------------------------------------------------
// Task 7.2 — Unit: upload control renders only for admins.
// Validates: Requirements 3.1, 3.2
// -----------------------------------------------------------------------------
describe('Task 7.2: upload control admin gating', () => {
  it('renders the upload control when isAdmin() is true', async () => {
    mockedIsAdmin.mockReturnValue(true);
    mockedListDocuments.mockResolvedValue({ documents: [], total: 0 });

    renderPage();
    await waitForLoaded();

    // Per-section upload controls (documents-page-upload-delete-per-category):
    // the base-labelled control resolves to a single input on the documents
    // section, and at least one "Téléverser" button renders for admins.
    expect(screen.getByLabelText('Téléverser un document')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Téléverser' }).length).toBeGreaterThan(0);
  });

  it('hides the upload control when isAdmin() is false', async () => {
    mockedIsAdmin.mockReturnValue(false);
    mockedListDocuments.mockResolvedValue({ documents: [], total: 0 });

    renderPage();
    await waitForLoaded();

    expect(screen.queryByLabelText('Téléverser un document')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Téléverser' })).toBeNull();
  });
});

// -----------------------------------------------------------------------------
// Task 7.3 — Unit: successful upload refreshes list; item appears under its
// category; download requests GET /api/documents/{id}/download.
// Validates: Requirements 5.1, 5.2
// -----------------------------------------------------------------------------
describe('Task 7.3: upload refresh and download wiring', () => {
  it('refreshes the list after a successful upload and shows the new item under its category', async () => {
    mockedIsAdmin.mockReturnValue(true);
    const uploaded = makeDocument('new-1', 'guide.md', 100, 'documents');

    // First load: empty. After upload: contains the new document.
    mockedListDocuments
      .mockResolvedValueOnce({ documents: [], total: 0 })
      .mockResolvedValueOnce({ documents: [uploaded], total: 1 });
    mockedUploadDocument.mockResolvedValue(uploaded);

    renderPage();
    await waitForLoaded();

    const file = new File(['# hello'], 'guide.md', { type: 'text/markdown' });
    const input = screen.getByLabelText('Téléverser un document') as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(mockedUploadDocument).toHaveBeenCalledTimes(1);
      expect(mockedUploadDocument).toHaveBeenCalledWith(file);
    });

    // List refreshed twice: initial mount + post-upload.
    await waitFor(() => expect(mockedListDocuments).toHaveBeenCalledTimes(2));

    // New item appears under the Documents category.
    const section = sectionForCategory('documents');
    expect(section).not.toBeNull();
    expect(within(section as HTMLElement).getByText('guide.md')).toBeInTheDocument();
  });

  it('requests the download for the selected item', async () => {
    mockedIsAdmin.mockReturnValue(false);
    const doc = makeDocument('doc-9', 'notes.txt', 512, 'documents');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });
    mockedDownloadDocument.mockResolvedValue(undefined);

    renderPage();
    await waitForLoaded();

    const button = await screen.findByRole('button', { name: 'Télécharger' });
    await userEvent.click(button);

    expect(mockedDownloadDocument).toHaveBeenCalledTimes(1);
    expect(mockedDownloadDocument).toHaveBeenCalledWith('doc-9', 'notes.txt');
  });

  it('shows an upload error banner when the upload fails', async () => {
    mockedIsAdmin.mockReturnValue(true);
    mockedListDocuments.mockResolvedValue({ documents: [], total: 0 });
    mockedUploadDocument.mockRejectedValue(new Error('rejected'));

    renderPage();
    await waitForLoaded();

    const file = new File(['x'], 'bad.exe', { type: 'application/octet-stream' });
    const input = screen.getByLabelText('Téléverser un document') as HTMLInputElement;
    await userEvent.upload(input, file);

    expect(await screen.findByText('Échec du téléversement du document.')).toBeInTheDocument();
  });
});

// -----------------------------------------------------------------------------
// Displayed item content.
// Validates: Requirements 8.2, 8.3
// -----------------------------------------------------------------------------
describe('Property 8: displayed item content', () => {
  it('every rendered item shows the name, its formatted size, and a download control', async () => {
    await fc.assert(
      fc.asyncProperty(documentsArb, async (documents) => {
        cleanup();
        mockedListDocuments.mockResolvedValue({ documents, total: documents.length });

        renderPage();
        await waitForLoaded();

        const downloadButtons = screen.queryAllByRole('button', { name: 'Télécharger' });
        expect(downloadButtons).toHaveLength(documents.length);

        for (const doc of documents) {
          expect(screen.getAllByText(doc.original_name).length).toBeGreaterThan(0);
          expect(screen.getAllByText(formatSize(doc.size)).length).toBeGreaterThan(0);
        }

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// -----------------------------------------------------------------------------
// Search filter subset and membership.
// Validates: Requirements 9.1, 9.2
// -----------------------------------------------------------------------------
describe('Property 9: search filter subset and membership', () => {
  it('displays exactly the case-insensitive substring matches; all docs when empty', async () => {
    await fc.assert(
      fc.asyncProperty(documentsArb, queryArb, async (documents, query) => {
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

        const expectedIds = new Set(expected.map((d) => d.id));
        for (const doc of documents) {
          const shown = screen.queryAllByText(doc.original_name).length > 0;
          if (expectedIds.has(doc.id)) {
            expect(shown).toBe(true);
          }
        }

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// -----------------------------------------------------------------------------
// formatSize
// Validates: Requirements 8.2
// -----------------------------------------------------------------------------
describe('formatSize', () => {
  it('returns a non-empty string containing a size unit for any non-negative integer', () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 500_000_000_000 }), (bytes) => {
        const result = formatSize(bytes);
        expect(typeof result).toBe('string');
        expect(result.length).toBeGreaterThan(0);
        expect(/\b(o|Ko|Mo|Go)\b/.test(result)).toBe(true);
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

describe('DocumentsPage — mount and interactions', () => {
  it('calls documentService.listDocuments on mount', async () => {
    mockedListDocuments.mockResolvedValue({ documents: [], total: 0 });

    renderPage();
    await waitForLoaded();

    expect(mockedListDocuments).toHaveBeenCalledTimes(1);
  });

  it('calls downloadDocument with the document id and original_name when Télécharger is clicked', async () => {
    const doc = makeDocument('doc-1', 'statuts.pdf', 2048, 'documents');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });
    mockedDownloadDocument.mockResolvedValue(undefined);

    renderPage();
    await waitForLoaded();

    const button = await screen.findByRole('button', { name: 'Télécharger' });
    await userEvent.click(button);

    expect(mockedDownloadDocument).toHaveBeenCalledTimes(1);
    expect(mockedDownloadDocument).toHaveBeenCalledWith('doc-1', 'statuts.pdf');
  });

  it('shows a French error message when the document list fails to load', async () => {
    mockedListDocuments.mockRejectedValue(new Error('network'));

    renderPage();

    expect(await screen.findByText('Impossible de charger les documents')).toBeInTheDocument();
  });

  it('shows a French per-download error message when the download fails', async () => {
    const doc = makeDocument('doc-1', 'rapport.pdf', 1024, 'documents');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });
    mockedDownloadDocument.mockRejectedValue(new Error('denied'));

    renderPage();
    await waitForLoaded();

    const button = await screen.findByRole('button', { name: 'Télécharger' });
    await userEvent.click(button);

    expect(
      await screen.findByText('Échec du téléchargement de « rapport.pdf »'),
    ).toBeInTheDocument();
  });
});

afterEach(() => {
  cleanup();
});
