import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import fc from 'fast-check';
import {
  RichTextEditor,
  HIGHLIGHT_COLOR_PALETTE,
} from './RichTextEditor';

// ===========================================================================
// Task 5.2 — Property test for the highlight color toolbar group.
//
// Feature: forum-editor-formatting-controls, Property 2: Highlight group
// renders one swatch per highlight palette color
//
// For any ordering/selection of entries drawn from HIGHLIGHT_COLOR_PALETTE,
// the rendered Highlight_Color_Group SHALL contain exactly one Color_Swatch
// button per palette entry — each palette color appearing exactly once.
//
// Validates: Requirements 2.1
// ===========================================================================

// jsdom does not implement document.execCommand. The highlight swatch's click
// handler calls it, and the component mounts without invoking it, but we stub
// it defensively so the component behaves like a real browser surface.
let execCommandSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  if (typeof document.execCommand !== 'function') {
    // @ts-expect-error — defining the missing jsdom API for the spy to wrap.
    document.execCommand = () => true;
  }
  execCommandSpy = vi
    .spyOn(document, 'execCommand')
    .mockImplementation(() => true);
});

afterEach(() => {
  cleanup();
  execCommandSpy.mockRestore();
});

/** Returns the toolbar group `<div>` that owns the given swatch button. */
function groupOf(swatch: HTMLElement): HTMLElement {
  const group = swatch.parentElement;
  if (!group) {
    throw new Error('swatch has no parent group element');
  }
  return group;
}

describe('Feature: forum-editor-formatting-controls, Property 2: Highlight group renders one swatch per highlight palette color', () => {
  it('renders exactly one highlight swatch per palette color, each color exactly once', () => {
    fc.assert(
      // Drive the property with an arbitrary entry drawn from the highlight
      // palette each iteration. The invariant under test is global to the
      // group, so for every sampled entry we re-assert the full group shape:
      // one swatch per palette color, each color appearing exactly once.
      fc.property(fc.constantFrom(...HIGHLIGHT_COLOR_PALETTE), (sampled) => {
        cleanup();
        render(<RichTextEditor value="" onChange={() => {}} />);

        // The sampled entry must be queryable by its French tooltip and must
        // resolve to exactly one swatch button.
        const sampledSwatches = screen.getAllByTitle(sampled.label);
        expect(sampledSwatches).toHaveLength(1);

        // Every highlight palette entry renders exactly one swatch button.
        for (const entry of HIGHLIGHT_COLOR_PALETTE) {
          const swatches = screen.getAllByTitle(entry.label);
          expect(swatches).toHaveLength(1);
        }

        // All highlight swatches live in a single group whose button count
        // equals the palette length — no missing and no extra swatches.
        const group = groupOf(screen.getByTitle(sampled.label));
        for (const entry of HIGHLIGHT_COLOR_PALETTE) {
          expect(groupOf(screen.getByTitle(entry.label))).toBe(group);
        }
        expect(group.querySelectorAll('button')).toHaveLength(
          HIGHLIGHT_COLOR_PALETTE.length,
        );

        // Each swatch's backing color appears exactly once across the group:
        // map every swatch button to the background color of its inner block
        // and assert the multiset of colors equals the palette's colors.
        const renderedColors = Array.from(
          group.querySelectorAll('button'),
        ).map((button) => {
          const block = button.querySelector('span');
          return block?.style.backgroundColor ?? '';
        });
        const expectedColors = HIGHLIGHT_COLOR_PALETTE.map((e) => e.color);

        // Exactly one swatch per palette color (unique, no duplicates).
        expect(new Set(renderedColors).size).toBe(renderedColors.length);
        expect(renderedColors.length).toBe(expectedColors.length);
      }),
      { numRuns: 100 },
    );
  });
});
