"""Integration tests for the ``retrieve_servers`` route flow with the proxy fix.

Spec: .kiro/specs/openstack-proxy-connection (task 4.3)

These exercise the full HTTP route
``POST /api/prerequisites/installations/{installation_id}/servers-nodes/servers/retrieve``
through FastAPI's test client, so they cover the router flow end-to-end (auth,
config upsert, secret resolution, the two-step OpenStack call, and error
mapping) with the forward-proxy fix in place.

Covered cases (design.md, Integration Tests):
- Proxy configured + a mocked proxied transport returning a token then a Nova
  server list -> HTTP 200 with the mapped ``{id, name, status}`` rows, and BOTH
  OpenStack clients constructed with ``proxy=<configured url>`` (Req 2.3).
- Proxy configured but a connect failure on the (proxied) call -> HTTP 502
  ``CONNECTION_FAILED`` with no secret/token in the body (Req 2.4).
- No proxy configured against a mocked directly-reachable OpenStack -> unchanged
  HTTP 200 behavior, with BOTH clients built with no ``proxy`` key (Req 3.1).

**Validates: Requirements 2.3, 2.4, 3.1**

Approach (matches the existing openstack tests):
- Inject ``settings.OPENSTACK_HTTPS_PROXY`` via ``object.__setattr__`` so the
  value is honored regardless of pydantic's field guard, restoring the previous
  state afterwards (mirrors the exploration / preservation fixtures).
- Replace ``httpx.AsyncClient`` on the ``openstack`` module namespace with a fake
  async client that records the FULL constructor kwargs, so the presence/absence
  of ``proxy`` at each call site can be asserted. No real network or proxy runs.
"""
import httpx
import pytest
from fastapi import status

from app.config import settings
from app.models import User, UserRole  # noqa: F401
from app.models.credential_config import CredentialConfig  # noqa: F401 (register table)
from app.prerequisites import openstack as openstack_module
from app.auth.token import create_access_token


SENTINEL_PROXY = "http://51.178.90.72:9999/"

# A Keystone token we assert is never echoed to the client in any body.
KEYSTONE_TOKEN = "gAAAAA-integration-keystone-subject-token"

# Sentinel marking "this attribute did not exist before the test" so cleanup can
# remove it again rather than restoring a bogus value.
_MISSING = object()


@pytest.fixture
def set_proxy():
    """Inject ``settings.OPENSTACK_HTTPS_PROXY`` and restore the prior state.

    Uses ``object.__setattr__`` to bypass pydantic's field guard so the same
    fixture works whether or not the field is present, matching the exploration
    and preservation test fixtures. ``_resolve_proxy`` reads the value via
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


class _FakeResponse:
    """Minimal stand-in for ``httpx.Response`` used by the proxy."""

    def __init__(self, status_code, *, headers=None, json_body=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._json_body = json_body

    @property
    def is_success(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._json_body is None:
            raise ValueError("no JSON body")
        return self._json_body


def _make_capturing_client(captured_kwargs, *, servers_response=None, connect_error=False):
    """Fake ``httpx.AsyncClient`` recording each construction's full kwargs.

    ``post`` returns a Keystone token response and ``get`` returns
    ``servers_response`` (or an empty Nova list). When ``connect_error`` is True
    both ``post`` and ``get`` raise ``httpx.ConnectError`` to simulate an
    unreachable target (even through the proxy).
    """

    default_servers = _FakeResponse(200, json_body={"servers": []})

    class _Client:
        def __init__(self, *args, **kwargs):
            captured_kwargs.append(dict(kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, **kwargs):
            if connect_error:
                raise httpx.ConnectError("connection refused")
            return _FakeResponse(
                201,
                headers={"X-Subject-Token": KEYSTONE_TOKEN},
                json_body={"token": {}},
            )

        async def get(self, url, **kwargs):
            if connect_error:
                raise httpx.ConnectError("connection refused")
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
        email="proxyintegration@prereq.test",
        password_hash="hashed_password",
        first_name="Proxy",
        last_name="Integration",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ===========================================================================
# Case 1 - Full route flow with a proxy configured and a mocked proxied
# transport returning a token then a server list -> HTTP 200 + mapped rows.
#
# **Validates: Requirements 2.3**
# ===========================================================================
def test_route_with_proxy_returns_200_and_mapped_rows(
    client, member_user, installation_id, monkeypatch, set_proxy
):
    """Proxy configured + successful proxied calls -> HTTP 200 and mapped rows.

    Asserts the mapped ``{id, name, status}`` rows are returned and that BOTH
    OpenStack clients were constructed with the configured proxy, and that the
    secret / token never appear in the response body.

    **Validates: Requirements 2.3**
    """
    set_proxy(SENTINEL_PROXY)

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

    secret = "route-proxy-success-secret"
    resp = client.post(
        _retrieve_url(installation_id),
        json={
            "auth_url": "https://keystone.example/v3",
            "credential_id": "cred-proxy-ok",
            "nova_endpoint": "https://nova.example/v2.1",
            "credential_secret": secret,
        },
        headers=_headers(member_user),
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["servers"] == [
        {"id": "srv-1", "name": "web-1", "status": "ACTIVE"},
        {"id": "srv-2", "name": "db-1", "status": "SHUTOFF"},
    ]

    # Both OpenStack calls routed through the configured proxy.
    assert len(captured) == 2, (
        f"expected two client constructions (token + servers), got {len(captured)}"
    )
    for idx, kwargs in enumerate(captured):
        assert kwargs.get("proxy") == SENTINEL_PROXY, (
            f"construction #{idx} must be built with proxy={SENTINEL_PROXY!r}; "
            f"captured kwargs={kwargs!r}"
        )

    # No secret or token leaks into the response body.
    assert secret not in resp.text
    assert KEYSTONE_TOKEN not in resp.text


# ===========================================================================
# Case 2 - Route flow with a proxy configured but a connect failure ->
# HTTP 502 CONNECTION_FAILED and no secret/token in the body.
#
# **Validates: Requirements 2.4**
# ===========================================================================
def test_route_with_proxy_connect_failure_returns_502_no_leak(
    client, member_user, installation_id, monkeypatch, set_proxy
):
    """Proxy configured but the (proxied) call cannot connect -> HTTP 502.

    The failure surfaces as ``OpenStackConnectionError`` -> HTTP 502
    ``CONNECTION_FAILED`` and neither the secret nor the token appears in the
    body.

    **Validates: Requirements 2.4**
    """
    set_proxy(SENTINEL_PROXY)

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(captured, connect_error=True),
    )

    secret = "route-proxy-connect-secret"
    resp = client.post(
        _retrieve_url(installation_id),
        json={
            "auth_url": "https://keystone.example/v3",
            "credential_id": "cred-proxy-fail",
            "nova_endpoint": "https://nova.example/v2.1",
            "credential_secret": secret,
        },
        headers=_headers(member_user),
    )

    assert resp.status_code == status.HTTP_502_BAD_GATEWAY
    assert _error_code(resp.json()) == "CONNECTION_FAILED"

    # The client was still constructed with the configured proxy before failing.
    assert len(captured) >= 1
    assert captured[0].get("proxy") == SENTINEL_PROXY

    # No secret or token leaks into the error body.
    assert secret not in resp.text
    assert KEYSTONE_TOKEN not in resp.text


# ===========================================================================
# Case 3 - Route flow with no proxy configured against a mocked
# directly-reachable OpenStack -> unchanged HTTP 200 behavior.
#
# **Validates: Requirements 3.1**
# ===========================================================================
def test_route_without_proxy_returns_200_unchanged(
    client, member_user, installation_id, monkeypatch, set_proxy
):
    """No proxy configured + directly-reachable OpenStack -> unchanged HTTP 200.

    The mapped rows are returned and BOTH clients are built with NO ``proxy``
    key (direct connection), preserving today's behavior.

    **Validates: Requirements 3.1**
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
                        {"id": "srv-9", "name": "edge-1", "status": "ACTIVE"}
                    ]
                },
            ),
        ),
    )

    secret = "route-direct-success-secret"
    resp = client.post(
        _retrieve_url(installation_id),
        json={
            "auth_url": "https://keystone.example/v3",
            "credential_id": "cred-direct-ok",
            "nova_endpoint": "https://nova.example/v2.1",
            "credential_secret": secret,
        },
        headers=_headers(member_user),
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["servers"] == [
        {"id": "srv-9", "name": "edge-1", "status": "ACTIVE"}
    ]

    # Both OpenStack calls used a direct connection (no proxy key).
    assert len(captured) == 2, (
        f"expected two client constructions (token + servers), got {len(captured)}"
    )
    for idx, kwargs in enumerate(captured):
        assert "proxy" not in kwargs, (
            f"construction #{idx} must have no 'proxy' key with an empty proxy; "
            f"captured kwargs={kwargs!r}"
        )

    # No secret or token leaks into the response body.
    assert secret not in resp.text
    assert KEYSTONE_TOKEN not in resp.text
