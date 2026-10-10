import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fc from 'fast-check';
import type { InternalAxiosRequestConfig } from 'axios';
import api from './api';

// Bugfix spec: document-upload-400-fix — Task 2
// Property 2: Preservation — Non-FormData requests are unchanged.
//
// isBugCondition(input) = isFormData(input.data)
//                         AND input.headers["Content-Type"] = "application/json"
//
// These tests follow the observation-first methodology: the assertions below
// encode the behavior OBSERVED by running the UNFIXED interceptors, so they
// PASS on unfixed code and lock the baseline the fix must preserve:
//   - JSON / non-FormData bodies keep `Content-Type: application/json`.
//   - The `Authorization: Bearer <token>` header is attached iff localStorage
//     holds an `access_token`, for both JSON and FormData configs.
//   - A 401 on a protected (non-auth) endpoint clears the token and redirects
//     to `/login`; a 401 on an AUTH_ENDPOINT does neither and is surfaced.
//
// EXPECTED OUTCOME ON UNFIXED CODE: PASS (baseline behavior to preserve).
//
// **Validates: Requirements 3.1, 3.2, 3.3**

type RequestInterceptor = (
  config: InternalAxiosRequestConfig,
) => InternalAxiosRequestConfig | Promise<InternalAxiosRequestConfig>;

type ResponseErrorInterceptor = (error: unknown) => unknown;

// Reach into the axios interceptor managers to invoke the actual registered
// handlers, exactly as axios would around a dispatched request/response.
function getRequestInterceptor(): RequestInterceptor {
  const manager = api.interceptors.request as unknown as {
    handlers: Array<{ fulfilled: RequestInterceptor } | null>;
  };
  const handler = manager.handlers.find((h) => h && typeof h.fulfilled === 'function');
  if (!handler) {
    throw new Error('No request interceptor registered on the api client');
  }
  return handler.fulfilled;
}

function getResponseErrorInterceptor(): ResponseErrorInterceptor {
  const manager = api.interceptors.response as unknown as {
    handlers: Array<{ rejected: ResponseErrorInterceptor } | null>;
  };
  const handler = manager.handlers.find((h) => h && typeof h.rejected === 'function');
  if (!handler) {
    throw new Error('No response error interceptor registered on the api client');
  }
  return handler.rejected;
}

// Build a config the way axios presents it to the interceptor: the instance
// default `Content-Type: application/json` is merged into `config.headers`.
function makeConfig(
  data: unknown,
  {
    url = '/forum/posts',
    method = 'post',
    headerOverrides = {},
  }: { url?: string; method?: string; headerOverrides?: Record<string, string> } = {},
): InternalAxiosRequestConfig {
  return {
    url,
    method,
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
  return headers['Content-Type'] ?? headers['content-type'];
}

function authOf(config: InternalAxiosRequestConfig): unknown {
  const headers = config.headers as unknown as Record<string, unknown>;
  return headers.Authorization ?? headers.authorization;
}

// A JSON-ish body that is NOT FormData: plain objects, arrays, strings, or
// nullish bodies. These all satisfy NOT isBugCondition.
const nonFormDataBody = fc.oneof(
  fc.constant(undefined),
  fc.constant(null),
  fc.string({ maxLength: 30 }),
  fc.object({ maxDepth: 2 }),
  fc.array(fc.integer(), { maxLength: 5 }),
);

describe('Property 2 (preservation): JSON / non-FormData bodies keep application/json (Requirement 3.1)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('for any non-FormData body, varied URL/method/headers, the interceptor keeps Content-Type: application/json', async () => {
    const interceptor = getRequestInterceptor();

    await fc.assert(
      fc.asyncProperty(
        nonFormDataBody,
        fc.constantFrom('/forum/posts', '/auth/login', '/documents', '/users/me', '/anything'),
        fc.constantFrom('get', 'post', 'put', 'patch', 'delete'),
        async (body, url, method) => {
          const result = await interceptor(makeConfig(body, { url, method }));
          // Non-FormData bodies must retain the forced JSON content type.
          expect(contentTypeOf(result)).toBe('application/json');
        },
      ),
      { numRuns: 100 },
    );
  });
});

describe('Property 2 (preservation): Authorization header behavior is unchanged (Requirement 3.2)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('attaches Bearer <token> when a token is present, for both JSON and FormData bodies', async () => {
    const interceptor = getRequestInterceptor();

    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 1, maxLength: 40 }),
        fc.boolean(),
        async (token, useFormData) => {
          localStorage.setItem('access_token', token);
          try {
            const body = useFormData ? new FormData() : { title: 'x' };
            const result = await interceptor(makeConfig(body));
            expect(authOf(result)).toBe(`Bearer ${token}`);
          } finally {
            localStorage.clear();
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('does not attach an Authorization header when no token is present, for both JSON and FormData bodies', async () => {
    const interceptor = getRequestInterceptor();

    await fc.assert(
      fc.asyncProperty(fc.boolean(), async (useFormData) => {
        localStorage.clear();
        const body = useFormData ? new FormData() : { title: 'x' };
        const result = await interceptor(makeConfig(body));
        expect(authOf(result)).toBeUndefined();
      }),
      { numRuns: 50 },
    );
  });
});

describe('Property 2 (preservation): 401 handling clears token + redirects for protected endpoints only (Requirement 3.3)', () => {
  const AUTH_ENDPOINTS = ['/auth/login', '/auth/login/2fa'];
  let originalLocation: Location;

  beforeEach(() => {
    localStorage.clear();
    // jsdom does not implement navigation; replace window.location with a
    // stub whose `href` is a plain writable property so we can observe the
    // redirect the interceptor performs.
    originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: { ...originalLocation, href: 'http://localhost/' } as unknown as Location,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: originalLocation,
    });
    vi.restoreAllMocks();
  });

  function make401(url: string) {
    return {
      response: { status: 401 },
      config: { url },
    };
  }

  it('for any protected (non-auth) endpoint, a 401 clears the token and redirects to /login', async () => {
    const onError = getResponseErrorInterceptor();

    await fc.assert(
      fc.asyncProperty(
        fc.constantFrom('/documents', '/forum/posts', '/users/me', '/oracle', '/api/whatever'),
        async (url) => {
          localStorage.setItem('access_token', 'live-token');
          window.location.href = 'http://localhost/';

          await expect(Promise.resolve(onError(make401(url)))).rejects.toBeDefined();

          expect(localStorage.getItem('access_token')).toBeNull();
          expect(window.location.href).toBe('/login');
        },
      ),
      { numRuns: 50 },
    );
  });

  it('for any AUTH_ENDPOINT, a 401 does NOT clear the token or redirect and is surfaced to the caller', async () => {
    const onError = getResponseErrorInterceptor();

    await fc.assert(
      fc.asyncProperty(fc.constantFrom(...AUTH_ENDPOINTS), async (url) => {
        localStorage.setItem('access_token', 'live-token');
        window.location.href = 'http://localhost/';

        await expect(Promise.resolve(onError(make401(url)))).rejects.toBeDefined();

        // Auth-endpoint 401s are the caller's problem: no side effects.
        expect(localStorage.getItem('access_token')).toBe('live-token');
        expect(window.location.href).toBe('http://localhost/');
      }),
      { numRuns: 50 },
    );
  });
});
