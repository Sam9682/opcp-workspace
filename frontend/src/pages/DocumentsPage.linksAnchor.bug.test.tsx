/**
 * Bug condition exploration tests for the "documents-links-html-link" bugfix.
 *
 * Property 1 (Bug Condition): Links render as an anchor to the target URL.
 *   isBugCondition(doc) === (doc.category === 'links')
 *
 * These tests encode the EXPECTED (post-fix) behaviour and are run against the
 * UNFIXED code. They are EXPECTED TO FAIL here — that failure confirms the bug:
 * a `links` document is currently rendered with a "Download" button and its
 * target URL is never surfaced in the DOM.
 *
 * Conventions reused from DocumentsPage.test.tsx: mock documentService/
 * authService, render inside a LanguageProvider, extend makeDocument to accept
 * an optional target_url, and use fast-check with NUM_RUNS = 100.
 *
 * Validates: Requirements 2.1, 2.2, 2.3
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
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

// Build a full Document record. `target_url` is optional so `links` fixtures can
// carry a URL; the field is declared on the Document type by the fix, so before
// the fix it is simply an extra (ignored) property on the object.
function makeDocument(
  id: string,
  original_name: string,
  size: number,
  category: DocumentCategory,
  target_url?: string | null,
): Document {
  return {
    id,
    filename: `${id}.links`,
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

async function waitForLoaded(): Promise<void> {
  await screen.findByLabelText('Rechercher un document');
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
// Bug condition — concrete failing shape.
// A `links` document with a valid https target_url must render as an anchor.
// -----------------------------------------------------------------------------
describe('Bug condition: links document renders as an anchor (frontend)', () => {
  it('renders <a href=target_url target="_blank" rel="noopener noreferrer"> for a links doc', async () => {
    const doc = makeDocument('link-1', 'AWS Console', 42, 'links', 'https://example.com');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

    renderPage();
    await waitForLoaded();

    // Expected post-fix behaviour: an anchor pointing at the target URL.
    const anchor = screen.getByRole('link', { name: /AWS Console/i });
    expect(anchor).toBeInstanceOf(HTMLAnchorElement);
    expect(anchor).toHaveAttribute('href', 'https://example.com');
    expect(anchor).toHaveAttribute('target', '_blank');
    expect(anchor).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('does NOT wire a Download button to the download flow for a links doc', async () => {
    const doc = makeDocument('link-2', 'Intranet', 10, 'links', 'https://intranet.example.org/home');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

    renderPage();
    await waitForLoaded();

    // No "Télécharger" (Download) control should exist for the links document.
    expect(screen.queryByRole('button', { name: 'Télécharger' })).toBeNull();
  });
});

// -----------------------------------------------------------------------------
// Scoped PBT: for any links doc carrying a valid https URL, the page renders an
// anchor to that URL and no Download button. Generators are scoped to the
// concrete failing shape (links category + valid https URL) for reproducibility.
// -----------------------------------------------------------------------------
describe('Property 1: any links doc with a target_url renders as an anchor', () => {
  const hostArb = fc
    .array(fc.constantFrom(...'abcdefghijklmnopqrstuvwxyz0123456789'.split('')), {
      minLength: 3,
      maxLength: 12,
    })
    .map((chars) => chars.join(''));

  const urlArb: fc.Arbitrary<string> = hostArb.map((h) => `https://${h}.example.com`);

  const nameArb: fc.Arbitrary<string> = fc
    .array(fc.constantFrom(...'abcdefghijABCDEFGHIJ0123456789-_.'.split('')), {
      minLength: 1,
      maxLength: 12,
    })
    .map((chars) => chars.join(''));

  it('anchor href equals target_url and no Download button is rendered', async () => {
    await fc.assert(
      fc.asyncProperty(nameArb, urlArb, async (name, url) => {
        cleanup();
        const doc = makeDocument('link-p', name, 100, 'links', url);
        mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

        renderPage();
        await waitForLoaded();

        const anchor = screen.getByRole('link', { name: new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i') });
        expect(anchor).toBeInstanceOf(HTMLAnchorElement);
        expect(anchor).toHaveAttribute('href', url);
        expect(anchor).toHaveAttribute('target', '_blank');
        expect(anchor).toHaveAttribute('rel', 'noopener noreferrer');
        expect(screen.queryByRole('button', { name: 'Télécharger' })).toBeNull();

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// -----------------------------------------------------------------------------
// Edge case: a links doc WITHOUT a usable target_url should fall back to the
// Download button rather than rendering a broken anchor (href empty/null).
// -----------------------------------------------------------------------------
describe('Edge case: links doc without a usable target_url falls back to Download', () => {
  it('renders the Download button (not a broken anchor) when target_url is null', async () => {
    const doc = makeDocument('link-3', 'No URL Link', 5, 'links', null);
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

    renderPage();
    await waitForLoaded();

    // Fallback: the existing Download control is present...
    expect(screen.getByRole('button', { name: 'Télécharger' })).toBeInTheDocument();
    // ...and there is no anchor for this document.
    expect(screen.queryByRole('link', { name: /No URL Link/i })).toBeNull();
  });
});
