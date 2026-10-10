import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, cleanup, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { TopicDetailPage } from './TopicDetailPage';
import { forumService, type TopicDetail } from '../services/forumService';
import { authService } from '../services/authService';
import { LanguageProvider } from '../hooks/useLanguage';

/**
 * Bugfix: forum-text-formatting-fix — Task 1
 * Property 1 (Bug Condition): Formatting Renders Flattened At Display Time
 *
 * This is a BUG CONDITION EXPLORATION test. It is EXPECTED TO FAIL on the
 * unfixed code — the failure confirms the CSS-scoping root cause. The same
 * assertions encode the Expected Behavior (Correctness Property 1), so this
 * test will PASS once the fix (later tasks) is applied.
 *
 * Root cause under test: RichTextEditor ships a <style> block whose formatting
 * rules are scoped to `[contenteditable] h1/h2/h3`, `[contenteditable] ul/ol`,
 * `[contenteditable] img`, `[contenteditable] hr`. At display time the same
 * stored HTML is placed inside a NON-contenteditable `<div class="prose
 * prose-sm">` on TopicDetailPage, so those scoped rules never match and the
 * formatting renders flattened.
 *
 * Deterministic (scoped-PBT) approach: this is a deterministic rendering bug,
 * so we scope the property to one concrete failing fragment per formatting
 * type rather than randomizing, to guarantee reproducibility.
 *
 * Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
 */

// forumService is the only persistence path; mock it so the topic load resolves
// to deterministic content carrying editor-produced formatting.
vi.mock('../services/forumService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/forumService')>();
  return {
    ...actual,
    forumService: {
      ...actual.forumService,
      getTopic: vi.fn(),
      getTopicPublic: vi.fn(),
      createPost: vi.fn(),
      updatePost: vi.fn(),
      deletePost: vi.fn(),
    },
  };
});

// authService.isAuthenticated() selects the getTopic vs getTopicPublic path.
vi.mock('../services/authService', () => ({
  authService: {
    isAuthenticated: vi.fn(() => false),
  },
}));

const mockedForum = vi.mocked(forumService);
const mockedAuth = vi.mocked(authService);

// One concrete formatting fragment per formatting type from the Bug Condition
// (`containsFormatting`). Each is a deterministic case in the scoped property.
const FORMATTING_FRAGMENTS: ReadonlyArray<{ name: string; content: string }> = [
  { name: 'heading (h1)', content: '<h1>Titre</h1>' },
  { name: 'unordered list', content: '<ul><li>a</li><li>b</li></ul>' },
  { name: 'image', content: '<img src="https://example.com/x.png">' },
  { name: 'horizontal rule', content: '<hr>' },
];

const buildTopic = (content: string): TopicDetail => ({
  id: 'topic-1',
  title: 'Sujet de test',
  author_id: 'author-1',
  author_name: 'Alice',
  is_pinned: false,
  is_locked: false,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  post_count: 1,
  posts: [
    {
      id: 'post-1',
      topic_id: 'topic-1',
      author_id: 'author-1',
      author_name: 'Alice',
      content,
      is_hidden: false,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
  ],
});

// Locate the container that renders the stored post HTML via
// dangerouslySetInnerHTML (the `.prose` display div holding the post content).
const findDisplayContainer = (root: HTMLElement, _content: string): HTMLElement | null => {
  const proseNodes = Array.from(root.querySelectorAll<HTMLElement>('.prose'));
  // The display container's innerHTML round-trips the stored content; pick the
  // prose node whose markup contains the injected fragment's leading tag.
  return (
    proseNodes.find((el) => el.querySelector('h1, ul, img, hr') !== null) ??
    proseNodes.find((el) => el.innerHTML.length > 0) ??
    null
  );
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  cleanup();
  mockedAuth.isAuthenticated.mockReturnValue(false);
});

afterEach(() => {
  cleanup();
});

describe('Property 1 (Bug Condition): forum post formatting renders flattened at display time', () => {
  it.each(FORMATTING_FRAGMENTS)(
    'display container carries the shared `rich-content` class for $name',
    async ({ content }) => {
      mockedForum.getTopicPublic.mockResolvedValue(buildTopic(content));

      const { container } = render(
        <LanguageProvider>
          <MemoryRouter initialEntries={['/forum/topics/topic-1']}>
            <Routes>
              <Route path="/forum/topics/:topicId" element={<TopicDetailPage />} />
            </Routes>
          </MemoryRouter>
        </LanguageProvider>,
      );

      // Wait for the topic to load and the post HTML to render.
      await waitFor(() => {
        expect(mockedForum.getTopicPublic).toHaveBeenCalledWith('topic-1');
      });

      const display = await waitFor(() => {
        const el = findDisplayContainer(container, content);
        expect(el).not.toBeNull();
        return el as HTMLElement;
      });

      // Expected Behavior (Correctness Property 1): the display container must
      // carry the shared `rich-content` class so the shared formatting rules
      // apply to it. On UNFIXED code the display div only has
      // `text-sm text-gray-700 prose prose-sm max-w-none` — no `rich-content` —
      // so this assertion FAILS, confirming the bug.
      expect(display.classList.contains('rich-content')).toBe(true);
    },
  );
});

describe('Property 1 (Bug Condition): root-cause — editor formatting rules are shared, not `[contenteditable]`-only', () => {
  // Read RichTextEditor source to inspect the shipped <style> selectors. On
  // unfixed code every formatting rule is scoped to `[contenteditable] ...`,
  // which cannot match the non-contenteditable display container. The fix
  // retargets them to also match `.rich-content ...`.
  const editorSource = readFileSync(
    resolve(dirname(fileURLToPath(import.meta.url)), '../components/RichTextEditor.tsx'),
    'utf-8',
  );

  it.each(['h1', 'h2', 'h3', 'ul', 'ol', 'img', 'hr'])(
    'formatting rule for `%s` is scoped to the shared `.rich-content` class',
    (tag) => {
      // Expected Behavior: each formatting selector targets the shared
      // `.rich-content` class (so it applies to the display container too).
      // On UNFIXED code the rules are `[contenteditable] <tag>` only, so no
      // `.rich-content <tag>` selector exists and this assertion FAILS.
      const sharedSelector = new RegExp(`\\.rich-content\\s+${tag}\\b`);
      expect(editorSource).toMatch(sharedSelector);
    },
  );

  it('formatting rules are NOT exclusively scoped to `[contenteditable]`', () => {
    // Count contenteditable-scoped formatting rules (excluding the editor-only
    // placeholder rule). On unfixed code, all four block/semantic groups are
    // scoped this way and none are shared — confirming the root cause.
    const contentEditableFormattingRules = [
      /\[contenteditable\]\s+h1\b/,
      /\[contenteditable\]\s+ul\b/,
      /\[contenteditable\]\s+img\b/,
      /\[contenteditable\]\s+hr\b/,
    ].filter((re) => re.test(editorSource)).length;

    const sharedFormattingRules = [
      /\.rich-content\s+h1\b/,
      /\.rich-content\s+ul\b/,
      /\.rich-content\s+img\b/,
      /\.rich-content\s+hr\b/,
    ].filter((re) => re.test(editorSource)).length;

    // Expected Behavior: the block/semantic formatting rules are shared via
    // `.rich-content`. On UNFIXED code sharedFormattingRules === 0, so this
    // FAILS, proving the rules are scoped to the editor only.
    expect(sharedFormattingRules).toBeGreaterThanOrEqual(contentEditableFormattingRules);
  });
});
