import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { RichTextEditor, HIGHLIGHT_COLOR_PALETTE } from './RichTextEditor';

// Task 2.2 — Example tests for the `hiliteColor → backColor` fallback branch.
//
// Clicking a highlight swatch (title prefixed with "Surlignage") runs
// `applyHighlight(color)`, which first calls
// `document.execCommand('hiliteColor', false, color)`. When that returns false
// the component falls back to `document.execCommand('backColor', false, color)`
// with the same color. When `hiliteColor` returns true, `backColor` must NOT be
// called.
//
// Validates: Requirements 2.4

// The first highlight swatch — used as the representative click target.
const FIRST_HIGHLIGHT = HIGHLIGHT_COLOR_PALETTE[0];

// Click the swatch button whose title matches the given highlight label.
const clickHighlightSwatch = (label: string) => {
  const button = screen.getByTitle(label);
  fireEvent.click(button);
};

// Extract the (command, color) pairs from the execCommand spy, ignoring the
// middle `showUI` argument the component always passes as `false`.
const commandCalls = (spy: ReturnType<typeof vi.spyOn>) =>
  spy.mock.calls.map((call) => ({ command: call[0], value: call[2] }));

describe('RichTextEditor highlight fallback (hiliteColor → backColor)', () => {
  let execCommandSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // jsdom does not implement document.execCommand, so install a stub we can
    // spy on. We provide a default no-op implementation and override the return
    // value per test via mockImplementation.
    // @ts-expect-error — execCommand is not typed as writable in jsdom's lib.
    document.execCommand = () => false;
    execCommandSpy = vi.spyOn(document, 'execCommand');
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('falls back to backColor when hiliteColor returns false', () => {
    // hiliteColor is not applied by the browser → returns false.
    execCommandSpy.mockImplementation((command: string) =>
      command === 'hiliteColor' ? false : true,
    );

    render(<RichTextEditor value="" onChange={() => {}} />);

    clickHighlightSwatch(FIRST_HIGHLIGHT.label);

    const calls = commandCalls(execCommandSpy);

    // hiliteColor was attempted first with the swatch color.
    expect(calls).toContainEqual({
      command: 'hiliteColor',
      value: FIRST_HIGHLIGHT.color,
    });

    // backColor was invoked as the fallback with the SAME color.
    expect(calls).toContainEqual({
      command: 'backColor',
      value: FIRST_HIGHLIGHT.color,
    });

    // Ordering: hiliteColor must be attempted before the backColor fallback.
    const commands = calls.map((c) => c.command);
    expect(commands.indexOf('hiliteColor')).toBeLessThan(
      commands.indexOf('backColor'),
    );
  });

  it('does not call backColor when hiliteColor returns true', () => {
    // hiliteColor is applied successfully → returns true, no fallback.
    execCommandSpy.mockImplementation((command: string) =>
      command === 'hiliteColor' ? true : true,
    );

    render(<RichTextEditor value="" onChange={() => {}} />);

    clickHighlightSwatch(FIRST_HIGHLIGHT.label);

    const calls = commandCalls(execCommandSpy);

    // hiliteColor was attempted with the swatch color.
    expect(calls).toContainEqual({
      command: 'hiliteColor',
      value: FIRST_HIGHLIGHT.color,
    });

    // backColor must NOT have been called at all.
    expect(
      calls.some((c) => c.command === 'backColor'),
    ).toBe(false);
  });
});
