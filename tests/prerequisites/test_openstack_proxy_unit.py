"""Unit tests for the OpenStack forward-proxy fix.

Spec: .kiro/specs/openstack-proxy-connection (task 4.1)

Focused, example-based unit tests for the pieces the fix touches:

- ``_resolve_proxy`` returns ``None`` for empty/whitespace-only settings and the
  URL otherwise.
- ``_get_token`` builds the client WITH ``proxy=`` when a proxy is configured and
  WITHOUT a ``proxy`` key when it is empty; reads the token from the
  ``X-Subject-Token`` header; maps 401/403 -> ``OpenStackAuthError`` and other
  non-2xx -> ``OpenStackServiceError``.
- ``_list_servers`` builds the client WITH ``proxy=`` when configured and WITHOUT
  it when empty; maps each Nova server to ``{id, name, status}``; maps
  connect/timeout -> ``OpenStackConnectionError`` and non-2xx ->
  ``OpenStackServiceError``; and handles a non-JSON body.
- ``Settings`` reads ``OPENSTACK_HTTPS_PROXY`` and the aliased ``https_proxy`` /
  ``http_proxy`` environment variables.

**Validates: Requirements 2.1, 2.2, 3.1, 3.2, 3.4**

Approach (matches the existing openstack proxy tests):
- ``settings.OPENSTACK_HTTPS_PROXY`` is injected via a robust fixture using
  ``object.__setattr__`` (the same pattern used by the exploration/preservation
  tests) so the resolver reads a known value regardless of process env.
- ``httpx.AsyncClient`` on the ``openstack`` module namespace is replaced with a
  fake async client recording the FULL constructor kwargs, so the presence /
  absence and value of ``proxy`` can be asserted directly. No real network,
  proxy, or environment mutation of ``os.environ`` is required for the method
  tests. The ``Settings`` tests construct a fresh ``Settings`` with explicit env
  vars to exercise the alias resolution.
"""
import asyncio

import httpx
import pytest

from app.config import settings, Settings
from app.prerequisites import openstack as openstack_module
from app.prerequisites.openstack import (
    OpenStackProxy,
    OpenStackAuthError,
    OpenStackConnectionError,
    OpenStackServiceError,
    NovaServerDTO,
    _resolve_proxy,
)


# A Keystone token asserted to flow through the proxy but never leaked.
KEYSTONE_TOKEN = "gAAAAA-unit-keystone-subject-token"

# A concrete configured proxy URL used across the "proxy set" cases.
PROXY_URL = "http://proxy.internal:3128"

# Sentinel marking "this attribute did not exist before the test" so cleanup can
# remove it again rather than restoring a bogus value.
_MISSING = object()


@pytest.fixture
def set_proxy(monkeypatch):
    """Inject ``settings.OPENSTACK_HTTPS_PROXY`` and restore afterwards.

    Uses ``object.__setattr__`` so the value is applied directly on the singleton
    settings instance without depending on process env, mirroring the fixture in
    the exploration/preservation tests. ``_resolve_proxy`` reads the field via
    ordinary attribute access.
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


# ===========================================================================
# _resolve_proxy (Req 2.1, 2.2, 3.1)
# ===========================================================================
@pytest.mark.parametrize("value", ["", " ", "   ", "\t", "\n", " \r\n\t "])
def test_resolve_proxy_returns_none_for_empty_or_whitespace(value, set_proxy):
    """Empty / whitespace-only proxy settings resolve to ``None`` (direct).

    **Validates: Requirements 3.1**
    """
    set_proxy(value)
    assert _resolve_proxy() is None


@pytest.mark.parametrize(
    "value",
    [
        "http://proxy.internal:3128",
        "https://secure-proxy.example:443",
        "http://51.178.90.72:9999/",
    ],
)
def test_resolve_proxy_returns_url_when_configured(value, set_proxy):
    """A non-empty proxy setting resolves to that exact URL.

    **Validates: Requirements 2.1, 2.2**
    """
    set_proxy(value)
    assert _resolve_proxy() == value


def test_resolve_proxy_preserves_internal_whitespace(set_proxy):
    """A URL with surrounding whitespace is still non-empty and returned verbatim.

    ``_resolve_proxy`` only checks that ``strip()`` is truthy; it returns the
    original (unstripped) value so the caller passes exactly what was configured.

    **Validates: Requirements 2.1**
    """
    set_proxy("  http://proxy.internal:3128  ")
    assert _resolve_proxy() == "  http://proxy.internal:3128  "


# ===========================================================================
# _get_token (Req 2.1, 3.1, 3.2, 3.4)
# ===========================================================================
def test_get_token_builds_client_with_proxy_when_configured(monkeypatch, set_proxy):
    """With a proxy configured, ``_get_token`` builds the client with ``proxy=``.

    **Validates: Requirements 2.1**
    """
    set_proxy(PROXY_URL)

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx, "AsyncClient", _make_capturing_client(captured)
    )

    token = asyncio.run(
        OpenStackProxy()._get_token(
            auth_url="https://keystone.example/v3",
            credential_id="cred-unit",
            secret="unit-secret",
        )
    )

    assert token == KEYSTONE_TOKEN
    assert len(captured) == 1
    assert captured[0].get("proxy") == PROXY_URL


def test_get_token_builds_client_without_proxy_when_empty(monkeypatch, set_proxy):
    """With an empty proxy, ``_get_token`` builds the client with no ``proxy`` key.

    **Validates: Requirements 3.1**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx, "AsyncClient", _make_capturing_client(captured)
    )

    asyncio.run(
        OpenStackProxy()._get_token(
            auth_url="https://keystone.example/v3",
            credential_id="cred-unit",
            secret="unit-secret",
        )
    )

    assert len(captured) == 1
    assert "proxy" not in captured[0]


def test_get_token_reads_token_from_x_subject_token_header(monkeypatch, set_proxy):
    """The token is read from the ``X-Subject-Token`` response header.

    **Validates: Requirements 2.1**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(
            captured,
            token_response=_FakeResponse(
                200,
                headers={"X-Subject-Token": "header-token-value"},
                json_body={"token": {}},
            ),
        ),
    )

    token = asyncio.run(
        OpenStackProxy()._get_token(
            auth_url="https://keystone.example/v3",
            credential_id="cred-unit",
            secret="unit-secret",
        )
    )
    assert token == "header-token-value"


def test_get_token_missing_header_raises_service_error(monkeypatch, set_proxy):
    """A 2xx response without ``X-Subject-Token`` raises ``OpenStackServiceError``.

    **Validates: Requirements 3.4**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(
            captured, token_response=_FakeResponse(201, headers={}, json_body={})
        ),
    )

    with pytest.raises(OpenStackServiceError) as exc_info:
        asyncio.run(
            OpenStackProxy()._get_token(
                auth_url="https://keystone.example/v3",
                credential_id="cred-unit",
                secret="unit-secret",
            )
        )
    assert exc_info.value.code == "OPENSTACK_ERROR"


@pytest.mark.parametrize("reject_status", [401, 403])
def test_get_token_401_403_raises_auth_error(reject_status, monkeypatch, set_proxy):
    """A 401/403 token response raises ``OpenStackAuthError`` (code AUTH_FAILED).

    **Validates: Requirements 3.2**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(
            captured, token_response=_FakeResponse(reject_status, json_body={})
        ),
    )

    with pytest.raises(OpenStackAuthError) as exc_info:
        asyncio.run(
            OpenStackProxy()._get_token(
                auth_url="https://keystone.example/v3",
                credential_id="cred-unit",
                secret="unit-secret",
            )
        )
    assert exc_info.value.code == "AUTH_FAILED"


@pytest.mark.parametrize("error_status", [400, 404, 429, 500, 503])
def test_get_token_non_2xx_raises_service_error(error_status, monkeypatch, set_proxy):
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
                credential_id="cred-unit",
                secret="unit-secret",
            )
        )
    assert exc_info.value.code == "OPENSTACK_ERROR"


@pytest.mark.parametrize(
    "network_error",
    [httpx.ConnectError("refused"), httpx.TimeoutException("timed out")],
)
def test_get_token_connect_timeout_raises_connection_error(
    network_error, monkeypatch, set_proxy
):
    """Connect/timeout failures on the token call raise ``OpenStackConnectionError``.

    **Validates: Requirements 3.4**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(captured, post_error=network_error),
    )

    with pytest.raises(OpenStackConnectionError) as exc_info:
        asyncio.run(
            OpenStackProxy()._get_token(
                auth_url="https://keystone.example/v3",
                credential_id="cred-unit",
                secret="unit-secret",
            )
        )
    assert exc_info.value.code == "CONNECTION_FAILED"


# ===========================================================================
# _list_servers (Req 2.2, 3.1, 3.4)
# ===========================================================================
def test_list_servers_builds_client_with_proxy_when_configured(monkeypatch, set_proxy):
    """With a proxy configured, ``_list_servers`` builds the client with ``proxy=``.

    **Validates: Requirements 2.2**
    """
    set_proxy(PROXY_URL)

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
    assert captured[0].get("proxy") == PROXY_URL


def test_list_servers_builds_client_without_proxy_when_empty(monkeypatch, set_proxy):
    """With an empty proxy, ``_list_servers`` builds the client with no ``proxy`` key.

    **Validates: Requirements 3.1**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx, "AsyncClient", _make_capturing_client(captured)
    )

    asyncio.run(
        OpenStackProxy()._list_servers(
            nova_endpoint="https://nova.example/v2.1",
            token=KEYSTONE_TOKEN,
        )
    )

    assert len(captured) == 1
    assert "proxy" not in captured[0]


def test_list_servers_maps_servers_to_id_name_status(monkeypatch, set_proxy):
    """Each Nova server maps to a ``{id, name, status}`` DTO.

    **Validates: Requirements 2.2**
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
                        {"id": "srv-1", "name": "web-1", "status": "ACTIVE"},
                        {"id": "srv-2", "name": "db-1", "status": "SHUTOFF"},
                    ]
                },
            ),
        ),
    )

    servers = asyncio.run(
        OpenStackProxy()._list_servers(
            nova_endpoint="https://nova.example/v2.1",
            token=KEYSTONE_TOKEN,
        )
    )

    assert servers == [
        NovaServerDTO(id="srv-1", name="web-1", status="ACTIVE"),
        NovaServerDTO(id="srv-2", name="db-1", status="SHUTOFF"),
    ]


def test_list_servers_maps_missing_fields_to_empty_strings(monkeypatch, set_proxy):
    """Servers missing fields map those fields to empty strings; non-dicts are skipped.

    **Validates: Requirements 2.2**
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
                        {"id": "srv-3"},
                        "not-a-dict",
                        {"name": "only-name"},
                    ]
                },
            ),
        ),
    )

    servers = asyncio.run(
        OpenStackProxy()._list_servers(
            nova_endpoint="https://nova.example/v2.1",
            token=KEYSTONE_TOKEN,
        )
    )

    assert servers == [
        NovaServerDTO(id="srv-3", name="", status=""),
        NovaServerDTO(id="", name="only-name", status=""),
    ]


@pytest.mark.parametrize("error_status", [400, 404, 429, 500, 503])
def test_list_servers_non_2xx_raises_service_error(error_status, monkeypatch, set_proxy):
    """A non-2xx Nova response raises ``OpenStackServiceError``.

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


@pytest.mark.parametrize(
    "network_error",
    [httpx.ConnectError("refused"), httpx.TimeoutException("timed out")],
)
def test_list_servers_connect_timeout_raises_connection_error(
    network_error, monkeypatch, set_proxy
):
    """Connect/timeout failures on the Nova call raise ``OpenStackConnectionError``.

    **Validates: Requirements 3.4**
    """
    set_proxy("")

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(captured, get_error=network_error),
    )

    with pytest.raises(OpenStackConnectionError) as exc_info:
        asyncio.run(
            OpenStackProxy()._list_servers(
                nova_endpoint="https://nova.example/v2.1",
                token=KEYSTONE_TOKEN,
            )
        )
    assert exc_info.value.code == "CONNECTION_FAILED"


def test_list_servers_non_json_body_raises_service_error(monkeypatch, set_proxy):
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


# ===========================================================================
# Settings.OPENSTACK_HTTPS_PROXY environment / alias resolution (Req 2.1, 2.2)
# ===========================================================================
def _fresh_settings(monkeypatch, env: dict[str, str]) -> Settings:
    """Build a fresh ``Settings`` reading only the given env vars.

    Clears every alias source first so a leftover process value cannot mask the
    case under test, sets ``SECRET_KEY`` (a required field) and ``env`` on the
    real environment, and disables ``.env`` loading so the result depends solely
    on the injected variables.
    """
    for name in (
        "OPENSTACK_HTTPS_PROXY",
        "https_proxy",
        "http_proxy",
        "HTTPS_PROXY",
        "HTTP_PROXY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_settings_defaults_to_empty_when_no_proxy_env(monkeypatch):
    """With no proxy env var set, ``OPENSTACK_HTTPS_PROXY`` defaults to ``""``.

    **Validates: Requirements 3.1**
    """
    s = _fresh_settings(monkeypatch, {})
    assert s.OPENSTACK_HTTPS_PROXY == ""


def test_settings_reads_openstack_https_proxy_env(monkeypatch):
    """``Settings`` reads the explicit ``OPENSTACK_HTTPS_PROXY`` env var.

    **Validates: Requirements 2.1, 2.2**
    """
    s = _fresh_settings(monkeypatch, {"OPENSTACK_HTTPS_PROXY": "http://explicit:3128"})
    assert s.OPENSTACK_HTTPS_PROXY == "http://explicit:3128"


def test_settings_reads_lowercase_https_proxy_alias(monkeypatch):
    """``Settings`` reads the aliased lowercase ``https_proxy`` env var.

    **Validates: Requirements 2.1, 2.2**
    """
    s = _fresh_settings(monkeypatch, {"https_proxy": "http://https-proxy:8080"})
    assert s.OPENSTACK_HTTPS_PROXY == "http://https-proxy:8080"


def test_settings_reads_lowercase_http_proxy_alias(monkeypatch):
    """``Settings`` reads the aliased lowercase ``http_proxy`` env var.

    **Validates: Requirements 2.1, 2.2**
    """
    s = _fresh_settings(monkeypatch, {"http_proxy": "http://http-proxy:8080"})
    assert s.OPENSTACK_HTTPS_PROXY == "http://http-proxy:8080"
