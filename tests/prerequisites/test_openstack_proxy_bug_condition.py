"""Bug condition exploration test for the OpenStack forward-proxy defect.

Spec: .kiro/specs/openstack-proxy-connection (task 1)

Property 1: Bug Condition - OpenStack clients omit the configured proxy.

**This test is EXPECTED TO FAIL on the unfixed code.** Its purpose is to surface
counterexamples proving the bug exists: when a forward proxy is configured
(``settings.OPENSTACK_HTTPS_PROXY`` non-empty), the two OpenStack outbound calls
in ``OpenStackProxy._get_token`` and ``OpenStackProxy._list_servers`` construct
``httpx.AsyncClient`` **without** any ``proxy`` argument, so the requests attempt
a non-routable direct connection to Keystone/Nova and fail with
``httpx.ConnectError`` -> ``OpenStackConnectionError`` -> HTTP 502.

Once the fix (tasks 3.1/3.2) routes both calls through the configured proxy,
this same test will PASS (both clients built with ``proxy=<configured url>``).

**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**

Design references:
- isBugCondition: proxy_url non-empty AND target not directly reachable AND
  client proxy unused (design.md, "Bug Condition").
- Property 1: both Keystone and Nova ``httpx.AsyncClient`` instances constructed
  with the configured proxy; the flow returns mapped ``{id, name, status}`` rows.

Approach (matches the existing openstack tests):
- Patch ``settings.OPENSTACK_HTTPS_PROXY`` to a sentinel proxy URL, iterating a
  small set of non-empty proxy URLs (scoped PBT for a deterministic bug). We use
  ``raising=False`` so the test works whether or not the settings field exists
  yet on the unfixed code (the field is added in task 3.1).
- Replace ``httpx.AsyncClient`` on the ``openstack`` module namespace with a fake
  async client that RECORDS THE FULL constructor kwargs of every construction, so
  the presence/absence of ``proxy`` at each call site can be asserted directly.
- No real network or real proxy is used.
"""
import asyncio
import uuid

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
    OpenStackConnectionError,
)
from app.auth.token import create_access_token


# The observed target-environment proxy from the bug report, used as the primary
# sentinel. The scoped property iterates a small set of non-empty proxy URLs.
SENTINEL_PROXY = "http://51.178.90.72:9999/"

_PROXY_URLS = [
    SENTINEL_PROXY,
    "http://proxy.internal:3128",
    "http://10.0.0.5:8080/",
    "https://secure-proxy.example:443",
]

KEYSTONE_TOKEN = "gAAAAA-fake-keystone-subject-token"

# Sentinel marking "this attribute did not exist before the test" so cleanup can
# remove it again rather than restoring a bogus value.
_MISSING = object()


@pytest.fixture
def set_proxy(monkeypatch):
    """Inject ``settings.OPENSTACK_HTTPS_PROXY`` robustly, on fixed OR unfixed code.

    On the fixed code ``OPENSTACK_HTTPS_PROXY`` is a real pydantic field and a
    plain ``monkeypatch.setattr`` would work. On the UNFIXED code the field does
    not exist yet (it is added in task 3.1) and pydantic's ``Settings`` uses
    ``extra="ignore"``, so it rejects setting an unknown field via normal
    attribute assignment. To keep this exploration test runnable on the current
    code, we set the value through ``object.__setattr__`` (bypassing pydantic's
    field guard) and restore the previous state afterwards. ``_resolve_proxy``
    reads ``settings.OPENSTACK_HTTPS_PROXY`` via ordinary attribute access, which
    resolves this injected value identically in both cases.
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
# Fake httpx.AsyncClient that captures the FULL constructor kwargs.
#
# The proxy uses ``async with httpx.AsyncClient(**client_kwargs) as client:``
# then ``await client.post(...)`` / ``await client.get(...)``. Unlike the
# existing openstack test fakes (which pop ``verify`` and drop the rest into
# ``**kwargs``), this fake stores EVERY keyword it received so the assertion can
# check whether ``proxy`` was passed at each call site.
# ---------------------------------------------------------------------------
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


def _make_capturing_client(captured_kwargs, *, connect_error=False):
    """Build a fake ``httpx.AsyncClient`` class recording each construction's kwargs.

    ``captured_kwargs`` is a shared list; every construction appends the full
    keyword-argument dict it received. When ``connect_error`` is True, ``post``
    raises ``httpx.ConnectError`` to simulate an unreachable direct target (the
    end-to-end symptom). Otherwise ``post`` returns a Keystone token response and
    ``get`` returns an empty Nova server list so ``retrieve`` runs both calls.
    """

    class _Client:
        def __init__(self, *args, **kwargs):
            captured_kwargs.append(dict(kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, **kwargs):
            if connect_error:
                raise httpx.ConnectError("connection refused (direct target unreachable)")
            return _FakeResponse(
                201,
                headers={"X-Subject-Token": KEYSTONE_TOKEN},
                json_body={"token": {}},
            )

        async def get(self, url, **kwargs):
            if connect_error:
                raise httpx.ConnectError("connection refused (direct target unreachable)")
            return _FakeResponse(200, json_body={"servers": []})

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


# ===========================================================================
# Test case 1 - Keystone client omits the configured proxy (Property 1 / Req 2.1)
# ===========================================================================
@hyp_settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(proxy_url=st.sampled_from(_PROXY_URLS))
def test_get_token_client_built_with_configured_proxy(proxy_url, monkeypatch, set_proxy):
    """With a proxy configured, ``_get_token`` MUST build the client with ``proxy=``.

    On the UNFIXED code the client is built as ``httpx.AsyncClient(verify=...)``
    with no ``proxy`` key, so this assertion fails - proving the bug.

    **Validates: Requirements 1.1, 2.1**
    """
    set_proxy(proxy_url)

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx, "AsyncClient", _make_capturing_client(captured)
    )

    asyncio.run(
        OpenStackProxy()._get_token(
            auth_url="https://keystone.example/v3",
            credential_id="cred-bug",
            secret="bug-secret",
        )
    )

    assert len(captured) == 1, "expected exactly one client construction for _get_token"
    kwargs = captured[0]
    assert "proxy" in kwargs, (
        f"BUG: _get_token built httpx.AsyncClient without a 'proxy' key though "
        f"OPENSTACK_HTTPS_PROXY={proxy_url!r} was configured. Captured kwargs={kwargs!r}"
    )
    assert kwargs["proxy"] == proxy_url


# ===========================================================================
# Test case 2 - Nova client omits the configured proxy (Property 1 / Req 2.2)
# ===========================================================================
@hyp_settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(proxy_url=st.sampled_from(_PROXY_URLS))
def test_list_servers_client_built_with_configured_proxy(proxy_url, monkeypatch, set_proxy):
    """With a proxy configured, ``_list_servers`` MUST build the client with ``proxy=``.

    On the UNFIXED code the client is built as ``httpx.AsyncClient(verify=...)``
    with no ``proxy`` key, so this assertion fails - proving the bug.

    **Validates: Requirements 1.3, 2.2**
    """
    set_proxy(proxy_url)

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
    assert len(captured) == 1, "expected exactly one client construction for _list_servers"
    kwargs = captured[0]
    assert "proxy" in kwargs, (
        f"BUG: _list_servers built httpx.AsyncClient without a 'proxy' key though "
        f"OPENSTACK_HTTPS_PROXY={proxy_url!r} was configured. Captured kwargs={kwargs!r}"
    )
    assert kwargs["proxy"] == proxy_url


# ===========================================================================
# Test case 2b - retrieve builds BOTH clients with the configured proxy (Property 1)
# ===========================================================================
def test_retrieve_builds_both_clients_with_configured_proxy(monkeypatch, set_proxy):
    """End-to-end: with a proxy configured, BOTH calls build a client with ``proxy=``.

    Asserts the expected behavior from Property 1: both the Keystone and Nova
    clients are constructed with the configured proxy and the flow returns the
    mapped rows. On the UNFIXED code neither construction carries ``proxy``.

    **Validates: Requirements 2.1, 2.2, 2.3**
    """
    set_proxy(SENTINEL_PROXY)

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx, "AsyncClient", _make_capturing_client(captured)
    )

    servers = asyncio.run(
        OpenStackProxy().retrieve(
            auth_url="https://keystone.example/v3",
            credential_id="cred-bug",
            secret="bug-secret",
            nova_endpoint="https://nova.example/v2.1",
        )
    )

    assert servers == []
    assert len(captured) == 2, (
        f"expected two client constructions (token + servers), got {len(captured)}"
    )
    for idx, kwargs in enumerate(captured):
        assert "proxy" in kwargs, (
            f"BUG: construction #{idx} built httpx.AsyncClient without a 'proxy' key "
            f"though OPENSTACK_HTTPS_PROXY={SENTINEL_PROXY!r} was configured. "
            f"Captured kwargs={kwargs!r}"
        )
        assert kwargs["proxy"] == SENTINEL_PROXY


# ===========================================================================
# Test case 3 - End-to-end connect failure with a proxy set (observed symptom)
#
# This case reproduces the observed symptom and PASSES on the unfixed code (the
# direct connection fails), documenting that the failure surfaces as
# OpenStackConnectionError -> HTTP 502. It is included per the task's Test case 3.
# ===========================================================================
@pytest.fixture
def member_user(db_session):
    """Create an authenticated member user (retrieve requires auth)."""
    user = User(
        email="proxybug@prereq.test",
        password_hash="hashed_password",
        first_name="Proxy",
        last_name="Bug",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_retrieve_raises_connection_error_when_direct_target_unreachable(monkeypatch, set_proxy):
    """With a proxy set but the direct target unreachable, ``retrieve`` raises
    ``OpenStackConnectionError`` (the observed symptom on the unfixed code).

    **Validates: Requirements 1.1, 1.2**
    """
    set_proxy(SENTINEL_PROXY)

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(captured, connect_error=True),
    )

    with pytest.raises(OpenStackConnectionError):
        asyncio.run(
            OpenStackProxy().retrieve(
                auth_url="https://keystone.example/v3",
                credential_id="cred-bug",
                secret="bug-secret",
                nova_endpoint="https://nova.example/v2.1",
            )
        )


def test_route_returns_502_when_proxy_set_but_target_unreachable(
    client, member_user, installation_id, monkeypatch, set_proxy
):
    """The ``retrieve_servers`` route returns HTTP 502 ``CONNECTION_FAILED`` when a
    proxy is configured but the direct target is unreachable, with no secret leak.

    **Validates: Requirements 1.2, 2.3**
    """
    set_proxy(SENTINEL_PROXY)

    captured: list = []
    monkeypatch.setattr(
        openstack_module.httpx,
        "AsyncClient",
        _make_capturing_client(captured, connect_error=True),
    )

    secret = "route-bug-secret"
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

    assert resp.status_code == status.HTTP_502_BAD_GATEWAY
    assert _error_code(resp.json()) == "CONNECTION_FAILED"
    assert secret not in resp.text
    assert KEYSTONE_TOKEN not in resp.text
