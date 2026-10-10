/**
 * Bug condition exploration tests for the
 * "documents-page-upload-delete-per-category" bugfix.
 *
 * Property 1 (Bug Condition) — Per-Section Upload, Admin Delete, Plain-Text
 * Links. isBugCondition(X) is true when:
 *   (X.isAdmin AND NOT X.hasPerSectionUploadControls)
 *   OR (X.isAdmin AND X.renderedItem.exists AND NOT X.renderedItem.hasDeleteControl)
 *   OR (X.renderedItem.category = 'links'
 *       AND X.renderedItem.hasUsableTargetUrl
 *       AND X.renderedItem.linkRendersAsButton)
 *
 * These tests encode the EXPECTED (post-fix) behaviour and are run against the
 * UNFIXED code. They are EXPECTED TO FAIL here — that failure confirms the bug:
 *   (a) an admin sees only a single global upload control, no per-section ones;
 *   (b) no Delete control is rendered next to items and deleteDocument is absent;
 *   (c) a usable `links` item renders as a button-styled anchor rather than a
 *       plain hyperlink.
 *
 * Conventions reused from DocumentsPage.test.tsx / DocumentsPage.linksAnchor.bug
 * .test.tsx: mock documentService (extended with deleteDocument) / authService,
 * render inside a LanguageProvider (default French), the makeDocument helper
 * (extended with target_url), fast-check with NUM_RUNS = 100, and window.confirm
 * stubbed via vi.spyOn.
 *
 * Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.4
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, within, waitFor } from '@testing-library/react';
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

// Mock the service module. Extended with a `deleteDocument` mock so the wiring
// test can assert the fix calls it; on unfixed code the page never invokes it.
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

// French category labels (default Active_Language). Used to build the expected
// per-section upload accessible label "<upload label> — <category label>".
const CATEGORY_LABELS: Record<DocumentCategory, string> = {
  documents: 'Documents',
  scripts: 'Scripts',
  links: 'Liens',
  docs: 'Documentation',
  trainings: 'Formations',
};

// Base upload label from the translations (FR).
const UPLOAD_LABEL = 'Téléverser un document';

// Build a full Document record. target_url is optional so `links` fixtures can
// carry a URL; cast keeps this compilable before the fix declares target_url.
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

async function waitForLoaded(): Promise<void> {
  await screen.findByLabelText('Rechercher un document');
}

// Return the <section> element for a given category, or null if not rendered.
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
  // Stub confirmation to accept by default; the delete-wiring test relies on it.
  confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
  // Default: non-admin unless a test opts in.
  mockedIsAdmin.mockReturnValue(false);
});

afterEach(() => {
  confirmSpy.mockRestore();
  cleanup();
});

// -----------------------------------------------------------------------------
// (a) Per-section upload control (admin). Every rendered category section must
// expose its own upload control targeted by a per-section accessible label
// "<upload label> — <category label>". Scoped to a concrete admin state with
// items across multiple categories for reproducibility.
//
// EXPECTED TO FAIL on unfixed code: only a single global upload control exists.
// Validates: Requirements 1.1, 2.1
// -----------------------------------------------------------------------------
describe('Bug condition (a): admin sees a per-section upload control in every section', () => {
  it('renders an upload control labeled per category inside each rendered section', async () => {
    mockedIsAdmin.mockReturnValue(true);
    const docs = [
      makeDocument('d1', 'guide.pdf', 40, 'docs'),
      makeDocument('l1', 'AWS', 30, 'links', 'https://example.com'),
      makeDocument('s1', 'deploy.sh', 20, 'scripts'),
      makeDocument('t1', 'course.md', 10, 'trainings'),
    ];
    mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

    renderPage();
    await waitForLoaded();

    const presentCategories: DocumentCategory[] = ['docs', 'links', 'scripts', 'trainings'];
    for (const category of presentCategories) {
      const section = sectionForCategory(category);
      expect(section).not.toBeNull();
      const perSectionLabel = `${UPLOAD_LABEL} — ${CATEGORY_LABELS[category]}`;
      // Each section must contain its own upload control targeted by the
      // per-section accessible label.
      const control = within(section as HTMLElement).getByLabelText(perSectionLabel);
      expect(control).toBeInTheDocument();
    }
  });
});

// -----------------------------------------------------------------------------
// (b) Admin delete control present next to a rendered item.
//
// EXPECTED TO FAIL on unfixed code: no Delete control is rendered.
// Validates: Requirements 1.2, 2.2
// -----------------------------------------------------------------------------
describe('Bug condition (b): admin sees a Delete control next to a rendered item', () => {
  it('renders a "Supprimer" control alongside a listed item for admins', async () => {
    mockedIsAdmin.mockReturnValue(true);
    const doc = makeDocument('doc-1', 'statuts.pdf', 2048, 'documents');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

    renderPage();
    await waitForLoaded();

    const section = sectionForCategory('documents');
    expect(section).not.toBeNull();
    const item = within(section as HTMLElement).getByRole('listitem');
    // A Delete control must exist next to the item.
    expect(within(item).getByRole('button', { name: /supprimer/i })).toBeInTheDocument();
  });

  it('shows the Delete control across arbitrary admin document lists', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(
          fc.record({
            original_name: fc
              .array(fc.constantFrom(...'abcdefghij0123456789'.split('')), { minLength: 1, maxLength: 10 })
              .map((c) => c.join('')),
            category: fc.constantFrom<DocumentCategory>('documents', 'scripts', 'links'),
          }),
          { minLength: 1, maxLength: 4 },
        ),
        async (rows) => {
          cleanup();
          mockedIsAdmin.mockReturnValue(true);
          const docs = rows.map((r, i) => makeDocument(`doc-${i}`, r.original_name, 100, r.category));
          mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

          renderPage();
          await waitForLoaded();

          // One Delete control per rendered item for an admin.
          const deleteButtons = screen.queryAllByRole('button', { name: /supprimer/i });
          expect(deleteButtons).toHaveLength(docs.length);
          cleanup();
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});

// -----------------------------------------------------------------------------
// (c) Delete wiring: activating Delete (confirmation stubbed to true) calls
// documentService.deleteDocument(doc.id) then re-fetches via listDocuments.
//
// EXPECTED TO FAIL on unfixed code: the control and method are absent.
// Validates: Requirements 1.2, 2.2
// -----------------------------------------------------------------------------
describe('Bug condition (c): activating Delete calls deleteDocument and refreshes', () => {
  it('calls deleteDocument(id) then re-fetches the list when confirmed', async () => {
    mockedIsAdmin.mockReturnValue(true);
    const doc = makeDocument('doc-9', 'notes.txt', 512, 'documents');
    // First load returns the doc; the post-delete refresh returns an empty list.
    mockedListDocuments
      .mockResolvedValueOnce({ documents: [doc], total: 1 })
      .mockResolvedValueOnce({ documents: [], total: 0 });

    renderPage();
    await waitForLoaded();

    const deleteButton = await screen.findByRole('button', { name: /supprimer/i });
    await userEvent.click(deleteButton);

    await waitFor(() => {
      expect(mockedDeleteDocument).toHaveBeenCalledTimes(1);
      expect(mockedDeleteDocument).toHaveBeenCalledWith('doc-9');
    });
    // List refreshed twice: initial mount + post-delete.
    await waitFor(() => expect(mockedListDocuments).toHaveBeenCalledTimes(2));
  });
});

// -----------------------------------------------------------------------------
// (d) Plain-text link: a `links` item with a usable target_url renders a plain
// hyperlink (getByRole('link') with href/target/rel set) and NOT a button-styled
// anchor (no bg-[#000E9C], no rounded, no padding classes).
//
// EXPECTED TO FAIL on unfixed code: the anchor carries button styling.
// Validates: Requirements 1.3, 2.4
// -----------------------------------------------------------------------------
describe('Bug condition (d): usable links item renders as a plain hyperlink, not a button', () => {
  it('renders a plain anchor with link attributes and no button styling', async () => {
    const doc = makeDocument('link-1', 'AWS Console', 42, 'links', 'https://example.com');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

    renderPage();
    await waitForLoaded();

    const anchor = screen.getByRole('link', { name: /AWS Console/i });
    expect(anchor).toBeInstanceOf(HTMLAnchorElement);
    expect(anchor).toHaveAttribute('href', 'https://example.com');
    expect(anchor).toHaveAttribute('target', '_blank');
    expect(anchor).toHaveAttribute('rel', 'noopener noreferrer');

    // Must NOT carry button styling classes.
    const cls = anchor.getAttribute('class') ?? '';
    expect(cls).not.toMatch(/bg-\[#000E9C\]/);
    expect(cls).not.toMatch(/rounded/);
    // No padding utility classes (e.g. px-3 / py-1.5).
    expect(cls).not.toMatch(/\bp[xy]?-\d/);
  });

  it('renders a plain hyperlink for any links doc with a usable https URL', async () => {
    const hostArb = fc
      .array(fc.constantFrom(...'abcdefghijklmnopqrstuvwxyz0123456789'.split('')), {
        minLength: 3,
        maxLength: 12,
      })
      .map((chars) => chars.join(''));
    const urlArb = hostArb.map((h) => `https://${h}.example.com`);
    const nameArb = fc
      .array(fc.constantFrom(...'abcdefghijABCDEFGHIJ0123456789-_.'.split('')), {
        minLength: 1,
        maxLength: 12,
      })
      .map((chars) => chars.join(''));

    await fc.assert(
      fc.asyncProperty(nameArb, urlArb, async (name, url) => {
        cleanup();
        const doc = makeDocument('link-p', name, 100, 'links', url);
        mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

        renderPage();
        await waitForLoaded();

        const anchor = screen.getByRole('link', {
          name: new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'),
        });
        expect(anchor).toHaveAttribute('href', url);
        const cls = anchor.getAttribute('class') ?? '';
        expect(cls).not.toMatch(/bg-\[#000E9C\]/);
        expect(cls).not.toMatch(/rounded/);
        expect(cls).not.toMatch(/\bp[xy]?-\d/);
        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});
