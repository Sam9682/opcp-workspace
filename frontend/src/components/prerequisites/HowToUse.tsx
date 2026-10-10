import { PREREQ_MARKERS } from './types';
import { useTranslation } from '../../hooks/useLanguage';

/**
 * Legend describing the Mandatory / Optional markers, built from the shared
 * `PREREQ_MARKERS` constant so it stays consistent with the per-row markers
 * rendered on the question/answer pages (Req 3.2).
 */
const MarkerLegend = () => {
  const { t } = useTranslation();
  return (
    <div className="mb-6 rounded border border-gray-200 bg-gray-50 p-3">
      <span className="mr-3 text-sm font-medium text-gray-700">Légende :</span>
      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1">
        <span className="text-sm text-gray-700">
          <span aria-hidden="true" className="mr-1">
            {PREREQ_MARKERS.mandatory.icon}
          </span>
          {t(PREREQ_MARKERS.mandatory.labelKey)}
        </span>
        <span className="text-sm text-gray-700">
          <span aria-hidden="true" className="mr-1">
            {PREREQ_MARKERS.optional.icon}
          </span>
          {t(PREREQ_MARKERS.optional.labelKey)}
        </span>
      </div>
    </div>
  );
};

/**
 * Short bulleted list of completion tips / example guidance drawn from the
 * customer instructions (Req 3.3).
 */
const COMPLETION_TIPS: readonly string[] = [
  'Selectionnez une installation puis commencez par la page « Network Checklist » avant de compléter les autres onglets.',
  'Répondez à toutes les questions Obligatoires (🔴) dans la colonne « Réponse client ».',
  'Les questions Optionnelles (⚪) peuvent être traitées plus tard.',
  'Remplacez les valeurs d’exemple par votre configuration réelle.',
  'Impliquez les équipes réseau et datacenter dès le début.',
  'Si une question n’est pas claire, laissez-la vide et ajoutez un commentaire.',
  'La colonne « Commentaires » fournit des indications utiles.',
];

/**
 * Archetype 1 — read-only "How to use" page. Presentational only: no props,
 * no persistence, and no editable controls, so it renders identically for
 * every role (Req 3.1). Shows the marker legend (Req 3.2), completion tips
 * and example guidance (Req 3.3), and a visually distinct secrets warning
 * (Req 3.4).
 */
export const HowToUse = () => (
  <div className="card p-6">
    <h1 className="text-2xl font-bold text-[#000E9C] mb-5">Comment utiliser</h1>

    <MarkerLegend />

    <section className="mb-8">
      <h2 className="text-lg font-semibold text-[#000E9C] mb-4 border-b border-gray-200 pb-2">
        Conseils pour compléter les prérequis
      </h2>
      <ul className="list-disc space-y-2 pl-6 text-sm text-gray-800">
        {COMPLETION_TIPS.map((tip) => (
          <li key={tip}>{tip}</li>
        ))}
      </ul>
    </section>

    <div
      role="alert"
      className="rounded-md border-l-4 border-red-500 bg-red-50 p-4"
    >
      <p className="flex items-start gap-2 text-sm font-semibold text-red-800">
        <span aria-hidden="true">⚠️</span>
        <span>
          Ne saisissez jamais de secrets, de clés PSK ou d’identifiants sur cette
          page. Transmettez ces valeurs uniquement via un canal sécurisé.
        </span>
      </p>
    </div>
  </div>
);
