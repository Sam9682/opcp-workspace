import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { SourcesList } from './SourcesList';
import type { Source } from '../services/oracleService';

// Task 9.4 — SourcesList component tests.
// Validates: Requirements 3.4, 3.5

afterEach(() => {
  cleanup();
});

const SAMPLE_SOURCES: Source[] = [
  { title: 'Guide OPCP', file_path: 'docs/guide.md', similarity: 0.92 },
  { title: 'FAQ', file_path: 'docs/faq.md', similarity: 0.8123 },
];

describe('SourcesList', () => {
  // Req 3.4: with sources, a collapsible "Sources" section lists title,
  // file_path and similarity.
  describe('with sources', () => {
    it('renders a collapsible "Sources" section', () => {
      const { container } = render(<SourcesList sources={SAMPLE_SOURCES} />);
      const details = container.querySelector('details');
      expect(details).toBeTruthy();
      // The summary labels the section "Sources" with a count.
      expect(screen.getByText(/Sources \(2\)/)).toBeTruthy();
    });

    it('lists each source title', () => {
      render(<SourcesList sources={SAMPLE_SOURCES} />);
      expect(screen.getByText('Guide OPCP')).toBeTruthy();
      expect(screen.getByText('FAQ')).toBeTruthy();
    });

    it('lists each source file_path', () => {
      render(<SourcesList sources={SAMPLE_SOURCES} />);
      expect(screen.getByText('docs/guide.md')).toBeTruthy();
      expect(screen.getByText('docs/faq.md')).toBeTruthy();
    });

    it('shows the similarity for each source (as a percentage)', () => {
      render(<SourcesList sources={SAMPLE_SOURCES} />);
      // 0.92 -> "92.0%", 0.8123 -> "81.2%"
      expect(screen.getByText('92.0%')).toBeTruthy();
      expect(screen.getByText('81.2%')).toBeTruthy();
    });
  });

  // Req 3.5: without sources, no "Sources" section is rendered.
  describe('without sources', () => {
    it('renders nothing when sources is an empty array', () => {
      const { container } = render(<SourcesList sources={[]} />);
      expect(container.querySelector('details')).toBeNull();
      expect(screen.queryByText(/Sources/)).toBeNull();
    });

    it('renders nothing when sources is undefined', () => {
      const { container } = render(<SourcesList />);
      expect(container.querySelector('details')).toBeNull();
      expect(screen.queryByText(/Sources/)).toBeNull();
    });
  });
});
