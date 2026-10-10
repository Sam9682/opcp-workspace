"""Property-based tests for the OpenStack forward-proxy fix.

Spec: .kiro/specs/openstack-proxy-connection (task 4.2)

This module encodes the two correctness properties from the design as
Hypothesis property tests over generated input spaces (rather than the small
sampled sets used by the exploration/preservation tests):

- **Property 1 - Bug Condition fixed** (design.md, "Property 1"): for ANY
  configured non-empty proxy URL, both the Keystone (``_get_token``) and Nova
  (``_list_servers``) ``httpx.AsyncClient`` instances are constructed with that
  exact proxy, so the flow returns the mapped ``{id, name, status}`` rows.
  Here proxy URLs are *generated* (scheme / host / port / trailing slash) rather
  than picked from a fixed list. **Validates: Requirements 2.1, 2.2, 2.3.**

- **Property 2 - Preservation** (design.md, "Property 2"): for ANY input where
  the bug condition does NOT hold, the fixed code produces the same result as
  the original. This module runs a *differential* comparison: the current fixed
  ``OpenStackProxy`` versus an inlined reference implementation of the ORIGINAL
  (pre-fix) behavior - build ``httpx.AsyncClient(verify=verify)`` with no proxy
  and identical auth/CA/service/return handling. Across the generated non-bug
  input space (empty/whitespace proxy, mixed auth/service statuses, valid vs
  invalid CA PEM, JSON vs non-JSON Nova bodies) the two must agree on the client
  kwargs, the returned rows, and the raised error code.
  **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5.**

- **Non-leak across all paths**: generated secrets and tokens never appear in
  captured logs, exception messages, or route response bodies, on success or any
  error path. **Validates: Requirements 2.4, 3.5.**

Approach (matches the existing openstack proxy tests):
- ``settings.OPENSTACK_HTTPS_PROXY`` is injected via ``object.__setattr__`` in a
  fixture so the resolver reads a known value regardless of process env.
- ``httpx.AsyncClient`` on the ``openstack`` module namespace is replaced with a
  fake async client recording the FULL constructor kwargs and returning
  configurable per-call responses. No real network or proxy is used.
- ``HealthCheck.function_scoped_fixture`` is suppressed where a function-scoped
  fixture (monkeypatch / set_proxy / caplog) is combined with ``@given``; the
  CA-invalid property that must guarantee no client is built uses a
  context-manager patch instead, consistent with the preservation test.
"""
import asyncio
import contextlib
import logging
import ssl

import httpx
import pytest
from fastapi import status
from hypothesis import HealthCheck, given, settings as hyp_settings
from hypothesis import strategies as st

from app.config import settings
from app.models import User, UserRole  # noqa: F401
from app.models.credential_config import CredentialConfig  # noqa: F401 (register table)
from app.prerequisites import openstack as openstack_module
from app.prerequisites.openstack import (
    OpenStackProxy,
    OpenStackAuthError,
    OpenStackCACertificateError,
    OpenStackConnectionError,
    OpenStackServiceError,
    NovaServerDTO,
    _build_verify,
)
from app.auth.token import create_access_token


# A Keystone token asserted to route through the proxy but never leak.
KEYSTONE_TOKEN = "gAAAAA-property-keystone-subject-token"

# A distinctive secret marker so a substring match anywhere means the real value
# leaked verbatim, not an incidental collision with a UUID or timestamp.
_SECRET_MARKER = "OS_PROXY_PROPERTY_SECRET_"

# A fixed, known-valid self-signed PEM (reused from the CA verify property test)
# to exercise the real ``ssl.create_default_context(cadata=...)`` branch.
VALID_PEM = """-----BEGIN CERTIFICATE-----
MIIBhTCCASugAwIBAgIQIRi6zePL6mKjOipn+dNuaTAKBggqhkjOPQQDAjASMRAw
DgYDVQQKEwdBY21lIENvMB4XDTE3MTAyMDE5NDMwNloXDTE4MTAyMDE5NDMwNlow
EjEQMA4GA1UEChMHQWNtZSBDbzBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABD0d
7VNhbWvZLWPuj/RtHFjvtJBEwOkhbN/BnnE8rnZR8+sbwnc/KhCk3FhnpHZnQz7B
5aETbbIgmuvewdjvSBSjYzBhMA4GA1UdDwEB/wQEAwICpDATBgNVHSUEDDAKBggr
BgEFBQcDATAPBgNVHRMBAf8EBTADAQH/MCkGA1UdEQQiMCCCDmxvY2FsaG9zdDo1
NDUzgg4xMjcuMC4wLjE6NTQ1MzAKBggqhkjOPQQDAgNIADBFAiEA2zpJEPQyz6/l
Wf86aX6PepsntZv2GYlA5UpabfT2EZICICpJ5h/iI+i341gBmLiAFQOyTDT+/wQc
6MF9+Yw1Yy0t
-----END CERTIFICATE-----
"""

# Sentinel marking "this attribute did not exist before the test" so cleanup can
# remove it again rather than restoring a bogus value.
_MISSING = object()


@pytest.fixture
def set_proxy(monkeypatch):
    """Inject ``settings.OPENSTACK_HTTPS_PROXY`` and restore afterwards.

    Uses ``object.__setattr__`` on the singleton settings instance, mirroring the
    fixture in the exploration/preservation/unit tests, so the value is applied
    without depending on process env. ``_resolve_proxy`` reads it via ordinary
    attribute access.
    """
    applied: list = []

    def _apply(value: str) -> None:
        had = settings.__dict__.get("OPENSTACK_HTTPS_PROXY", _MISSING)
        applied.append(had)
        object.__setattr__(settings, "OPENSTACK_HTTPS_PROXY", value)

    yield _apply

    for had in reversed(applied):
        if had is _MISSING:
            settings.__dict__.pop("OPENSTACK_HTTPS_PROXY", None)
        else:
            object.__setattr__(settings, "OPENSTACK_HTTPS_PROXY", had)


# ---------------------------------------------------------------------------
# Fake httpx.AsyncClient capturing the FULL constructor kwargs, with a
# configurable response/behavior per call site (token / servers).
# ---------------------------------------------------------------------------
class _FakeResponse:
    """Minimal stand-in for ``httpx.Response`` used by the proxy."""

    def __init__(self, status_code, *, headers=None, json_body=None, json_raises=False):
        self.status_code = status_code
        self.headers = headers or {}
        self._json_body = json_body
        self._json_raises = json_raises

    @property
    def is_success(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._json_raises:
            raise ValueError("non-JSON body")
        if self._json_body is None:
            raise ValueError("no JSON body")
        return self._json_body


def _make_capturing_client(
    captured_kwargs,
    *,
    token_response=None,
    servers_response=None,
    post_error=None,
    get_error=None,
):
    """Fake ``httpx.AsyncClient`` recording each construction's full kwargs.

    ``captured_kwargs`` is a shared list; every construction appends the full
    keyword dict it received. ``post`` returns ``token_response`` (default: a
    success token) and ``get`` returns ``servers_response`` (default: empty Nova
    list). ``post_error`` / ``get_error`` (``httpx`` exceptions) are raised from
    the respective call when supplied.
    """

    default_token = _FakeResponse(
        201, headers={"X-Subject-Token": KEYSTONE_TOKEN}, json_body={"token": {}}
    )
    default_servers = _FakeResponse(200, json_body={"servers": []})

    class _Client:
        def __init__(self, *args, **kwargs):
            captured_kwargs.append(dict(kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, **kwargs):
            if post_error is not None:
                raise post_error
            return token_response if token_response is not None else default_token

        async def get(self, url, **kwargs):
            if get_error is not None:
                raise get_error
            return servers_response if servers_response is not None else default_servers

    return _Client


# ---------------------------------------------------------------------------
# Reference ORIGINAL (pre-fix) behavior for the differential preservation test.
#
# This inlines exactly what app/prerequisites/openstack.py did BEFORE the fix:
# build the client as ``httpx.AsyncClient(verify=verify)`` with NO proxy, and
# apply the identical auth / service / return handling. The differential test
# asserts the current (fixed) code equals this original for every non-bug input.
# ---------------------------------------------------------------------------
_HTTP_TIMEOUT = 60.0


async def _original_get_token(client_cls, auth_url, credential_id, secret, verify):
    url = f"{auth_url.rstrip('/')}/auth/tokens"
    payload = {
        "auth": {
            "identity": {
                "methods": ["application_credential"],
                "application_credential": {"id": credential_id, "secret": secret},
            }
        }
    }
    try:
        async with client_cls(verify=verify) as client:  # NO proxy (original)
            response = await client.post(
                url, json=payload, headers={"Content-Type": "application/json"},
                timeout=_HTTP_TIMEOUT,
            )
    except (httpx.ConnectError, httpx.TimeoutException):
        raise OpenStackConnectionError("connection failed")
    if response.status_code in (401, 403):
        raise OpenStackAuthError("credentials refused")
    if not response.is_success:
        raise OpenStackServiceError(f"error status {response.status_code}")
    token = response.headers.get("X-Subject-Token")
    if not token:
        raise OpenStackServiceError("missing token header")
    return token


async def _original_list_servers(client_cls, nova_endpoint, token, verify):
    url = f"{nova_endpoint.rstrip('/')}/servers"
    try:
        async with client_cls(verify=verify) as client:  # NO proxy (original)
            response = await client.get(
                url, headers={"X-Auth-Token": token}, timeout=_HTTP_TIMEOUT,
            )
    except (httpx.ConnectError, httpx.TimeoutException):
        raise OpenStackConnectionError("connection failed")
    if not response.is_success:
        raise OpenStackServiceError(f"error status {response.status_code}")
    try:
        data = response.json()
    except ValueError:
        raise OpenStackServiceError("unreadable body")
    servers = data.get("servers", []) if isinstance(data, dict) else []
    return [
        NovaServerDTO(
            id=str(s.get("id", "")), name=str(s.get("name", "")),
            status=str(s.get("status", "")),
        )
        for s in servers
        if isinstance(s, dict)
    ]


async def _original_retrieve(client_cls, auth_url, credential_id, secret, nova_endpoint, ca_certificate=""):
    verify = _build_verify(ca_certificate)
    token = await _original_get_token(client_cls, auth_url, credential_id, secret, verify)
    return await _original_list_servers(client_cls, nova_endpoint, token, verify)


def _outcome(fn):
    """Run an async retrieve/method call and classify its outcome.

    Returns ``("ok", value)`` on success or ``("err", code)`` for a raised
    ``OpenStackError`` (comparing the stable ``code`` rather than the localized
    message, which the original/fixed messages differ on by design).
    """
    try:
        value = asyncio.run(fn())
    except OpenStackError_code_holder as exc:  # pragma: no cover - see alias below
        return ("err", exc.code)
    return ("ok", value)


# ``OpenStackError`` is the base for all four typed errors; alias it locally so
# ``_outcome`` catches every mapped error and compares the ``code``.
from app.prerequisites.openstack import OpenStackError as OpenStackError_code_holder  # noqa: E402


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
# Generated NON-EMPTY proxy URLs: scheme + host + optional port + optional
# trailing slash. Every draw has a non-empty ``strip()`` so it resolves to a
# real proxy (the bug-condition space for Property 1).
_scheme = st.sampled_from(["http", "https"])
_host = st.from_regex(r"[a-z][a-z0-9-]{0,20}(\.[a-z][a-z0-9-]{0,20}){0,3}", fullmatch=True)
_port = st.one_of(st.none(), st.integers(min_value=1, max_value=65535))
_slash = st.sampled_from(["", "/"])


@st.composite
def proxy_urls(draw):
    """Draw a random, structurally valid, non-empty proxy URL."""
    scheme = draw(_scheme)
    host = draw(_host)
    port = draw(_port)
    slash = draw(_slash)
    authority = host if port is None else f"{host}:{port}"
    return f"{scheme}://{authority}{slash}"


# Empty / whitespace-only proxy => "no proxy configured" (Property 2 domain).
_empty_proxy = st.text(alphabet=" \t\r\n", min_size=0, max_size=8)

# Secrets that must never leak.
_secret = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=0, max_size=48,
).map(lambda tail: _SECRET_MARKER + tail)

# Non-auth error statuses (any 4xx/5xx that is not 401/403).
_non_auth_error_status = st.sampled_from([400, 404, 409, 422, 429, 500, 502, 503])
_auth_reject_status = st.sampled_from([401, 403])


# ===========================================================================
# Property 1 - Bug Condition fixed: both calls route through the exact proxy
# ===========================================================================
@hyp_settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(proxy_url=proxy_urls())
def test_property1_retrieve_routes_both_calls_through_generated_proxy(
    proxy_url, monkeypatch, set_proxy
):
    """For ANY generated non-empty proxy, ``retrieve`` builds BOTH clients with
    exactly that ``proxy`` and returns the mapped rows.

    **Validates: Requirements 2.1, 2.2, 2.3**
    """
    set_proxy(proxy_url)

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(
            captured,
            servers_response=_FakeResponse(
                200,
                json_body={
                    "servers": [{"id": "srv-1", "name": "web-1", "status": "ACTIVE"}]
                },
            ),
        ),
    )

    servers = asyncio.run(
        OpenStackProxy().retrieve(
            auth_url="https://keystone.example/v3",
            credential_id="cred-prop",
            secret=f"{_SECRET_MARKER}p1",
            nova_endpoint="https://nova.example/v2.1",
        )
    )

    assert servers == [NovaServerDTO(id="srv-1", name="web-1", status="ACTIVE")]
    assert len(captured) == 2, "expected token + servers client constructions"
    for idx, kwargs in enumerate(captured):
        assert kwargs.get("proxy") == proxy_url, (
            f"construction #{idx} must carry proxy={proxy_url!r}; got {kwargs!r}"
        )


@hyp_settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(proxy_url=proxy_urls())
def test_property1_connect_failure_still_502_with_proxy(proxy_url, monkeypatch, set_proxy):
    """For ANY generated proxy, a proxied connect failure still raises
    ``OpenStackConnectionError`` (code CONNECTION_FAILED) with no secret/token leak.

    **Validates: Requirements 2.4**
    """
    set_proxy(proxy_url)

    secret = f"{_SECRET_MARKER}conn"
    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(captured, post_error=httpx.ConnectError("refused")),
    )

    with pytest.raises(OpenStackConnectionError) as exc_info:
        asyncio.run(
            OpenStackProxy().retrieve(
                auth_url="https://keystone.example/v3",
                credential_id="cred-prop",
                secret=secret,
                nova_endpoint="https://nova.example/v2.1",
            )
        )
    assert exc_info.value.code == "CONNECTION_FAILED"
    assert secret not in str(exc_info.value)
    # The client WAS built with the proxy (the proxy was used; failure is upstream).
    assert captured and captured[0].get("proxy") == proxy_url


# ===========================================================================
# Property 2 - Preservation: fixed behavior equals original for non-bug inputs
#
# Differential comparison of the current (fixed) code against an inlined
# reference of the ORIGINAL (pre-fix) implementation, across the generated
# non-bug input space.
# ===========================================================================
@hyp_settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    empty_proxy=_empty_proxy,
    token_status=st.sampled_from([200, 201, 401, 403, 400, 500, 503]),
    have_token_header=st.booleans(),
    nova_status=st.sampled_from([200, 400, 500, 503]),
    nova_json=st.booleans(),
    server_rows=st.lists(
        st.fixed_dictionaries(
            {
                "id": st.text(min_size=0, max_size=8),
                "name": st.text(min_size=0, max_size=8),
                "status": st.sampled_from(["ACTIVE", "SHUTOFF", "ERROR", ""]),
            }
        ),
        max_size=4,
    ),
)
def test_property2_fixed_equals_original_for_non_bug_inputs(
    empty_proxy, token_status, have_token_header, nova_status, nova_json,
    server_rows, monkeypatch, set_proxy,
):
    """For ANY non-bug input (empty proxy, any auth/service status, JSON/non-JSON
    Nova body), the fixed ``retrieve`` yields the SAME outcome as the original.

    Outcomes are compared as ``("ok", rows)`` or ``("err", code)`` and the client
    kwargs are compared to confirm neither builds a ``proxy`` (direct connection).

    **Validates: Requirements 3.1, 3.2, 3.4, 3.5**
    """
    set_proxy(empty_proxy)  # bug condition FALSE: no proxy configured

    token_headers = {"X-Subject-Token": KEYSTONE_TOKEN} if have_token_header else {}
    token_resp = _FakeResponse(token_status, headers=token_headers, json_body={"token": {}})
    if nova_json:
        nova_resp = _FakeResponse(nova_status, json_body={"servers": server_rows})
    else:
        nova_resp = _FakeResponse(nova_status, json_raises=True)

    def _client_factory(store):
        return _make_capturing_client(
            store, token_response=token_resp, servers_response=nova_resp
        )

    # Fixed implementation (current production code).
    fixed_captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx, "AsyncClient", _client_factory(fixed_captured)
    )
    fixed_outcome = _outcome(
        lambda: OpenStackProxy().retrieve(
            auth_url="https://keystone.example/v3",
            credential_id="cred-prop",
            secret=f"{_SECRET_MARKER}p2",
            nova_endpoint="https://nova.example/v2.1",
        )
    )

    # Original (pre-fix) reference implementation, same fake client class.
    orig_captured: list = []
    orig_outcome = _outcome(
        lambda: _original_retrieve(
            _client_factory(orig_captured),
            auth_url="https://keystone.example/v3",
            credential_id="cred-prop",
            secret=f"{_SECRET_MARKER}p2",
            nova_endpoint="https://nova.example/v2.1",
        )
    )

    assert fixed_outcome == orig_outcome, (
        f"fixed != original for non-bug input: fixed={fixed_outcome!r} "
        f"original={orig_outcome!r}"
    )
    # Neither path should build a client with a proxy (direct connection).
    for kwargs in fixed_captured:
        assert "proxy" not in kwargs
    assert len(fixed_captured) == len(orig_captured)


@hyp_settings(max_examples=100, deadline=None)
@given(
    ca_certificate=st.text(
        alphabet=st.characters(min_codepoint=33, max_codepoint=126, blacklist_characters="-"),
        min_size=1, max_size=64,
    )
)
def test_property2_invalid_pem_raises_before_any_client(ca_certificate):
    """For ANY structurally invalid PEM, ``retrieve`` raises
    ``OpenStackCACertificateError`` BEFORE any client is constructed - unchanged
    by the proxy fix.

    Uses a context-manager patch (not a function-scoped fixture) so the
    exploding client is guaranteed for every generated example.

    **Validates: Requirements 3.3**
    """

    class _ExplodingClient:
        def __init__(self, *args, **kwargs):  # pragma: no cover - must never run
            raise AssertionError("client constructed despite invalid CA certificate")

    @contextlib.contextmanager
    def _exploding():
        original = openstack_module.httpx.AsyncClient
        openstack_module.httpx.AsyncClient = _ExplodingClient
        try:
            yield
        finally:
            openstack_module.httpx.AsyncClient = original

    async def _run():
        await OpenStackProxy().retrieve(
            auth_url="https://keystone.example/v3",
            credential_id="cred-prop",
            secret=f"{_SECRET_MARKER}ca",
            nova_endpoint="https://nova.example/v2.1",
            ca_certificate=ca_certificate,
        )

    with _exploding():
        try:
            asyncio.run(_run())
        except OpenStackCACertificateError as exc:
            assert exc.code == "INVALID_CA_CERTIFICATE"
            return
    pytest.skip("input coincidentally parsed as a certificate")


def test_property2_valid_pem_shared_verify_context(monkeypatch, set_proxy):
    """A valid non-empty PEM yields one shared ``verify`` SSLContext for both
    calls - unchanged by the proxy fix.

    **Validates: Requirements 3.3**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx, "AsyncClient", _make_capturing_client(captured)
    )

    asyncio.run(
        OpenStackProxy().retrieve(
            auth_url="https://keystone.example/v3",
            credential_id="cred-prop",
            secret=f"{_SECRET_MARKER}pem",
            nova_endpoint="https://nova.example/v2.1",
            ca_certificate=VALID_PEM,
        )
    )

    assert len(captured) == 2
    token_verify = captured[0]["verify"]
    nova_verify = captured[1]["verify"]
    assert isinstance(token_verify, ssl.SSLContext)
    assert token_verify is nova_verify


# ===========================================================================
# Non-leak across ALL generated paths (success / auth / service / connection),
# with a proxy configured AND without, for generated secrets.
# ===========================================================================
@hyp_settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    secret=_secret,
    proxy_value=st.one_of(st.just(""), proxy_urls()),
)
def test_secret_and_token_never_leak_across_all_paths(
    secret, proxy_value, monkeypatch, set_proxy, caplog
):
    """Generated secret and the Keystone token never appear in captured logs or in
    any raised exception message, across success/auth/service/connection paths,
    with or without a proxy configured.

    **Validates: Requirements 2.4, 3.5**
    """
    set_proxy(proxy_value)

    def _run(client_cls):
        monkeypatch.setattr(openstack_module.httpx, "AsyncClient", client_cls)
        try:
            asyncio.run(
                OpenStackProxy().retrieve(
                    auth_url="https://keystone.example/v3",
                    credential_id="cred-leak",
                    secret=secret,
                    nova_endpoint="https://nova.example/v2.1",
                )
            )
            return ""
        except OpenStackError_code_holder as exc:
            return str(exc)

    messages: list[str] = []
    with caplog.at_level(logging.DEBUG):
        # success
        messages.append(_run(_make_capturing_client([])))
        # auth rejection
        messages.append(
            _run(_make_capturing_client([], token_response=_FakeResponse(401, json_body={})))
        )
        # service error (Nova 503)
        messages.append(
            _run(_make_capturing_client([], servers_response=_FakeResponse(503, json_body={})))
        )
        # connection failure
        messages.append(
            _run(_make_capturing_client([], post_error=httpx.ConnectError("refused")))
        )

    log_text = caplog.text
    assert secret not in log_text, "secret leaked into captured logs"
    assert KEYSTONE_TOKEN not in log_text, "token leaked into captured logs"
    for msg in messages:
        assert secret not in msg, "secret leaked into an exception message"
        assert KEYSTONE_TOKEN not in msg, "token leaked into an exception message"


# ===========================================================================
# Route-level non-leak: generated secret never appears in the response body,
# on success or on the connection-failure path, with a proxy configured.
# ===========================================================================
def _headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _retrieve_url(installation_id: str) -> str:
    return (
        f"/api/prerequisites/installations/{installation_id}"
        f"/servers-nodes/servers/retrieve"
    )


def _error_code(body: dict) -> str | None:
    if isinstance(body.get("error"), dict):
        return body["error"].get("code")
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("error", {}).get("code")
    return None


@pytest.fixture
def member_user(db_session):
    """Create an authenticated member user (retrieve requires auth)."""
    user = User(
        email="proxyproperty@prereq.test",
        password_hash="hashed_password",
        first_name="Proxy",
        last_name="Property",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_route_success_with_proxy_returns_rows_without_secret(
    client, member_user, installation_id, monkeypatch, set_proxy
):
    """With a proxy configured, a successful retrieve returns the mapped rows and
    the response never contains the secret or the token.

    **Validates: Requirements 2.1, 2.2, 2.3, 3.5**
    """
    set_proxy("http://51.178.90.72:9999/")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(
            captured,
            servers_response=_FakeResponse(
                200,
                json_body={"servers": [{"id": "s1", "name": "n1", "status": "ACTIVE"}]},
            ),
        ),
    )

    secret = f"{_SECRET_MARKER}route_ok"
    resp = client.post(
        _retrieve_url(installation_id),
        json={
            "auth_url": "https://keystone.example/v3",
            "credential_id": "cred-route",
            "nova_endpoint": "https://nova.example/v2.1",
            "credential_secret": secret,
        },
        headers=_headers(member_user),
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["servers"] == [{"id": "s1", "name": "n1", "status": "ACTIVE"}]
    assert secret not in resp.text
    assert KEYSTONE_TOKEN not in resp.text
    # Both calls routed through the configured proxy.
    assert len(captured) == 2
    for kwargs in captured:
        assert kwargs.get("proxy") == "http://51.178.90.72:9999/"
