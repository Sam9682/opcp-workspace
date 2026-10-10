import { useEffect, useState } from 'react';
import { authService } from '../../services/authService';
import { prerequisitesService } from '../../services/prerequisitesService';
import { RichTextEditor } from '../RichTextEditor';

interface StaticContentPageProps {
  installationId: string;
  slug: string;
  title: string;
}

type SaveStatus = 'idle' | 'saving' | 'error';

/**
 * Static content archetype (Basics, Network Flux). Loads server-persisted
 * content for every authenticated user. Admins get a rich-text editor plus a
 * Save button; members see the content read-only. Save failures surface a
 * visible error banner while preserving the value the admin typed.
 */
export const StaticContentPage = ({
  installationId,
  slug,
  title,
}: StaticContentPageProps) => {
  const canEdit = authService.isAdmin();
  const [content, setContent] = useState('');
  const [draft, setDraft] = useState('');
  const [status, setStatus] = useState<SaveStatus>('idle');
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    prerequisitesService
      .loadStaticContent(installationId, slug)
      .then((res) => {
        if (cancelled) return;
        setContent(res.content);
        setDraft(res.content);
        setLoadError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [installationId, slug]);

  const handleSave = async () => {
    setStatus('saving');
    try {
      await prerequisitesService.saveStaticContent(installationId, slug, draft);
      setContent(draft);
      setStatus('idle');
    } catch {
      // Req 6.5 — surface a visible error indication, preserve the typed value.
      setStatus('error');
    }
  };

  return (
    <div className="card p-6">
      <h1 className="text-2xl font-bold text-[#000E9C] mb-5">{title}</h1>

      {loadError && (
        <div
          role="status"
          className="mb-6 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
        >
          Impossible de charger le contenu. Veuillez réessayer plus tard.
        </div>
      )}

      {status === 'error' && (
        <div
          role="alert"
          className="mb-6 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          Échec de l'enregistrement. Vos modifications ont été conservées, veuillez réessayer.
        </div>
      )}

      {canEdit ? (
        <div>
          <RichTextEditor
            value={draft}
            onChange={setDraft}
            placeholder="Saisissez le contenu de la page…"
            disabled={status === 'saving'}
          />
          <div className="mt-4">
            <button
              type="button"
              onClick={handleSave}
              disabled={status === 'saving'}
              className="rounded bg-[#000E9C] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#4949FF] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {status === 'saving' ? 'Enregistrement…' : 'Enregistrer'}
            </button>
          </div>
        </div>
      ) : (
        <div
          className="prose prose-sm max-w-none"
          dangerouslySetInnerHTML={{ __html: content }}
        />
      )}
    </div>
  );
};
