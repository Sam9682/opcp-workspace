import { useEffect, useMemo, useRef, useState } from 'react';
import { documentService, type Document } from '../services/documentService';
import {
  AUDIENCE_LEVELS,
  documentAdapterService,
  isSupportedSourceType,
  type AdaptationRequest,
  type AdaptationResponse,
  type AudienceLevel,
} from '../services/documentAdapterService';
import {
  oracleService,
  type AIProviderId,
  type AvailableProvider,
} from '../services/oracleService';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import { useTranslation } from '../hooks/useLanguage';

/**
 * Document Audience Adapter page.
 *
 * Feature: document-audience-adapter
 *
 * Three-section layout (Requirement 1.4), in order:
 *   1. Source selection        (task 12.1)
 *   2. Audience & AI provider  (task 12.2)
 *   3. Generation & download   (this task, 12.3)
 *
 * All three sections are implemented. Section 3 reads the shared
 * source/audience/provider state set up by sections 1 and 2, runs the
 * adaptation, previews the result, and exports it to PDF/Word.
 */

/** How the Member provides the source document. */
type SourceMode = 'library' | 'upload';

export const DocumentAdapterPage = () => {
  const { t } = useTranslation();

  // ---- Source selection state (section 1) ----
  const [sourceMode, setSourceMode] = useState<SourceMode>('library');

  // Library mode: the available documents and the chosen one.
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(true);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>('');

  // Upload mode: the pending file selection and any validation/upload error.
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // ---- Shared source selection result (consumed by sections 2 and 3) ----
  // Exactly one of these source references is set at a time, mirroring the
  // backend's exactly-one-of rule. `sourceName` is the original name used for
  // the export filename.
  const [selectedDocumentSourceId, setSelectedDocumentSourceId] = useState<
    string | undefined
  >(undefined);
  const [uploadedFilename, setUploadedFilename] = useState<string | undefined>(
    undefined,
  );
  const [sourceName, setSourceName] = useState<string | undefined>(undefined);

  // ---- Audience & provider state (section 2) ----
  // Default audience is `it_beginner` (Requirement 3.3). This is now settable
  // from the UI and is the single source of truth section 3 (task 12.3) reads.
  const [audienceLevel, setAudienceLevel] = useState<AudienceLevel>(
    'it_beginner',
  );

  // Enabled AI providers and the currently selected provider id. The provider
  // list is loaded from the Oracle providers endpoint and filtered to the
  // enabled ones (Requirement 4.1, 4.2).
  const [enabledProviders, setEnabledProviders] = useState<AvailableProvider[]>(
    [],
  );
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [providerId, setProviderId] = useState<AIProviderId | ''>('');

  // ---- Generation, preview & download state (section 3) ----
  // `adapting` gates the Generate button while a request is in flight. The
  // adapted result (content + source name) is retained across download
  // attempts so a download failure never clears the preview (Requirement 6.4).
  const [adapting, setAdapting] = useState(false);
  const [adaptResult, setAdaptResult] = useState<AdaptationResponse | null>(
    null,
  );
  const [adaptError, setAdaptError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  // Tracks which export format is being downloaded so we can disable both
  // actions and show progress on the active one.
  const [downloadingFormat, setDownloadingFormat] = useState<
    'pdf' | 'docx' | null
  >(null);

  // Load the Documents library listing for library mode (Requirement 2.1).
  useEffect(() => {
    let cancelled = false;
    setLoadingDocuments(true);
    documentService
      .listDocuments()
      .then((res) => {
        if (cancelled) return;
        setDocuments(res.documents);
      })
      .catch(() => {
        if (cancelled) return;
        setDocumentsError(t('page.documentAdapter.error.adapt'));
      })
      .finally(() => {
        if (cancelled) return;
        setLoadingDocuments(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load the available AI providers, filter to the enabled ones, and preselect
  // the enabled provider whose `default` flag is set — falling back to the
  // first enabled provider when none is flagged (Requirement 4.1, 4.2, 4.3;
  // Correctness Property 5).
  useEffect(() => {
    let cancelled = false;
    setLoadingProviders(true);
    oracleService
      .getAvailableProviders()
      .then((res) => {
        if (cancelled) return;
        const enabled = res.providers.filter((p) => p.enabled);
        setEnabledProviders(enabled);
        const preselected =
          enabled.find((p) => p.default) ?? enabled[0] ?? undefined;
        setProviderId(preselected ? preselected.id : '');
      })
      .catch(() => {
        if (cancelled) return;
        setEnabledProviders([]);
        setProviderId('');
      })
      .finally(() => {
        if (cancelled) return;
        setLoadingProviders(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Only PDF/Word documents are valid sources (Requirement 2.3, 2.4).
  const libraryOptions = useMemo(
    () => documents.filter((doc) => isSupportedSourceType(doc.mime_type)),
    [documents],
  );

  /** Clear any previously resolved source reference across modes. */
  const resetSourceSelection = () => {
    setSelectedDocumentSourceId(undefined);
    setUploadedFilename(undefined);
    setSourceName(undefined);
  };

  const handleModeChange = (mode: SourceMode) => {
    setSourceMode(mode);
    setSourceError(null);
    resetSourceSelection();
    // Reset the per-mode inputs so switching modes starts clean.
    setSelectedDocumentId('');
    setPendingFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Library mode: selecting a document resolves the shared source reference by
  // id, using its original name for the export filename.
  const handleLibrarySelect = (id: string) => {
    setSelectedDocumentId(id);
    setSourceError(null);
    const doc = libraryOptions.find((d) => d.id === id);
    if (doc) {
      setSelectedDocumentSourceId(doc.id);
      setUploadedFilename(undefined);
      setSourceName(doc.original_name);
    } else {
      resetSourceSelection();
    }
  };

  // Upload mode: validate the MIME type before accepting the file. Rejected
  // files surface the PDF/Word message and clear any pending selection
  // (Requirement 2.4).
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    resetSourceSelection();
    if (!file) {
      setPendingFile(null);
      return;
    }
    if (!isSupportedSourceType(file.type)) {
      setPendingFile(null);
      setSourceError(t('page.documentAdapter.source.invalidType'));
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }
    setSourceError(null);
    setPendingFile(file);
  };

  // Upload mode: on confirm, upload via the existing Documents service and
  // store the returned stored filename plus the source name for later sections
  // (Requirement 2.3).
  const handleConfirmUpload = async () => {
    if (!pendingFile) return;
    try {
      setUploading(true);
      setSourceError(null);
      const uploaded = await documentService.uploadDocument(pendingFile);
      setUploadedFilename(uploaded.filename);
      setSelectedDocumentSourceId(undefined);
      setSourceName(uploaded.original_name);
    } catch {
      setSourceError(t('page.documentAdapter.error.adapt'));
    } finally {
      setUploading(false);
    }
  };

  // A source is resolved once either reference is set.
  const hasSource = Boolean(selectedDocumentSourceId || uploadedFilename);

  // When no enabled provider exists, generation must be disabled and the
  // no-provider message shown (Requirement 4.4). Section 3 consumes this flag
  // to gate the Generate action.
  const hasProvider = enabledProviders.length > 0;
  const noProvider = !loadingProviders && !hasProvider;

  // ---- Section 3 handlers ----

  // The Generate button is disabled while a request is in flight, when no
  // source is resolved, or when there is no enabled provider (Requirement 5.2,
  // 2.5, 4.4).
  const generateDisabled = adapting || !hasSource || !providerId || noProvider;

  // Run the adaptation. Builds the request from the shared state, carrying
  // exactly one of document_id/uploaded_filename plus audience_level and
  // ai_provider (Requirement 5.1). On success stores the response for preview;
  // on failure shows the adapt error and re-enables Generate (Requirement 5.5).
  const handleGenerate = async () => {
    // Source-required guard: triggering generate with no resolved source
    // surfaces the source-required message (Requirement 2.5).
    if (!hasSource) {
      setSourceError(t('page.documentAdapter.source.required'));
      return;
    }
    if (!providerId) return;

    const request: AdaptationRequest = selectedDocumentSourceId
      ? {
          document_id: selectedDocumentSourceId,
          audience_level: audienceLevel,
          ai_provider: providerId,
        }
      : {
          uploaded_filename: uploadedFilename,
          audience_level: audienceLevel,
          ai_provider: providerId,
        };

    try {
      setAdapting(true);
      setAdaptError(null);
      setDownloadError(null);
      const result = await documentAdapterService.adapt(request);
      setAdaptResult(result);
    } catch {
      setAdaptError(t('page.documentAdapter.error.adapt'));
    } finally {
      setAdapting(false);
    }
  };

  // Copy the exact adapted content to the clipboard (Requirement 5.4).
  const handleCopy = async () => {
    if (!adaptResult) return;
    try {
      await navigator.clipboard.writeText(adaptResult.adapted_content);
    } catch {
      // Clipboard access can be denied; copy is best-effort and non-blocking.
    }
  };

  // Export the adapted content to PDF or Word. On failure, show the download
  // error while retaining the preview content (Requirement 6.4).
  const handleDownload = async (format: 'pdf' | 'docx') => {
    if (!adaptResult) return;
    try {
      setDownloadingFormat(format);
      setDownloadError(null);
      await documentAdapterService.exportAdapted(
        adaptResult.adapted_content,
        adaptResult.source_name,
        audienceLevel,
        format,
      );
    } catch {
      setDownloadError(t('page.documentAdapter.error.download'));
    } finally {
      setDownloadingFormat(null);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-[#000E9C] mb-5">
        {t('page.documentAdapter.title')}
      </h1>

      {/* ---- Section 1: Source selection (task 12.1) ---- */}
      <section className="card p-6 mb-5">
        <h2 className="text-lg font-semibold text-[#000E9C] mb-3">
          {t('page.documentAdapter.section.source')}
        </h2>

        <div className="flex items-center gap-4 mb-4">
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="radio"
              name="document-adapter-source-mode"
              value="library"
              checked={sourceMode === 'library'}
              onChange={() => handleModeChange('library')}
              className="text-[#000E9C] focus:ring-[#4949FF]"
            />
            {t('page.documentAdapter.source.fromLibrary')}
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="radio"
              name="document-adapter-source-mode"
              value="upload"
              checked={sourceMode === 'upload'}
              onChange={() => handleModeChange('upload')}
              className="text-[#000E9C] focus:ring-[#4949FF]"
            />
            {t('page.documentAdapter.source.fromUpload')}
          </label>
        </div>

        {sourceMode === 'library' ? (
          <div>
            {loadingDocuments ? (
              <p className="text-sm text-gray-600">{t('page.documentAdapter.generating')}</p>
            ) : documentsError ? (
              <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
                {documentsError}
              </div>
            ) : (
              <label className="block">
                <span className="sr-only">
                  {t('page.documentAdapter.source.fromLibrary')}
                </span>
                <select
                  value={selectedDocumentId}
                  onChange={(e) => handleLibrarySelect(e.target.value)}
                  aria-label={t('page.documentAdapter.source.fromLibrary')}
                  className="w-full px-3 py-2.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent"
                >
                  <option value="">
                    {t('page.documentAdapter.source.required')}
                  </option>
                  {libraryOptions.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.original_name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={handleFileChange}
              aria-label={t('page.documentAdapter.source.fromUpload')}
              className="text-sm text-gray-700"
            />
            {pendingFile && !uploadedFilename && (
              <button
                type="button"
                onClick={() => void handleConfirmUpload()}
                disabled={uploading}
                className="px-3 py-1.5 text-sm font-medium text-white bg-[#000E9C] rounded hover:bg-[#4949FF] disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {uploading
                  ? t('page.documentAdapter.generating')
                  : t('page.documentAdapter.source.fromUpload')}
              </button>
            )}
          </div>
        )}

        {sourceError && (
          <div className="mt-3 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
            {sourceError}
          </div>
        )}

        {sourceName && (
          <p className="mt-3 text-sm text-gray-600">{sourceName}</p>
        )}
      </section>

      {/* ---- Section 2: Audience & AI provider selection (task 12.2) ----
          Renders the four AudienceLevel options in progression order
          (default it_beginner, Requirement 3.3) and the enabled-provider
          dropdown preselected per the default-flag rule (Correctness
          Property 5). When no enabled provider exists, the no-provider message
          is shown (Requirement 4.4). */}
      <section className="card p-6 mb-5">
        <h2 className="text-lg font-semibold text-[#000E9C] mb-3">
          {t('page.documentAdapter.section.audience')}
        </h2>

        {/* Audience level: four options in progression order (Requirement 3.1,
            3.2, 3.3). */}
        <fieldset className="mb-5">
          <legend className="text-sm font-medium text-gray-700 mb-2">
            {t('page.documentAdapter.section.audience')}
          </legend>
          <div className="space-y-2">
            {AUDIENCE_LEVELS.map((level) => (
              <label
                key={level}
                className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer"
              >
                <input
                  type="radio"
                  name="document-adapter-audience-level"
                  value={level}
                  checked={audienceLevel === level}
                  onChange={() => setAudienceLevel(level)}
                  className="text-[#000E9C] focus:ring-[#4949FF]"
                />
                {t(`page.documentAdapter.audience.${level}`)}
              </label>
            ))}
          </div>
        </fieldset>

        {/* AI provider: a dropdown of the enabled providers, preselected per
            the default-flag rule (Requirement 4.1, 4.2, 4.3). */}
        <div>
          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">
              {t('page.documentAdapter.section.audience')}
            </span>
            {loadingProviders ? (
              <p className="text-sm text-gray-600">
                {t('page.documentAdapter.generating')}
              </p>
            ) : noProvider ? (
              <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-3 py-2 rounded text-sm">
                {t('page.documentAdapter.provider.none')}
              </div>
            ) : (
              <select
                value={providerId}
                onChange={(e) =>
                  setProviderId(e.target.value as AIProviderId)
                }
                aria-label={t('page.documentAdapter.section.audience')}
                className="w-full px-3 py-2.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent"
              >
                {enabledProviders.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </select>
            )}
          </label>
        </div>
      </section>

      {/* ---- Section 3: Generation, preview & download (task 12.3) ----
          Generate button (disabled while in flight or when source/provider
          prerequisites are missing), progress indicator, preview panel via
          MarkdownRenderer, copy action, and PDF/Word download actions.
          (Requirements 1.4, 2.5, 5.1–5.5, 6.1–6.4) */}
      <section className="card p-6 mb-5">
        <h2 className="text-lg font-semibold text-[#000E9C] mb-3">
          {t('page.documentAdapter.section.generate')}
        </h2>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => void handleGenerate()}
            disabled={generateDisabled}
            className="px-4 py-2 text-sm font-medium text-white bg-[#000E9C] rounded hover:bg-[#4949FF] disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {adapting
              ? t('page.documentAdapter.generating')
              : t('page.documentAdapter.generate')}
          </button>
          {adapting && (
            <span
              role="status"
              aria-live="polite"
              className="text-sm text-gray-600"
            >
              {t('page.documentAdapter.generating')}
            </span>
          )}
        </div>

        {adaptError && (
          <div className="mt-3 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
            {adaptError}
          </div>
        )}

        {adaptResult && (
          <div className="mt-5">
            {/* Preview of the adapted content (Requirement 5.3). */}
            <div className="border border-gray-200 rounded p-4 bg-white">
              <MarkdownRenderer content={adaptResult.adapted_content} />
            </div>

            {/* Copy and download actions (Requirements 5.4, 6.1, 6.2, 6.3). */}
            <div className="flex flex-wrap items-center gap-3 mt-4">
              <button
                type="button"
                onClick={() => void handleCopy()}
                className="px-3 py-1.5 text-sm font-medium text-[#000E9C] border border-[#000E9C] rounded hover:bg-[#000E9C] hover:text-white transition-colors"
              >
                {t('page.documentAdapter.copy')}
              </button>
              <button
                type="button"
                onClick={() => void handleDownload('pdf')}
                disabled={downloadingFormat !== null}
                className="px-3 py-1.5 text-sm font-medium text-white bg-[#000E9C] rounded hover:bg-[#4949FF] disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {downloadingFormat === 'pdf'
                  ? t('page.documentAdapter.generating')
                  : t('page.documentAdapter.download.pdf')}
              </button>
              <button
                type="button"
                onClick={() => void handleDownload('docx')}
                disabled={downloadingFormat !== null}
                className="px-3 py-1.5 text-sm font-medium text-white bg-[#000E9C] rounded hover:bg-[#4949FF] disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {downloadingFormat === 'docx'
                  ? t('page.documentAdapter.generating')
                  : t('page.documentAdapter.download.docx')}
              </button>
            </div>

            {downloadError && (
              <div className="mt-3 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
                {downloadError}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
};
