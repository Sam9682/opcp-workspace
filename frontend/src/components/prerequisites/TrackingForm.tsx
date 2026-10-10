import { usePersistentForm } from '../../hooks/usePersistentForm';
import { useTranslation } from '../../hooks/useLanguage';
import { STATUS_OPTIONS } from './types';
import type { FormConfig, RowState } from './types';

interface TrackingFormProps {
  title: string;
  storageKey: string;
  config: FormConfig;
}

const EMPTY_ROW: RowState = {
  value: '',
  status: 'pending',
  dateReceived: '',
  comments: '',
};

const FIELD_CLASS =
  'w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent';

/**
 * Visible key mapping each status choice to its icon + French label.
 */
const StatusLegend = () => {
  const { t } = useTranslation();
  return (
    <div className="mb-6 rounded border border-gray-200 bg-gray-50 p-3">
      <span className="mr-3 text-sm font-medium text-gray-700">Légende :</span>
      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1">
        {STATUS_OPTIONS.map((opt) => (
          <span key={opt.value} className="text-sm text-gray-700">
            <span aria-hidden="true" className="mr-1">
              {opt.icon}
            </span>
            {t(opt.labelKey)}
          </span>
        ))}
      </div>
    </div>
  );
};

/**
 * Data-driven tracking form shared by every prerequisites page. Renders the
 * page title, a status legend, then each configured sub-section as a heading
 * followed by its rows. Every row exposes exactly four fields (Value, Status,
 * Date Received, Comments) wired to the persistence hook.
 */
export const TrackingForm = ({ title, storageKey, config }: TrackingFormProps) => {
  const { state, updateField } = usePersistentForm(storageKey, config);
  const { t } = useTranslation();

  return (
    <div className="card p-6">
      <h1 className="text-2xl font-bold text-[#000E9C] mb-5">{title}</h1>

      <StatusLegend />

      {config.sections.map((section) => (
        <section key={section.id} className="mb-8">
          <h2 className="text-lg font-semibold text-[#000E9C] mb-4 border-b border-gray-200 pb-2">
            {section.title}
          </h2>

          <div className="space-y-6">
            {section.rows.map((row) => {
              const rowState = state[row.id] ?? EMPTY_ROW;
              const valueId = `${row.id}-value`;
              const statusId = `${row.id}-status`;
              const dateId = `${row.id}-date`;
              const commentsId = `${row.id}-comments`;

              return (
                <div key={row.id}>
                  <p className="text-sm font-medium text-gray-800 mb-2">{row.label}</p>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                    <div>
                      <label
                        htmlFor={valueId}
                        className="block text-xs font-medium text-gray-500 mb-1"
                      >
                        Valeur
                      </label>
                      <input
                        type="text"
                        id={valueId}
                        aria-label={`Valeur — ${row.label}`}
                        value={rowState.value}
                        onChange={(e) => updateField(row.id, 'value', e.target.value)}
                        className={FIELD_CLASS}
                      />
                    </div>

                    <div>
                      <label
                        htmlFor={statusId}
                        className="block text-xs font-medium text-gray-500 mb-1"
                      >
                        Statut
                      </label>
                      <select
                        id={statusId}
                        aria-label={`Statut — ${row.label}`}
                        value={rowState.status}
                        onChange={(e) => updateField(row.id, 'status', e.target.value)}
                        className={FIELD_CLASS}
                      >
                        {STATUS_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {`${opt.icon} ${t(opt.labelKey)}`}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label
                        htmlFor={dateId}
                        className="block text-xs font-medium text-gray-500 mb-1"
                      >
                        Date de réception
                      </label>
                      <input
                        type="date"
                        id={dateId}
                        aria-label={`Date de réception — ${row.label}`}
                        value={rowState.dateReceived}
                        onChange={(e) =>
                          updateField(row.id, 'dateReceived', e.target.value)
                        }
                        className={FIELD_CLASS}
                      />
                    </div>

                    <div>
                      <label
                        htmlFor={commentsId}
                        className="block text-xs font-medium text-gray-500 mb-1"
                      >
                        Commentaires
                      </label>
                      <textarea
                        id={commentsId}
                        aria-label={`Commentaires — ${row.label}`}
                        value={rowState.comments}
                        onChange={(e) => updateField(row.id, 'comments', e.target.value)}
                        rows={1}
                        className={FIELD_CLASS}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
};
