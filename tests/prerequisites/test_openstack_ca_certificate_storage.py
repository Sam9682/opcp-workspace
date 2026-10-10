"""Example / edge storage tests for the OpenStack CA certificate field.

Spec: .kiro/specs/openstack-ca-certificate (task 4.5)

Two example/edge tests covering non-encrypted storage and the empty-string
boundary of the ``ca_certificate`` credential field:

- 2.3 — Non-encrypted storage. After a PUT with a representative PEM, the
    persisted ``ca_certificate`` DB column equals the plaintext PEM *verbatim*
    (proving it is NOT encrypted, in contrast to
    ``credential_secret_encrypted`` which is Fernet ciphertext).
    _Requirements: 2.3_

- 2.2 — Empty-string save/load boundary. Saving with ``ca_certificate=""``
    then loading returns ``ca_certificate == ""``.
    _Requirements: 2.2_

These tests exercise the real credential endpoints (no outbound OpenStack call
is made, since neither test triggers ``/servers/retrieve``), and inspect the
``CredentialConfig`` row directly via ``db_session`` for the storage assertion.
The endpoint URL helpers and the auth-header helper mirror the patterns in
``tests/prerequisites/test_openstack_credentials.py``; the ``client``,
``db_session`` and ``installation_id`` fixtures come from ``tests/conftest.py``.
"""
import uuid

import pytest
from fastapi import status

from app.models import User, UserRole
from app.models.credential_config import CredentialConfig  # noqa: F401 (register table)
from app.auth.token import create_access_token


# A representative multi-line PEM certificate. Its exact bytes are what we
# expect to find, unchanged, in the persisted ``ca_certificate`` column. The
# storage path never parses it, so any well-formed PEM-looking text works to
# prove verbatim, non-encrypted persistence.
REPRESENTATIVE_PEM = (
    "-----BEGIN CERTIFICATE-----\n"
    "MIIBkTCB+wIJANhcO7YG8k8kMA0GCSqGSIb3DQEBCwUAMBQxEjAQBgNVBAMMCXRl\n"
    "c3QtY2EtMTAeFw0yNDAxMDEwMDAwMDBaFw0zNDAxMDEwMDAwMDBaMBQxEjAQBgNV\n"
    "BAMMCXRlc3QtY2EtMTCBnzANBgkqhkiG9w0BAQEFAAOBjQAwgYkCgYEAwF3Yk2Yl\n"
    "RepresentativeFakeBase64CertificateBodyForStorageTestOnly12345678\n"
    "-----END CERTIFICATE-----\n"
)


# ---------------------------------------------------------------------------
# Fixtures / helpers (mirrors tests/prerequisites/test_openstack_credentials.py)
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


# ===========================================================================
# Task 4.5 — Example / edge storage tests
# ===========================================================================
class TestCaCertificateStorage:
    def test_ca_certificate_persisted_as_plaintext_not_encrypted(
        self, client, db_session, member_user, installation_id
    ):
        """The persisted CA certificate equals the plaintext PEM verbatim (Req 2.3).

        Unlike the credential secret (stored as Fernet ciphertext in
        ``credential_secret_encrypted``), the CA certificate is a non-secret
        field stored without encryption. After a PUT, the DB row's
        ``ca_certificate`` column must contain the exact PEM text that was sent.
        """
        resp = client.put(
            _cred_url(installation_id),
            json={
                "auth_url": "https://keystone.example/v3",
                "credential_id": "cred-ca",
                "nova_endpoint": "https://nova.example/v2.1",
                "credential_secret": "s3cr3t-value",
                "ca_certificate": REPRESENTATIVE_PEM,
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
        # Stored verbatim: the column holds the exact plaintext PEM, proving it
        # is not encrypted or otherwise transformed on the way to the database.
        assert row.ca_certificate == REPRESENTATIVE_PEM
        # Contrast with the secret, which is stored only as (different) ciphertext.
        assert row.credential_secret_encrypted is not None
        assert row.credential_secret_encrypted != REPRESENTATIVE_PEM

    def test_empty_ca_certificate_save_then_load_returns_empty(
        self, client, member_user, installation_id
    ):
        """Saving an empty CA certificate then loading returns ``""`` (Req 2.2).

        An empty CA certificate is a valid, meaningful state (use the system
        default trust store). The save must succeed and the subsequent load must
        report an empty string for ``ca_certificate``.
        """
        put = client.put(
            _cred_url(installation_id),
            json={
                "auth_url": "https://keystone.example/v3",
                "credential_id": "cred-empty",
                "nova_endpoint": "https://nova.example/v2.1",
                "credential_secret": "another-secret",
                "ca_certificate": "",
            },
            headers=_headers(member_user),
        )
        assert put.status_code == status.HTTP_200_OK
        assert put.json()["ca_certificate"] == ""

        get = client.get(_cred_url(installation_id), headers=_headers(member_user))
        assert get.status_code == status.HTTP_200_OK
        assert get.json()["ca_certificate"] == ""
