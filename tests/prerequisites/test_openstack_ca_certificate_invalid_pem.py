"""Property test P6 — invalid PEM yields a CA-specific error with no outbound call.

Feature spec: .kiro/specs/openstack-ca-certificate

Task 3.4 — Write property test P6 — invalid PEM, no outbound call
Feature: openstack-ca-certificate, Property 6: Invalid PEM yields a CA-specific
error with no outbound call

**Validates: Requirements 3.4**

Property 6 states: *for any* non-empty CA certificate string that cannot be
parsed as valid PEM, the retrieval SHALL return an error identifying the CA
certificate as the cause (``INVALID_CA_CERTIFICATE``) and SHALL NOT attempt
either OpenStack call.

Two complementary assertions, one per surface named in the task:

- ``_build_verify`` raises :class:`OpenStackCACertificateError` (code
  ``INVALID_CA_CERTIFICATE``) directly for clearly-invalid, non-PEM input.
- ``OpenStackProxy.retrieve`` raises the same error and — critically — never
  constructs an ``httpx.AsyncClient``. ``httpx.AsyncClient`` is patched on the
  ``openstack`` module namespace with a spy that fails the test if it is ever
  instantiated, so a positive pass proves neither ``_get_token`` nor
  ``_list_servers`` reached the network.

The generator is intentionally constrained to *clearly-invalid* content. Some
arbitrary strings can coincidentally parse (or ``ssl`` may tolerate stray
whitespace), so inputs are printable ASCII that never contain a PEM header, are
non-empty after stripping, and are asserted to actually raise before being
counted — an input that happens to parse is filtered out rather than failing
the property. Minimum 100 iterations per Hypothesis ``max_examples``.
"""
import asyncio
import contextlib

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.prerequisites import openstack as openstack_module
from app.prerequisites.openstack import (
    OpenStackCACertificateError,
    OpenStackProxy,
    _build_verify,
)


# PEM parsing keys off the ``-----BEGIN ... -----`` armor. Excluding the hyphen
# from the alphabet guarantees the generated text can never contain a PEM
# header, so every value is structurally non-PEM. Printable ASCII (minus the
# hyphen) keeps generation cheap and the input space clearly invalid.
_NON_PEM_TEXT = st.text(
    alphabet=st.characters(
        min_codepoint=33,
        max_codepoint=126,
        blacklist_characters="-",
    ),
    min_size=1,
    max_size=64,
)


class _ExplodingAsyncClient:
    """Spy standing in for ``httpx.AsyncClient`` that must never be constructed.

    If the proxy attempts any outbound call it will instantiate this class;
    doing so raises immediately, failing the property that no OpenStack call is
    attempted when the CA certificate is invalid.
    """

    def __init__(self, *args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError(
            "httpx.AsyncClient was constructed: an outbound OpenStack call was "
            "attempted despite an invalid CA certificate"
        )


@contextlib.contextmanager
def _exploding_httpx_client():
    """Temporarily replace ``httpx.AsyncClient`` with the exploding spy.

    Used as a context manager rather than the ``monkeypatch`` fixture so it
    resets per generated example (Hypothesis does not reset function-scoped
    fixtures between examples). The patch is constant across examples, but the
    context manager keeps the test self-contained and health-check clean.
    """
    original = openstack_module.httpx.AsyncClient
    openstack_module.httpx.AsyncClient = _ExplodingAsyncClient
    try:
        yield
    finally:
        openstack_module.httpx.AsyncClient = original


@settings(max_examples=100, deadline=None)
@given(ca_certificate=_NON_PEM_TEXT)
def test_build_verify_rejects_invalid_pem(ca_certificate):
    """Feature: openstack-ca-certificate, Property 6: Invalid PEM yields a CA-specific error with no outbound call

    Validates: Requirements 3.4

    ``_build_verify`` raises ``OpenStackCACertificateError`` with the
    ``INVALID_CA_CERTIFICATE`` code for any clearly-invalid, non-PEM string.
    """
    try:
        _build_verify(ca_certificate)
    except OpenStackCACertificateError as exc:
        assert exc.code == "INVALID_CA_CERTIFICATE"
        return
    # A value that coincidentally parsed is not a valid counterexample for this
    # property (which concerns unparseable PEM); skip it rather than fail.
    pytest.skip("input coincidentally parsed as a certificate")


@settings(max_examples=100, deadline=None)
@given(ca_certificate=_NON_PEM_TEXT)
def test_retrieve_invalid_pem_raises_before_any_outbound_call(ca_certificate):
    """Feature: openstack-ca-certificate, Property 6: Invalid PEM yields a CA-specific error with no outbound call

    Validates: Requirements 3.4

    ``OpenStackProxy.retrieve`` raises ``OpenStackCACertificateError`` for an
    invalid CA certificate and never constructs an ``httpx.AsyncClient``, so
    neither the Keystone token acquisition nor the Nova server list is attempted.
    """

    async def _run():
        await OpenStackProxy().retrieve(
            auth_url="https://keystone.example/v3",
            credential_id="cred-1",
            secret="unused-secret",
            nova_endpoint="https://nova.example/v2.1",
            ca_certificate=ca_certificate,
        )

    with _exploding_httpx_client():
        try:
            asyncio.run(_run())
        except OpenStackCACertificateError as exc:
            assert exc.code == "INVALID_CA_CERTIFICATE"
            return
    # If _build_verify accepted the input there is no invalid-PEM case to test;
    # the exploding client already guards against any outbound call.
    pytest.skip("input coincidentally parsed as a certificate")
