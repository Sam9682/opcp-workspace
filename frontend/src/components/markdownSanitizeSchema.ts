import { defaultSchema } from 'rehype-sanitize';
import type { Options as SanitizeSchema } from 'rehype-sanitize';

/**
 * Sanitization schema for the Oracle chat MarkdownRenderer.
 *
 * Built by spreading `defaultSchema` from `rehype-sanitize` (GitHub's
 * allow-list). The default schema already:
 *  - strips `<script>` elements (Requirement 3.2),
 *  - drops `on*` event-handler attributes since they are not allow-listed
 *    (Requirement 3.3),
 *  - restricts `href`/`src` to a safe protocol set that excludes
 *    `javascript:` (Requirement 3.4).
 *
 * The default protocol allow-list is inherited unchanged, so no extra
 * configuration is needed to exclude `javascript:` URLs.
 *
 * We extend the default schema only where a needed Safe_HTML attribute is
 * missing: we keep `className` on `code`/`pre` so code fences and prose code
 * styling survive sanitization. The default `code` entry only permits the
 * `language-*` class produced by fenced blocks, so we preserve that matcher
 * and additionally allow a general `className`.
 */
export const markdownSanitizeSchema: SanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    // Preserve the default `language-*` matcher and also allow a general
    // `className` so code/prose styling classes survive.
    code: [...(defaultSchema.attributes?.code ?? []), 'className'],
    // `pre` has no default attribute entry; allow `className` for styling.
    pre: [...(defaultSchema.attributes?.pre ?? []), 'className'],
  },
  // `protocols` is intentionally inherited unchanged from `defaultSchema`,
  // which already excludes `javascript:` from `href`/`src`.
};
