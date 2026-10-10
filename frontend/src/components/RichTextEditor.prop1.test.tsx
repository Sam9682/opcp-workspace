import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import fc from 'fast-check';
import { RichTextEditor, TEXT_COLOR_PALETTE } from './RichTextEditor';

// Task 5.1 — Property 1: Text group renders one swatch per text palette color.
//
// Feature: forum-editor-formatting-controls
// Property 1: Text group renders one swatch per text palette color
// Validates: Requirements 1.1
//
// For any ordering/subset drawn from the text palette, the rendered
// Text_Color_Group must contain exactly one Color_Swatch button per palette
// entry — each palette color appearing exactly once, and no extra text swatch
// buttons present. We drive the universal assertion with fast-check over the
// palette, running a minimum of 100 iterations.

// jsdom does not implement document.execCommand; stub it so the component's
// click handlers (and any focus side effects) do not throw during render.
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

describe('RichTextEditor — Property 1: text group renders one swatch per text palette color', () => {
  it('renders exactly one swatch per text palette color, each color once', () => {
    fc.assert(
      fc.property(
        // Shuffle the palette entries so the property holds regardless of the
        // order in which we probe palette colors.
        fc.shuffledSubarray(TEXT_COLOR_PALETTE, {
          minLength: TEXT_COLOR_PALETTE.length,
          maxLength: TEXT_COLOR_PALETTE.length,
        }),
        (probeOrder) => {
          // Tag each property case for traceability.
          // Feature: forum-editor-formatting-controls, Property 1: Text group renders one swatch per text palette color
          render(<RichTextEditor value="" onChange={() => {}} />);

          try {
            // Each palette color is reachable via exactly one swatch button,
            // identified by its French tooltip label.
            for (const entry of probeOrder) {
              const swatches = screen.getAllByTitle(entry.label);
              expect(swatches).toHaveLength(1);
            }

            // The owning Text_Color_Group contains exactly one button per
            // palette entry — no missing and no extra text swatches.
            const firstSwatch = screen.getByTitle(TEXT_COLOR_PALETTE[0].label);
            const group = groupOf(firstSwatch);

            // Every text palette swatch lives in that same group.
            for (const entry of TEXT_COLOR_PALETTE) {
              expect(groupOf(screen.getByTitle(entry.label))).toBe(group);
            }

            const buttons = group.querySelectorAll('button');
            expect(buttons).toHaveLength(TEXT_COLOR_PALETTE.length);

            // Each palette color appears exactly once across the group's
            // swatch buttons (one swatch per color, no duplicates).
            const titles = Array.from(buttons).map((b) =>
              b.getAttribute('title'),
            );
            const expectedTitles = TEXT_COLOR_PALETTE.map((e) => e.label);
            expect([...titles].sort()).toEqual([...expectedTitles].sort());
            expect(new Set(titles).size).toBe(TEXT_COLOR_PALETTE.length);
          } finally {
            // Each property case renders a fresh editor; clean up to avoid
            // leaking DOM across iterations.
            cleanup();
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
