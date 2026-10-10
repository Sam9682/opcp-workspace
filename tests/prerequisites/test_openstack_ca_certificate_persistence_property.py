"""Property test P3 — CA certificate persistence round-trip.

Spec: .kiro/specs/openstack-ca-certificate (task 4.3)

- Property 3: CA certificate persistence round-trip
    Feature: openstack-ca-certificate, Property 3: CA certificate persistence
    round-trip.

    For any CA certificate string (including the empty string), saving the
    credential configuration for an installation via the credentials endpoints
    and then loading it returns a configuration whose ``ca_certificate`` equals
    the saved value.

    **Validates: Requirements 2.1, 2.2, 2.4**

The credentials endpoints (``PUT``/``GET`` on
``/api/prerequisites/installations/{id}/servers-nodes/credentials``) persist the
CA certificate as a non-secret plaintext field. Persistence does not parse the
value as PEM (PEM validation only happens at retrieve time), so an arbitrary
string — including the empty string — must round-trip verbatim.

This test is DB-backed and reuses the ``client``/``db_session``/``member_user``/
``installation_id`` fixtures from the prerequisites test suite. Following the
established property-test pattern in ``test_openstack_credentials.py``, a single
function-scoped ``client``/``installation`` is reused across examples and the
credential config row is cleared at the end of each example so state never leaks
between examples. Function-scoped-fixture health checks are suppressed as
recommended by Hypothesis for this pattern.
"""
import uuid

import pytest
from fastapi import status
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models import User, UserRole
from app.models.credential_config import CredentialConfig  # noqa: F401 (register table)
from app.auth.token import create_access_token


# ---------------------------------------------------------------------------
# Fixtures / helpers (mirroring tests/prerequisites/test_openstack_credentials.py)
# ---------------------------------------------------------------------------
@pytest.fixture
def member_user(db_session):
    """Create an authenticated member user (credentials endpoints require auth)."""
    user = User(
        email="ca-cert@prereq.test",
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


def _cred_url(installation_id: str) -> str:
    return (
        f"/api/prerequisites/installations/{installation_id}"
        f"/servers-nodes/credentials"
    )


# CA certificate strings are non-secret free-form text. The generator includes
# the empty string (min_size=0) so the empty-value boundary (Req 2.2) is
# exercised alongside arbitrary multi-line/PEM-like content. Printable
# characters plus newlines keep the generated values representative of pasted
# PEM text while remaining JSON-serializable.
_CA_CERTIFICATE = st.text(
    alphabet=st.characters(
        min_codepoint=32,
        max_codepoint=126,
        blacklist_categories=("Cs",),
    )
    | st.sampled_from(["\n", "\r"]),
    min_size=0,
    max_size=200,
)


# ===========================================================================
# Task 4.3 — Property 3: CA certificate persistence round-trip
# Feature: openstack-ca-certificate, Property 3: CA certificate persistence
# round-trip
# Validates Requirements 2.1, 2.2, 2.4
# ===========================================================================
class TestProperty3CaCertificatePersistenceRoundTrip:
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(ca_certificate=_CA_CERTIFICATE)
    def test_ca_certificate_round_trips_through_save_then_load(
        self, client, db_session, member_user, installation_id, ca_certificate
    ):
        """For any CA string, save-then-load returns the same ``ca_certificate``."""
        headers = _headers(member_user)

        # Save (PUT) with the generated CA certificate plus the required
        # auth_url / credential_id / nova_endpoint fields and a secret.
        put = client.put(
            _cred_url(installation_id),
            json={
                "auth_url": "https://keystone.example/v3",
                "credential_id": "cred-ca",
                "nova_endpoint": "https://nova.example/v2.1",
                "credential_secret": "ca-roundtrip-secret",
                "ca_certificate": ca_certificate,
            },
            headers=headers,
        )
        assert put.status_code == status.HTTP_200_OK
        # The save response already echoes the persisted (non-secret) CA value.
        assert put.json()["ca_certificate"] == ca_certificate

        # Load (GET) and assert the CA certificate round-trips verbatim.
        get = client.get(_cred_url(installation_id), headers=headers)
        assert get.status_code == status.HTTP_200_OK
        assert get.json()["ca_certificate"] == ca_certificate

        # Clean up this example's row so state never leaks between examples.
        db_session.query(CredentialConfig).filter(
            CredentialConfig.installation_id == uuid.UUID(installation_id)
        ).delete()
        db_session.commit()
