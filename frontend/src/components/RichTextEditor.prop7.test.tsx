import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import fc from 'fast-check';
import {
  RichTextEditor,
  TEXT_COLOR_PALETTE,
  HIGHLIGHT_COLOR_PALETTE,
} from './RichTextEditor';

// Task 5.7 — Property 7: Disabled editor disables every swatch.
//
// Feature: forum-editor-formatting-controls
// Property 7: Disabled editor disables every swatch
// Validates: Requirements 3.5
//
// For any Color_Swatch drawn from either palette (TEXT_COLOR_PALETTE +
// HIGHLIGHT_COLOR_PALETTE), while the RichTextEditor is rendered with
// disabled=true, that swatch button must be rendered as disabled. We drive the
// universal assertion with fast-check over the combined palettes, running a
// minimum of 100 iterations.

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

const ALL_SWATCHES = [...TEXT_COLOR_PALETTE, ...HIGHLIGHT_COLOR_PALETTE];

describe('RichTextEditor — Property 7: disabled editor disables every swatch', () => {
  it('renders every palette swatch as disabled when disabled=true (min 100 iterations)', () => {
    fc.assert(
      fc.property(fc.constantFrom(...ALL_SWATCHES), (swatch) => {
        // Feature: forum-editor-formatting-controls, Property 7: Disabled
        // editor disables every swatch
        cleanup();

        render(<RichTextEditor value="" onChange={() => {}} disabled />);

        // The swatch button is reachable by its French tooltip and is rendered
        // disabled while the editor is in the disabled state.
        const button = screen.getByTitle(swatch.label);
        expect(button).toBeDisabled();
      }),
      { numRuns: 100 },
    );
  });
});
