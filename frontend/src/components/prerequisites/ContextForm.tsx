import { useEffect, useState } from 'react';
import type { ContextConfig, ContextRow } from './types';
import { useTranslation } from '../../hooks/useLanguage';
import { authService } from '../../services/authService';
import { prerequisitesService } from '../../services/prerequisitesService';

interface ContextFormProps {
  installationId: string;
  slug: string;
  title: string;
  config: ContextConfig;
  /**
   * `card` (default) renders the standalone card wrapper and page heading.
   * `embedded` drops the outer card and `<h1>` so the form can be hosted
   * inside another container (e.g. a tab panel that already provides both).
   */
  variant?: 'card' | 'embedded';
}

const FIELD_CLASS =
  'w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent';

const READONLY_FIELD_CLASS =
  'w-full px-3 py-2 border border-gray-200 rounded text-sm bg-gray-100 text-gray-600 cursor-not-allowed';

/**
 * Data-driven key/value information form for the OPCP Context prerequisites
 * tab. Rows are grouped into ordered sections and, for the Contacts group,
 * nested subsections. Each row renders a French label paired with a single
 * free-text input seeded from its `defaultValue` and overridden by any saved
 * answer.
 *
 * Unlike the question/answer tabs (which gate editing on `isAuthenticated()`),
 * the context form is editable only by administrators: `authService.isAdmin()`
 * decides whether inputs are editable or read-only. Answers persist through
 * `prerequisitesService` (no localStorage).
 */
export const ContextForm = ({
  installationId,
  slug,
  title,
  config,
  variant = 'card',
}: ContextFormProps) => {
  // `t` is reserved for future i18n; labels are the French literals from the
  // config, consistent with the rest of the prerequisites UI.
  useTranslation();
  const canEdit = authService.isAdmin();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [errorRowIds, setErrorRowIds] = useState<Set<string>>(new Set());
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    prerequisitesService
      .loadClientAnswers(installationId, slug)
      .then((r) => {
        if (!cancelled) setAnswers(r.answers ?? {});
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [installationId, slug]);

  const resolveValue = (row: ContextRow) => answers[row.id] ?? row.defaultValue;

  const handleChange = (rowId: string, value: string) => {
    // Preserve the typed value locally regardless of persistence outcome.
    setAnswers((a) => ({ ...a, [rowId]: value }));
  };

  const saveValue = async (rowId: string, value: string) => {
    try {
      await prerequisitesService.saveClientAnswer(installationId, slug, rowId, value);
      setErrorRowIds((s) => {
        if (!s.has(rowId)) return s;
        const next = new Set(s);
        next.delete(rowId);
        return next;
      });
    } catch {
      // Record a per-row error indication; the typed value is kept in state.
      setErrorRowIds((s) => new Set(s).add(rowId));
    }
  };

  const commit = (rowId: string, value: string) => {
    if (!canEdit) return;
    void saveValue(rowId, value);
  };

  const embedded = variant === 'embedded';

  /** Render a single labeled key/value row as a `<label>` + free-text input. */
  const renderRow = (row: ContextRow) => {
    const inputId = `${row.id}-value`;
    const hasError = errorRowIds.has(row.id);

    return (
      <div key={row.id} className="grid grid-cols-1 gap-1 md:grid-cols-3 md:items-center md:gap-3">
        <label htmlFor={inputId} className="text-sm font-medium text-gray-700 md:col-span-1">
          {row.label}
        </label>
        <div className="md:col-span-2">
          <input
            type="text"
            id={inputId}
            aria-label={row.label}
            value={resolveValue(row)}
            readOnly={!canEdit}
            disabled={!canEdit}
            onChange={(e) => handleChange(row.id, e.target.value)}
            onBlur={(e) => commit(row.id, e.target.value)}
            className={canEdit ? FIELD_CLASS : READONLY_FIELD_CLASS}
          />
          {hasError && (
            <p role="alert" className="mt-1 text-xs text-red-600">
              Échec de l'enregistrement. Réessayez.
            </p>
          )}
        </div>
      </div>
    );
  };

  const body = (
    <>
      {embedded ? (
        <h2 className="text-2xl font-bold text-[#000E9C] mb-5">{title}</h2>
      ) : (
        <h1 className="text-2xl font-bold text-[#000E9C] mb-5">{title}</h1>
      )}

      {loadError && (
        <div
          role="alert"
          className="mb-6 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          Impossible de charger les réponses enregistrées.
        </div>
      )}

      {config.sections.map((section) => (
        <section key={section.id} className="mb-8">
          <h2 className="text-lg font-semibold text-[#000E9C] mb-4 border-b border-gray-200 pb-2">
            {section.title}
          </h2>

          {section.rows && section.rows.length > 0 && (
            <div className="space-y-4">{section.rows.map(renderRow)}</div>
          )}

          {section.subsections?.map((subsection) => (
            <div key={subsection.id} className="mt-6">
              <h3 className="text-base font-semibold text-[#4949FF] mb-3">{subsection.title}</h3>
              <div className="space-y-4">{subsection.rows.map(renderRow)}</div>
            </div>
          ))}
        </section>
      ))}
    </>
  );

  if (embedded) {
    return body;
  }

  return <div className="card p-6">{body}</div>;
};
