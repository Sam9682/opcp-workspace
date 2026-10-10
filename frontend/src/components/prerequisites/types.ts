export type Status = 'received' | 'pending' | 'blocked' | 'na';

export interface StatusMeta {
  value: Status;
  labelKey: string;
  icon: string;
}

export const STATUS_OPTIONS: StatusMeta[] = [
  { value: 'received', labelKey: 'prereq.status.received', icon: '✅' },
  { value: 'pending', labelKey: 'prereq.status.pending', icon: '⏳' },
  { value: 'blocked', labelKey: 'prereq.status.blocked', icon: '❌' },
  { value: 'na', labelKey: 'prereq.status.na', icon: '—' },
];

// Static description of a parameter row (from config)
export interface ParameterRow {
  id: string; // stable key, unique within a page
  label: string; // French label shown to the coordinator
  defaultValue?: string;
}

export interface SubSection {
  id: string;
  title: string; // French sub-section heading
  rows: ParameterRow[];
}

export interface FormConfig {
  sections: SubSection[];
}

// Editable per-row state (persisted)
export interface RowState {
  value: string;
  status: Status;
  dateReceived: string; // ISO yyyy-mm-dd or ''
  comments: string;
}

export type RowField = keyof RowState;

// Persisted shape: rowId -> RowState
export type FormState = Record<string, RowState>;

// Shared navigation config for the prerequisites dropdown (desktop + mobile)
export interface PrereqNavItem {
  labelKey: string;
  route: string; // always `/prerequisites/${slug}`
  archetype: 'how-to-use' | 'static' | 'qa';
}

// Content and answers are now installation-scoped, so the per-slug pages can no
// longer be reached without an Installation. The nav therefore points at the
// Installation list entry point (`/prerequisites/installations`), from which a
// user selects an Installation before drilling into a slug. The global
// how-to-use page (no per-installation data) remains directly reachable.
export const PREREQ_NAV_ITEMS = [
  { labelKey: 'prereq.nav.howToUse', route: '/prerequisites/how-to-use', archetype: 'how-to-use' },
  { labelKey: 'prereq.nav.installations', route: '/prerequisites/installations', archetype: 'static' },
] as const satisfies readonly PrereqNavItem[];

// Shared marker legend used by the How-to-use legend and per-row markers on
// question/answer pages so they stay consistent.
export const PREREQ_MARKERS = {
  mandatory: { labelKey: 'prereq.marker.mandatory', icon: '🔴' },
  optional: { labelKey: 'prereq.marker.optional', icon: '⚪' },
} as const;
// ---------------------------------------------------------------------------
// Question-archetype data models (Network Checklist, Core Control Plane,
// CloudStore, VCF). These live alongside the legacy ParameterRow/SubSection/
// FormConfig types, which are retained unchanged for TrackingForm.
// ---------------------------------------------------------------------------

// A single question row: two read-only question columns plus per-row metadata
// and an editable Client answer (persisted separately as ClientAnswers).
export interface QuestionRow {
  id: string; // stable, unique within a page
  questionPrimary: string; // read-only question column 1
  questionSecondary?: string; // read-only question column 2
  mandatory: boolean; // drives the Mandatory/Optional marker
  exampleValue?: string; // example value shown to the customer
  commentsHint?: string; // Comments/Details hint
}

export interface QuestionSection {
  id: string;
  title: string;
  rows: QuestionRow[];
}

export interface QuestionFormConfig {
  sections: QuestionSection[];
}

// Static-content model: a single HTML/markdown string persisted per slug.
export interface StaticContent {
  slug: string;
  content: string;
  updatedAt?: string;
}

// Client-answer model: a rowId -> answer map persisted per slug.
export interface ClientAnswers {
  slug: string;
  answers: Record<string, string>;
}

// ---------------------------------------------------------------------------
// Context-archetype data models (OPCP Context tab). These render a labeled
// key/value information form grouped into sections and nested subsections
// (Contacts). They live alongside the existing ParameterRow/SubSection types,
// which are retained unchanged for TrackingForm. The existing SubSection does
// not nest, which is why a dedicated nested shape is introduced here.
// ---------------------------------------------------------------------------

// A single labeled key/value entry. `id` is stable and unique page-wide
// (it is the persistence rowId). `defaultValue` seeds the field when no
// saved value exists for the installation.
export interface ContextRow {
  id: string; // stable, unique within the context page (the rowId)
  label: string; // French label shown to the user
  defaultValue: string; // seeded value; '' means "empty default"
}

// A nested subsection (used by the Contacts section). Mirrors the shape of a
// section minus further nesting — subsections do not nest further.
export interface ContextSubSection {
  id: string;
  title: string; // French subsection heading
  rows: ContextRow[];
}

// An ordered section. A section carries either direct rows, nested
// subsections, or both. Rendering order is: section rows first (if any),
// then each subsection with its heading above its rows.
export interface ContextSection {
  id: string;
  title: string; // French section heading
  rows?: ContextRow[];
  subsections?: ContextSubSection[];
}

// The configuration shape for the OPCP Context tab.
export interface ContextConfig {
  sections: ContextSection[];
}
