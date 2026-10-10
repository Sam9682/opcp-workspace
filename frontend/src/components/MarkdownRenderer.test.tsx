import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import fc from 'fast-check';
import * as MarkdownRendererModule from './MarkdownRenderer';
import { MarkdownRenderer } from './MarkdownRenderer';

// Task 4.1 — MarkdownRenderer test suite scaffold (example + edge tests).
//
// This file establishes the shared helpers, the fast-check configuration, and
// the example/edge tests for the Oracle chat MarkdownRenderer. The 15 property
// tests (tasks 4.2–4.16) are appended to this same file and reuse the helpers
// and `FC_CONFIG` defined here.
//
// Validates: Requirements 5.1, 4.2, 4.3, 4.4

// ---------------------------------------------------------------------------
// Shared test configuration
// ---------------------------------------------------------------------------

// Minimum property-test iterations mandated by the design (>= 100). Every
// property test in tasks 4.2–4.16 passes `FC_CONFIG` to `fc.assert` so the
// iteration floor is enforced consistently.
export const NUM_RUNS = 100;

export const FC_CONFIG: fc.Parameters<unknown> = { numRuns: NUM_RUNS };

// ---------------------------------------------------------------------------
// Shared render helpers
// ---------------------------------------------------------------------------

/**
 * Render the MarkdownRenderer with the given content and return the Testing
 * Library result together with the outer prose container element.
 *
 * The container is located by its class contract (`prose prose-sm max-w-none`)
 * so helpers do not depend on incidental DOM structure. Property and example
 * tests build on this single entry point.
 */
export function renderMarkdown(content: string) {
  const result = render(<MarkdownRenderer content={content} />);
  const prose = result.container.querySelector('.prose') as HTMLElement | null;
  return { ...result, prose };
}

/** The exact, ordered class contract for the prose container (Requirement 4.2). */
export const PROSE_CONTAINER_CLASS = 'prose prose-sm max-w-none';

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// Example / edge tests
// ---------------------------------------------------------------------------

describe('MarkdownRenderer — named-export contract (Requirement 4.4)', () => {
  it('is importable as the named export `MarkdownRenderer`', () => {
    expect(MarkdownRendererModule.MarkdownRenderer).toBeDefined();
    expect(typeof MarkdownRendererModule.MarkdownRenderer).toBe('function');
  });

  it('accepts a single `content` string prop and renders (Requirement 4.1)', () => {
    const { prose } = renderMarkdown('hello world');
    expect(prose).not.toBeNull();
    expect(prose?.textContent).toContain('hello world');
  });
});

describe('MarkdownRenderer — prose container (Requirement 4.2)', () => {
  it('renders an outer container carrying exactly `prose prose-sm max-w-none`', () => {
    const { container } = renderMarkdown('some content');
    const prose = container.querySelector('.prose') as HTMLElement;
    expect(prose).not.toBeNull();
    expect(prose.className).toBe(PROSE_CONTAINER_CLASS);
  });
});

describe('MarkdownRenderer — empty content edge case (Requirement 4.3)', () => {
  it('renders the prose container with an empty body for empty content', () => {
    const { prose } = renderMarkdown('');
    expect(prose).not.toBeNull();
    // Empty string yields the container with no rendered markdown body.
    expect(prose?.textContent).toBe('');
    expect(prose?.querySelector('p')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Property tests (tasks 4.2–4.16) are appended below this line and reuse
// `renderMarkdown`, `FC_CONFIG`, and `NUM_RUNS` from this scaffold.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Shared generators for property tests (tasks 4.2–4.6)
// ---------------------------------------------------------------------------
//
// Per the design's Testing Strategy, text used inside a specific markdown
// construct must not itself introduce markdown/HTML syntax that would alter the
// parse. We therefore constrain generated text to printable characters that
// exclude: newlines, backticks, `<`, `*`, `#`, and leading/trailing whitespace.
// The result is a single line of "inert" text whose rendered `textContent`
// equals the input.

// Printable characters that carry no markdown/HTML meaning for the constructs
// under test: letters, digits, spaces, and a handful of inert punctuation. We
// deliberately exclude newline/backtick/`<`/`*`/`#` (construct delimiters) as
// well as `-`, `_`, `[`, `]`, `(`, `)`, `!`, `.`, `|`, `>`, `&`, `~` and digits
// followed by `.` which could otherwise start their own list/heading/emphasis.
const SAFE_CHAR_SET =
  'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ';

const SAFE_CHARS = fc.constantFrom(...SAFE_CHAR_SET.split(''));

/** A non-empty single-line string with no markdown/HTML-significant chars and no leading/trailing whitespace. */
const safeText = fc
  .string({ unit: SAFE_CHARS, minLength: 1, maxLength: 40 })
  .map((s) => s.trim())
  .filter((s) => s.length > 0);

// ---------------------------------------------------------------------------
// Task 4.2 — Property 1: Blank-line-separated blocks become separate paragraphs
// ---------------------------------------------------------------------------

describe('Feature: oracle-chat-formatting, Property 1: Blank-line-separated blocks become separate paragraphs', () => {
  it('renders exactly two <p> elements, each containing its block text (Requirement 1.1)', () => {
    fc.assert(
      fc.property(safeText, safeText, (a, b) => {
        const { prose } = renderMarkdown(`${a}\n\n${b}`);
        const paragraphs = prose?.querySelectorAll('p') ?? [];
        expect(paragraphs.length).toBe(2);
        expect(paragraphs[0].textContent).toBe(a);
        expect(paragraphs[1].textContent).toBe(b);
      }),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.3 — Property 2: Single newline produces a line break within a paragraph
// ---------------------------------------------------------------------------

describe('Feature: oracle-chat-formatting, Property 2: Single newline produces a line break within a paragraph', () => {
  it('renders one <p> containing a <br> between the two texts (Requirement 1.2)', () => {
    fc.assert(
      fc.property(safeText, safeText, (a, b) => {
        const { prose } = renderMarkdown(`${a}\n${b}`);
        const paragraphs = prose?.querySelectorAll('p') ?? [];
        expect(paragraphs.length).toBe(1);
        const p = paragraphs[0];
        expect(p.querySelector('br')).not.toBeNull();
        expect(p.textContent).toContain(a);
        expect(p.textContent).toContain(b);
      }),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.4 — Property 3: Unordered lists yield one list item per entry
// ---------------------------------------------------------------------------

describe('Feature: oracle-chat-formatting, Property 3: Unordered lists yield one list item per entry', () => {
  it('renders exactly one <ul> with N <li>, no literal bullet, one per item (Requirement 1.3)', () => {
    fc.assert(
      fc.property(
        fc.array(safeText, { minLength: 1, maxLength: 8 }),
        fc.constantFrom('-', '*'),
        (items, marker) => {
          const source = items.map((item) => `${marker} ${item}`).join('\n');
          const { prose } = renderMarkdown(source);
          const uls = prose?.querySelectorAll('ul') ?? [];
          expect(uls.length).toBe(1);
          const lis = uls[0].querySelectorAll('li');
          expect(lis.length).toBe(items.length);
          items.forEach((item, i) => {
            expect(lis[i].textContent).toBe(item);
            expect(lis[i].textContent).not.toContain('•');
          });
        },
      ),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.5 — Property 4: Ordered lists yield one list item per entry
// ---------------------------------------------------------------------------

describe('Feature: oracle-chat-formatting, Property 4: Ordered lists yield one list item per entry', () => {
  it('renders exactly one <ol> with N <li>, one per item (Requirement 1.4)', () => {
    fc.assert(
      fc.property(fc.array(safeText, { minLength: 1, maxLength: 8 }), (items) => {
        const source = items.map((item, i) => `${i + 1}. ${item}`).join('\n');
        const { prose } = renderMarkdown(source);
        const ols = prose?.querySelectorAll('ol') ?? [];
        expect(ols.length).toBe(1);
        const lis = ols[0].querySelectorAll('li');
        expect(lis.length).toBe(items.length);
        items.forEach((item, i) => {
          expect(lis[i].textContent).toBe(item);
        });
      }),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.6 — Property 5: Heading markers map to the corresponding heading level
// ---------------------------------------------------------------------------

describe('Feature: oracle-chat-formatting, Property 5: Heading markers map to the corresponding heading level', () => {
  it('renders an <hL> element containing the text for L in {1,2,3} (Requirement 1.5)', () => {
    fc.assert(
      fc.property(fc.constantFrom(1, 2, 3), safeText, (level, text) => {
        const source = `${'#'.repeat(level)} ${text}`;
        const { prose } = renderMarkdown(source);
        const heading = prose?.querySelector(`h${level}`);
        expect(heading).not.toBeNull();
        expect(heading?.textContent).toBe(text);
      }),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.7 — Property 6: Double-asterisk text becomes strong
// ---------------------------------------------------------------------------

describe('Feature: oracle-chat-formatting, Property 6: Double-asterisk text becomes strong', () => {
  it('renders a <strong> element containing the wrapped text (Requirement 1.6)', () => {
    fc.assert(
      fc.property(safeText, (text) => {
        const { prose } = renderMarkdown(`**${text}**`);
        const strong = prose?.querySelector('strong');
        expect(strong).not.toBeNull();
        expect(strong?.textContent).toBe(text);
      }),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.8 — Property 7: Single-backtick text becomes inline code
// ---------------------------------------------------------------------------

describe('Feature: oracle-chat-formatting, Property 7: Single-backtick text becomes inline code', () => {
  it('renders a <code> not nested inside <pre> containing the text (Requirement 1.7)', () => {
    fc.assert(
      fc.property(safeText, (text) => {
        const { prose } = renderMarkdown(`\`${text}\``);
        const codes = Array.from(prose?.querySelectorAll('code') ?? []);
        // Inline code: a <code> element that is NOT inside a <pre>.
        const inline = codes.find((c) => c.closest('pre') === null);
        expect(inline).toBeDefined();
        expect(inline?.textContent).toBe(text);
      }),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.9 — Property 8: Fenced blocks become preformatted code
// ---------------------------------------------------------------------------

describe('Feature: oracle-chat-formatting, Property 8: Fenced blocks become preformatted code', () => {
  it('renders a <pre> containing a <code> whose text is the block body (Requirement 1.8)', () => {
    fc.assert(
      fc.property(safeText, (body) => {
        const { prose } = renderMarkdown(`\`\`\`\n${body}\n\`\`\``);
        const pre = prose?.querySelector('pre');
        expect(pre).not.toBeNull();
        const code = pre?.querySelector('code');
        expect(code).not.toBeNull();
        // Fenced code preserves text literally; the code element's textContent
        // may include a trailing newline, so compare after trimming that off.
        expect(code?.textContent?.replace(/\n$/, '')).toBe(body);
      }),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.10 — Property 9: Streaming tolerates incomplete input without error
// ---------------------------------------------------------------------------

describe('Feature: oracle-chat-formatting, Property 9: Streaming tolerates incomplete input without error', () => {
  it('renders every prefix of arbitrary (including hostile) markdown without throwing (Requirement 2.2)', () => {
    // Fragments include partial/hostile markdown constructs that commonly appear
    // mid-stream: unclosed emphasis, half-open fences, dangling link syntax, etc.
    const fragment = fc.constantFrom(
      '**',
      '`',
      '```',
      '[',
      '](',
      '# ',
      '- ',
      '1. ',
      'text ',
      '\n',
      '\n\n',
      '<div>',
      '*italic',
      '~~',
      '> quote',
    );
    const hostileMarkdown = fc
      .array(fragment, { minLength: 0, maxLength: 12 })
      .map((parts) => parts.join(''));

    fc.assert(
      fc.property(hostileMarkdown, fc.nat(), (full, cut) => {
        const prefixLen = full.length === 0 ? 0 : cut % (full.length + 1);
        const prefix = full.slice(0, prefixLen);
        expect(() => {
          const { unmount } = render(<MarkdownRenderer content={prefix} />);
          unmount();
        }).not.toThrow();
      }),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.11 — Property 10: Incremental rendering equals single-pass rendering
// ---------------------------------------------------------------------------

describe('Feature: oracle-chat-formatting, Property 10: Incremental rendering equals single-pass rendering', () => {
  it('growing prefixes then the full string equal a single fresh mount (Requirements 2.1, 2.3)', () => {
    // Use inert but structurally meaningful markdown so the comparison exercises
    // real block/inline structure while remaining deterministic.
    const line = fc.constantFrom(
      'hello world',
      '# Heading',
      '- item one',
      '1. first',
      '**bold** text',
      '`code` span',
      'plain paragraph',
    );
    const document = fc
      .array(line, { minLength: 1, maxLength: 6 })
      .map((lines) => lines.join('\n\n'));

    fc.assert(
      fc.property(document, (full) => {
        // Incremental render: mount once, then re-render through growing prefixes
        // up to and including the full string.
        const { container: incContainer, rerender } = render(
          <MarkdownRenderer content={full.slice(0, 1)} />,
        );
        const steps = [
          Math.floor(full.length / 3),
          Math.floor((full.length * 2) / 3),
          full.length,
        ];
        for (const end of steps) {
          rerender(<MarkdownRenderer content={full.slice(0, end)} />);
        }
        const incrementalHtml = (
          incContainer.querySelector('.prose') as HTMLElement
        ).innerHTML;

        // Single-pass render of the full string in a fresh mount.
        const { container: onceContainer } = render(
          <MarkdownRenderer content={full} />,
        );
        const singlePassHtml = (
          onceContainer.querySelector('.prose') as HTMLElement
        ).innerHTML;

        expect(incrementalHtml).toBe(singlePassHtml);
      }),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.12 — Property 11: Safe HTML is preserved
// ---------------------------------------------------------------------------
//
// For any Safe_HTML element drawn from the permitted set (paragraph, list,
// heading, emphasis, code, link), embedding it in the content renders the
// corresponding element in the output. We draw from a fixed set of safe
// markdown/HTML samples and assert the expected element appears carrying the
// sample text.

describe('Feature: oracle-chat-formatting, Property 11: Safe HTML is preserved', () => {
  it('renders the corresponding element for each permitted Safe_HTML sample (Requirement 3.1)', () => {
    // Each sample builds inert content for a permitted element and states the
    // selector that must appear plus the text it must carry. `build` receives a
    // generated inert text token so the assertion is content-agnostic.
    const samples: ReadonlyArray<{
      readonly build: (text: string) => string;
      readonly selector: string;
    }> = [
      // Paragraph (markdown → <p>)
      { build: (t) => t, selector: 'p' },
      // Unordered list (markdown → <ul>/<li>)
      { build: (t) => `- ${t}`, selector: 'ul li' },
      // Heading level 2 (markdown → <h2>)
      { build: (t) => `## ${t}`, selector: 'h2' },
      // Emphasis / strong (markdown → <strong>)
      { build: (t) => `**${t}**`, selector: 'strong' },
      // Inline code (markdown → <code>)
      { build: (t) => `\`${t}\``, selector: 'code' },
      // Link (markdown → <a>)
      { build: (t) => `[${t}](https://example.com)`, selector: 'a' },
    ];

    fc.assert(
      fc.property(fc.constantFrom(...samples), safeText, (sample, text) => {
        const { prose } = renderMarkdown(sample.build(text));
        const element = prose?.querySelector(sample.selector);
        expect(element).not.toBeNull();
        expect(element?.textContent).toBe(text);
      }),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.13 — Property 12: Script elements are excluded
// ---------------------------------------------------------------------------
//
// For any content containing a <script> element with an arbitrary payload at
// any position, the rendered output contains no <script> element and none of
// the script's executable contents. We embed a unique payload token so its
// absence is unambiguous, and place the script before/after/between inert text.

describe('Feature: oracle-chat-formatting, Property 12: Script elements are excluded', () => {
  it('renders no <script> element and drops its executable contents (Requirement 3.2)', () => {
    // A unique, syntactically-inert JS payload token whose presence in the
    // rendered output would prove the script survived sanitization.
    const uniquePayload = fc
      .string({ unit: SAFE_CHARS, minLength: 6, maxLength: 20 })
      .map((s) => `ZZ${s.replace(/\s/g, '')}ZZ`)
      .filter((s) => s.length > 4);

    fc.assert(
      fc.property(
        safeText,
        safeText,
        uniquePayload,
        fc.constantFrom('before', 'after', 'between'),
        (a, b, payload, position) => {
          const script = `<script>window.__x="${payload}";</script>`;
          let content: string;
          if (position === 'before') content = `${script}\n\n${a}\n\n${b}`;
          else if (position === 'after') content = `${a}\n\n${b}\n\n${script}`;
          else content = `${a}\n\n${script}\n\n${b}`;

          const { prose, container } = renderMarkdown(content);
          // No <script> element anywhere in the rendered output.
          expect(container.querySelector('script')).toBeNull();
          expect(prose?.querySelector('script')).toBeNull();
          // The script's executable payload text must be absent entirely.
          expect(container.innerHTML).not.toContain(payload);
          expect(container.textContent ?? '').not.toContain(payload);
        },
      ),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.14 — Property 13: Event-handler attributes are excluded
// ---------------------------------------------------------------------------
//
// For any content containing an element with an arbitrary on* event-handler
// attribute (e.g. onclick, onerror, onmouseover), no rendered element retains
// that event-handler attribute.

describe('Feature: oracle-chat-formatting, Property 13: Event-handler attributes are excluded', () => {
  it('renders no element retaining an on* event-handler attribute (Requirement 3.3)', () => {
    const handlerName = fc.constantFrom(
      'onclick',
      'onerror',
      'onmouseover',
      'onload',
      'onfocus',
      'onmouseenter',
    );
    // Elements that carry the handler; each is a plausible Safe_HTML host so the
    // element itself may survive while the handler must not.
    const hostTag = fc.constantFrom('a', 'span', 'p', 'div', 'img');

    fc.assert(
      fc.property(hostTag, handlerName, safeText, (tag, handler, text) => {
        // Build an element carrying an arbitrary event-handler attribute.
        const content =
          tag === 'img'
            ? `<img src="https://example.com/x.png" ${handler}="alert(1)" alt="${text}">`
            : `<${tag} ${handler}="alert(1)">${text}</${tag}>`;

        const { container } = renderMarkdown(content);
        // No element in the rendered output retains the event-handler attribute.
        const withHandler = container.querySelector(`[${handler}]`);
        expect(withHandler).toBeNull();
        // Belt-and-braces: confirm no element enumerates the handler attribute.
        const all = Array.from(container.querySelectorAll('*'));
        const anyRetained = all.some((el) => el.hasAttribute(handler));
        expect(anyRetained).toBe(false);
      }),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.15 — Property 14: `javascript:` URLs are excluded
// ---------------------------------------------------------------------------
//
// For any content containing a link or image whose URL uses the `javascript:`
// scheme, no rendered anchor (href) or image (src) retains a `javascript:` URL.

describe('Feature: oracle-chat-formatting, Property 14: `javascript:` URLs are excluded', () => {
  it('renders no anchor/image that retains a javascript: URL (Requirement 3.4)', () => {
    // An arbitrary javascript: URL payload.
    const jsUrl = fc
      .string({ unit: SAFE_CHARS, minLength: 1, maxLength: 20 })
      .map((s) => `javascript:alert('${s.replace(/\s/g, '')}')`);
    const kind = fc.constantFrom('link-md', 'image-md', 'anchor-html', 'img-html');

    fc.assert(
      fc.property(kind, jsUrl, safeText, (variant, url, text) => {
        let content: string;
        if (variant === 'link-md') content = `[${text}](${url})`;
        else if (variant === 'image-md') content = `![${text}](${url})`;
        else if (variant === 'anchor-html') content = `<a href="${url}">${text}</a>`;
        else content = `<img src="${url}" alt="${text}">`;

        const { container } = renderMarkdown(content);

        // No anchor retains a javascript: href.
        container.querySelectorAll('a').forEach((a) => {
          const href = a.getAttribute('href') ?? '';
          expect(href.trim().toLowerCase().startsWith('javascript:')).toBe(false);
        });
        // No image retains a javascript: src.
        container.querySelectorAll('img').forEach((img) => {
          const src = img.getAttribute('src') ?? '';
          expect(src.trim().toLowerCase().startsWith('javascript:')).toBe(false);
        });
        // No attribute value anywhere begins with the javascript: scheme.
        Array.from(container.querySelectorAll('*')).forEach((el) => {
          Array.from(el.attributes).forEach((attr) => {
            expect(
              attr.value.trim().toLowerCase().startsWith('javascript:'),
            ).toBe(false);
          });
        });
      }),
      FC_CONFIG,
    );
  });
});

// ---------------------------------------------------------------------------
// Task 4.16 — Property 15: The prose container is always present
// ---------------------------------------------------------------------------
//
// For any content string (including hostile/partial input), the outer container
// element carries exactly the classes `prose prose-sm max-w-none`.

describe('Feature: oracle-chat-formatting, Property 15: The prose container is always present', () => {
  it('renders an outer container carrying exactly the prose classes for any content (Requirement 4.2)', () => {
    // A broad arbitrary string including hostile/partial markdown and HTML so
    // the container contract is exercised across the full input space.
    const anyContent = fc.oneof(
      fc.string({ maxLength: 200 }),
      fc.constantFrom(
        '',
        ' ',
        '\n\n\n',
        '**unterminated',
        '```\nno close',
        '<script>alert(1)</script>',
        '<div onclick="x()">hi</div>',
        '[link](javascript:alert(1))',
        '# heading\n- item\n\n> quote',
        '<img src="javascript:alert(1)">',
        '~~~~ | | |',
      ),
    );

    fc.assert(
      fc.property(anyContent, (content) => {
        const { container } = renderMarkdown(content);
        const prose = container.querySelector('.prose') as HTMLElement | null;
        expect(prose).not.toBeNull();
        expect(prose?.className).toBe(PROSE_CONTAINER_CLASS);
      }),
      FC_CONFIG,
    );
  });
});
