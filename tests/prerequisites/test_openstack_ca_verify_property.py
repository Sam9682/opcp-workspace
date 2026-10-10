"""Property test P5 for the OpenStack CA-certificate TLS-verification flow.

Feature spec: .kiro/specs/openstack-ca-certificate (task 3.3)

Property 5: TLS verification uses the effective CA certificate for both calls

*For any* effective CA certificate value supplied for a retrieval, both the
Keystone token acquisition (``_get_token``) and the Nova server list
(``_list_servers``) construct their HTTP client with the *same* TLS
verification setting derived from that value:

- a certificate context built from the CA certificate when it is non-empty and
  valid (both calls receive the identical :class:`ssl.SSLContext` instance),
- the system default trust store (``verify=True``) when it is empty.

Validates: Requirements 3.1, 3.2, 3.3, 3.5

The proxy in ``app/prerequisites/openstack.py`` performs both outbound calls
through ``httpx.AsyncClient(verify=...)`` used as an async context manager. This
test replaces ``httpx.AsyncClient`` (patched on the ``openstack`` module
namespace) with a fake async client that records the ``verify`` value passed to
every constructor call, so no real network call is made and the verify argument
used by each of the two calls can be compared deterministically.
"""
import asyncio
import ssl

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.prerequisites import openstack as openstack_module
from app.prerequisites.openstack import OpenStackProxy


# A fixed, known-valid self-signed PEM certificate. Using a constant fixture for
# the non-empty branch keeps Hypothesis generation cheap while still exercising
# the real ``ssl.create_default_context(cadata=...)`` path in ``_build_verify``.
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

KEYSTONE_TOKEN = "gAAAAA-fake-keystone-subject-token"


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


def _make_recording_client(verify_calls):
    """Build a fake ``httpx.AsyncClient`` class recording each ``verify`` value.

    ``verify_calls`` is a shared list; every construction appends the ``verify``
    keyword it received. ``post`` returns a Keystone token response and ``get``
    returns an empty Nova server list, so ``retrieve`` runs through both calls.
    """

    class _Client:
        def __init__(self, *args, verify=True, **kwargs):
            verify_calls.append(verify)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, **kwargs):
            return _FakeResponse(
                201,
                headers={"X-Subject-Token": KEYSTONE_TOKEN},
                json_body={"token": {}},
            )

        async def get(self, url, **kwargs):
            return _FakeResponse(200, json_body={"servers": []})

    return _Client


# Parameterize over the two effective branches: an empty CA certificate (any
# whitespace-only string collapses to the system-trust-store branch) and the
# fixed known-valid PEM. Mapping arbitrary whitespace text to the empty branch
# keeps Hypothesis drawing genuinely distinct examples across the full run
# (minimum 100 iterations) rather than short-circuiting on a two-value space.
_EMPTY_CA = st.text(alphabet=" \t\r\n", min_size=0, max_size=8)
_CA_CERTIFICATE = st.one_of(_EMPTY_CA, st.just(VALID_PEM))


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(ca_certificate=_CA_CERTIFICATE)
def test_both_calls_use_same_effective_verify(ca_certificate, monkeypatch):
    """Feature: openstack-ca-certificate, Property 5: TLS verification uses the
    effective CA certificate for both calls.

    Parameterizes over the empty vs. non-empty valid PEM branch. Intercepts the
    ``verify`` argument passed to ``httpx.AsyncClient`` for both ``_get_token``
    and ``_list_servers`` and asserts both calls receive the same expected
    verify: an :class:`ssl.SSLContext` for a non-empty valid PEM, or ``True``
    (system trust store) for an empty CA certificate.

    Validates: Requirements 3.1, 3.2, 3.3, 3.5
    """
    verify_calls: list = []
    fake_client = _make_recording_client(verify_calls)
    monkeypatch.setattr(openstack_module.httpx, "AsyncClient", fake_client)

    # A non-empty valid PEM selects the SSLContext branch; anything empty or
    # whitespace-only selects the system-trust-store branch.
    use_pem = bool(ca_certificate.strip())

    servers = asyncio.run(
        OpenStackProxy().retrieve(
            auth_url="https://keystone.example/v3",
            credential_id="cred-p5",
            secret="p5-secret",
            nova_endpoint="https://nova.example/v2.1",
            ca_certificate=ca_certificate,
        )
    )

    # Both outbound calls must have constructed a client (token + server list).
    assert servers == []
    assert len(verify_calls) == 2, (
        f"expected exactly two client constructions, got {len(verify_calls)}"
    )

    token_verify, servers_verify = verify_calls

    if use_pem:
        # Non-empty valid PEM: both calls verify against an SSLContext, and it
        # is the *same* context instance (built once, shared by both calls).
        assert isinstance(token_verify, ssl.SSLContext)
        assert isinstance(servers_verify, ssl.SSLContext)
        assert token_verify is servers_verify, (
            "the two calls used different SSL contexts"
        )
    else:
        # Empty CA certificate: both calls fall back to the system trust store.
        assert token_verify is True
        assert servers_verify is True

    # Whatever the branch, both calls must use the identical verify value.
    assert token_verify == servers_verify
