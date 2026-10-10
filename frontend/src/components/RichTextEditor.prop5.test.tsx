import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import fc from 'fast-check';
import {
  RichTextEditor,
  TEXT_COLOR_PALETTE,
  HIGHLIGHT_COLOR_PALETTE,
} from './RichTextEditor';

// Property 5 — Applying a swatch persists the applied color into stored content.
//
// Feature: forum-editor-formatting-controls, Property 5: Applying a swatch
// persists the applied color into stored content.
//
// For any Color_Swatch in either palette (TEXT_COLOR_PALETTE or
// HIGHLIGHT_COLOR_PALETTE), activating it propagates the editor's innerHTML to
// onChange. Clicking a text swatch runs `execCommand('foreColor', ...)` and a
// highlight swatch runs `applyHighlight(...)`; both tails call `handleInput()`
// → `onChange(editorRef.current.innerHTML)`. That propagation is the stored-
// content contract under test.
//
// jsdom does not implement document.execCommand and will NOT mutate the DOM, so
// asserting exact browser-produced color markup is unreliable (the design
// acknowledges markup is browser-dependent). To keep the "encodes the applied
// color" assertion deterministic we stub document.execCommand so it appends a
// color-bearing span to the editor's innerHTML, mirroring what a real browser
// would do, then assert onChange receives that updated innerHTML (and that it
// carries the swatch color).
//
// Validates: Requirements 1.5, 2.5, 4.1

// Combined palette: each entry tagged with the command it drives so the test
// can stub execCommand to produce matching markup for both the foreColor and
// hiliteColor/backColor paths.
const COMBINED_PALETTE = [
  ...TEXT_COLOR_PALETTE.map((s) => ({ ...s, kind: 'text' as const })),
  ...HIGHLIGHT_COLOR_PALETTE.map((s) => ({ ...s, kind: 'highlight' as const })),
];

describe('RichTextEditor — Property 5: swatch application persists color into stored content', () => {
  let execCommandSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // Ensure the property exists before spying — some jsdom builds omit it.
    if (typeof document.execCommand !== 'function') {
      // @ts-expect-error — defining the missing jsdom API for the spy to wrap.
      document.execCommand = () => true;
    }
    // Stub execCommand so color commands append color-bearing markup to the
    // focused contenteditable, making the propagated innerHTML deterministic.
    execCommandSpy = vi
      .spyOn(document, 'execCommand')
      .mockImplementation((command: string, _showUI?: boolean, value?: string) => {
        if (
          (command === 'foreColor' ||
            command === 'hiliteColor' ||
            command === 'backColor') &&
          value
        ) {
          const editor = document.querySelector(
            '[contenteditable]',
          ) as HTMLElement | null;
          if (editor) {
            const prop = command === 'foreColor' ? 'color' : 'background-color';
            editor.innerHTML += `<span style="${prop}: ${value}">x</span>`;
          }
        }
        return true;
      });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('propagates editor innerHTML (encoding the applied color) to onChange for any swatch', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...COMBINED_PALETTE),
        (swatch) => {
          // Feature: forum-editor-formatting-controls, Property 5: Applying a
          // swatch persists the applied color into stored content
          const onChange = vi.fn();
          try {
            render(<RichTextEditor value="" onChange={onChange} />);

            fireEvent.click(screen.getByTitle(swatch.label));

            // The propagation contract: clicking the swatch invoked onChange
            // with the editor's current innerHTML.
            expect(onChange).toHaveBeenCalled();
            const lastArg = onChange.mock.calls.at(-1)?.[0] as string;
            expect(typeof lastArg).toBe('string');

            // The stored content encodes the applied swatch color (via our
            // deterministic execCommand stub standing in for browser markup).
            expect(lastArg).toContain(swatch.color);
          } finally {
            cleanup();
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
