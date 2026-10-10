import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import fc from 'fast-check';
import { RichTextEditor, TEXT_COLOR_PALETTE } from './RichTextEditor';

// Task 5.3 — Property test for the forum editor text-color swatches.
//
// Property 3: Activating a text swatch applies that color as font color.
// For any color in TEXT_COLOR_PALETTE, activating its Color_Swatch invokes the
// text-color command (`foreColor`) with exactly that color against the current
// selection — with no confirmation step.
//
// Validates: Requirements 1.3, 1.4

// jsdom does not implement document.execCommand, so install a stub we can spy
// on before wrapping it with the spy.
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

describe('RichTextEditor — Property 3: text swatch applies color as font color', () => {
  it('invokes foreColor with exactly the activated swatch color (min 100 iterations)', () => {
    fc.assert(
      fc.property(fc.constantFrom(...TEXT_COLOR_PALETTE), (swatch) => {
        // Feature: forum-editor-formatting-controls, Property 3: Activating a
        // text swatch applies that color as font color
        execCommandSpy.mockClear();
        cleanup();

        render(<RichTextEditor value="" onChange={() => {}} />);

        fireEvent.click(screen.getByTitle(swatch.label));

        // The text swatch applies the color immediately with no confirmation:
        // exactly one foreColor invocation carrying this swatch's color.
        expect(execCommandSpy).toHaveBeenCalledWith(
          'foreColor',
          false,
          swatch.color,
        );
        const foreColorCalls = execCommandSpy.mock.calls.filter(
          ([command]) => command === 'foreColor',
        );
        expect(foreColorCalls).toHaveLength(1);
        expect(foreColorCalls[0]).toEqual(['foreColor', false, swatch.color]);
      }),
      { numRuns: 100 },
    );
  });
});
