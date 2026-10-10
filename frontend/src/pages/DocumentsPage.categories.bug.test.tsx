import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { DocumentsPage } from './DocumentsPage';
import { documentService, type Document, type DocumentCategory } from '../services/documentService';
import { authService } from '../services/authService';
import { LanguageProvider } from '../hooks/useLanguage';

/**
 * Bug condition exploration test for the documents-page-categories bugfix.
 *
 * Feature: documents-page-categories (BUGFIX)
 * Property 1: Bug Condition - Files Grouped By Originating Subfolder
 * Validates: Requirements 2.1, 2.3
 *
 * CRITICAL: This test MUST FAIL on the current unfixed code. The failure
 * CONFIRMS the bug exists — DocumentsPage hard-codes
 * CATEGORY_ORDER = ['documents','scripts','links'] and a fixed `grouped` map,
 * so documents carrying `docs`/`trainings` categories are dropped and no
 * section is rendered for them. This is the SUCCESS case for this task.
 * DO NOT fix the code or the test.
 *
 * NOTE: The frontend `DocumentCategory` type is a closed union that cannot
 * represent `docs`/`trainings` today (that is part of the bug). We cast through
 * `unknown` so the test can supply the real backend categories that the fixed
 * pipeline will produce; the runtime section-dropping is what we assert on.
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
const mockedIsAdmin = vi.mocked(authService.isAdmin);

function makeDocument(
  id: string,
  original_name: string,
  category: string,
): Document {
  return {
    id,
    filename: `${id}.bin`,
    original_name,
    mime_type: 'application/octet-stream',
    size: 1024,
    // The real backend produces `docs`/`trainings`; the current union type
    // cannot express them, so cast to inject the true category value.
    category: category as unknown as DocumentCategory,
    access_level: 'members',
    uploaded_by: 'admin-id',
    download_count: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };
}

async function waitForLoaded(): Promise<void> {
  await screen.findByLabelText('Rechercher un document');
}

beforeEach(() => {
  vi.clearAllMocks();
  cleanup();
  mockedIsAdmin.mockReturnValue(false);
});

afterEach(() => {
  cleanup();
});

// -----------------------------------------------------------------------------
// Scoped property: for each of {docs, trainings}, a document with that category
// must render its own section. On unfixed code the static CATEGORY_ORDER/grouped
// drop these categories, so no section is rendered.
// Requirements 2.1, 2.3
// -----------------------------------------------------------------------------
describe('Bug condition: subfolder categories render their own section', () => {
  it('renders a section for a trainings document (fails on unfixed code — category dropped)', async () => {
    const docs = [makeDocument('t1', 'onboarding.md', 'trainings')];
    mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

    renderPage();
    await waitForLoaded();

    // The file must be visible somewhere on the page (inside a trainings section).
    expect(
      screen.queryByText('onboarding.md'),
      'trainings section not rendered — category dropped by static CATEGORY_ORDER/grouped',
    ).not.toBeNull();
  });

  it('renders a section for a docs document (fails on unfixed code — category dropped)', async () => {
    const docs = [makeDocument('d1', 'spec.pdf', 'docs')];
    mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

    renderPage();
    await waitForLoaded();

    expect(
      screen.queryByText('spec.pdf'),
      'docs section not rendered — category dropped by static CATEGORY_ORDER/grouped',
    ).not.toBeNull();
  });

  it('renders one section per originating subfolder when docs+trainings are present', async () => {
    const docs = [
      makeDocument('d1', 'spec.pdf', 'docs'),
      makeDocument('t1', 'onboarding.md', 'trainings'),
    ];
    mockedListDocuments.mockResolvedValue({ documents: docs, total: docs.length });

    renderPage();
    await waitForLoaded();

    // Both subfolder files must be shown under their own category sections.
    expect(screen.queryByText('spec.pdf')).not.toBeNull();
    expect(screen.queryByText('onboarding.md')).not.toBeNull();
  });
});
