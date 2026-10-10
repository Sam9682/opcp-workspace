// Helpers for building forum-related links.
//
// buildPublicHtmlUrl is the fixed construction (buildViewUrl') for the forum
// topic "View" button shown to logged-out visitors on the home page. It derives
// the origin (scheme + host + port) from the passed `origin` argument rather than
// a hardcoded host, so any explicit port present in the current site origin is
// preserved automatically and the produced URL resolves to the correct
// /api/forum/topics/{topicId}/publichtml page.
//
// The `origin` is an explicit argument so the fix/preservation properties can be
// unit- and property-tested by stubbing an origin. In the HomePage component it
// is called with `window.location.origin`.
export const buildPublicHtmlUrl = (origin: string, topicId: string): string =>
  `${origin}/api/forum/topics/${topicId}/publichtml`;
