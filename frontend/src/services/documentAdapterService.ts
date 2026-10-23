import api from './api';
import type { AIProviderId } from './oracleService';

/**
 * Document Audience Adapter service client.
 *
 * Feature: document-audience-adapter
 * Validates Requirements 2.4, 5.1, 6.2, 6.3
 *
 * Typed client for the two backend endpoints:
 * - `POST /api/document-adapter/adapt` generates audience-tailored content.
 * - `POST /api/document-adapter/export` renders the content into a downloadable
 *   PDF or Word file.
 *
 * The api client prefixes `/api` (see `api.ts`), so the paths below are given
 * without that prefix, consistent with `documentService` and `oracleService`.
 */

/** One of the four fixed target audience profiles, in progression order. */
export type AudienceLevel =
  | 'it_beginner'
  | 'intermediate_a'
  | 'intermediate_b'
  | 'opcp_expert';

/** The four audience levels in progression order (beginner -> OPCP expert). */
export const AUDIENCE_LEVELS: readonly AudienceLevel[] = [
  'it_beginner',
  'intermediate_a',
  'intermediate_b',
  'opcp_expert',
] as const;

/** Supported export formats. */
export type ExportFormat = 'pdf' | 'docx';

/**
 * Source document MIME types accepted by the adapter: PDF and Word
 * (legacy `.doc` and OpenXML `.docx`).
 */
export const SUPPORTED_SOURCE_MIME_TYPES = [
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
] as const;

/**
 * Return true if and only if `mimeType` is one of the supported source types.
 *
 * Validates Requirements 2.4 (Correctness Property 1): only PDF and Word
 * source files are accepted.
 */
export function isSupportedSourceType(mimeType: string): boolean {
  return (SUPPORTED_SOURCE_MIME_TYPES as readonly string[]).includes(mimeType);
}

/**
 * The adaptation request. Exactly one of `document_id` (a library document) or
 * `uploaded_filename` (a prior `/documents/upload` result) must be set.
 */
export interface AdaptationRequest {
  document_id?: string;
  uploaded_filename?: string;
  audience_level: AudienceLevel;
  ai_provider: AIProviderId;
}

/** The adaptation response returned by the adapt endpoint. */
export interface AdaptationResponse {
  adapted_content: string;
  audience_level: AudienceLevel;
  ai_provider: string;
  source_name: string;
  processing_time: number;
}

/**
 * Parse the `filename` from a `Content-Disposition` header value.
 *
 * Handles both the quoted `filename="..."` form the backend emits and the
 * RFC 5987 `filename*=UTF-8''...` form, returning `undefined` when no filename
 * is present so the caller can fall back to a client-built name.
 */
function parseContentDispositionFilename(
  disposition: string | undefined,
): string | undefined {
  if (!disposition) {
    return undefined;
  }

  // Prefer the RFC 5987 extended form when present (it carries encoding info).
  const extendedMatch = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(disposition);
  if (extendedMatch) {
    try {
      return decodeURIComponent(extendedMatch[1].trim().replace(/^"|"$/g, ''));
    } catch {
      // Fall through to the plain form if decoding fails.
    }
  }

  const plainMatch = /filename="?([^";]+)"?/i.exec(disposition);
  if (plainMatch) {
    return plainMatch[1].trim();
  }

  return undefined;
}

/**
 * Sanitize a source name into a filename stem, mirroring the backend
 * `build_export_filename` convention: strip the extension, replace runs of
 * characters outside `[A-Za-z0-9._-]` with a single `_`, trim leading/trailing
 * `_`, and fall back to `document` when empty.
 */
function sanitizeSourceStem(sourceName: string): string {
  const name = sourceName || '';
  const dot = name.lastIndexOf('.');
  const stem = dot > 0 ? name.slice(0, dot) : name;

  const sanitized = stem
    .replace(/[^A-Za-z0-9._-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');

  return sanitized || 'document';
}

/**
 * Build the fallback export filename, encoding the source identity and the
 * audience level: `{sanitized_source_stem}__{audience_level}.{ext}`.
 */
function buildFallbackFilename(
  sourceName: string,
  audienceLevel: AudienceLevel,
  format: ExportFormat,
): string {
  const stem = sanitizeSourceStem(sourceName);
  const ext = format === 'docx' ? 'docx' : 'pdf';
  return `${stem}__${audienceLevel}.${ext}`;
}

/** Save a blob to disk via a temporary download anchor. */
function saveBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const anchor = window.document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  window.document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

export const documentAdapterService = {
  /**
   * Generate audience-tailored content for the given source, audience level,
   * and provider.
   *
   * Validates Requirements 5.1: the request body carries the chosen source
   * reference, audience level, and provider verbatim.
   */
  async adapt(req: AdaptationRequest): Promise<AdaptationResponse> {
    const response = await api.post<AdaptationResponse>(
      '/document-adapter/adapt',
      req,
    );
    return response.data;
  },

  /**
   * Render adapted content into a downloadable PDF or Word file and save it.
   *
   * Validates Requirements 6.2, 6.3: the saved file uses the server-provided
   * `Content-Disposition` filename when present, with a client-side fallback
   * that still encodes the source identity and the audience level. The
   * blob/anchor download mirrors `documentService.downloadDocument`.
   */
  async exportAdapted(
    adaptedContent: string,
    sourceName: string,
    audienceLevel: AudienceLevel,
    format: ExportFormat,
  ): Promise<void> {
    const response = await api.post(
      '/document-adapter/export',
      {
        adapted_content: adaptedContent,
        source_name: sourceName,
        audience_level: audienceLevel,
        format,
      },
      { responseType: 'blob' },
    );

    const disposition =
      (response.headers?.['content-disposition'] as string | undefined) ??
      (response.headers?.['Content-Disposition'] as string | undefined);
    const filename =
      parseContentDispositionFilename(disposition) ??
      buildFallbackFilename(sourceName, audienceLevel, format);

    saveBlob(response.data as Blob, filename);
  },
};
