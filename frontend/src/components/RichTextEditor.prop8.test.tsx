import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import fc from 'fast-check';
import { RichContentStyles, TEXT_COLOR_PALETTE } from './RichTextEditor';

// ===========================================================================
// Task 5.8 — Property test for text color rendering on the display surface.
//
// Property 8: Text color renders identically on the display surface.
//
// For any stored HTML carrying text-color formatting, rendering it in the
// `.rich-content` Display_Surface produces the SAME text color as the
// `[contenteditable]` editor region renders for identical markup. Both surfaces
// mount the shared `RichContentStyles` stylesheet (which targets both
// `[contenteditable]` and `.rich-content`), so color — expressed as inline
// markup rather than a stylesheet rule — must resolve identically regardless of
// which container holds it.
//
// We render the SAME text-color markup inside both a `[contenteditable]` div
// and a `.rich-content` div, mount <RichContentStyles />, then compare the
// resolved text color of the colored element across the two containers. In
// jsdom, computed-style resolution of inline `color` is reliable, so querying
// the colored element in each container and comparing `color` is deterministic.
//
// Each palette color is exercised through two equivalent stored-markup shapes a
// browser's `foreColor` command may emit: the legacy `<font color>` element and
// a `<span style="color: ...">` element. Both are text-color formatting.
//
// Validates: Requirements 4.2, 4.4
// ===========================================================================

afterEach(() => {
  cleanup();
});

// The two stored-markup shapes that encode text color, parameterized by color.
const MARKUP_SHAPES: Array<{ name: string; build: (color: string) => string }> = [
  { name: 'font-color', build: (color) => `<font color="${color}">x</font>` },
  {
    name: 'span-style-color',
    build: (color) => `<span style="color: ${color}">x</span>`,
  },
];

// Resolve the rendered text color of the single colored element inside a
// container. `<font color>` sets the `color` attribute (reflected onto the
// element) while `<span style>` sets inline `color`; querySelector targets the
// colored leaf in either case.
const resolveTextColor = (container: HTMLElement): string => {
  const colored = container.querySelector('font, span') as HTMLElement | null;
  expect(colored).not.toBeNull();
  return getComputedStyle(colored as HTMLElement).color;
};

describe('Feature: forum-editor-formatting-controls, Property 8: Text color renders identically on the display surface', () => {
  it('renders identical text color in the [contenteditable] editor and the .rich-content display surface for any palette color (min 100 iterations)', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...TEXT_COLOR_PALETTE),
        fc.constantFrom(...MARKUP_SHAPES),
        (swatch, shape) => {
          // Feature: forum-editor-formatting-controls, Property 8: Text color
          // renders identically on the display surface
          cleanup();

          const markup = shape.build(swatch.color);

          // Mount the shared styles once, plus both surfaces carrying the SAME
          // stored text-color markup: the editor region ([contenteditable]) and
          // the display surface (.rich-content).
          const { container } = render(
            <>
              <RichContentStyles />
              <div
                data-testid="editor"
                contentEditable
                className="rich-content"
                dangerouslySetInnerHTML={{ __html: markup }}
              />
              <div
                data-testid="display"
                className="rich-content"
                dangerouslySetInnerHTML={{ __html: markup }}
              />
            </>,
          );

          const editor = container.querySelector(
            '[data-testid="editor"]',
          ) as HTMLElement;
          const display = container.querySelector(
            '[data-testid="display"]',
          ) as HTMLElement;

          const editorColor = resolveTextColor(editor);
          const displayColor = resolveTextColor(display);

          // The display surface renders the text in the same color as the
          // editor region for identical markup.
          expect(displayColor).toBe(editorColor);

          cleanup();
        },
      ),
      { numRuns: 100 },
    );
  });
});
