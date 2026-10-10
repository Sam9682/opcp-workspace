import { useEffect, useMemo, useRef, useState } from 'react';
import { documentService, type Document, type DocumentCategory } from '../services/documentService';
import { authService } from '../services/authService';
import { useTranslation } from '../hooks/useLanguage';

/** Maps each document category to its translation key (resolved at render time). */
const CATEGORY_LABEL_KEYS: Record<DocumentCategory, string> = {
  docs: 'page.documents.category.docs',
  documents: 'page.documents.category.documents',
  scripts: 'page.documents.category.scripts',
  links: 'page.documents.category.links',
  trainings: 'page.documents.category.trainings',
};

/**
 * Intended section order, matching the content subfolders of `docs/to_publish`.
 * A legacy `documents` category (and any other valid category not listed here)
 * is still rendered — see `orderedCategories` below — so no category is dropped.
 */
const CATEGORY_ORDER: DocumentCategory[] = ['docs', 'links', 'scripts', 'trainings'];

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  const units = ['Ko', 'Mo', 'Go'];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}

export const DocumentsPage = () => {
  const { t } = useTranslation();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  // Per-category callback-ref map: each rendered section owns its own file
  // <input>, so a section's "Upload" button triggers exactly that section's
  // input. A single shared ref cannot back multiple simultaneous inputs.
  const fileInputRefs = useRef<Partial<Record<DocumentCategory, HTMLInputElement | null>>>({});

  const isAdmin = authService.isAdmin(); // Requirement 3.1, 3.2

  /** Fetch the document list from the API. Shared by the initial effect and post-upload refresh. */
  const loadDocuments = async (): Promise<void> => {
    try {
      const res = await documentService.listDocuments();
      setDocuments(res.documents);
    } catch {
      setError(t('page.documents.error.load'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return documents;                                   // Requirement 9.2
    return documents.filter((d) => d.original_name.toLowerCase().includes(q)); // Requirement 9.1
  }, [documents, search]);

  // Partition the filtered documents by the categories actually present, so
  // valid-but-unlisted categories (e.g. docs/trainings, or a legacy documents
  // row) are grouped rather than dropped. Requirement 8.1 partition.
  const grouped = useMemo(() => {
    const map = new Map<DocumentCategory, Document[]>();
    for (const doc of filtered) {
      const bucket = map.get(doc.category);
      if (bucket) bucket.push(doc);
      else map.set(doc.category, [doc]);
    }
    return map;
  }, [filtered]);

  // Render the known subfolder order first, then any remaining present
  // categories (e.g. a legacy `documents` row) so nothing is dropped.
  const orderedCategories = useMemo(() => {
    const ordered = CATEGORY_ORDER.filter((category) => grouped.has(category));
    const rest = [...grouped.keys()].filter((category) => !CATEGORY_ORDER.includes(category));
    return [...ordered, ...rest];
  }, [grouped]);

  // Sections to render. Non-admins only see sections for categories that
  // actually have items (grouping/ordering preserved — Requirement 3.6). Admins
  // additionally see every category section (even when empty) so the per-section
  // upload control is always available, including for `documents` which is not
  // part of CATEGORY_ORDER. Present categories keep their order; empty admin-only
  // sections are appended after.
  const sectionCategories = useMemo(() => {
    if (!isAdmin) return orderedCategories;
    const allCategories: DocumentCategory[] = [...CATEGORY_ORDER, 'documents'];
    const extras = allCategories.filter((category) => !orderedCategories.includes(category));
    return [...orderedCategories, ...extras];
  }, [isAdmin, orderedCategories]);

  const handleDownload = async (doc: Document) => {
    try {
      setDownloadError(null);
      await documentService.downloadDocument(doc.id, doc.original_name); // Requirement 10.1
    } catch {
      setDownloadError(`${t('page.documents.error.downloadPrefix')}${doc.original_name}${t('page.documents.error.downloadSuffix')}`); // Requirement 10.3
    }
  };

  // Admin-only delete flow. A confirmation step gates the destructive call:
  // when the user cancels, no service call is made. On success we refresh the
  // list; on failure we surface a page-level delete-error banner mirroring the
  // upload/download error pattern. Requirement 2.2, 2.3.
  const handleDelete = async (doc: Document) => {
    if (!window.confirm(t('page.documents.delete.confirm'))) return;
    try {
      setDeleteError(null);
      await documentService.deleteDocument(doc.id);
      await loadDocuments();
    } catch {
      setDeleteError(t('page.documents.error.delete'));
    }
  };

  const handleUpload = async (file: File) => {
    try {
      setUploadError(null);
      await documentService.uploadDocument(file);  // Requirement 3.3
      await loadDocuments();                        // Requirement 5.1: refresh so item appears
    } catch {
      setUploadError(t('page.documents.error.upload'));
    }
  };

  // Handle a file selection from a specific section's input. Category stays
  // server-derived from the file extension, so no client category param is sent
  // (handleUpload calls uploadDocument(file) with only the File). Reset that
  // section's input so re-selecting the same file re-triggers change.
  const onFileChange = (category: DocumentCategory) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void handleUpload(file);
    const input = fileInputRefs.current[category];
    if (input) input.value = '';
  };

  if (loading) return <div className="card p-6 text-gray-600">{t('page.documents.loading')}</div>;
  if (error) return (
    <div className="card p-6 bg-red-50 border border-red-200 text-red-700">{error}</div>
  );

  return (
    <div>
      <h1 className="text-2xl font-bold text-[#000E9C] mb-5">{t('page.documents.title')}</h1>

      <div className="mb-5">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t('page.documents.search.placeholder')}
          aria-label={t('page.documents.search.ariaLabel')}
          className="w-full px-3 py-2.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent"
        />
      </div>

      {uploadError && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
          {uploadError}
        </div>
      )}

      {downloadError && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
          {downloadError}
        </div>
      )}

      {deleteError && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
          {deleteError}
        </div>
      )}

      {filtered.length === 0 && !isAdmin ? (
        <div className="card p-6 text-gray-600">{t('page.documents.empty')}</div>
      ) : (
        sectionCategories.map((category) => {
          const docs = grouped.get(category) ?? [];
          // Non-admins never see empty sections; admins always get every
          // category section so the per-section upload control is available.
          if (docs.length === 0 && !isAdmin) return null;
          const labelKey = CATEGORY_LABEL_KEYS[category];
          const categoryLabel = labelKey ? t(labelKey) : category;
          // Per-section upload accessible label: "<upload label> — <category label>"
          // (em dash U+2014), so assistive tech and tests can target the right
          // section's control via within(section).getByLabelText(...).
          const perSectionUploadLabel = `${t('page.documents.upload.label')} — ${categoryLabel}`;
          return (
            <section key={category} className="card p-6 mb-5">
              <h2 className="text-lg font-semibold text-[#000E9C] mb-3">{categoryLabel}</h2>

              {isAdmin && (
                <div className="flex items-center gap-3 mb-3">
                  {/* Base-label control on the `documents` section only, so
                      getByLabelText('Téléverser un document') resolves to a
                      single input. */}
                  {category === 'documents' && (
                    <label htmlFor={`document-upload-input-${category}`} className="sr-only">
                      {t('page.documents.upload.label')}
                    </label>
                  )}
                  <input
                    id={`document-upload-input-${category}`}
                    ref={(el) => {
                      fileInputRefs.current[category] = el;
                    }}
                    type="file"
                    onChange={onFileChange(category)}
                    aria-label={perSectionUploadLabel}
                    className="text-sm text-gray-700"
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRefs.current[category]?.click()}
                    className="px-3 py-1.5 text-sm font-medium text-white bg-[#000E9C] rounded hover:bg-[#4949FF] transition-colors"
                  >
                    {t('page.documents.upload.button')}
                  </button>
                </div>
              )}

              <ul className="divide-y divide-gray-100">
                {docs.map((doc) => {
                  // Bug condition: a `links` document with a usable target URL
                  // renders as an anchor opening the URL in a new tab, instead
                  // of the Download button wired to the file-download flow.
                  const isLink = doc.category === 'links' && !!doc.target_url;
                  return (
                    <li key={doc.id} className="flex items-center justify-between py-2.5">
                      <div>
                        <p className="text-sm font-medium text-gray-800">{doc.original_name}</p>
                        <p className="text-xs text-gray-500">{formatSize(doc.size)}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        {isLink ? (
                          <a
                            href={doc.target_url as string}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-medium text-[#000E9C] hover:underline transition-colors"
                          >
                            {`${t('page.documents.openLink')} : ${doc.original_name}`}
                          </a>
                        ) : (
                          <button
                            onClick={() => handleDownload(doc)}
                            className="px-3 py-1.5 text-sm font-medium text-white bg-[#000E9C] rounded hover:bg-[#4949FF] transition-colors"
                          >
                            {t('page.documents.download')}
                          </button>
                        )}
                        {/* Admin-only Delete control next to each item, alongside
                            the Download/hyperlink control. Gated on isAdmin so
                            non-admins never see it (Requirement 2.3). */}
                        {isAdmin && (
                          <button
                            type="button"
                            onClick={() => void handleDelete(doc)}
                            className="px-3 py-1.5 text-sm font-medium text-[#000E9C] border border-[#000E9C] rounded hover:bg-red-50 transition-colors"
                          >
                            {t('page.documents.delete')}
                          </button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })
      )}
    </div>
  );
};
