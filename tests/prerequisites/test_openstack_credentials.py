"""Backend proxy + endpoint tests for the OpenStack servers-nodes credential flow.

Spec: .kiro/specs/openstack-node-status (tasks 6.1, 6.2, 6.3, 6.4)

All four optional test tasks write to this single file:

- 6.1 Persistence + secret-handling tests
    PUT/POST stores the *encrypted* secret; GET returns config with
    ``secret_stored=True`` and no secret field; the stored ciphertext differs
    from the plaintext.
    **Validates: Requirements 3.1, 3.2, 3.3, 4.1** (backs Property 4)

- 6.2 Property test: the secret never appears in any response
    **Property 2: Secret never appears in any response.** With ``hypothesis``,
    the serialized save/load/retrieve/error response bodies contain neither the
    credential secret nor the Keystone token.
    **Validates: Requirements 3.3, 5.3, 8.4**

- 6.3 Successful token-and-servers retrieval test
    ``httpx`` is mocked: ``POST /auth/tokens`` returns an ``X-Subject-Token``
    header, ``GET /servers`` returns a server list; the endpoint returns mapped
    ``{id, name, status}`` and no secret/token in the body.
    **Validates: Requirements 5.1, 5.2, 6.1, 6.2** (backs Property 5)

- 6.4 Error-handling tests
    Keystone 401 -> ``AUTH_FAILED``; connection error -> ``CONNECTION_FAILED``;
    Nova 5xx -> ``OPENSTACK_ERROR``; every error body excludes the secret and
    the token.
    **Validates: Requirements 8.1, 8.2, 8.3, 8.4** (backs Property 6)

The OpenStack proxy in ``app/prerequisites/openstack.py`` performs all outbound
HTTP through ``httpx.AsyncClient`` used as an async context manager. These tests
replace ``httpx.AsyncClient`` (patched on the ``openstack`` module namespace)
with a fake async client so no real network call is made, and so Keystone and
Nova responses — including connection failures — can be simulated deterministically.
"""
import json
import uuid

import httpx
import pytest
from fastapi import status
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models import User, UserRole
from app.models.credential_config import CredentialConfig  # noqa: F401 (register table)
from app.prerequisites import openstack as openstack_module
from app.prerequisites.security import decrypt_secret
from app.auth.token import create_access_token


# A Keystone token value we assert is never echoed back to the client. The real
# proxy reads it from the ``X-Subject-Token`` header and keeps it server-side.
KEYSTONE_TOKEN = "gAAAAA-secret-keystone-subject-token-value"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def member_user(db_session):
    """Create an authenticated member user (retrieve/credentials require auth)."""
    user = User(
        email="openstack@prereq.test",
        password_hash="hashed_password",
        first_name="Nova",
        last_name="Operator",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _error_code(body: dict) -> str | None:
    """Extract the structured error code from a router error body.

    Matches the extraction pattern in tests/test_prerequisites_answers_authz.py:
    the app unwraps ``ErrorResponse.create`` to a top-level ``{"error": {...}}``
    body; fall back to the raw ``{"detail": {"error": {...}}}`` shape.
    """
    if isinstance(body.get("error"), dict):
        return body["error"].get("code")
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("error", {}).get("code")
    return None


def _cred_url(installation_id: str) -> str:
    return (
        f"/api/prerequisites/installations/{installation_id}"
        f"/servers-nodes/credentials"
    )


def _retrieve_url(installation_id: str) -> str:
    return (
        f"/api/prerequisites/installations/{installation_id}"
        f"/servers-nodes/servers/retrieve"
    )


# ---------------------------------------------------------------------------
# Fake httpx.AsyncClient
#
# openstack.py uses ``async with httpx.AsyncClient() as client:`` then calls
# ``await client.post(...)`` / ``await client.get(...)``. The fake below matches
# that surface: it is an async context manager whose ``post``/``get`` return a
# canned response, raise a connection error, or delegate to a per-call handler.
# ---------------------------------------------------------------------------
class _FakeResponse:
    """Minimal stand-in for ``httpx.Response`` used by the proxy."""

    def __init__(self, status_code: int, *, headers=None, json_body=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._json_body = json_body

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        if self._json_body is None:
            raise ValueError("no JSON body")
        return self._json_body


class _FakeAsyncClient:
    """Async-context-manager fake driven by a ``post_handler``/``get_handler``.

    Handlers receive ``(url, **kwargs)`` and return a ``_FakeResponse`` (or raise
    an ``httpx`` error to simulate a connection failure).
    """

    post_handler = None
    get_handler = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, **kwargs):
        assert type(self).post_handler is not None, "post_handler not set"
        return type(self).post_handler(url, **kwargs)

    async def get(self, url, **kwargs):
        assert type(self).get_handler is not None, "get_handler not set"
        return type(self).get_handler(url, **kwargs)


def _install_fake_httpx(monkeypatch, *, post_handler=None, get_handler=None):
    """Patch ``httpx.AsyncClient`` on the openstack module with the fake client."""

    class _Client(_FakeAsyncClient):
        pass

    _Client.post_handler = staticmethod(post_handler) if post_handler else None
    _Client.get_handler = staticmethod(get_handler) if get_handler else None
    monkeypatch.setattr(openstack_module.httpx, "AsyncClient", _Client)
    return _Client


def _successful_token_handler(url, **kwargs):
    """Keystone POST /auth/tokens -> 201 with the X-Subject-Token header."""
    return _FakeResponse(
        201,
        headers={"X-Subject-Token": KEYSTONE_TOKEN},
        json_body={"token": {}},
    )


def _servers_handler(servers):
    """Build a Nova GET /servers handler returning the given server dicts."""

    def _handler(url, **kwargs):
        # The proxy must forward the Keystone token as X-Auth-Token (Req 6.1).
        assert kwargs.get("headers", {}).get("X-Auth-Token") == KEYSTONE_TOKEN
        return _FakeResponse(200, json_body={"servers": servers})

    return _handler


# ===========================================================================
# Task 6.1 — Persistence + secret-handling
# Validates Requirements 3.1, 3.2, 3.3, 4.1 (backs Property 4)
# ===========================================================================
class TestCredentialPersistence:
    def test_put_stores_encrypted_secret_not_plaintext(
        self, client, db_session, member_user, installation_id
    ):
        """PUT persists non-secret fields and stores the secret encrypted.

        The stored ciphertext must differ from the plaintext (Req 3.2) and must
        decrypt back to the original secret (round-trip), while the non-secret
        fields are persisted verbatim (Req 3.1).
        """
        secret = "s3cr3t-application-credential"
        resp = client.put(
            _cred_url(installation_id),
            json={
                "auth_url": "https://keystone.example/v3",
                "credential_id": "cred-abc",
                "nova_endpoint": "https://nova.example/v2.1",
                "credential_secret": secret,
            },
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_200_OK

        row = (
            db_session.query(CredentialConfig)
            .filter(CredentialConfig.installation_id == uuid.UUID(installation_id))
            .first()
        )
        assert row is not None
        assert row.auth_url == "https://keystone.example/v3"
        assert row.credential_id == "cred-abc"
        assert row.nova_endpoint == "https://nova.example/v2.1"
        # The secret is persisted only as ciphertext, never as plaintext.
        assert row.credential_secret_encrypted is not None
        assert row.credential_secret_encrypted != secret
        assert secret not in row.credential_secret_encrypted
        assert decrypt_secret(row.credential_secret_encrypted) == secret

    def test_put_response_has_no_secret_field_and_flags_stored(
        self, client, member_user, installation_id
    ):
        """PUT response flags ``secret_stored=True`` and carries no secret field."""
        secret = "another-secret-value"
        resp = client.put(
            _cred_url(installation_id),
            json={
                "auth_url": "https://keystone.example/v3",
                "credential_id": "cred-xyz",
                "nova_endpoint": "https://nova.example/v2.1",
                "credential_secret": secret,
            },
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["secret_stored"] is True
        assert "credential_secret" not in body
        assert "secret" not in {k.lower() for k in body if k != "secret_stored"}
        assert secret not in resp.text

    def test_get_returns_config_with_secret_stored_true_no_secret(
        self, client, member_user, installation_id
    ):
        """After a PUT with a secret, GET returns config with secret_stored=True.

        The secret is never present in the GET body (Req 3.3); only the
        ``secret_stored`` flag and the non-secret fields are returned (Req 4.1).
        """
        secret = "get-roundtrip-secret"
        put = client.put(
            _cred_url(installation_id),
            json={
                "auth_url": "https://keystone.example/v3",
                "credential_id": "cred-get",
                "nova_endpoint": "https://nova.example/v2.1",
                "credential_secret": secret,
            },
            headers=_headers(member_user),
        )
        assert put.status_code == status.HTTP_200_OK

        get = client.get(_cred_url(installation_id), headers=_headers(member_user))
        assert get.status_code == status.HTTP_200_OK
        body = get.json()
        assert body["auth_url"] == "https://keystone.example/v3"
        assert body["credential_id"] == "cred-get"
        assert body["nova_endpoint"] == "https://nova.example/v2.1"
        assert body["secret_stored"] is True
        assert "credential_secret" not in body
        assert secret not in get.text

    def test_get_without_config_reports_secret_not_stored(
        self, client, member_user, installation_id
    ):
        """GET for an installation with no config returns an empty default."""
        resp = client.get(_cred_url(installation_id), headers=_headers(member_user))
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["secret_stored"] is False
        assert body["auth_url"] == ""
        assert "credential_secret" not in body

    def test_post_retrieve_stores_encrypted_secret(
        self, client, db_session, member_user, installation_id, monkeypatch
    ):
        """POST retrieve persists the config and stores the secret encrypted.

        The retrieve endpoint upserts before calling OpenStack; with httpx
        mocked for a successful flow the stored ciphertext must differ from the
        plaintext and decrypt back to it.
        """
        _install_fake_httpx(
            monkeypatch,
            post_handler=_successful_token_handler,
            get_handler=_servers_handler(
                [{"id": "srv-1", "name": "web-1", "status": "ACTIVE"}]
            ),
        )
        secret = "post-retrieve-secret"
        resp = client.post(
            _retrieve_url(installation_id),
            json={
                "auth_url": "https://keystone.example/v3",
                "credential_id": "cred-post",
                "nova_endpoint": "https://nova.example/v2.1",
                "credential_secret": secret,
            },
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_200_OK

        row = (
            db_session.query(CredentialConfig)
            .filter(CredentialConfig.installation_id == uuid.UUID(installation_id))
            .first()
        )
        assert row is not None
        assert row.credential_secret_encrypted is not None
        assert row.credential_secret_encrypted != secret
        assert decrypt_secret(row.credential_secret_encrypted) == secret


# ===========================================================================
# Task 6.3 — Successful token-and-servers retrieval
# Validates Requirements 5.1, 5.2, 6.1, 6.2 (backs Property 5)
# ===========================================================================
class TestSuccessfulRetrieval:
    def test_retrieve_returns_mapped_servers_without_secret_or_token(
        self, client, member_user, installation_id, monkeypatch
    ):
        """A successful two-step flow returns mapped {id,name,status} rows.

        Keystone returns the token in the X-Subject-Token header (Req 5.2), Nova
        returns a list, and the endpoint maps each server to id/name/status
        (Req 6.2). Neither the secret nor the Keystone token appears in the body
        (Req 5.3, 8.4).
        """
        servers = [
            {"id": "srv-1", "name": "controller", "status": "ACTIVE"},
            {"id": "srv-2", "name": "compute-1", "status": "SHUTOFF"},
        ]
        _install_fake_httpx(
            monkeypatch,
            post_handler=_successful_token_handler,
            get_handler=_servers_handler(servers),
        )
        secret = "successful-retrieve-secret"
        resp = client.post(
            _retrieve_url(installation_id),
            json={
                "auth_url": "https://keystone.example/v3",
                "credential_id": "cred-1",
                "nova_endpoint": "https://nova.example/v2.1",
                "credential_secret": secret,
            },
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["servers"] == [
            {"id": "srv-1", "name": "controller", "status": "ACTIVE"},
            {"id": "srv-2", "name": "compute-1", "status": "SHUTOFF"},
        ]
        # The secret and the Keystone token never leak into the response body.
        assert secret not in resp.text
        assert KEYSTONE_TOKEN not in resp.text

    def test_retrieve_uses_stored_secret_when_inline_omitted(
        self, client, member_user, installation_id, monkeypatch
    ):
        """When no inline secret is sent, the stored secret is used for the flow.

        First a PUT stores the secret; a subsequent retrieve without an inline
        secret succeeds using the decrypted stored secret.
        """
        stored_secret = "stored-then-reused-secret"
        put = client.put(
            _cred_url(installation_id),
            json={
                "auth_url": "https://keystone.example/v3",
                "credential_id": "cred-1",
                "nova_endpoint": "https://nova.example/v2.1",
                "credential_secret": stored_secret,
            },
            headers=_headers(member_user),
        )
        assert put.status_code == status.HTTP_200_OK

        _install_fake_httpx(
            monkeypatch,
            post_handler=_successful_token_handler,
            get_handler=_servers_handler(
                [{"id": "srv-9", "name": "db", "status": "ACTIVE"}]
            ),
        )
        resp = client.post(
            _retrieve_url(installation_id),
            json={
                "auth_url": "https://keystone.example/v3",
                "credential_id": "cred-1",
                "nova_endpoint": "https://nova.example/v2.1",
                # credential_secret omitted -> reuse the stored secret
            },
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["servers"] == [
            {"id": "srv-9", "name": "db", "status": "ACTIVE"}
        ]
        assert stored_secret not in resp.text
        assert KEYSTONE_TOKEN not in resp.text


# ===========================================================================
# Task 6.4 — Error handling
# Validates Requirements 8.1, 8.2, 8.3, 8.4 (backs Property 6)
# ===========================================================================
class TestErrorHandling:
    SECRET = "error-path-secret"

    def _retrieve(self, client, member_user, installation_id):
        return client.post(
            _retrieve_url(installation_id),
            json={
                "auth_url": "https://keystone.example/v3",
                "credential_id": "cred-err",
                "nova_endpoint": "https://nova.example/v2.1",
                "credential_secret": self.SECRET,
            },
            headers=_headers(member_user),
        )

    def test_keystone_401_maps_to_auth_failed(
        self, client, member_user, installation_id, monkeypatch
    ):
        """Keystone rejecting the credentials -> 401 AUTH_FAILED (Req 8.1)."""

        def _reject(url, **kwargs):
            return _FakeResponse(401, json_body={"error": "unauthorized"})

        _install_fake_httpx(monkeypatch, post_handler=_reject)
        resp = self._retrieve(client, member_user, installation_id)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert _error_code(resp.json()) == "AUTH_FAILED"
        assert self.SECRET not in resp.text
        assert KEYSTONE_TOKEN not in resp.text

    def test_connection_error_maps_to_connection_failed(
        self, client, member_user, installation_id, monkeypatch
    ):
        """A network failure contacting Keystone -> 502 CONNECTION_FAILED (Req 8.2)."""

        def _raise_connect(url, **kwargs):
            raise httpx.ConnectError("connection refused")

        _install_fake_httpx(monkeypatch, post_handler=_raise_connect)
        resp = self._retrieve(client, member_user, installation_id)
        assert resp.status_code == status.HTTP_502_BAD_GATEWAY
        assert _error_code(resp.json()) == "CONNECTION_FAILED"
        assert self.SECRET not in resp.text

    def test_nova_5xx_maps_to_openstack_error(
        self, client, member_user, installation_id, monkeypatch
    ):
        """Token succeeds but Nova returns 5xx -> 502 OPENSTACK_ERROR (Req 8.3)."""

        def _nova_5xx(url, **kwargs):
            return _FakeResponse(503, json_body={"error": "service unavailable"})

        _install_fake_httpx(
            monkeypatch,
            post_handler=_successful_token_handler,
            get_handler=_nova_5xx,
        )
        resp = self._retrieve(client, member_user, installation_id)
        assert resp.status_code == status.HTTP_502_BAD_GATEWAY
        assert _error_code(resp.json()) == "OPENSTACK_ERROR"
        assert self.SECRET not in resp.text
        assert KEYSTONE_TOKEN not in resp.text

    def test_error_bodies_exclude_secret_and_token(
        self, client, member_user, installation_id, monkeypatch
    ):
        """Across every error path the body excludes the secret and token (Req 8.4)."""

        # Auth failure
        _install_fake_httpx(
            monkeypatch,
            post_handler=lambda url, **kw: _FakeResponse(403, json_body={}),
        )
        r1 = self._retrieve(client, member_user, installation_id)
        assert self.SECRET not in r1.text and KEYSTONE_TOKEN not in r1.text

        # Timeout / connection failure
        def _timeout(url, **kwargs):
            raise httpx.TimeoutException("timed out")

        _install_fake_httpx(monkeypatch, post_handler=_timeout)
        r2 = self._retrieve(client, member_user, installation_id)
        assert self.SECRET not in r2.text and KEYSTONE_TOKEN not in r2.text


# ===========================================================================
# Task 6.2 — Property 2: Secret never appears in any response
# Validates Requirements 3.3, 5.3, 8.4
#
# Across save / load / retrieve / error, the serialized response body contains
# neither the credential secret nor the Keystone token, for arbitrary secrets.
# The Hypothesis pattern here mirrors the other installation-scoped property
# tests: a single function-scoped ``client``/``installation`` is reused across
# examples, and the credential config row is cleared at the end of each example
# so state never leaks between examples. Function-scoped-fixture health checks
# are suppressed as recommended by Hypothesis for this pattern.
# ===========================================================================

# Secrets are generated as a fixed, highly-distinctive prefix followed by
# arbitrary printable text. The prefix makes the "does the secret appear
# verbatim in the response" check meaningful: a bare one-character secret like
# "0" would trivially collide with incidental digits in UUIDs/error-ids that
# every JSON body contains, which is a substring-matching artifact rather than
# a real leak. Prefixing with a marker no response ever legitimately contains
# ensures a positive match means the actual secret value leaked verbatim, which
# is exactly what Property 2 forbids.
_SECRET_MARKER = "OS_SECRET_MARKER_"
_SECRET = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=0,
    max_size=48,
).map(lambda tail: _SECRET_MARKER + tail)


class TestProperty2SecretNeverInResponse:
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(secret=_SECRET)
    def test_secret_and_token_absent_from_all_responses(
        self, client, db_session, member_user, installation_id, monkeypatch, secret
    ):
        """For any secret, no response body carries the secret or Keystone token."""
        headers = _headers(member_user)

        def _assert_clean(response):
            text = response.text
            assert secret not in text, f"secret leaked in {response.request.url}"
            assert KEYSTONE_TOKEN not in text, (
                f"keystone token leaked in {response.request.url}"
            )
            # The serialized JSON must not carry a credential_secret field.
            try:
                body = response.json()
            except json.JSONDecodeError:
                return
            if isinstance(body, dict):
                assert "credential_secret" not in body

        payload = {
            "auth_url": "https://keystone.example/v3",
            "credential_id": "cred-prop",
            "nova_endpoint": "https://nova.example/v2.1",
            "credential_secret": secret,
        }

        # save
        _assert_clean(client.put(_cred_url(installation_id), json=payload, headers=headers))
        # load
        _assert_clean(client.get(_cred_url(installation_id), headers=headers))

        # retrieve (success)
        _install_fake_httpx(
            monkeypatch,
            post_handler=_successful_token_handler,
            get_handler=_servers_handler(
                [{"id": "p-1", "name": "n", "status": "ACTIVE"}]
            ),
        )
        _assert_clean(client.post(_retrieve_url(installation_id), json=payload, headers=headers))

        # retrieve (auth error)
        _install_fake_httpx(
            monkeypatch,
            post_handler=lambda url, **kw: _FakeResponse(401, json_body={}),
        )
        _assert_clean(client.post(_retrieve_url(installation_id), json=payload, headers=headers))

        # retrieve (connection error)
        def _raise_connect(url, **kwargs):
            raise httpx.ConnectError("refused")

        _install_fake_httpx(monkeypatch, post_handler=_raise_connect)
        _assert_clean(client.post(_retrieve_url(installation_id), json=payload, headers=headers))

        # Clean up this example's row so state never leaks between examples.
        db_session.query(CredentialConfig).filter(
            CredentialConfig.installation_id == uuid.UUID(installation_id)
        ).delete()
        db_session.commit()
