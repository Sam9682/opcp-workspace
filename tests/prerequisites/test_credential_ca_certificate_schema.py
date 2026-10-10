"""Unit tests for the ``ca_certificate`` credential schema field.

Feature spec: .kiro/specs/openstack-ca-certificate

Task 2.2 — Write unit tests for the schema field
Validates: Requirements 2.3, 1.3

These example tests assert the schema contract for the non-secret CA
certificate field:

- ``CredentialConfigResponse`` always carries ``ca_certificate`` (a non-secret
  field, returned to the client) while never carrying the credential secret —
  only the ``secret_stored`` flag reflects whether a secret is persisted
  (Requirement 2.3).
- ``CredentialConfigSaveRequest`` accepts an empty ``ca_certificate`` value: an
  empty CA certificate is a valid state (use the system trust store) and must
  never gate save/retrieve (Requirement 1.3).
"""
from app.prerequisites.schemas import (
    CredentialConfigResponse,
    CredentialConfigSaveRequest,
)


def test_response_includes_ca_certificate_but_not_secret():
    """Feature: openstack-ca-certificate — CredentialConfigResponse contract

    Validates: Requirements 2.3

    ``ca_certificate`` is a present, returned field on the response while the
    credential secret is never serialized (only ``secret_stored``).
    """
    response = CredentialConfigResponse(
        auth_url="https://keystone.example/v3",
        credential_id="cred-123",
        nova_endpoint="https://nova.example/v2.1",
        ca_certificate="-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n",
        secret_stored=True,
    )

    fields = CredentialConfigResponse.model_fields
    assert "ca_certificate" in fields
    # The secret must never be part of the response schema on any code path.
    assert "credential_secret" not in fields
    assert "credential_secret_encrypted" not in fields

    dumped = response.model_dump()
    assert "ca_certificate" in dumped
    assert dumped["ca_certificate"] == (
        "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"
    )
    assert "credential_secret" not in dumped
    assert "credential_secret_encrypted" not in dumped


def test_response_ca_certificate_defaults_to_empty():
    """Feature: openstack-ca-certificate — CredentialConfigResponse default

    Validates: Requirements 2.3

    When no CA certificate is set, the response field defaults to the empty
    string rather than being absent or null.
    """
    response = CredentialConfigResponse(
        auth_url="https://keystone.example/v3",
        credential_id="cred-123",
        nova_endpoint="https://nova.example/v2.1",
        secret_stored=False,
    )

    assert response.ca_certificate == ""


def test_save_request_accepts_empty_ca_certificate():
    """Feature: openstack-ca-certificate — CredentialConfigSaveRequest empty CA

    Validates: Requirements 1.3

    An empty ``ca_certificate`` validates successfully — it is optional and an
    empty value means "use the system default trust store".
    """
    request = CredentialConfigSaveRequest(
        auth_url="https://keystone.example/v3",
        credential_id="cred-123",
        nova_endpoint="https://nova.example/v2.1",
        ca_certificate="",
    )

    assert request.ca_certificate == ""


def test_save_request_ca_certificate_is_optional():
    """Feature: openstack-ca-certificate — CredentialConfigSaveRequest omitted CA

    Validates: Requirements 1.3

    Omitting ``ca_certificate`` entirely is valid and defaults to the empty
    string, so an absent value never gates save/retrieve.
    """
    request = CredentialConfigSaveRequest(
        auth_url="https://keystone.example/v3",
        credential_id="cred-123",
        nova_endpoint="https://nova.example/v2.1",
    )

    assert request.ca_certificate == ""
