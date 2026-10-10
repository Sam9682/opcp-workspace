import { describe, it, expect, vi, beforeEach } from 'vitest';

// Feature: forum-view-button-url-fix
// Task 2 — Preservation example test for the AI provider round-trip.
//
// Requirement 3.4: administrators still load, toggle, and persist AI provider
// enablement exactly as today, unaffected by the added "Forum" category.
//
// OBSERVATION-FIRST: this encodes the AI provider GET/PUT round-trip observed
// on the CURRENT (UNFIXED) code — adminService.getAIProviderConfig() calls
// GET /admin/ai-providers, and adminService.updateAIProviderConfig(updates)
// calls PUT /admin/ai-providers with { providers: updates } and returns the
// persisted state. These pass today and must keep passing after the fix.
//
// EXPECTED OUTCOME ON UNFIXED CODE: PASS (baseline behavior to preserve).
//
// **Validates: Requirement 3.4**

// Mock the shared axios client so we can observe the exact endpoints/payloads
// adminService uses, and simulate the backend persisting a toggle.
vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

import api from './api';
import { adminService, type AIProviderConfigResponse } from './adminService';

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
};

const initialConfig: AIProviderConfigResponse = {
  providers: [
    { provider: 'shai', name: 'SHAI', enabled: true, always_enabled: false },
    { provider: 'kiro', name: 'Kiro', enabled: false, always_enabled: false },
    { provider: 'openai', name: 'OpenAI', enabled: true, always_enabled: false },
    { provider: 'opcp_companion', name: 'OPCP Companion', enabled: true, always_enabled: true },
  ],
};

describe('Preservation: AI provider config round-trip is unchanged (Requirement 3.4)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getAIProviderConfig() reads GET /admin/ai-providers and returns the same providers', async () => {
    mockedApi.get.mockResolvedValueOnce({ data: initialConfig });

    const result = await adminService.getAIProviderConfig();

    expect(mockedApi.get).toHaveBeenCalledWith('/admin/ai-providers');
    expect(result).toEqual(initialConfig);
  });

  it('updateAIProviderConfig() writes PUT /admin/ai-providers with { providers } and persists the toggle', async () => {
    // Simulate the backend persisting the requested toggle (kiro: false -> true).
    const persisted: AIProviderConfigResponse = {
      providers: initialConfig.providers.map((p) =>
        p.provider === 'kiro' ? { ...p, enabled: true } : p,
      ),
    };
    mockedApi.put.mockResolvedValueOnce({ data: persisted });

    const updates = [{ provider: 'kiro' as const, enabled: true }];
    const result = await adminService.updateAIProviderConfig(updates);

    expect(mockedApi.put).toHaveBeenCalledWith('/admin/ai-providers', { providers: updates });
    expect(result).toEqual(persisted);
    expect(result.providers.find((p) => p.provider === 'kiro')?.enabled).toBe(true);
  });

  it('full round-trip: read, toggle, persist, then re-read reflects the change', async () => {
    // First read: initial state.
    mockedApi.get.mockResolvedValueOnce({ data: initialConfig });
    const before = await adminService.getAIProviderConfig();
    expect(before.providers.find((p) => p.provider === 'openai')?.enabled).toBe(true);

    // Toggle openai off and persist.
    const afterToggle: AIProviderConfigResponse = {
      providers: initialConfig.providers.map((p) =>
        p.provider === 'openai' ? { ...p, enabled: false } : p,
      ),
    };
    mockedApi.put.mockResolvedValueOnce({ data: afterToggle });
    const saved = await adminService.updateAIProviderConfig([
      { provider: 'openai', enabled: false },
    ]);
    expect(saved.providers.find((p) => p.provider === 'openai')?.enabled).toBe(false);

    // Re-read returns the persisted state.
    mockedApi.get.mockResolvedValueOnce({ data: afterToggle });
    const reread = await adminService.getAIProviderConfig();
    expect(reread.providers.find((p) => p.provider === 'openai')?.enabled).toBe(false);
  });
});
