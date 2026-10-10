import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, within, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import fc from 'fast-check';
import { DocumentsPage } from './DocumentsPage';
import { documentService, type Document, type DocumentCategory } from '../services/documentService';
import { authService } from '../services/authService';
import { LanguageProvider } from '../hooks/useLanguage';

/**
 * Preservation tests for the documents-page-categories bugfix.
 *
 * Feature: documents-page-categories (BUGFIX)
 * Property 2: Preservation - Behavior Unrelated To Subfolder Grouping
 * Validates: Requirements 3.1, 3.3, 3.5, 3.6
 *
 * Written BEFORE the fix (observation-first). They capture the CURRENT
 * (unfixed) observable behavior of DocumentsPage for inputs unrelated to
 * subfolder grouping, so they MUST PASS on the unfixed code. After the fix they
 * are re-run to confirm no regressions.
 *
 * Covered here (frontend-observable behaviors):
 *   - Search: filename search filters displayed files by case-insensitive
 *     substring of original_name (Requirement 3.1) — randomized queries.
 *   - Empty-category: a category with no matching files renders no section
 *     (Requirement 3.5).
 *   - Empty-state: when nothing matches the current view the empty-state
 *     message is shown (Requirement 3.6).
 *   - Download / upload wiring is preserved (Requirement 3.3).
 *
 * NOTE: These use the currently-typed categories (documents/scripts/links)
 * because they assert behavior that must be UNCHANGED by the subfolder-grouping
 * fix. The fix-specific categories (docs/trainings) are covered by the bug
 * exploration test, not here.
 */

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

const NUM_RUNS = 100;

// The categories that exist on the CURRENT (unfixed) union — these are the
// inputs whose behavior must be preserved by the fix.
const CATEGORIES: DocumentCategory[] = ['documents', 'scripts', 'links'];

// Full label map for the widened DocumentCategory union (French — the default
// Active_Language). docs -> "Documentation", trainings -> "Formations" per the
// translation keys. The preservation tests still only exercise the original
// three categories (see CATEGORIES above); the extra keys exist solely to keep
// this map assignable to Record<DocumentCategory, string> after the widening.
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

// Visible, non-whitespace characters so DOM text matching is stable; mixed case
// so the case-insensitive search filter is exercised.
const nameCharArb = fc.constantFrom(...'abcdefghijABCDEFGHIJ0123456789-_.'.split(''));
const nameArb: fc.Arbitrary<string> = fc
  .array(nameCharArb, { minLength: 1, maxLength: 12 })
  .map((chars) => chars.join(''));

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
// Search preservation (property-based). Requirement 3.1
// -----------------------------------------------------------------------------
describe('Preservation: filename search filters by case-insensitive substring', () => {
  it('displays exactly the substring matches; all docs when the query is empty', async () => {
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

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// -----------------------------------------------------------------------------
// Empty-category preservation (property-based). Requirement 3.5
// -----------------------------------------------------------------------------
describe('Preservation: empty category sections are omitted', () => {
  it('renders no section for a category with zero matching documents', async () => {
    await fc.assert(
      fc.asyncProperty(documentsArb, async (documents) => {
        cleanup();
        mockedListDocuments.mockResolvedValue({ documents, total: documents.length });

        renderPage();
        await waitForLoaded();

        for (const category of CATEGORIES) {
          const expectedDocs = documents.filter((d) => d.category === category);
          const section = sectionForCategory(category);
          if (expectedDocs.length === 0) {
            expect(section).toBeNull();
          } else {
            expect(section).not.toBeNull();
            const items = within(section as HTMLElement).getAllByRole('listitem');
            expect(items).toHaveLength(expectedDocs.length);
          }
        }

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// -----------------------------------------------------------------------------
// Empty-state preservation. Requirement 3.6
// -----------------------------------------------------------------------------
describe('Preservation: empty-state message', () => {
  it('shows the empty-state message when the list is empty', async () => {
    mockedListDocuments.mockResolvedValue({ documents: [], total: 0 });

    renderPage();
    await waitForLoaded();

    expect(screen.getByText('Aucun document disponible.')).toBeInTheDocument();
  });

  it('shows the empty-state message when a search matches nothing', async () => {
    const docs = [makeDocument('d1', 'alpha.pdf', 10, 'documents')];
    mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

    renderPage();
    const input = await screen.findByLabelText('Rechercher un document');

    fireEvent.change(input, { target: { value: 'zzzznomatch' } });

    expect(await screen.findByText('Aucun document disponible.')).toBeInTheDocument();
  });
});

// -----------------------------------------------------------------------------
// Download / upload wiring preservation. Requirement 3.3
// -----------------------------------------------------------------------------
describe('Preservation: download and upload wiring', () => {
  it('requests the download for the selected item by id and original_name', async () => {
    const doc = makeDocument('doc-9', 'notes.txt', 512, 'documents');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

    renderPage();
    await waitForLoaded();

    const button = await screen.findByRole('button', { name: 'Télécharger' });
    await userEvent.click(button);

    expect(mockedDownloadDocument).toHaveBeenCalledTimes(1);
    expect(mockedDownloadDocument).toHaveBeenCalledWith('doc-9', 'notes.txt');
  });

  it('refreshes the list after a successful admin upload so the new item appears', async () => {
    mockedIsAdmin.mockReturnValue(true);
    const uploaded = makeDocument('new-1', 'guide.md', 100, 'documents');
    mockedListDocuments
      .mockResolvedValueOnce({ documents: [], total: 0 })
      .mockResolvedValueOnce({ documents: [uploaded], total: 1 });
    mockedUploadDocument.mockResolvedValue(uploaded);

    renderPage();
    await waitForLoaded();

    const file = new File(['# hello'], 'guide.md', { type: 'text/markdown' });
    const input = screen.getByLabelText('Téléverser un document') as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => expect(mockedUploadDocument).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mockedListDocuments).toHaveBeenCalledTimes(2));

    const section = sectionForCategory('documents');
    expect(section).not.toBeNull();
    expect(within(section as HTMLElement).getByText('guide.md')).toBeInTheDocument();
  });
});
