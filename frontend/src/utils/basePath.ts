// Helpers for serving the SPA under a configurable base path.
//
// BASE_PATH is the mount point of the application (e.g. '/' at the domain root,
// or '/opcp' when reverse-proxied under a sub-path). It is derived from
// VITE_BASE_PATH when provided, otherwise from Vite's BASE_URL (driven by the
// `base` option in vite.config.ts). It is normalized to either '/' (root) or a
// leading-slash, no-trailing-slash prefix such as '/opcp'.
//
// withBase joins BASE_PATH with an application-relative path while guaranteeing
// exactly one slash at the junction, so callers never produce '//' in URLs.

const rawBase = (import.meta.env.VITE_BASE_PATH ?? import.meta.env.BASE_URL ?? '/') as string;

const normalizeBase = (value: string): string => {
  const trimmed = value.trim();
  if (!trimmed || trimmed === '/') return '/';
  const withLeadingSlash = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
  return withLeadingSlash.replace(/\/+$/, '');
};

export const BASE_PATH = normalizeBase(rawBase);

export const withBase = (path: string): string => {
  // Leave absolute URLs (http://, https://, //cdn...) untouched.
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(path) || path.startsWith('//')) {
    return path;
  }

  const base = BASE_PATH === '/' ? '' : BASE_PATH;
  const suffix = path.startsWith('/') ? path : `/${path}`;
  return `${base}${suffix}` || '/';
};
