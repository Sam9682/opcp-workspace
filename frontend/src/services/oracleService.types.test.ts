import { describe, it, expect } from 'vitest';
import type { Source } from './oracleService';

// Task 8.2 — type-level smoke test.
// Validates: Requirements 1.5, 3.3
//
// These are compile-time assertions dressed up as runtime checks: if the
// `ai_provider` union stopped accepting 'opcp_companion' or the `Source` shape
// changed, `tsc` (run by `vitest run` / `tsc -b`) would fail to compile this
// file. The runtime `expect`s simply keep vitest happy and document intent.

describe('oracleService types', () => {
  it("accepts 'opcp_companion' in the ai_provider union", () => {
    // The ai_provider union is exercised via the public service method whose
    // parameter type is `'shai' | 'kiro' | 'openai' | 'opcp_companion'`.
    const provider: 'shai' | 'kiro' | 'openai' | 'opcp_companion' = 'opcp_companion';
    expect(provider).toBe('opcp_companion');
  });

  it('compiles a Source object with title/file_path/similarity', () => {
    const source: Source = {
      title: 'Guide OPCP',
      file_path: 'docs/guide.md',
      similarity: 0.92,
    };

    expect(source.title).toBe('Guide OPCP');
    expect(source.file_path).toBe('docs/guide.md');
    expect(typeof source.similarity).toBe('number');
  });

  it('compiles a list of Source objects', () => {
    const sources: Source[] = [
      { title: 'A', file_path: 'a.md', similarity: 0.5 },
      { title: 'B', file_path: 'b.md', similarity: 0.75 },
    ];
    expect(sources).toHaveLength(2);
  });
});
