import { describe, it, expect, vi, beforeEach } from 'vitest';
import fc from 'fast-check';

// The service imports the default axios instance from './api' and calls
// `.post` on it. We replace that module with a stub whose `post` we can
// inspect, so we can capture the exact request body sent by `adapt` without a
// real network call.
vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

// Import after the mock is registered so the service binds to the stub.
import api from './api';
import {
  documentAdapterService,
  AUDIENCE_LEVELS,
  type AdaptationRequest,
  type AudienceLevel,
} from './documentAdapterService';
import type { AIProviderId } from './oracleService';

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

const AI_PROVIDER_IDS: readonly AIProviderId[] = [
  'shai',
  'kiro',
  'openai',
  'opcp_companion',
] as const;

beforeEach(() => {
  mockedApi.get.mockReset();
  mockedApi.put.mockReset();
  mockedApi.post.mockReset();
  mockedApi.delete.mockReset();
  // The adapt response shape is irrelevant to this property; the data must
  // simply be present so `adapt` resolves.
  mockedApi.post.mockResolvedValue({ data: { adapted_content: '' } });
});

describe('documentAdapterService.adapt request construction', () => {
  // Feature: document-audience-adapter, Property 6: The adaptation request
  // carries the chosen source, audience, and provider
  // Validates: Requirements 5.1, 3.4

  const audienceArb = fc.constantFrom<AudienceLevel>(...AUDIENCE_LEVELS);
  const providerArb = fc.constantFrom<AIProviderId>(...AI_PROVIDER_IDS);

  // A valid source reference is exactly one of document_id or
  // uploaded_filename. Model both variants with a non-empty identifier.
  const sourceArb = fc.oneof(
    fc
      .string({ minLength: 1 })
      .map((id) => ({ kind: 'library' as const, value: id })),
    fc
      .string({ minLength: 1 })
      .map((name) => ({ kind: 'upload' as const, value: name })),
  );

  it('posts a body carrying exactly the chosen source, audience_level, and ai_provider', async () => {
    await fc.assert(
      fc.asyncProperty(
        sourceArb,
        audienceArb,
        providerArb,
        async (source, audienceLevel, provider) => {
          mockedApi.post.mockClear();

          const req: AdaptationRequest = {
            audience_level: audienceLevel,
            ai_provider: provider,
            ...(source.kind === 'library'
              ? { document_id: source.value }
              : { uploaded_filename: source.value }),
          };

          await documentAdapterService.adapt(req);

          // The endpoint and HTTP verb are fixed.
          expect(mockedApi.post).toHaveBeenCalledTimes(1);
          const [url, body] = mockedApi.post.mock.calls[0];
          expect(url).toBe('/document-adapter/adapt');

          const sent = body as AdaptationRequest;

          // The chosen source reference is carried verbatim, and the other
          // source field is absent (exactly-one-of preserved).
          if (source.kind === 'library') {
            expect(sent.document_id).toBe(source.value);
            expect(sent.uploaded_filename).toBeUndefined();
          } else {
            expect(sent.uploaded_filename).toBe(source.value);
            expect(sent.document_id).toBeUndefined();
          }

          // The chosen audience and provider are carried verbatim.
          expect(sent.audience_level).toBe(audienceLevel);
          expect(sent.ai_provider).toBe(provider);
        },
      ),
      { numRuns: 100 },
    );
  });
});
