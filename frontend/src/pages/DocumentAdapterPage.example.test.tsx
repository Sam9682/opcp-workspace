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
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DocumentAdapterPage } from './DocumentAdapterPage';
import { documentService, type Document } from '../services/documentService';
import {
  oracleService,
  type AvailableProvider,
} from '../services/oracleService';
import { documentAdapterService } from '../services/documentAdapterService';
import { LanguageProvider } from '../hooks/useLanguage';

/**
 * Example / edge-case tests for the Document Adapter page (task 12.5).
 *
 * Feature: document-audience-adapter
 *
 * These complement the property tests (task 12.4) by pinning down concrete
 * scenarios and error paths:
 *   - three-section order (Requirement 1.4)
 *   - default audience it_beginner (Requirement 3.3)
 *   - source-required guard (Requirement 2.5)
 *   - no-provider guard (Requirement 4.4)
 *   - progress / disable states (Requirement 5.2)
 *   - adapt error path (Requirement 5.5)
 *   - download error path retains preview (Requirement 6.4)
 *
 * The page consumes the translation context, so it renders inside a
 * LanguageProvider. The default Active_Language is French, so assertions use
 * the French strings from the `fr` dictionary.
 */

// Mock all three services the page depends on. Behaviour is set per test.
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

vi.mock('../services/documentAdapterService', async () => {
  // Keep the real AUDIENCE_LEVELS / isSupportedSourceType exports the page
  // imports, but stub the network methods.
  const actual = await vi.importActual<
    typeof import('../services/documentAdapterService')
  >('../services/documentAdapterService');
  return {
    ...actual,
    documentAdapterService: {
      adapt: vi.fn(),
      exportAdapted: vi.fn(),
    },
  };
});

const mockedListDocuments = vi.mocked(documentService.listDocuments);
const mockedGetProviders = vi.mocked(oracleService.getAvailableProviders);
const mockedAdapt = vi.mocked(documentAdapterService.adapt);
const mockedExportAdapted = vi.mocked(documentAdapterService.exportAdapted);

// French strings (default Active_Language) used in assertions.
const FR = {
  sectionSource: 'Document source',
  sectionAudience: 'Public cible et IA',
  sectionContext: 'Contexte personnel complémentaire',
  sectionGenerate: 'Génération et téléchargement',
  audienceBeginner: 'Débutant IT',
  sourceRequired: 'Veuillez sélectionner un document source.',
  providerNone: "Aucun fournisseur d'IA disponible.",
  generate: 'Générer',
  generating: 'Génération en cours…',
  errorAdapt: 'Échec de la génération. Veuillez réessayer.',
  errorDownload: 'Échec du téléchargement. Veuillez réessayer.',
} as const;

function renderPage() {
  return render(
    <LanguageProvider>
      <DocumentAdapterPage />
    </LanguageProvider>,
  );
}

function makePdfDocument(id: string, name: string): Document {
  return {
    id,
    filename: `${id}.pdf`,
    original_name: name,
    mime_type: 'application/pdf',
    size: 1024,
    category: 'documents',
    access_level: 'members',
    uploaded_by: 'admin-id',
    download_count: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };
}

function makeProvider(
  overrides: Partial<AvailableProvider> = {},
): AvailableProvider {
  return {
    id: 'openai',
    name: 'OpenAI',
    description: 'OpenAI provider',
    default: true,
    enabled: true,
    ...overrides,
  };
}

/** Wait until the provider section has finished loading (guards against the
 * "Génération en cours…" loading placeholder leaking into assertions). */
async function waitForProvidersLoaded(): Promise<void> {
  await waitFor(() => {
    expect(mockedGetProviders).toHaveBeenCalled();
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  cleanup();
  // Sensible defaults: no documents, one enabled default provider.
  mockedListDocuments.mockResolvedValue({ documents: [], total: 0 });
  mockedGetProviders.mockResolvedValue({ providers: [makeProvider()] });
  mockedAdapt.mockResolvedValue({
    adapted_content: 'Adapted content body',
    audience_level: 'it_beginner',
    ai_provider: 'openai',
    source_name: 'guide.pdf',
    processing_time: 0.1,
  });
  mockedExportAdapted.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
});

// -----------------------------------------------------------------------------
// Section order (Requirement 1.4): source, audience/provider, additional
// context, then generate.
// -----------------------------------------------------------------------------
describe('section layout', () => {
  it('renders source, audience/provider, context, then generate sections in order', async () => {
    renderPage();
    await waitForProvidersLoaded();

    const headings = screen
      .getAllByRole('heading', { level: 2 })
      .map((h) => h.textContent);

    expect(headings).toEqual([
      FR.sectionSource,
      FR.sectionAudience,
      FR.sectionContext,
      FR.sectionGenerate,
    ]);
  });
});

// -----------------------------------------------------------------------------
// Default audience it_beginner (Requirement 3.3)
// -----------------------------------------------------------------------------
describe('default audience', () => {
  it('checks the it_beginner radio on load', async () => {
    renderPage();
    await waitForProvidersLoaded();

    const beginner = screen.getByRole('radio', {
      name: FR.audienceBeginner,
    }) as HTMLInputElement;

    expect(beginner.checked).toBe(true);
  });
});

// -----------------------------------------------------------------------------
// Source-required guard (Requirement 2.5)
// -----------------------------------------------------------------------------
describe('source-required guard', () => {
  it('disables Generate and surfaces the source-required message when no source is chosen', async () => {
    renderPage();
    await waitForProvidersLoaded();

    // With no source resolved, Generate must be disabled (Requirement 2.5).
    const generate = await screen.findByRole('button', { name: FR.generate });
    expect(generate).toBeDisabled();

    // The source-required message is presented to the Member (it is the
    // library select's placeholder option).
    expect(screen.getByText(FR.sourceRequired)).toBeInTheDocument();
  });

  it('enables Generate once a library source is selected', async () => {
    const doc = makePdfDocument('doc-1', 'guide.pdf');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

    renderPage();
    await waitForProvidersLoaded();

    const select = await screen.findByRole('combobox', {
      name: 'Depuis la bibliothèque',
    });
    await userEvent.selectOptions(select, 'doc-1');

    const generate = screen.getByRole('button', { name: FR.generate });
    expect(generate).toBeEnabled();
  });
});

// -----------------------------------------------------------------------------
// No-provider guard (Requirement 4.4)
// -----------------------------------------------------------------------------
describe('no-provider guard', () => {
  it('shows the no-provider message and disables Generate when no enabled provider exists', async () => {
    const doc = makePdfDocument('doc-1', 'guide.pdf');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });
    // Only a disabled provider is returned -> no enabled providers.
    mockedGetProviders.mockResolvedValue({
      providers: [makeProvider({ enabled: false })],
    });

    renderPage();
    await waitForProvidersLoaded();

    // No-provider message is shown (Requirement 4.4).
    expect(await screen.findByText(FR.providerNone)).toBeInTheDocument();

    // Even with a valid source selected, Generate stays disabled because there
    // is no provider to generate with.
    const select = await screen.findByRole('combobox', {
      name: 'Depuis la bibliothèque',
    });
    await userEvent.selectOptions(select, 'doc-1');

    const generate = screen.getByRole('button', { name: FR.generate });
    expect(generate).toBeDisabled();
  });
});

// -----------------------------------------------------------------------------
// Progress / disable states (Requirement 5.2)
// -----------------------------------------------------------------------------
describe('progress and disable states', () => {
  it('disables Generate and shows the generating label while adapting', async () => {
    const doc = makePdfDocument('doc-1', 'guide.pdf');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

    // Hold the adapt promise open so we can observe the in-flight state.
    let resolveAdapt: (value: {
      adapted_content: string;
      audience_level: 'it_beginner';
      ai_provider: string;
      source_name: string;
      processing_time: number;
    }) => void = () => {};
    mockedAdapt.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveAdapt = resolve;
        }),
    );

    renderPage();
    await waitForProvidersLoaded();

    const select = await screen.findByRole('combobox', {
      name: 'Depuis la bibliothèque',
    });
    await userEvent.selectOptions(select, 'doc-1');

    const generate = screen.getByRole('button', { name: FR.generate });
    await userEvent.click(generate);

    // While in flight: the button is disabled and shows the generating label,
    // and the polite status region announces progress (Requirement 5.2).
    await waitFor(() => {
      const inFlight = screen.getByRole('button', { name: FR.generating });
      expect(inFlight).toBeDisabled();
    });
    expect(screen.getByRole('status')).toHaveTextContent(FR.generating);

    // Resolve and confirm the button returns to its idle state.
    resolveAdapt({
      adapted_content: 'Adapted content body',
      audience_level: 'it_beginner',
      ai_provider: 'openai',
      source_name: 'guide.pdf',
      processing_time: 0.1,
    });

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: FR.generate }),
      ).toBeEnabled();
    });
  });
});

// -----------------------------------------------------------------------------
// Adapt error path (Requirement 5.5)
// -----------------------------------------------------------------------------
describe('adapt error path', () => {
  it('shows the adapt error and re-enables Generate when adapt rejects', async () => {
    const doc = makePdfDocument('doc-1', 'guide.pdf');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });
    mockedAdapt.mockRejectedValue(new Error('boom'));

    renderPage();
    await waitForProvidersLoaded();

    const select = await screen.findByRole('combobox', {
      name: 'Depuis la bibliothèque',
    });
    await userEvent.selectOptions(select, 'doc-1');

    await userEvent.click(screen.getByRole('button', { name: FR.generate }));

    // Error banner shows and Generate is re-enabled (Requirement 5.5).
    expect(await screen.findByText(FR.errorAdapt)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: FR.generate })).toBeEnabled();
  });
});

// -----------------------------------------------------------------------------
// Download error path (Requirement 6.4)
// -----------------------------------------------------------------------------
describe('download error path', () => {
  it('shows the download error and retains the preview when exportAdapted rejects', async () => {
    const doc = makePdfDocument('doc-1', 'guide.pdf');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });
    mockedAdapt.mockResolvedValue({
      adapted_content: 'Adapted content body',
      audience_level: 'it_beginner',
      ai_provider: 'openai',
      source_name: 'guide.pdf',
      processing_time: 0.1,
    });
    mockedExportAdapted.mockRejectedValue(new Error('download failed'));

    renderPage();
    await waitForProvidersLoaded();

    const select = await screen.findByRole('combobox', {
      name: 'Depuis la bibliothèque',
    });
    await userEvent.selectOptions(select, 'doc-1');

    await userEvent.click(screen.getByRole('button', { name: FR.generate }));

    // Preview appears after a successful adapt.
    expect(await screen.findByText('Adapted content body')).toBeInTheDocument();

    // Trigger the PDF download, which rejects.
    await userEvent.click(
      screen.getByRole('button', { name: 'Télécharger en PDF' }),
    );

    // The download error is shown and the preview content is retained
    // (Requirement 6.4).
    expect(await screen.findByText(FR.errorDownload)).toBeInTheDocument();
    expect(screen.getByText('Adapted content body')).toBeInTheDocument();

    // Sanity: the export was attempted with the adapted content, source name,
    // audience, and format.
    await waitFor(() => {
      expect(mockedExportAdapted).toHaveBeenCalledWith(
        'Adapted content body',
        'guide.pdf',
        'it_beginner',
        'pdf',
      );
    });
  });
});

// -----------------------------------------------------------------------------
// Additional personal context field
// -----------------------------------------------------------------------------
describe('additional personal context', () => {
  it('renders the context section with a 5000-char-capped textarea and a live counter', async () => {
    renderPage();
    await waitForProvidersLoaded();

    // The section header renders (FR string).
    expect(
      screen.getByRole('heading', { level: 2, name: FR.sectionContext }),
    ).toBeInTheDocument();

    const textarea = screen.getByRole('textbox', {
      name: FR.sectionContext,
    }) as HTMLTextAreaElement;
    expect(textarea).toHaveAttribute('maxlength', '5000');

    // Counter starts at 0 / 5000 and updates as the Member types.
    expect(screen.getByText('0 / 5000')).toBeInTheDocument();

    await userEvent.type(textarea, 'Hello');
    expect(textarea.value).toBe('Hello');
    expect(screen.getByText('5 / 5000')).toBeInTheDocument();
  });

  it('sends the entered context as additional_context in the adapt request', async () => {
    const doc = makePdfDocument('doc-1', 'guide.pdf');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

    renderPage();
    await waitForProvidersLoaded();

    const select = await screen.findByRole('combobox', {
      name: 'Depuis la bibliothèque',
    });
    await userEvent.selectOptions(select, 'doc-1');

    const textarea = screen.getByRole('textbox', { name: FR.sectionContext });
    await userEvent.type(textarea, 'Focus on civil engineering.');

    await userEvent.click(screen.getByRole('button', { name: FR.generate }));

    await waitFor(() => {
      expect(mockedAdapt).toHaveBeenCalledWith(
        expect.objectContaining({
          document_id: 'doc-1',
          additional_context: 'Focus on civil engineering.',
        }),
      );
    });
  });

  it('omits additional_context when the field is left empty', async () => {
    const doc = makePdfDocument('doc-1', 'guide.pdf');
    mockedListDocuments.mockResolvedValue({ documents: [doc], total: 1 });

    renderPage();
    await waitForProvidersLoaded();

    const select = await screen.findByRole('combobox', {
      name: 'Depuis la bibliothèque',
    });
    await userEvent.selectOptions(select, 'doc-1');

    await userEvent.click(screen.getByRole('button', { name: FR.generate }));

    await waitFor(() => {
      expect(mockedAdapt).toHaveBeenCalledWith(
        expect.objectContaining({ additional_context: undefined }),
      );
    });
  });
});
