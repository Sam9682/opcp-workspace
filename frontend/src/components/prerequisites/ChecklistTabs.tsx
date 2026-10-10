import { useId, useState } from 'react';
import { ContextForm } from './ContextForm';
import { QuestionAnswerForm } from './QuestionAnswerForm';
import { ServersTable } from './ServersTable';
import type { ContextConfig, QuestionFormConfig } from './types';

/**
 * A checklist tab is either a question/answer category (driven by a
 * `QuestionFormConfig`) or a special-purpose tab (`kind: 'servers'`) that
 * renders reference data instead of an editable form.
 */
export type ChecklistTab =
  | {
      kind?: 'qa';
      slug: string;
      title: string;
      config: QuestionFormConfig;
    }
  | {
      kind: 'servers';
      slug: string;
      title: string;
    }
  | {
      kind: 'context';
      slug: string;
      title: string;
      config: ContextConfig;
    };

interface ChecklistTabsProps {
  installationId: string;
  tabs: ReadonlyArray<ChecklistTab>;
}

/**
 * Tabbed-notebook wrapper for the aggregate prerequisites view. Each checklist
 * category (Network Checklist, Core Control Plane, CloudStore, VCF) is exposed
 * as its own tab instead of being stacked vertically on one page.
 *
 * All panels stay mounted (inactive ones hidden with `hidden`) so each
 * `QuestionAnswerForm` keeps its independently loaded/persisted answer state
 * when the user switches tabs. Implements the WAI-ARIA tabs pattern with
 * roving arrow-key navigation.
 */
export const ChecklistTabs = ({ installationId, tabs }: ChecklistTabsProps) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const baseId = useId();

  if (tabs.length === 0) return null;

  const clampedActive = Math.min(activeIndex, tabs.length - 1);

  const tabId = (index: number) => `${baseId}-tab-${index}`;
  const panelId = (index: number) => `${baseId}-panel-${index}`;

  const focusTab = (index: number) => {
    const el = document.getElementById(tabId(index));
    el?.focus();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    const last = tabs.length - 1;
    let next: number | null = null;

    switch (event.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        next = clampedActive === last ? 0 : clampedActive + 1;
        break;
      case 'ArrowLeft':
      case 'ArrowUp':
        next = clampedActive === 0 ? last : clampedActive - 1;
        break;
      case 'Home':
        next = 0;
        break;
      case 'End':
        next = last;
        break;
      default:
        return;
    }

    event.preventDefault();
    setActiveIndex(next);
    focusTab(next);
  };

  return (
    <div className="card p-6">
      <div
        role="tablist"
        aria-label="Sections des prérequis"
        className="mb-6 flex flex-wrap gap-1 border-b border-gray-200"
      >
        {tabs.map((tab, index) => {
          const selected = index === clampedActive;
          return (
            <button
              key={tab.slug}
              type="button"
              role="tab"
              id={tabId(index)}
              aria-selected={selected}
              aria-controls={panelId(index)}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActiveIndex(index)}
              onKeyDown={handleKeyDown}
              className={
                selected
                  ? 'border-b-2 border-[#4949FF] px-4 py-2 text-sm font-semibold text-[#000E9C] -mb-px focus:outline-none focus:ring-2 focus:ring-[#4949FF] focus:ring-offset-1 rounded-t'
                  : 'border-b-2 border-transparent px-4 py-2 text-sm font-medium text-gray-500 hover:text-[#000E9C] hover:border-gray-300 -mb-px focus:outline-none focus:ring-2 focus:ring-[#4949FF] focus:ring-offset-1 rounded-t'
              }
            >
              {tab.title}
            </button>
          );
        })}
      </div>

      {tabs.map((tab, index) => (
        <div
          key={tab.slug}
          role="tabpanel"
          id={panelId(index)}
          aria-labelledby={tabId(index)}
          hidden={index !== clampedActive}
        >
          {tab.kind === 'servers' ? (
            <ServersTable title={tab.title} variant="embedded" installationId={installationId} />
          ) : tab.kind === 'context' ? (
            <ContextForm
              installationId={installationId}
              slug={tab.slug}
              title={tab.title}
              config={tab.config}
              variant="embedded"
            />
          ) : (
            <QuestionAnswerForm
              installationId={installationId}
              slug={tab.slug}
              title={tab.title}
              config={tab.config}
              variant="embedded"
            />
          )}
        </div>
      ))}
    </div>
  );
};
