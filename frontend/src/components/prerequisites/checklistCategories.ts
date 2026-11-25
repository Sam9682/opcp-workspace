import type { ChecklistTab } from "./ChecklistTabs";
import {
  cloudStoreQuestionConfig,
  coreControlPlaneConfig,
  networkChecklistConfig,
  opcpContextConfig,
  vcfConfig,
} from "./configs";
import { NO, USE_CASE_GATED_TABS, normalizeYesNo } from "./types";
import type { ContextConfig, QuestionFormConfig } from "./types";

/**
 * Ordered checklist set for the prerequisites question archetype. This is the
 * single source of truth shared by:
 *  - the aggregate tabbed view + per-slug lookup (InstallationPrereqPage), and
 *  - the export / import / architecture-document features
 *    (installationExport service).
 *
 * Keeping one definition means the tabs rendered in the UI and the tabs written
 * to / read from an export file cannot drift apart. Each entry pairs a
 * canonical slug (the persistence key) with its display title and, for
 * question tabs, its question config. The `servers-nodes` tab is a special
 * `kind: 'servers'` entry that renders reference inventory instead of a form.
 */
/** Slug of the OPCP Context tab (the first, context-kind entry). */
export const CONTEXT_SLUG = "opcp-context";

export const CHECKLIST_CATEGORIES: ReadonlyArray<ChecklistTab> = [
  {
    kind: "context",
    slug: CONTEXT_SLUG,
    title: "OPCP Context",
    config: opcpContextConfig,
  },
  {
    slug: "network-checklist",
    title: "Network Checklist",
    config: networkChecklistConfig,
  },
  {
    slug: "core-control-plane",
    title: "Core Control Plane",
    config: coreControlPlaneConfig,
  },
  { slug: "cloudstore", title: "CloudStore", config: cloudStoreQuestionConfig },
  { slug: "vcf", title: "VCF", config: vcfConfig },
  { kind: "servers", slug: "servers-nodes", title: "Servers nodes" },
];

/** Slug of the special servers/nodes tab. */
export const SERVERS_NODES_SLUG = "servers-nodes";

/**
 * The question/answer tabs (everything except the servers inventory and the
 * context tab). The context tab is excluded because its config is a
 * `ContextConfig`, not a `QuestionFormConfig`; keeping it out preserves the
 * soundness of the `as QuestionFormConfig` casts in the export service.
 */
export const QA_CATEGORIES = CHECKLIST_CATEGORIES.filter(
  (
    c,
  ): c is Extract<ChecklistTab, { kind?: "qa"; config: QuestionFormConfig }> =>
    c.kind !== "servers" && c.kind !== "context",
);

/**
 * Explicit, type-narrowed handle to the single context tab so export / import /
 * architecture-document code can include it without string-matching the slug.
 */
export const CONTEXT_CATEGORY = CHECKLIST_CATEGORIES.find(
  (c): c is Extract<ChecklistTab, { kind: "context" }> => c.kind === "context",
)!;

/**
 * True when `slug` is gated by an OPCP Context use case (CloudStore, VCF) that
 * resolves to "No" in `contextAnswers` (falling back to the row's default when
 * no answer is saved). Used to skip those tabs in the export and the
 * architecture document.
 */
export const isUseCaseDisabled = (
  slug: string,
  contextAnswers: Record<string, string> | undefined,
): boolean => {
  const rowId = USE_CASE_GATED_TABS[slug];
  if (!rowId) return false;
  const row = (CONTEXT_CATEGORY.config as ContextConfig).sections
    .flatMap((s) => [
      ...(s.rows ?? []),
      ...(s.subsections ?? []).flatMap((sub) => sub.rows),
    ])
    .find((r) => r.id === rowId);
  return normalizeYesNo(contextAnswers?.[rowId] ?? row?.defaultValue) === NO;
};
