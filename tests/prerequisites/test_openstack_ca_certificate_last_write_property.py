"""Property test P4 for the OpenStack CA certificate feature.

Spec: .kiro/specs/openstack-ca-certificate (task 4.4)

Property 4: Exactly one CA certificate per installation (last-write-wins)
    *For any* sequence of two saves of different CA certificate values to the
    same installation, loading the configuration SHALL return the value from the
    most recent save, and exactly one configuration row SHALL exist for that
    installation.

    Feature: openstack-ca-certificate, Property 4: Exactly one CA certificate
    per installation (last-write-wins)

    **Validates: Requirements 2.5**

The CA certificate is a non-secret field: it is persisted verbatim on every
save via ``PUT /api/prerequisites/installations/{id}/servers-nodes/credentials``
and returned on ``GET``. This test drives two saves with two distinct CA values
through the credentials endpoint, asserts the load returns the second value, and
queries the ``CredentialConfig`` table directly to confirm the
``uq_credential_config_installation`` unique constraint keeps exactly one row.

The endpoint URL helpers and the ``client`` / ``db_session`` / ``installation_id``
fixtures follow the same patterns as tests/prerequisites/test_openstack_credentials.py
and tests/conftest.py.
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
# Fixtures / helpers (mirroring test_openstack_credentials.py)
# ---------------------------------------------------------------------------
@pytest.fixture
def member_user(db_session):
    """Create an authenticated member user (credentials endpoints require auth)."""
    user = User(
        email="ca-lastwrite@prereq.test",
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


def _save_payload(ca_certificate: str) -> dict:
    """A valid save payload carrying the given CA certificate value.

    The non-CA required fields are held constant so the only thing changing
    between the two saves is ``ca_certificate``.
    """
    return {
        "auth_url": "https://keystone.example/v3",
        "credential_id": "cred-ca-lastwrite",
        "nova_endpoint": "https://nova.example/v2.1",
        "credential_secret": "ca-lastwrite-secret",
        "ca_certificate": ca_certificate,
    }


# Two distinct CA certificate values are generated as a pair of arbitrary
# printable strings constrained to be different from each other. The empty
# string is a valid CA value (system trust store), so it is included in the
# input space; ``filter`` guarantees the two values differ, which is what
# "two distinct values" requires.
_CA_TEXT = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=0,
    max_size=64,
)
_DISTINCT_CA_PAIR = st.tuples(_CA_TEXT, _CA_TEXT).filter(lambda pair: pair[0] != pair[1])


class TestProperty4OneRowLastWriteWins:
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(ca_pair=_DISTINCT_CA_PAIR)
    def test_two_distinct_saves_last_write_wins_single_row(
        self, client, db_session, member_user, installation_id, ca_pair
    ):
        """Feature: openstack-ca-certificate, Property 4: Exactly one CA
        certificate per installation (last-write-wins).

        Save two distinct CA certificate values in sequence for the same
        installation, then assert (a) GET returns the second value, and (b)
        exactly one CredentialConfig row exists for that installation.
        """
        first_ca, second_ca = ca_pair
        headers = _headers(member_user)

        # First save.
        r1 = client.put(
            _cred_url(installation_id),
            json=_save_payload(first_ca),
            headers=headers,
        )
        assert r1.status_code == status.HTTP_200_OK

        # Second save with a distinct CA value.
        r2 = client.put(
            _cred_url(installation_id),
            json=_save_payload(second_ca),
            headers=headers,
        )
        assert r2.status_code == status.HTTP_200_OK

        # Load returns the value from the most recent save (last-write-wins).
        get = client.get(_cred_url(installation_id), headers=headers)
        assert get.status_code == status.HTTP_200_OK
        assert get.json()["ca_certificate"] == second_ca

        # Exactly one configuration row exists for this installation.
        rows = (
            db_session.query(CredentialConfig)
            .filter(
                CredentialConfig.installation_id == uuid.UUID(installation_id)
            )
            .all()
        )
        assert len(rows) == 1
        # The single row's stored (plaintext, non-secret) value is the second.
        assert (rows[0].ca_certificate or "") == second_ca

        # Clean up this example's row so state never leaks between examples.
        db_session.query(CredentialConfig).filter(
            CredentialConfig.installation_id == uuid.UUID(installation_id)
        ).delete()
        db_session.commit()
