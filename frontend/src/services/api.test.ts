import { describe, it, expect, beforeEach } from 'vitest';
import fc from 'fast-check';
import type { InternalAxiosRequestConfig } from 'axios';
import api from './api';

// Bugfix spec: document-upload-400-fix — Task 1
// Property 1: Bug Condition — FormData uploads use multipart content type.
//
// isBugCondition(input) = isFormData(input.data)
//                         AND input.headers["Content-Type"] = "application/json"
//
// This test runs the SHARED axios client's registered request interceptor
// against a synthetic config whose `data` is a FormData instance carrying the
// client's default `Content-Type: application/json`. After the interceptor
// runs, the resulting Content-Type must NOT remain `application/json` so the
// browser can add the `multipart/form-data; boundary=...` header.
//
// EXPECTED OUTCOME ON UNFIXED CODE: FAIL. The interceptor does not strip the
// forced JSON content type on FormData bodies, so `application/json` is
// retained — this proves the bug exists.
//
// **Validates: Requirements 1.1, 1.2, 2.1, 2.2**

// The interceptor is registered on the real `api` instance. We reach into the
// axios interceptor manager to invoke the actual registered success handler,
// exactly as axios would before dispatching a request.
type RequestInterceptor = (
  config: InternalAxiosRequestConfig,
) => InternalAxiosRequestConfig | Promise<InternalAxiosRequestConfig>;

function getRequestInterceptor(): RequestInterceptor {
  // axios stores registered interceptors in `.handlers`; the first is ours.
  const manager = api.interceptors.request as unknown as {
    handlers: Array<{ fulfilled: RequestInterceptor } | null>;
  };
  const handler = manager.handlers.find((h) => h && typeof h.fulfilled === 'function');
  if (!handler) {
    throw new Error('No request interceptor registered on the api client');
  }
  return handler.fulfilled;
}

// Build a config the way axios would present it to the interceptor: the
// instance default `Content-Type: application/json` is merged into
// `config.headers`, and `config.data` is the (FormData) request body.
function makeConfig(
  data: unknown,
  headerOverrides: Record<string, string> = {},
): InternalAxiosRequestConfig {
  return {
    url: '/documents/upload',
    method: 'post',
    baseURL: '/api',
    data,
    headers: {
      'Content-Type': 'application/json',
      ...headerOverrides,
    },
  } as unknown as InternalAxiosRequestConfig;
}

function contentTypeOf(config: InternalAxiosRequestConfig): unknown {
  const headers = config.headers as unknown as Record<string, unknown>;
  // Cover both canonical and lowercase variants.
  return headers['Content-Type'] ?? headers['content-type'];
}

describe('Property 1: FormData uploads must not keep application/json (Requirements 1.1, 1.2, 2.1, 2.2)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('for any FormData body under the default JSON content type, the interceptor leaves no application/json content type', async () => {
    const interceptor = getRequestInterceptor();

    await fc.assert(
      fc.asyncProperty(
        // Varied FormData bodies: differing field names, values, and files.
        fc.array(
          fc.oneof(
            fc.record({
              kind: fc.constant('text' as const),
              name: fc.string({ minLength: 1, maxLength: 12 }),
              value: fc.string({ maxLength: 20 }),
            }),
            fc.record({
              kind: fc.constant('file' as const),
              name: fc.string({ minLength: 1, maxLength: 12 }),
              filename: fc.string({ minLength: 1, maxLength: 12 }),
              content: fc.string({ maxLength: 20 }),
            }),
          ),
          { minLength: 1, maxLength: 5 },
        ),
        async (fields) => {
          const form = new FormData();
          for (const field of fields) {
            if (field.kind === 'file') {
              form.append(
                field.name,
                new File([field.content], field.filename || 'f.bin'),
              );
            } else {
              form.append(field.name, field.value);
            }
          }

          const config = makeConfig(form);
          const result = await interceptor(config);

          // The whole point: a FormData body must not go out as JSON.
          expect(contentTypeOf(result)).not.toBe('application/json');
        },
      ),
      { numRuns: 100 },
    );
  });

  it('concrete upload case: documentService.uploadDocument(file, "private") FormData does not carry application/json', async () => {
    const interceptor = getRequestInterceptor();

    // Reproduce the exact body documentService.uploadDocument builds.
    const form = new FormData();
    form.append('file', new File(['hello'], 'guide.pdf', { type: 'application/pdf' }));
    form.append('access_level', 'private');

    const config = makeConfig(form);
    const result = await interceptor(config);

    expect(contentTypeOf(result)).not.toBe('application/json');
  });

  it('upload-endpoint case: FormData with file and access_level would not be sent as application/json', async () => {
    const interceptor = getRequestInterceptor();

    const form = new FormData();
    form.append('file', new File(['data'], 'report.pdf', { type: 'application/pdf' }));
    form.append('access_level', 'public');

    const result = await interceptor(makeConfig(form));

    // No forced JSON content type may remain, so the browser can add the
    // multipart boundary.
    const ct = contentTypeOf(result);
    expect(ct).not.toBe('application/json');
  });
});
