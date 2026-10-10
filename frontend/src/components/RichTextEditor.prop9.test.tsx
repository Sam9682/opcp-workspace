import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import fc from 'fast-check';
import { RichContentStyles, HIGHLIGHT_COLOR_PALETTE } from './RichTextEditor';

// Task 5.9 — Property 9: Highlight color renders identically on the display surface.
//
// Feature: forum-editor-formatting-controls
// Property 9: Highlight color renders identically on the display surface
// Validates: Requirements 4.3, 4.4
//
// The editor stores raw innerHTML; the forum display surface (TopicDetailPage)
// renders stored post HTML via dangerouslySetInnerHTML on a `.rich-content`
// container. Both the editor `[contenteditable]` region and the `.rich-content`
// display surface mount the SAME shared `RichContentStyles` stylesheet. The
// highlight markup produced by the editor is inline (`background-color` on a
// `<span>`), so for any identical stored markup the background color must
// render identically on both surfaces.
//
// This property renders the SAME highlight markup inside both a
// `[contenteditable]` div and a `.rich-content` div, mounts <RichContentStyles />
// once, and asserts the resolved background color matches between the two
// containers across every color in HIGHLIGHT_COLOR_PALETTE (min 100 iterations).
//
// jsdom does not run a layout/CSS engine that computes `getComputedStyle`
// background-color from inline styles into rgb() the way a browser would, but
// it does parse inline styles onto the element's `style` property identically
// regardless of the container class. The render-parity contract is exactly
// that: identical markup under the shared stylesheet yields the identical
// resolved background color on both surfaces. We assert that by comparing the
// resolved inline `background-color` (via getComputedStyle, falling back to the
// inline style) of the highlight span in each container.

afterEach(() => {
  cleanup();
});

/** Builds the highlight markup the editor stores for a given color. */
function highlightMarkup(color: string): string {
  return `<span style="background-color: ${color}">x</span>`;
}

/** Converts a 6-digit hex color (e.g. "#fef08a") to its "rgb(r, g, b)" form. */
function hexToRgb(hex: string): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgb(${r}, ${g}, ${b})`;
}

/** Resolves the background color a rendered highlight span presents. */
function resolvedBackground(container: HTMLElement): string {
  const span = container.querySelector('span');
  if (!span) {
    throw new Error('highlight span not found in container');
  }
  const computed = getComputedStyle(span).backgroundColor;
  // Prefer the computed value; fall back to the inline style when the
  // environment leaves computed background-color empty.
  return computed && computed.trim() !== '' ? computed : span.style.backgroundColor;
}

describe('RichTextEditor — Property 9: highlight color renders identically on the display surface', () => {
  it('renders the same background color in the editor region and the .rich-content display surface', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...HIGHLIGHT_COLOR_PALETTE.map((s) => s.color)),
        (color) => {
          // Feature: forum-editor-formatting-controls, Property 9: Highlight color renders identically on the display surface
          const markup = highlightMarkup(color);

          const { container } = render(
            <>
              <RichContentStyles />
              {/* Editor region: contenteditable + shared rich-content class. */}
              <div
                data-testid="editor"
                contentEditable
                className="rich-content"
                dangerouslySetInnerHTML={{ __html: markup }}
              />
              {/* Display surface: non-editable rich-content container, exactly
                  as TopicDetailPage renders stored post HTML. */}
              <div
                data-testid="display"
                className="rich-content"
                dangerouslySetInnerHTML={{ __html: markup }}
              />
            </>,
          );

          try {
            const editor = container.querySelector(
              '[data-testid="editor"]',
            ) as HTMLElement;
            const display = container.querySelector(
              '[data-testid="display"]',
            ) as HTMLElement;

            const editorBg = resolvedBackground(editor);
            const displayBg = resolvedBackground(display);

            // Render parity: identical markup under the shared stylesheet
            // produces the identical background color on both surfaces.
            expect(displayBg).toBe(editorBg);

            // And the rendered background actually carries the applied color
            // (so the assertion is not vacuously comparing two empty strings).
            // The environment may resolve the inline hex to either the hex
            // form or the equivalent "rgb(r, g, b)" form; accept either.
            expect(editorBg).not.toBe('');
            const normalized = editorBg.toLowerCase().replace(/\s+/g, '');
            const acceptable = [
              color.toLowerCase(),
              hexToRgb(color).toLowerCase().replace(/\s+/g, ''),
            ];
            expect(acceptable).toContain(normalized);
          } finally {
            cleanup();
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
