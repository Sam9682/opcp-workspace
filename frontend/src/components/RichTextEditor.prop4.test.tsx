import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import fc from 'fast-check';
import { RichTextEditor, HIGHLIGHT_COLOR_PALETTE } from './RichTextEditor';

// ===========================================================================
// Task 5.4 — Property test for the highlight command path.
//
// Feature: forum-editor-formatting-controls, Property 4: Activating a highlight
// swatch applies that color as highlight color
//
// For any color drawn from HIGHLIGHT_COLOR_PALETTE, activating its swatch drives
// the highlight command path. The swatch's onClick calls `applyHighlight(color)`
// which runs `document.execCommand('hiliteColor', false, color)` first, falling
// back to `backColor` only when `hiliteColor` returns false. By stubbing the
// spy to return true, the fallback is never taken, so we assert exactly one
// `hiliteColor` call carrying the swatch's color.
//
// Validates: Requirements 2.3
// ===========================================================================

describe('Feature: forum-editor-formatting-controls, Property 4: Activating a highlight swatch applies that color as highlight color', () => {
  let execCommandSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // jsdom does not implement document.execCommand. Install a stub we can spy
    // on, and have it return true so the `hiliteColor → backColor` fallback is
    // never taken — isolating the assertion to the hiliteColor path.
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
    vi.restoreAllMocks();
  });

  it('drives the hiliteColor command with the swatch color for any highlight palette color', () => {
    fc.assert(
      fc.property(fc.constantFrom(...HIGHLIGHT_COLOR_PALETTE), (swatch) => {
        // Feature: forum-editor-formatting-controls, Property 4: Activating a
        // highlight swatch applies that color as highlight color
        try {
          execCommandSpy.mockClear();
          render(<RichTextEditor value="" onChange={() => {}} />);

          // Activate the swatch via its French tooltip.
          fireEvent.click(screen.getByTitle(swatch.label));

          // The (command, color) pairs the component issued, ignoring the
          // middle `showUI` argument that is always false.
          const calls = execCommandSpy.mock.calls.map((call) => ({
            command: call[0],
            value: call[2],
          }));

          // The highlight path was driven with hiliteColor + the swatch color.
          expect(calls).toContainEqual({
            command: 'hiliteColor',
            value: swatch.color,
          });

          // hiliteColor is invoked exactly once with the swatch color.
          const hiliteCalls = calls.filter(
            (c) => c.command === 'hiliteColor',
          );
          expect(hiliteCalls).toHaveLength(1);
          expect(hiliteCalls[0].value).toBe(swatch.color);

          // Spy returns true → the backColor fallback must NOT be taken.
          expect(calls.some((c) => c.command === 'backColor')).toBe(false);
        } finally {
          cleanup();
        }
      }),
      { numRuns: 100 },
    );
  });
});
