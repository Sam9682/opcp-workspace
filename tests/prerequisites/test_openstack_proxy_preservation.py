"""Preservation property tests for the OpenStack forward-proxy fix.

Spec: .kiro/specs/openstack-proxy-connection (task 2)

Property 2: Preservation - behavior unchanged without a proxy and across all
existing code paths.

**These tests are EXPECTED TO PASS on the UNFIXED code.** They pin the baseline
behavior that the upcoming fix (tasks 3.1/3.2) must preserve: when no proxy is
configured, both OpenStack calls build a client with NO ``proxy`` key (direct
connection), and the auth / CA / service-error / non-leak behaviors are all
unchanged regardless of the proxy setting.

Methodology (observation-first): each property was first run against the current
(unfixed) ``app/prerequisites/openstack.py`` to observe the actual outputs, then
those observations were encoded as assertions here. No production code is
modified by this task.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 2.4**

Design references:
- isBugCondition is FALSE for every input here (empty/whitespace proxy, or a
  path unrelated to transport routing), so the fixed code must match the
  original (design.md, Property 2 / Preservation Requirements).
- Preservation Requirements: direct connection when proxy empty (3.1); 401/403
  -> OpenStackAuthError -> 401 AUTH_FAILED (3.2); invalid PEM ->
  OpenStackCACertificateError before any client, valid PEM -> shared verify
  (3.3); non-auth status / unreadable body -> OpenStackServiceError -> 502
  OPENSTACK_ERROR (3.4); secret/token never logged/returned (3.5, 2.4).

Approach (matches the existing openstack tests):
- Patch ``settings.OPENSTACK_HTTPS_PROXY`` robustly through ``object.__setattr__``
  so the tests run whether or not the field exists yet on the unfixed Settings
  (the field is added in task 3.1). ``_resolve_proxy`` (added in task 3.2) reads
  it via ordinary attribute access; before the fix nothing reads it, so an empty
  value simply preserves today's proxy-less client construction.
- Replace ``httpx.AsyncClient`` on the ``openstack`` module namespace with a fake
  async client that records the FULL constructor kwargs, so the presence/absence
  of ``proxy`` can be asserted directly. No real network or proxy is used.
"""
import asyncio
import contextlib
import logging

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
    OpenStackServiceError,
    _build_verify,
)
from app.auth.token import create_access_token


# A Keystone token we assert is never echoed to the client or into logs. The
# real proxy reads it from the ``X-Subject-Token`` header and keeps it local.
KEYSTONE_TOKEN = "gAAAAA-preservation-keystone-subject-token"

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
    """Inject ``settings.OPENSTACK_HTTPS_PROXY`` robustly, on fixed OR unfixed code.

    On the UNFIXED code the field does not exist yet (added in task 3.1) and the
    pydantic ``Settings`` uses ``extra="ignore"``, which rejects setting an
    unknown field via normal attribute assignment. So we set the value through
    ``object.__setattr__`` (bypassing pydantic's field guard) and restore the
    previous state afterwards. This mirrors the exploration test's fixture.
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
):
    """Fake ``httpx.AsyncClient`` recording each construction's full kwargs.

    ``captured_kwargs`` is a shared list; every construction appends the full
    keyword dict it received (so the presence/absence of ``proxy`` and the
    ``verify`` value can be asserted). ``post`` returns ``token_response`` (or a
    default success token) and ``get`` returns ``servers_response`` (or an empty
    Nova list). ``post_error`` (an ``httpx`` exception) is raised from ``post``
    when supplied.
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
            return servers_response if servers_response is not None else default_servers

    return _Client


def _headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _retrieve_url(installation_id: str) -> str:
    return (
        f"/api/prerequisites/installations/{installation_id}"
        f"/servers-nodes/servers/retrieve"
    )


def _error_code(body: dict) -> str | None:
    """Extract the structured error code from a router error body."""
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
        email="proxypreserve@prereq.test",
        password_hash="hashed_password",
        first_name="Proxy",
        last_name="Preserve",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# Whitespace-only / empty proxy values collapse to "no proxy configured". Mapping
# arbitrary whitespace text keeps Hypothesis drawing distinct examples across the
# full run rather than short-circuiting on a single value.
_EMPTY_PROXY = st.text(alphabet=" \t\r\n", min_size=0, max_size=8)

# A distinctive secret marker so a substring match in a response/log means the
# real secret value leaked verbatim, not an incidental collision with a UUID.
_SECRET_MARKER = "OS_PROXY_PRESERVE_SECRET_"
_SECRET = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=0,
    max_size=48,
).map(lambda tail: _SECRET_MARKER + tail)


# ===========================================================================
# Case 1 - No-proxy direct connection preserved (Req 3.1)
#
# For ALL empty / whitespace-only proxy values, both _get_token and
# _list_servers build a client with NO ``proxy`` key (direct connection).
# ===========================================================================
@hyp_settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(proxy_value=_EMPTY_PROXY)
def test_get_token_no_proxy_key_when_proxy_empty(proxy_value, monkeypatch, set_proxy):
    """With an empty/whitespace proxy, ``_get_token`` builds a client with no proxy.

    Pins the "empty means direct" rule: the direct-connection client construction
    carries no ``proxy`` key today and must continue to after the fix.

    **Validates: Requirements 3.1**
    """
    set_proxy(proxy_value)

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx, "AsyncClient", _make_capturing_client(captured)
    )

    asyncio.run(
        OpenStackProxy()._get_token(
            auth_url="https://keystone.example/v3",
            credential_id="cred-preserve",
            secret="preserve-secret",
        )
    )

    assert len(captured) == 1
    assert "proxy" not in captured[0], (
        f"empty proxy must yield a direct connection with no 'proxy' key; "
        f"captured kwargs={captured[0]!r}"
    )


@hyp_settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(proxy_value=_EMPTY_PROXY)
def test_list_servers_no_proxy_key_when_proxy_empty(proxy_value, monkeypatch, set_proxy):
    """With an empty/whitespace proxy, ``_list_servers`` builds a client with no proxy.

    **Validates: Requirements 3.1**
    """
    set_proxy(proxy_value)

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx, "AsyncClient", _make_capturing_client(captured)
    )

    servers = asyncio.run(
        OpenStackProxy()._list_servers(
            nova_endpoint="https://nova.example/v2.1",
            token=KEYSTONE_TOKEN,
        )
    )

    assert servers == []
    assert len(captured) == 1
    assert "proxy" not in captured[0], (
        f"empty proxy must yield a direct connection with no 'proxy' key; "
        f"captured kwargs={captured[0]!r}"
    )


def test_retrieve_no_proxy_builds_both_clients_without_proxy(monkeypatch, set_proxy):
    """End-to-end with no proxy: BOTH clients are built with no ``proxy`` key.

    **Validates: Requirements 3.1**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx, "AsyncClient", _make_capturing_client(captured)
    )

    servers = asyncio.run(
        OpenStackProxy().retrieve(
            auth_url="https://keystone.example/v3",
            credential_id="cred-preserve",
            secret="preserve-secret",
            nova_endpoint="https://nova.example/v2.1",
        )
    )

    assert servers == []
    assert len(captured) == 2
    for idx, kwargs in enumerate(captured):
        assert "proxy" not in kwargs, (
            f"construction #{idx} must have no 'proxy' key with an empty proxy; "
            f"captured kwargs={kwargs!r}"
        )


# ===========================================================================
# Case 2 - Auth rejection preserved (Req 3.2)
#
# A 401/403 token response raises OpenStackAuthError -> HTTP 401 AUTH_FAILED,
# regardless of the proxy setting (empty or non-empty).
# ===========================================================================
@hyp_settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    reject_status=st.sampled_from([401, 403]),
    proxy_value=st.sampled_from(["", "   ", "http://proxy.internal:3128"]),
)
def test_auth_rejection_raises_auth_error_regardless_of_proxy(
    reject_status, proxy_value, monkeypatch, set_proxy
):
    """A 401/403 Keystone response raises ``OpenStackAuthError`` (code AUTH_FAILED).

    Holds for any proxy setting, empty or not, since auth mapping is independent
    of transport routing.

    **Validates: Requirements 3.2**
    """
    set_proxy(proxy_value)

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(
            captured,
            token_response=_FakeResponse(reject_status, json_body={"error": "denied"}),
        ),
    )

    with pytest.raises(OpenStackAuthError) as exc_info:
        asyncio.run(
            OpenStackProxy()._get_token(
                auth_url="https://keystone.example/v3",
                credential_id="cred-preserve",
                secret="preserve-secret",
            )
        )
    assert exc_info.value.code == "AUTH_FAILED"


def test_route_auth_rejection_returns_401_auth_failed(
    client, member_user, installation_id, monkeypatch, set_proxy
):
    """The route maps a Keystone 401 to HTTP 401 ``AUTH_FAILED`` (proxy empty).

    **Validates: Requirements 3.2**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(
            captured, token_response=_FakeResponse(401, json_body={})
        ),
    )

    secret = "route-auth-secret"
    resp = client.post(
        _retrieve_url(installation_id),
        json={
            "auth_url": "https://keystone.example/v3",
            "credential_id": "cred-auth",
            "nova_endpoint": "https://nova.example/v2.1",
            "credential_secret": secret,
        },
        headers=_headers(member_user),
    )

    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert _error_code(resp.json()) == "AUTH_FAILED"
    assert secret not in resp.text
    assert KEYSTONE_TOKEN not in resp.text


# ===========================================================================
# Case 3 - CA handling preserved (Req 3.3)
#
# Invalid PEM raises OpenStackCACertificateError before any client is built;
# a valid non-empty PEM yields a shared ssl verify context used by both calls.
# ===========================================================================
# Non-PEM text: excluding the hyphen guarantees no PEM armor can appear, so the
# value is structurally invalid.
_NON_PEM_TEXT = st.text(
    alphabet=st.characters(
        min_codepoint=33, max_codepoint=126, blacklist_characters="-"
    ),
    min_size=1,
    max_size=64,
)


class _ExplodingAsyncClient:
    """Spy that fails the test if any client is constructed (no outbound call)."""

    def __init__(self, *args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError(
            "httpx.AsyncClient was constructed despite an invalid CA certificate"
        )


@contextlib.contextmanager
def _exploding_httpx_client():
    """Temporarily replace ``httpx.AsyncClient`` with the exploding spy.

    Used as a context manager rather than the ``monkeypatch`` fixture so the
    patch is self-contained per example (Hypothesis does not reset
    function-scoped fixtures between generated examples).
    """
    original = openstack_module.httpx.AsyncClient
    openstack_module.httpx.AsyncClient = _ExplodingAsyncClient
    try:
        yield
    finally:
        openstack_module.httpx.AsyncClient = original


@hyp_settings(max_examples=100, deadline=None)
@given(ca_certificate=_NON_PEM_TEXT)
def test_invalid_pem_raises_before_any_client(ca_certificate):
    """Invalid PEM raises ``OpenStackCACertificateError`` before any client is built.

    **Validates: Requirements 3.3**
    """

    async def _run():
        await OpenStackProxy().retrieve(
            auth_url="https://keystone.example/v3",
            credential_id="cred-preserve",
            secret="preserve-secret",
            nova_endpoint="https://nova.example/v2.1",
            ca_certificate=ca_certificate,
        )

    with _exploding_httpx_client():
        try:
            asyncio.run(_run())
        except OpenStackCACertificateError as exc:
            assert exc.code == "INVALID_CA_CERTIFICATE"
            return
    # A value that coincidentally parsed is not a valid invalid-PEM counterexample.
    pytest.skip("input coincidentally parsed as a certificate")


def test_valid_pem_shared_verify_context_across_both_calls(monkeypatch, set_proxy):
    """A valid non-empty PEM yields a single shared ``verify`` context for both calls.

    The ``verify`` value built once in ``retrieve`` is the SAME SSLContext object
    passed to both the Keystone and Nova client constructions.

    **Validates: Requirements 3.3**
    """
    import ssl

    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx, "AsyncClient", _make_capturing_client(captured)
    )

    asyncio.run(
        OpenStackProxy().retrieve(
            auth_url="https://keystone.example/v3",
            credential_id="cred-preserve",
            secret="preserve-secret",
            nova_endpoint="https://nova.example/v2.1",
            ca_certificate=VALID_PEM,
        )
    )

    assert len(captured) == 2
    token_verify = captured[0]["verify"]
    nova_verify = captured[1]["verify"]
    assert isinstance(token_verify, ssl.SSLContext)
    # Same object built once and shared by both calls.
    assert token_verify is nova_verify


# ===========================================================================
# Case 4 - Service error preserved (Req 3.4)
#
# A non-auth error status (token OR Nova) and a non-JSON Nova body each raise
# OpenStackServiceError -> HTTP 502 OPENSTACK_ERROR.
# ===========================================================================
# Non-auth error statuses: any 4xx/5xx that is not 401/403.
_NON_AUTH_ERROR_STATUS = st.sampled_from([400, 404, 429, 500, 502, 503])


@hyp_settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(error_status=_NON_AUTH_ERROR_STATUS)
def test_token_non_auth_error_raises_service_error(error_status, monkeypatch, set_proxy):
    """A non-auth error status on the token call raises ``OpenStackServiceError``.

    **Validates: Requirements 3.4**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(
            captured, token_response=_FakeResponse(error_status, json_body={})
        ),
    )

    with pytest.raises(OpenStackServiceError) as exc_info:
        asyncio.run(
            OpenStackProxy()._get_token(
                auth_url="https://keystone.example/v3",
                credential_id="cred-preserve",
                secret="preserve-secret",
            )
        )
    assert exc_info.value.code == "OPENSTACK_ERROR"


@hyp_settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(error_status=_NON_AUTH_ERROR_STATUS)
def test_nova_non_auth_error_raises_service_error(error_status, monkeypatch, set_proxy):
    """A non-auth error status on the Nova call raises ``OpenStackServiceError``.

    **Validates: Requirements 3.4**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(
            captured, servers_response=_FakeResponse(error_status, json_body={})
        ),
    )

    with pytest.raises(OpenStackServiceError) as exc_info:
        asyncio.run(
            OpenStackProxy()._list_servers(
                nova_endpoint="https://nova.example/v2.1",
                token=KEYSTONE_TOKEN,
            )
        )
    assert exc_info.value.code == "OPENSTACK_ERROR"


def test_nova_non_json_body_raises_service_error(monkeypatch, set_proxy):
    """A 2xx Nova response with a non-JSON body raises ``OpenStackServiceError``.

    **Validates: Requirements 3.4**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(
            captured, servers_response=_FakeResponse(200, json_raises=True)
        ),
    )

    with pytest.raises(OpenStackServiceError) as exc_info:
        asyncio.run(
            OpenStackProxy()._list_servers(
                nova_endpoint="https://nova.example/v2.1",
                token=KEYSTONE_TOKEN,
            )
        )
    assert exc_info.value.code == "OPENSTACK_ERROR"


def test_route_service_error_returns_502_openstack_error(
    client, member_user, installation_id, monkeypatch, set_proxy
):
    """The route maps a Nova 503 to HTTP 502 ``OPENSTACK_ERROR`` (proxy empty).

    **Validates: Requirements 3.4**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(
            captured, servers_response=_FakeResponse(503, json_body={})
        ),
    )

    secret = "route-service-secret"
    resp = client.post(
        _retrieve_url(installation_id),
        json={
            "auth_url": "https://keystone.example/v3",
            "credential_id": "cred-svc",
            "nova_endpoint": "https://nova.example/v2.1",
            "credential_secret": secret,
        },
        headers=_headers(member_user),
    )

    assert resp.status_code == status.HTTP_502_BAD_GATEWAY
    assert _error_code(resp.json()) == "OPENSTACK_ERROR"
    assert secret not in resp.text
    assert KEYSTONE_TOKEN not in resp.text


# ===========================================================================
# Case 5 - Non-leak preserved (Req 3.5, 2.4)
#
# Across success and every error path, generated secrets/tokens never appear in
# captured logs, exception messages, or the response body.
# ===========================================================================
@hyp_settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(secret=_SECRET)
def test_secret_and_token_never_in_logs_or_exception_messages(
    secret, monkeypatch, set_proxy, caplog
):
    """Across success/auth/service/connection paths, the secret and token never
    appear in captured logs or in any raised exception message.

    **Validates: Requirements 3.5, 2.4**
    """
    set_proxy("")

    def _run_success():
        captured: list = []
        monkeypatch.setattr(
            openstack_module.httpx, "AsyncClient", _make_capturing_client(captured)
        )
        asyncio.run(
            OpenStackProxy().retrieve(
                auth_url="https://keystone.example/v3",
                credential_id="cred-leak",
                secret=secret,
                nova_endpoint="https://nova.example/v2.1",
            )
        )

    def _run_auth():
        captured: list = []
        monkeypatch.setattr(
            openstack_module.httpx,
            "AsyncClient",
            _make_capturing_client(
                captured, token_response=_FakeResponse(401, json_body={})
            ),
        )
        try:
            asyncio.run(
                OpenStackProxy().retrieve(
                    auth_url="https://keystone.example/v3",
                    credential_id="cred-leak",
                    secret=secret,
                    nova_endpoint="https://nova.example/v2.1",
                )
            )
        except OpenStackAuthError as exc:
            return str(exc)
        return ""

    def _run_service():
        captured: list = []
        monkeypatch.setattr(
            openstack_module.httpx,
            "AsyncClient",
            _make_capturing_client(
                captured, servers_response=_FakeResponse(503, json_body={})
            ),
        )
        try:
            asyncio.run(
                OpenStackProxy().retrieve(
                    auth_url="https://keystone.example/v3",
                    credential_id="cred-leak",
                    secret=secret,
                    nova_endpoint="https://nova.example/v2.1",
                )
            )
        except OpenStackServiceError as exc:
            return str(exc)
        return ""

    def _run_connection():
        captured: list = []
        monkeypatch.setattr(
            openstack_module.httpx,
            "AsyncClient",
            _make_capturing_client(
                captured, post_error=httpx.ConnectError("refused")
            ),
        )
        try:
            asyncio.run(
                OpenStackProxy().retrieve(
                    auth_url="https://keystone.example/v3",
                    credential_id="cred-leak",
                    secret=secret,
                    nova_endpoint="https://nova.example/v2.1",
                )
            )
        except Exception as exc:  # OpenStackConnectionError
            return str(exc)
        return ""

    messages: list[str] = []
    with caplog.at_level(logging.DEBUG):
        _run_success()
        messages.append(_run_auth())
        messages.append(_run_service())
        messages.append(_run_connection())

    log_text = caplog.text
    assert secret not in log_text, "secret leaked into captured logs"
    assert KEYSTONE_TOKEN not in log_text, "keystone token leaked into captured logs"
    for msg in messages:
        assert secret not in msg, "secret leaked into an exception message"
        assert KEYSTONE_TOKEN not in msg, "keystone token leaked into an exception message"


def test_success_response_body_excludes_secret_and_token(
    client, member_user, installation_id, monkeypatch, set_proxy
):
    """A successful retrieve response never contains the secret or the token.

    **Validates: Requirements 3.5, 2.4**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(
            captured,
            servers_response=_FakeResponse(
                200,
                json_body={
                    "servers": [
                        {"id": "srv-1", "name": "web-1", "status": "ACTIVE"}
                    ]
                },
            ),
        ),
    )

    secret = "route-success-secret"
    resp = client.post(
        _retrieve_url(installation_id),
        json={
            "auth_url": "https://keystone.example/v3",
            "credential_id": "cred-ok",
            "nova_endpoint": "https://nova.example/v2.1",
            "credential_secret": secret,
        },
        headers=_headers(member_user),
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["servers"] == [
        {"id": "srv-1", "name": "web-1", "status": "ACTIVE"}
    ]
    assert secret not in resp.text
    assert KEYSTONE_TOKEN not in resp.text
