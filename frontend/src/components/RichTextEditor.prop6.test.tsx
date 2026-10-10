import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import fc from 'fast-check';
import {
  RichTextEditor,
  TEXT_COLOR_PALETTE,
  HIGHLIGHT_COLOR_PALETTE,
} from './RichTextEditor';

// Task 5.6 — Property 6: Every swatch has a French tooltip.
//
// Feature: forum-editor-formatting-controls
// Property 6: Every swatch has a French tooltip
// Validates: Requirements 3.4
//
// For any Color_Swatch drawn from either palette (TEXT_COLOR_PALETTE or
// HIGHLIGHT_COLOR_PALETTE), the rendered swatch button must carry a non-empty
// French-language `title` attribute. We drive the universal assertion with
// fast-check over the combined palettes, running a minimum of 100 iterations.

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

// The union of both palettes — every swatch the editor renders.
const ALL_SWATCHES = [...TEXT_COLOR_PALETTE, ...HIGHLIGHT_COLOR_PALETTE];

describe('RichTextEditor — Property 6: every swatch has a French tooltip', () => {
  it('renders a non-empty French title on every swatch in both palettes', () => {
    fc.assert(
      fc.property(
        // Any swatch drawn from the combined palettes must satisfy the
        // property, regardless of which one fast-check probes.
        fc.constantFrom(...ALL_SWATCHES),
        (swatch) => {
          // Tag each property case for traceability.
          // Feature: forum-editor-formatting-controls, Property 6: Every swatch has a French tooltip
          render(<RichTextEditor value="" onChange={() => {}} />);

          try {
            // The swatch is reachable via its French tooltip label, and the
            // rendered button carries that label as a non-empty title.
            const button = screen.getByTitle(swatch.label);
            const title = button.getAttribute('title');

            expect(typeof title).toBe('string');
            expect(title).not.toBeNull();
            expect((title ?? '').trim().length).toBeGreaterThan(0);
            expect(title).toBe(swatch.label);
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
