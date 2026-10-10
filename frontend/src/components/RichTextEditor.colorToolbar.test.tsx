import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import {
  RichTextEditor,
  TEXT_COLOR_PALETTE,
  HIGHLIGHT_COLOR_PALETTE,
} from './RichTextEditor';

// Task 3.2 — Example tests for the color toolbar groups' layout and
// single-click behavior.
//
// These example tests render the RichTextEditor and assert:
//   * Each color group renders exactly one swatch per palette entry and carries
//     the shared grouping/divider classes (`flex gap-1 border-r border-gray-300 pr-2`).
//   * A single click on a text swatch invokes `document.execCommand('foreColor', ...)`
//     with that swatch's color and no confirmation step.
//   * A single click on a highlight swatch drives the highlight command path
//     (`document.execCommand('hiliteColor', ...)`) with that swatch's color.
//
// Validates: Requirements 1.1, 1.3, 1.4, 2.1, 2.3, 3.1, 3.2, 3.3

const GROUP_CLASSES = ['flex', 'gap-1', 'border-r', 'border-gray-300', 'pr-2'];

// jsdom does not implement document.execCommand, so install a stub we can spy
// on. The highlight path depends on the return value (`hiliteColor` returning
// a truthy value skips the `backColor` fallback), so default to returning true.
let execCommandSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  // Ensure the property exists before spying — some jsdom builds omit it.
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

describe('RichTextEditor color toolbar — Text_Color_Group layout', () => {
  it('renders exactly one swatch per text palette entry', () => {
    render(<RichTextEditor value="" onChange={() => {}} />);

    for (const entry of TEXT_COLOR_PALETTE) {
      const swatches = screen.getAllByTitle(entry.label);
      expect(swatches).toHaveLength(1);
    }
  });

  it('groups the text swatches under the shared grouping/divider classes', () => {
    render(<RichTextEditor value="" onChange={() => {}} />);

    const firstText = screen.getByTitle(TEXT_COLOR_PALETTE[0].label);
    const group = groupOf(firstText);

    for (const cls of GROUP_CLASSES) {
      expect(group).toHaveClass(cls);
    }

    // Every text swatch lives in this same group container.
    for (const entry of TEXT_COLOR_PALETTE) {
      expect(groupOf(screen.getByTitle(entry.label))).toBe(group);
    }
    expect(group.querySelectorAll('button')).toHaveLength(
      TEXT_COLOR_PALETTE.length,
    );
  });
});

describe('RichTextEditor color toolbar — Highlight_Color_Group layout', () => {
  it('renders exactly one swatch per highlight palette entry', () => {
    render(<RichTextEditor value="" onChange={() => {}} />);

    for (const entry of HIGHLIGHT_COLOR_PALETTE) {
      const swatches = screen.getAllByTitle(entry.label);
      expect(swatches).toHaveLength(1);
    }
  });

  it('groups the highlight swatches under the shared grouping/divider classes', () => {
    render(<RichTextEditor value="" onChange={() => {}} />);

    const firstHighlight = screen.getByTitle(HIGHLIGHT_COLOR_PALETTE[0].label);
    const group = groupOf(firstHighlight);

    for (const cls of GROUP_CLASSES) {
      expect(group).toHaveClass(cls);
    }

    for (const entry of HIGHLIGHT_COLOR_PALETTE) {
      expect(groupOf(screen.getByTitle(entry.label))).toBe(group);
    }
    expect(group.querySelectorAll('button')).toHaveLength(
      HIGHLIGHT_COLOR_PALETTE.length,
    );
  });

  it('renders the text and highlight swatches in separate groups', () => {
    render(<RichTextEditor value="" onChange={() => {}} />);

    const textGroup = groupOf(screen.getByTitle(TEXT_COLOR_PALETTE[0].label));
    const highlightGroup = groupOf(
      screen.getByTitle(HIGHLIGHT_COLOR_PALETTE[0].label),
    );
    expect(textGroup).not.toBe(highlightGroup);
  });
});

describe('RichTextEditor color toolbar — single-click behavior', () => {
  it('applies the swatch color via foreColor on a single text-swatch click', () => {
    render(<RichTextEditor value="" onChange={() => {}} />);

    const swatch = screen.getByTitle(TEXT_COLOR_PALETTE[1].label);
    fireEvent.click(swatch);

    // A single click applies the color with no confirmation step.
    expect(execCommandSpy).toHaveBeenCalledWith(
      'foreColor',
      false,
      TEXT_COLOR_PALETTE[1].color,
    );
    // No prompt/confirm-style second command for the text path.
    const foreColorCalls = execCommandSpy.mock.calls.filter(
      ([command]) => command === 'foreColor',
    );
    expect(foreColorCalls).toHaveLength(1);
  });

  it('applies every text swatch color via foreColor with that swatch color', () => {
    render(<RichTextEditor value="" onChange={() => {}} />);

    for (const entry of TEXT_COLOR_PALETTE) {
      execCommandSpy.mockClear();
      fireEvent.click(screen.getByTitle(entry.label));
      expect(execCommandSpy).toHaveBeenCalledWith(
        'foreColor',
        false,
        entry.color,
      );
    }
  });

  it('drives the highlight command path via hiliteColor on a single highlight-swatch click', () => {
    render(<RichTextEditor value="" onChange={() => {}} />);

    const swatch = screen.getByTitle(HIGHLIGHT_COLOR_PALETTE[0].label);
    fireEvent.click(swatch);

    expect(execCommandSpy).toHaveBeenCalledWith(
      'hiliteColor',
      false,
      HIGHLIGHT_COLOR_PALETTE[0].color,
    );
  });

  it('applies every highlight swatch color via the highlight command path', () => {
    render(<RichTextEditor value="" onChange={() => {}} />);

    for (const entry of HIGHLIGHT_COLOR_PALETTE) {
      execCommandSpy.mockClear();
      fireEvent.click(screen.getByTitle(entry.label));
      expect(execCommandSpy).toHaveBeenCalledWith(
        'hiliteColor',
        false,
        entry.color,
      );
    }
  });
});
