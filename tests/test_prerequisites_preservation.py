"""Preservation property tests for the prerequisites 404 bugfix.

Bugfix spec: .kiro/specs/basics-prerequisites-404-fix

Property 2 (Preservation): every request that does NOT match the
`/api/prerequisites/*` contract must behave EXACTLY as it does today. The fix
(mounting a new prerequisites router) is purely additive, so it must not change
any existing route, the root/health endpoints, the app's normal unmatched-route
404, or global middleware (CORS, rate limiting).

Methodology (observation-first): the assertions below encode behavior OBSERVED
on the CURRENT (unfixed) app. They are EXPECTED TO PASS now (capturing the
baseline) and must CONTINUE to pass after the fix (proving no regression). No
application code is modified by this task.

isBugCondition(request): path matches
    /api/prerequisites/installations/{id}/{slug}/content
    /api/prerequisites/installations/{id}/{slug}/answers
    /api/prerequisites/installations/{id}/{slug}/answers/{rowId}
This file exercises the complement: `NOT isBugCondition(request)`.

Migrated by: .kiro/specs/vcf-prerequisites-update (task 6.1) to the
installation-scoped family. The preservation intent is unchanged: non-family
paths still behave exactly as before.

Validates: Requirements 9.3, 7.7 (preservation intent, formerly 3.1-3.5)
"""
import pytest

try:
    from hypothesis import given, settings, HealthCheck, strategies as st
    HAS_HYPOTHESIS = True
except Exception:  # pragma: no cover - hypothesis is expected to be installed
    HAS_HYPOTHESIS = False


# ---------------------------------------------------------------------------
# isBugCondition encoding (shared with the exploration test). A request is in
# the prerequisites family iff its path matches one of the three contract
# shapes. Preservation only cares about the COMPLEMENT of this predicate.
# ---------------------------------------------------------------------------
def _is_bug_condition(path: str) -> bool:
    """Return True if `path` targets the installation-scoped prerequisites contract.

    The family is now
    ``/api/prerequisites/installations/{id}/{slug}/content|answers[/{row_id}]``.
    """
    parts = [p for p in path.split("/") if p]
    if len(parts) < 6:
        return False
    if parts[0] != "api" or parts[1] != "prerequisites" or parts[2] != "installations":
        return False
    resource = parts[5]
    if resource == "content" and len(parts) == 6:
        return True
    if resource == "answers" and len(parts) in (6, 7):
        return True
    return False


# ---------------------------------------------------------------------------
# Recorded baselines (observed on the UNFIXED app through the conftest `client`
# fixture, i.e. the SQLite/Base.metadata.create_all test harness). Each entry:
#   (method, path, expected_status, body_check)
# `body_check(body_dict)` returns a stable assertion, avoiding volatile fields
# such as `timestamp`/`requestId` present in structured error bodies.
# ---------------------------------------------------------------------------
def _detail_not_found(body):
    return body == {"detail": "Not Found"}


def _detail_method_not_allowed(body):
    return body == {"detail": "Method Not Allowed"}


def _error_code(code):
    def _check(body):
        return isinstance(body, dict) and body.get("error", {}).get("code") == code
    return _check


def _root_body(body):
    return (
        body.get("message") == "Welcome to AI-SHAI API"
        and "version" in body
        and body.get("docs") == "/docs"
    )


def _health_body(body):
    return (
        body.get("status") == "healthy"
        and body.get("app") == "AI-SHAI"
        and "version" in body
    )


def _documents_empty(body):
    return body == {"documents": [], "total": 0}


def _any_body(body):
    return True


# (method, path, expected_status, body_check, note)
BASELINE = [
    # --- Root / health (Req 3.2) ---
    ("GET", "/", 200, _root_body, "root welcome payload"),
    ("GET", "/health", 200, _health_body, "health payload"),

    # --- Existing router prefixes respond as before (Req 3.1, 3.4) ---
    # Public info endpoints (no auth) -> 200
    ("GET", "/api/info/homepage", 200, _any_body, "public homepage info"),
    ("GET", "/api/info/legal", 200, _any_body, "public legal info"),
    # Documents list under the SQLite test harness -> 200 empty list
    ("GET", "/api/documents", 200, _documents_empty, "empty documents list"),
    # Protected endpoints reject unauthenticated callers with a structured 403
    ("GET", "/api/forum/topics", 403, _error_code("HTTP_ERROR"), "forum requires auth"),
    ("GET", "/api/events", 403, _error_code("HTTP_ERROR"), "events requires auth"),
    # Validation on a real POST endpoint (empty body) -> structured 400
    ("POST", "/api/auth/login", 400, _error_code("VALIDATION_ERROR"), "login validation"),
    # Wrong method on a real path -> 405 (route exists, verb does not)
    ("GET", "/api/auth/login", 405, _detail_method_not_allowed, "login GET not allowed"),

    # --- Unrelated unmatched paths keep the app's normal 404 (Req 3.1) ---
    # Undefined subpaths under existing prefixes still fall through to the
    # framework's default unmatched-route 404 -> the fix must NOT broaden this.
    ("GET", "/api/nope", 404, _detail_not_found, "unmatched path 404"),
    ("GET", "/api/admin/users", 404, _detail_not_found, "undefined admin subpath"),
    ("GET", "/api/notifications", 404, _detail_not_found, "undefined notifications root"),
    ("GET", "/api/users", 404, _detail_not_found, "undefined users root"),
    ("GET", "/api/oracle", 404, _detail_not_found, "undefined oracle root"),
    ("GET", "/api/forum/categories", 404, _detail_not_found, "undefined forum subpath"),
]


@pytest.mark.parametrize(
    "method,path,status,body_check,note",
    BASELINE,
    ids=[f"{m}:{p}" for m, p, _s, _c, _n in BASELINE],
)
def test_non_prerequisites_baseline_preserved(client, method, path, status, body_check, note):
    """Each representative non-prerequisites request matches its recorded baseline.

    Sanity: the path must be OUTSIDE the prerequisites family (NOT isBugCondition).
    Then the observed (status, body) must equal the baseline captured on the
    unfixed app. The same assertions re-run after the fix prove no regression.

    Validates: Requirements 3.1, 3.2, 3.4
    """
    assert not _is_bug_condition(path), (
        f"test setup error: {path} is inside the prerequisites family"
    )

    resp = client.request(method, path)

    assert resp.status_code == status, (
        f"REGRESSION: {method} {path} ({note}) -> {resp.status_code}, "
        f"expected baseline {status}. Body: {resp.text[:200]}"
    )
    body = resp.json()
    assert body_check(body), (
        f"REGRESSION: {method} {path} ({note}) body changed from baseline. "
        f"Got: {body}"
    )


def test_root_body_is_exact_baseline(client):
    """`GET /` returns exactly its current body (Req 3.2)."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {
        "message": "Welcome to AI-SHAI API",
        "version": "1.0.0",
        "docs": "/docs",
    }


def test_health_body_is_exact_baseline(client):
    """`GET /health` returns exactly its current body (Req 3.2)."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "healthy",
        "app": "AI-SHAI",
        "version": "1.0.0",
    }


def test_unrelated_unmatched_path_returns_normal_404(client):
    """An unrelated unmatched path keeps the framework's default 404 (Req 3.1).

    The new prerequisites router must NOT broaden matching so that it swallows
    paths outside its family. `/api/nope` must stay `{"detail": "Not Found"}`.
    """
    resp = client.get("/api/nope")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}


def test_cors_headers_unchanged_on_existing_route(client):
    """CORS middleware still echoes the allowed origin on an existing route (Req 3.5)."""
    resp = client.get(
        "/api/info/homepage",
        headers={"Origin": "https://opcp-psmc.com"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://opcp-psmc.com"
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_unchanged_on_existing_route(client):
    """CORS preflight (OPTIONS) still succeeds on an existing route (Req 3.5)."""
    resp = client.options(
        "/api/info/homepage",
        headers={
            "Origin": "https://opcp-psmc.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://opcp-psmc.com"
    allow_methods = resp.headers.get("access-control-allow-methods", "")
    assert "GET" in allow_methods


def test_rate_limit_behavior_unchanged_on_existing_route(client):
    """Repeated auth-validation requests stay 400 (not rate-limited) on the unfixed
    baseline, confirming rate-limit/middleware behavior on an existing route is
    unchanged by the additive fix (Req 3.5).

    Empty-body POSTs fail validation (400) before any credential check; slowapi's
    per-IP limit for this endpoint is well above this small burst, so every
    attempt returns the same structured 400.
    """
    for _ in range(5):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Property-based preservation: for MANY generated requests OUTSIDE the
# prerequisites family, the app must never route them into a prerequisites
# handler. On the unfixed app there is no such handler at all; the invariant we
# assert (stable across the fix) is that non-family paths under `/api` that are
# not otherwise defined keep the framework's normal unmatched-route 404 and are
# never served as prerequisites resources.
# ---------------------------------------------------------------------------
if HAS_HYPOTHESIS:

    # Path segments that stay clearly OUTSIDE the /api/prerequisites/* family.
    _SAFE_SEGMENT = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
        min_size=1,
        max_size=12,
    ).filter(lambda s: s not in ("", "prerequisites"))

    @st.composite
    def _non_prerequisites_api_paths(draw):
        """Generate `/api/<...>` paths guaranteed to be outside the family.

        The first segment after `/api` is never `prerequisites`, so the path can
        never match the bug condition regardless of the remaining segments.
        """
        first = draw(_SAFE_SEGMENT.filter(lambda s: s != "prerequisites"))
        rest = draw(st.lists(_SAFE_SEGMENT, min_size=0, max_size=3))
        return "/api/" + "/".join([first, *rest])

    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(path=_non_prerequisites_api_paths())
    def test_generated_non_family_paths_never_served_as_prerequisites(client, path):
        """Property: any generated `/api/*` path outside the prerequisites family
        is never a prerequisites resource, and undefined ones keep the normal 404.

        Validates: Requirements 3.1, 3.3
        """
        # Invariant on the generator: never inside the family.
        assert not _is_bug_condition(path)

        resp = client.get(path)
        # It must resolve to one of the app's real, pre-existing outcomes: an
        # existing route (2xx/4xx from that route) or the framework's normal
        # unmatched-route 404 -- never a prerequisites-served 200 shape.
        if resp.status_code == 404:
            # Undefined paths keep the framework default body.
            assert resp.json() == {"detail": "Not Found"}
        # Regardless of status, the response must not be a prerequisites
        # content/answers payload (those shapes only exist for the family).
        try:
            body = resp.json()
        except Exception:
            body = None
        if isinstance(body, dict):
            served_as_prereq = (
                set(body.keys()) in ({"slug", "content", "updated_at"},
                                     {"slug", "content"},
                                     {"slug", "answers"})
            )
            assert not served_as_prereq, (
                f"REGRESSION: non-family path {path} was served a prerequisites "
                f"payload: {body}"
            )

    @settings(max_examples=50, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        slug=st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=10),
        verb=st.sampled_from(["GET", "PUT", "POST", "DELETE"]),
    )
    def test_prerequisites_sibling_paths_are_not_the_family(client, slug, verb):
        """Property: sibling prerequisites paths that are NOT part of the contract
        (e.g. `/api/prerequisites/{slug}` with no resource, or an unknown resource)
        are outside the bug condition and keep the app's normal 404.

        This guards the boundary of the family so the fix stays narrowly scoped.
        Validates: Requirement 3.1
        """
        # A prerequisites path WITHOUT a recognized /content or /answers resource
        # is not part of the contract -> NOT isBugCondition.
        path = f"/api/prerequisites/{slug}"
        assert not _is_bug_condition(path)
        resp = client.request(verb, path)
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Not Found"}
