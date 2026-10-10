import { useParams } from 'react-router-dom';
import { StaticContentPage } from '../components/prerequisites/StaticContentPage';
import { QuestionAnswerForm } from '../components/prerequisites/QuestionAnswerForm';
import { ServersTable } from '../components/prerequisites/ServersTable';
import { ChecklistTabs } from '../components/prerequisites/ChecklistTabs';
import { FIRST_PREREQ_SLUG } from '../components/prerequisites/InstallationListPage';
import { CHECKLIST_CATEGORIES } from '../components/prerequisites/checklistCategories';
import type { QuestionFormConfig } from '../components/prerequisites/types';

/**
 * Per-slug prerequisites descriptor. Static slugs render the
 * `StaticContentPage`; question slugs render the `QuestionAnswerForm` with the
 * associated config. Titles mirror the labels the retired per-slug wrapper
 * pages used so the rendered heading is unchanged.
 */
type PrereqSlugConfig =
  | { archetype: 'static'; title: string }
  | { archetype: 'qa'; title: string; config: QuestionFormConfig }
  | { archetype: 'servers'; title: string };

const STATIC_SLUG_CONFIG: Record<string, PrereqSlugConfig> = {
  basics: { archetype: 'static', title: 'Basics' },
  'network-flux': { archetype: 'static', title: 'Network Flux' },
};

// Checklist-tab slugs are derived from the ordered checklist set so the
// aggregate render and the single-category lookup share one definition. The
// servers tab maps to the 'servers' archetype; every other tab is a question
// archetype.
const QUESTION_SLUG_CONFIG: Record<string, PrereqSlugConfig> =
  Object.fromEntries(
    CHECKLIST_CATEGORIES.map((category) => [
      category.slug,
      category.kind === 'servers'
        ? ({ archetype: 'servers', title: category.title } as PrereqSlugConfig)
        : ({
            archetype: 'qa',
            title: category.title,
            config: category.config,
          } as PrereqSlugConfig),
    ]),
  );

const PREREQ_SLUG_CONFIG: Record<string, PrereqSlugConfig> = {
  ...STATIC_SLUG_CONFIG,
  ...QUESTION_SLUG_CONFIG,
};

/**
 * Installation-scoped prerequisites page (Req 5.3). Reads `installationId` and
 * `slug` from the route (`/prerequisites/installations/:installationId/:slug`),
 * looks up the archetype/title/config for the slug, and renders the matching
 * page component with the `installationId` threaded through.
 *
 * When the slug is the default-installation entry slug (`FIRST_PREREQ_SLUG`),
 * the page renders the aggregate view: one `QuestionAnswerForm` per checklist
 * category in order, each stacked as its own section and keyed on its own
 * canonical slug so answer persistence stays scoped to `(installationId, slug)`
 * exactly as for single-category access. An unknown slug renders a not-found
 * message.
 */
export const InstallationPrereqPage = () => {
  const { installationId, slug } = useParams<{
    installationId: string;
    slug: string;
  }>();

  // Guard with `Object.hasOwn` so prototype-inherited keys (e.g. "constructor",
  // "hasOwnProperty", "toString") do not resolve to inherited values and
  // instead fall through to the not-found path like any other unknown slug.
  const config =
    slug && Object.hasOwn(PREREQ_SLUG_CONFIG, slug)
      ? PREREQ_SLUG_CONFIG[slug]
      : undefined;

  if (!installationId || !slug || !config) {
    return (
      <div className="card p-6">
        <div
          role="alert"
          className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
        >
          Page de prérequis introuvable.
        </div>
      </div>
    );
  }

  // Default-installation entry: render all four checklist categories in a
  // tabbed notebook (one tab per category) instead of stacking them. Each tab
  // is keyed on its own canonical slug so answer persistence stays scoped to
  // `(installationId, slug)`.
  if (slug === FIRST_PREREQ_SLUG) {
    return <ChecklistTabs installationId={installationId} tabs={CHECKLIST_CATEGORIES} />;
  }

  if (config.archetype === 'static') {
    return (
      <StaticContentPage
        installationId={installationId}
        slug={slug}
        title={config.title}
      />
    );
  }

  if (config.archetype === 'servers') {
    return <ServersTable title={config.title} installationId={installationId} />;
  }

  return (
    <QuestionAnswerForm
      installationId={installationId}
      slug={slug}
      title={config.title}
      config={config.config}
    />
  );
};
