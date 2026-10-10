import { useEffect, useState } from 'react';
import { PREREQ_MARKERS } from './types';
import type { QuestionFormConfig } from './types';
import { useTranslation } from '../../hooks/useLanguage';
import { authService } from '../../services/authService';
import { prerequisitesService } from '../../services/prerequisitesService';
import { buildVcfDomainJson, type VcfDomain } from './vcfDomainTemplates';

// Slug of the VCF checklist tab. The two "generate domain JSON" download
// buttons are surfaced only on this form.
const VCF_SLUG = 'vcf';

/**
 * Trigger a browser download of `content` as a file named `filename`.
 * Uses an object URL + synthetic anchor click, which is the portable way to
 * offer a client-generated file for download without a server round-trip.
 */
const downloadTextFile = (filename: string, content: string, mimeType: string) => {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};

interface QuestionAnswerFormProps {
  installationId: string;
  slug: string;
  title: string;
  config: QuestionFormConfig;
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
 * Visible key mapping the mandatory/optional markers to their icon + label so
 * the per-row markers stay consistent with the shared legend.
 */
const MarkerLegend = () => {
  const { t } = useTranslation();
  return (
    <div className="mb-6 rounded border border-gray-200 bg-gray-50 p-3">
      <span className="mr-3 text-sm font-medium text-gray-700">Légende :</span>
      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1">
        {(Object.keys(PREREQ_MARKERS) as (keyof typeof PREREQ_MARKERS)[]).map((key) => (
          <span key={key} className="text-sm text-gray-700">
            <span aria-hidden="true" className="mr-1">
              {PREREQ_MARKERS[key].icon}
            </span>
            {t(PREREQ_MARKERS[key].labelKey)}
          </span>
        ))}
      </div>
    </div>
  );
};

/**
 * Data-driven question/answer form for the prerequisites pages that follow the
 * question archetype (Network Checklist, Core Control Plane, CloudStore, VCF).
 *
 * Each row renders two read-only question columns, a Mandatory/Optional marker,
 * the example value, a Comments/Details hint, and one editable Client answer.
 * The Client answer is editable for any authenticated user (administrators
 * included); unauthenticated visitors see it read-only. Answers persist through
 * `prerequisitesService` (no localStorage).
 */
export const QuestionAnswerForm = ({
  installationId,
  slug,
  title,
  config,
  variant = 'card',
}: QuestionAnswerFormProps) => {
  const { t } = useTranslation();
  const canAnswer = authService.isAuthenticated();
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

  const handleChange = (rowId: string, value: string) => {
    // Preserve the typed value locally regardless of persistence outcome.
    setAnswers((a) => ({ ...a, [rowId]: value }));
  };

  const saveAnswer = async (rowId: string, value: string) => {
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

  const isVcf = slug === VCF_SLUG;

  const downloadDomainJson = (domain: VcfDomain) => {
    const json = buildVcfDomainJson(domain, answers);
    const filename = domain === 'management' ? 'management.json' : 'workload.json';
    downloadTextFile(filename, `${JSON.stringify(json, null, 2)}\n`, 'application/json');
  };

  const embedded = variant === 'embedded';

  const body = (
    <>
      {embedded ? (
        <h2 className="text-2xl font-bold text-[#000E9C] mb-5">{title}</h2>
      ) : (
        <h1 className="text-2xl font-bold text-[#000E9C] mb-5">{title}</h1>
      )}

      <MarkerLegend />

      {isVcf && (
        <div className="mb-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => downloadDomainJson('management')}
            className="rounded bg-[#000E9C] px-4 py-2 text-sm font-semibold text-white hover:bg-[#000B7A] focus:outline-none focus:ring-2 focus:ring-[#4949FF] focus:ring-offset-1"
          >
            Générer le fichier JSON du domaine de management
          </button>
          <button
            type="button"
            onClick={() => downloadDomainJson('workload')}
            className="rounded bg-[#000E9C] px-4 py-2 text-sm font-semibold text-white hover:bg-[#000B7A] focus:outline-none focus:ring-2 focus:ring-[#4949FF] focus:ring-offset-1"
          >
            Générer le fichier JSON du domaine workload
          </button>
        </div>
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

          <div className="space-y-6">
            {section.rows.map((row) => {
              const marker = row.mandatory
                ? PREREQ_MARKERS.mandatory
                : PREREQ_MARKERS.optional;
              const answerId = `${row.id}-answer`;
              const hasError = errorRowIds.has(row.id);

              return (
                <div key={row.id} className="border-b border-gray-100 pb-4 last:border-b-0">
                  <div className="mb-2 flex items-center gap-2">
                    <span
                      aria-label={t(marker.labelKey)}
                      title={t(marker.labelKey)}
                      className="text-sm"
                    >
                      {marker.icon}
                    </span>
                    <span className="text-xs font-medium text-gray-500">
                      {t(marker.labelKey)}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div>
                      <p className="block text-xs font-medium text-gray-500 mb-1">Question</p>
                      <p className="text-sm font-medium text-gray-800">{row.questionPrimary}</p>
                    </div>

                    <div>
                      <p className="block text-xs font-medium text-gray-500 mb-1">Détail</p>
                      <p className="text-sm text-gray-700">{row.questionSecondary ?? '—'}</p>
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
                    <div>
                      <p className="block text-xs font-medium text-gray-500 mb-1">Exemple</p>
                      <p className="text-sm text-gray-700">{row.exampleValue ?? '—'}</p>
                    </div>

                    <div>
                      <p className="block text-xs font-medium text-gray-500 mb-1">
                        Commentaires
                      </p>
                      <p className="text-sm text-gray-700">{row.commentsHint ?? '—'}</p>
                    </div>

                    <div>
                      <label
                        htmlFor={answerId}
                        className="block text-xs font-medium text-gray-500 mb-1"
                      >
                        Réponse client
                      </label>
                      <input
                        type="text"
                        id={answerId}
                        aria-label={`Réponse client — ${row.questionPrimary}`}
                        value={answers[row.id] ?? ''}
                        readOnly={!canAnswer}
                        disabled={!canAnswer}
                        onChange={(e) => handleChange(row.id, e.target.value)}
                        onBlur={(e) => {
                          if (canAnswer) void saveAnswer(row.id, e.target.value);
                        }}
                        className={canAnswer ? FIELD_CLASS : READONLY_FIELD_CLASS}
                      />
                      {hasError && (
                        <p role="alert" className="mt-1 text-xs text-red-600">
                          Échec de l'enregistrement. Réessayez.
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </>
  );

  if (embedded) {
    return body;
  }

  return <div className="card p-6">{body}</div>;
};
