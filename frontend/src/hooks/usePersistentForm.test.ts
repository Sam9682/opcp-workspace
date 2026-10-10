import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import fc from 'fast-check';
import type { FormConfig, FormState, RowField, Status } from '../components/prerequisites/types';
import { usePersistentForm, buildDefaults, isValidFormState } from './usePersistentForm';

// Minimum property-test iterations mandated by the design (>= 100).
const NUM_RUNS = 100;

// A small hand-written config with multiple sections/rows, one carrying a
// non-empty defaultValue, so defaults and merges are exercised meaningfully.
const testConfig: FormConfig = {
  sections: [
    {
      id: 'section-a',
      title: 'Section A',
      rows: [
        { id: 'row-1', label: 'Row 1' },
        { id: 'row-2', label: 'Row 2', defaultValue: 'preset' },
      ],
    },
    {
      id: 'section-b',
      title: 'Section B',
      rows: [
        { id: 'row-3', label: 'Row 3' },
        { id: 'row-4', label: 'Row 4' },
      ],
    },
  ],
};

const ALL_ROW_IDS = testConfig.sections.flatMap((s) => s.rows.map((r) => r.id));
const VALID_STATUSES: Status[] = ['received', 'pending', 'blocked', 'na'];
const EDITABLE_FIELDS: RowField[] = ['value', 'status', 'dateReceived', 'comments'];

// Generator for an arbitrary sequence of field edits over the known rows.
const editArb = fc.record({
  rowId: fc.constantFrom(...ALL_ROW_IDS),
  field: fc.constantFrom(...EDITABLE_FIELDS),
  value: fc.string(),
});

// When editing the status field the value must be a valid Status, otherwise
// the persisted state would fail isValidFormState. This generator picks a
// coherent value for the chosen field.
const coherentEditArb = editArb.map((edit) =>
  edit.field === 'status'
    ? { ...edit, value: VALID_STATUSES[edit.value.length % VALID_STATUSES.length] }
    : edit,
);

beforeEach(() => {
  localStorage.clear();
});

// Property 5: Persist-then-load round trip.
// Validates: Requirements 7.1, 7.2
describe('Property 5: persist-then-load round trip', () => {
  it('re-initializing with the same key reflects persisted edits', () => {
    fc.assert(
      fc.property(
        fc.array(coherentEditArb, { minLength: 1, maxLength: 20 }),
        fc.string({ minLength: 1 }),
        (edits, keySuffix) => {
          localStorage.clear();
          const storageKey = `key-${keySuffix}`;

          // First hook instance: apply arbitrary edits, which persist to storage.
          const first = renderHook(() => usePersistentForm(storageKey, testConfig));
          for (const edit of edits) {
            act(() => {
              first.result.current.updateField(edit.rowId, edit.field, edit.value);
            });
          }
          const persistedState = first.result.current.state;

          // Second, fresh hook instance with the same key + config.
          const second = renderHook(() => usePersistentForm(storageKey, testConfig));

          // Its initial state equals the persisted state from the first instance.
          expect(second.result.current.state).toEqual(persistedState);
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});

// Property 6: Unparseable storage falls back to defaults.
// Validates: Requirement 7.4
describe('Property 6: unparseable storage falls back to defaults', () => {
  it('populates defaults and does not throw for non-form-state strings', () => {
    const defaults = buildDefaults(testConfig);

    fc.assert(
      fc.property(fc.string(), fc.string({ minLength: 1 }), (raw, keySuffix) => {
        // Keep only strings that are NOT valid serialized form states, so we
        // genuinely exercise the fallback path.
        fc.pre(!isSerializedValidFormState(raw));

        localStorage.clear();
        const storageKey = `key-${keySuffix}`;
        localStorage.setItem(storageKey, raw);

        let state: FormState | undefined;
        expect(() => {
          const { result } = renderHook(() => usePersistentForm(storageKey, testConfig));
          state = result.current.state;
        }).not.toThrow();

        expect(state).toEqual(defaults);
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// Helper: a raw string is a "valid serialized form state" only if it parses as
// JSON AND satisfies the hook's own validator. Anything else must fall back.
function isSerializedValidFormState(raw: string): boolean {
  try {
    return isValidFormState(JSON.parse(raw), testConfig);
  } catch {
    return false;
  }
}

// Property 4: Editing a field updates the in-memory value.
// Validates: Requirement 5.4
describe('Property 4: editing a field updates the in-memory value', () => {
  it('after updateField, the row/field equals the entered value', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...ALL_ROW_IDS),
        fc.constantFrom(...EDITABLE_FIELDS),
        fc.string(),
        fc.string({ minLength: 1 }),
        (rowId, field, rawValue, keySuffix) => {
          localStorage.clear();
          // Status must be a valid Status value.
          const value =
            field === 'status'
              ? VALID_STATUSES[rawValue.length % VALID_STATUSES.length]
              : rawValue;
          const storageKey = `key-${keySuffix}`;

          const { result } = renderHook(() => usePersistentForm(storageKey, testConfig));
          act(() => {
            result.current.updateField(rowId, field, value);
          });

          expect(result.current.state[rowId][field]).toBe(value);
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});

// Property 7: Per-page storage isolation.
// Validates: Requirement 7.5
describe('Property 7: per-page storage isolation', () => {
  it('editing page A leaves page B storage unchanged', () => {
    fc.assert(
      fc.property(
        fc.array(coherentEditArb, { minLength: 1, maxLength: 20 }),
        fc.string({ minLength: 1 }),
        fc.string({ minLength: 1 }),
        (edits, suffixA, suffixB) => {
          // Ensure the two keys are genuinely distinct.
          fc.pre(suffixA !== suffixB);

          localStorage.clear();
          const keyA = `page-a-${suffixA}`;
          const keyB = `page-b-${suffixB}`;

          const before = localStorage.getItem(keyB);

          const pageA = renderHook(() => usePersistentForm(keyA, testConfig));
          for (const edit of edits) {
            act(() => {
              pageA.result.current.updateField(edit.rowId, edit.field, edit.value);
            });
          }

          // Page B's stored data is unchanged (still absent here).
          expect(localStorage.getItem(keyB)).toBe(before);
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});
