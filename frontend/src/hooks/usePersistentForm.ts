import { useState } from 'react';
import type {
  FormConfig,
  FormState,
  RowState,
  RowField,
} from '../components/prerequisites/types';

/**
 * Build the default form state from a config: every row across every section
 * gets a RowState whose `value` is the row's `defaultValue` (or ''), `status`
 * is 'pending', and `dateReceived`/`comments` are empty strings.
 */
export function buildDefaults(config: FormConfig): FormState {
  const defaults: FormState = {};
  for (const section of config.sections) {
    for (const row of section.rows) {
      defaults[row.id] = {
        value: row.defaultValue ?? '',
        status: 'pending',
        dateReceived: '',
        comments: '',
      };
    }
  }
  return defaults;
}

const VALID_STATUSES: ReadonlyArray<RowState['status']> = [
  'received',
  'pending',
  'blocked',
  'na',
];

function isRowState(x: unknown): x is RowState {
  if (typeof x !== 'object' || x === null) {
    return false;
  }
  const row = x as Record<string, unknown>;
  return (
    typeof row.value === 'string' &&
    typeof row.dateReceived === 'string' &&
    typeof row.comments === 'string' &&
    typeof row.status === 'string' &&
    VALID_STATUSES.includes(row.status as RowState['status'])
  );
}

/**
 * Type guard verifying that `x` is a non-null object whose every entry is a
 * valid RowState. The `config` argument is accepted for signature symmetry and
 * potential future validation against the known row ids.
 */
export function isValidFormState(
  x: unknown,
  _config: FormConfig,
): x is FormState {
  if (typeof x !== 'object' || x === null || Array.isArray(x)) {
    return false;
  }
  return Object.values(x as Record<string, unknown>).every(isRowState);
}

/**
 * React hook that seeds a tracking form from localStorage (falling back to
 * config-derived defaults on missing/corrupt data) and persists every edit
 * back to localStorage under `storageKey`.
 */
export function usePersistentForm(
  storageKey: string,
  config: FormConfig,
): {
  state: FormState;
  updateField: (rowId: string, field: RowField, value: string) => void;
} {
  const [state, setState] = useState<FormState>(() => {
    const defaults = buildDefaults(config);
    let raw: string | null = null;
    try {
      raw = localStorage.getItem(storageKey);
    } catch {
      // localStorage may be unavailable (disabled/privacy mode): use defaults.
      return defaults;
    }
    if (raw === null) {
      return defaults;
    }
    try {
      const parsed: unknown = JSON.parse(raw);
      if (!isValidFormState(parsed, config)) {
        return defaults;
      }
      // Merge parsed rows over defaults so rows added to the config later still
      // appear (missing rows get defaults) and unknown stored rows are ignored.
      const merged: FormState = { ...defaults };
      for (const rowId of Object.keys(defaults)) {
        if (parsed[rowId] !== undefined) {
          merged[rowId] = parsed[rowId];
        }
      }
      return merged;
    } catch {
      return defaults;
    }
  });

  const updateField = (rowId: string, field: RowField, value: string) => {
    setState((prev) => {
      const current = prev[rowId] ?? {
        value: '',
        status: 'pending' as RowState['status'],
        dateReceived: '',
        comments: '',
      };
      const next: FormState = {
        ...prev,
        [rowId]: { ...current, [field]: value },
      };
      try {
        localStorage.setItem(storageKey, JSON.stringify(next));
      } catch {
        // Write failures (quota, unavailable storage) must not break editing;
        // in-memory state remains authoritative for the session.
      }
      return next;
    });
  };

  return { state, updateField };
}
