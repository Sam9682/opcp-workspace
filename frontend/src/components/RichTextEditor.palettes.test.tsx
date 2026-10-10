import { describe, it, expect } from 'vitest';
import { TEXT_COLOR_PALETTE, HIGHLIGHT_COLOR_PALETTE } from './RichTextEditor';

// Task 1.2 — Example tests for the RichTextEditor color palette definitions.
//
// These example tests assert the shape and integrity of the two exported
// palettes (text color + highlight color): the expected entries are present,
// every entry carries a non-empty CSS color and a non-empty French label, and
// colors are unique within each palette.
//
// Validates: Requirements 1.2, 2.2, 3.4

// ---------------------------------------------------------------------------
// Expected palette contents (kept in sync with RichTextEditor.tsx)
// ---------------------------------------------------------------------------

const EXPECTED_TEXT_COLORS = [
  '#000000',
  '#e11d48',
  '#2563eb',
  '#16a34a',
  '#d97706',
  '#7c3aed',
];

const EXPECTED_HIGHLIGHT_COLORS = [
  '#fef08a',
  '#bbf7d0',
  '#bfdbfe',
  '#fecaca',
  '#e9d5ff',
];

// A label is considered a non-empty French label when it has visible content.
const isNonEmptyString = (value: unknown): boolean =>
  typeof value === 'string' && value.trim().length > 0;

describe('TEXT_COLOR_PALETTE', () => {
  it('contains the expected color entries in order', () => {
    expect(TEXT_COLOR_PALETTE.map((entry) => entry.color)).toEqual(
      EXPECTED_TEXT_COLORS,
    );
  });

  it('exposes a non-empty color for every entry', () => {
    for (const entry of TEXT_COLOR_PALETTE) {
      expect(isNonEmptyString(entry.color)).toBe(true);
    }
  });

  it('exposes a non-empty French label for every entry', () => {
    for (const entry of TEXT_COLOR_PALETTE) {
      expect(isNonEmptyString(entry.label)).toBe(true);
      // French labels for text colors are prefixed with "Texte".
      expect(entry.label).toMatch(/^Texte\s+\S/);
    }
  });

  it('has unique colors within the palette', () => {
    const colors = TEXT_COLOR_PALETTE.map((entry) => entry.color);
    expect(new Set(colors).size).toBe(colors.length);
  });
});

describe('HIGHLIGHT_COLOR_PALETTE', () => {
  it('contains the expected color entries in order', () => {
    expect(HIGHLIGHT_COLOR_PALETTE.map((entry) => entry.color)).toEqual(
      EXPECTED_HIGHLIGHT_COLORS,
    );
  });

  it('exposes a non-empty color for every entry', () => {
    for (const entry of HIGHLIGHT_COLOR_PALETTE) {
      expect(isNonEmptyString(entry.color)).toBe(true);
    }
  });

  it('exposes a non-empty French label for every entry', () => {
    for (const entry of HIGHLIGHT_COLOR_PALETTE) {
      expect(isNonEmptyString(entry.label)).toBe(true);
      // French labels for highlight colors are prefixed with "Surlignage".
      expect(entry.label).toMatch(/^Surlignage\s+\S/);
    }
  });

  it('has unique colors within the palette', () => {
    const colors = HIGHLIGHT_COLOR_PALETTE.map((entry) => entry.color);
    expect(new Set(colors).size).toBe(colors.length);
  });
});
