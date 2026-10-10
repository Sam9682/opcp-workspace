"""Pydantic schemas for OPCP prerequisites endpoints

Bugfix: basics-prerequisites-404-fix
Validates Requirements 2.1, 2.3, 2.4

These schemas match the exact request/response shapes the frontend
``prerequisitesService.ts`` already sends and expects:

- ``StaticContentResponse``  -> ``{ slug, content, updated_at? }``
- ``StaticContentUpdateRequest`` (PUT body) -> ``{ content }``
- ``ClientAnswersResponse``   -> ``{ slug, answers }`` (``answers`` keyed by ``row_id``)
- ``ClientAnswerUpdateRequest`` (PUT body) -> ``{ answer }``

Error bodies reuse ``ErrorResponse`` from ``app.auth.schemas`` (imported here so
callers/routers get a single, consistent error contract) and are NOT redefined.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Re-export the shared error schema so error bodies stay consistent with the
# other routers. Do NOT redefine ErrorResponse here.
from app.auth.schemas import ErrorResponse

__all__ = [
    "StaticContentResponse",
    "StaticContentUpdateRequest",
    "ClientAnswersResponse",
    "ClientAnswerUpdateRequest",
    "PrerequisiteUpdateResponse",
    "InstallationCreateRequest",
    "InstallationUpdateRequest",
    "InstallationResponse",
    "InstallationListResponse",
    "CredentialConfigResponse",
    "CredentialConfigSaveRequest",
    "NovaServerSchema",
    "RetrieveServersResponse",
    "ServerNodePayload",
    "ServerNodesResponse",
    "ServerNodesSaveRequest",
    "ErrorResponse",
]


class StaticContentResponse(BaseModel):
    """Response schema for static prerequisites content (e.g. Basics, Network Flux).

    Matches the frontend ``StaticContentResponse`` interface:
    ``{ slug: string, content: string, updated_at?: string }``.
    """
    slug: str
    content: str
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }


class StaticContentUpdateRequest(BaseModel):
    """Request schema for saving static prerequisites content.

    Matches the frontend PUT body ``{ content }``.
    """
    content: str


class ClientAnswersResponse(BaseModel):
    """Response schema for a slug's client answers.

    Matches the frontend ``ClientAnswersResponse`` interface:
    ``{ slug: string, answers: Record<string, string> }``. The ``answers`` map
    is keyed by ``row_id``.
    """
    slug: str
    answers: dict[str, str]

    model_config = {
        "from_attributes": True
    }


class ClientAnswerUpdateRequest(BaseModel):
    """Request schema for saving a single client answer.

    Matches the frontend PUT body ``{ answer }``.
    """
    answer: str


class PrerequisiteUpdateResponse(BaseModel):
    """Response schema for successful PUT (upsert) operations."""
    success: bool
    slug: str

    model_config = {
        "from_attributes": True
    }


class InstallationCreateRequest(BaseModel):
    """Request schema for creating an Installation.

    Validates Requirements 6.1, 6.2, 6.5:
    - ``project_name`` is required and must not be blank/whitespace-only.
      The ``field_validator`` strips surrounding whitespace and raises a
      ``ValueError`` for empty values so FastAPI returns a 422 validation error.
    """
    project_name: str = Field(min_length=1)

    @field_validator("project_name")
    @classmethod
    def _strip_non_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("project_name must not be blank")
        return v


class InstallationUpdateRequest(InstallationCreateRequest):
    """Request schema for updating an Installation.

    Shares the same validation as :class:`InstallationCreateRequest`
    (non-blank ``project_name``). Validates Requirements 6.3, 6.5.
    """
    pass


class InstallationResponse(BaseModel):
    """Response schema for a single Installation.

    Matches the frontend Installation shape:
    ``{ id, project_name, created_at, updated_at }``. Validates Requirements 6.1, 6.2, 6.3.
    """
    id: UUID
    project_name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstallationListResponse(BaseModel):
    """Response schema for listing Installations.

    Matches the frontend ``{ installations: [...] }`` shape. Validates Requirement 6.1.
    """
    installations: list[InstallationResponse]


class CredentialConfigResponse(BaseModel):
    """OpenStack credential config returned to the client.

    The credential secret is NEVER present on this schema; only a
    ``secret_stored`` flag reflects whether an encrypted secret is persisted.
    This guarantees the secret can never be serialized back to the client on
    any code path. Validates Requirements 3.3, 5.3, 8.4.
    """
    auth_url: str
    credential_id: str
    nova_endpoint: str
    ca_certificate: str = ""  # non-secret, always returned (empty when unset)
    secret_stored: bool

    model_config = ConfigDict(from_attributes=False)


class CredentialConfigSaveRequest(BaseModel):
    """Request schema for saving/updating the OpenStack credential config.

    The non-secret fields are required and must be non-empty
    (``Field(min_length=1)``). ``credential_secret`` is optional; omit it to
    reuse the previously stored secret. Validates Requirements 3.3, 5.3.
    """
    auth_url: str = Field(min_length=1)
    credential_id: str = Field(min_length=1)
    nova_endpoint: str = Field(min_length=1)
    credential_secret: Optional[str] = None  # omit to reuse stored secret
    ca_certificate: str = ""  # optional; empty => system trust store


class NovaServerSchema(BaseModel):
    """A single OpenStack (Nova) server as returned to the client.

    Matches the frontend ``NovaServer`` shape ``{ id, name, status }``.
    Validates Requirements 5.3, 8.4.
    """
    id: str
    name: str
    status: str


class RetrieveServersResponse(BaseModel):
    """Response schema for the servers/retrieve endpoint.

    Matches the frontend ``RetrieveServersResponse`` shape
    ``{ servers: NovaServer[] }``. The secret and Keystone token are never
    included. Validates Requirements 5.3, 8.4.
    """
    servers: list[NovaServerSchema]


class ServerNodePayload(BaseModel):
    """A single server node override row (wire shape, snake_case).

    Matches the frontend ``ServerNodeOverridePayload`` shape
    ``{ node_uuid, serial_number, instance_uuid, power_state, provision_state,
    remark }``. ``node_uuid`` is the join key against the hardcoded default
    inventory and must be non-empty; the five editable fields default to the
    empty string. Validates Requirements 3.1, 3.2, 3.3.
    """
    node_uuid: str = Field(min_length=1)
    serial_number: str = ""
    instance_uuid: str = ""
    power_state: str = ""
    provision_state: str = ""
    remark: str = ""


class ServerNodesResponse(BaseModel):
    """Response schema for the servers-nodes overrides endpoints.

    Matches the frontend ``ServerNodesResponse`` shape ``{ nodes: [...] }``.
    The list is empty when no overrides are stored for the installation.
    Validates Requirements 3.1, 3.2, 3.3.
    """
    nodes: list[ServerNodePayload]


class ServerNodesSaveRequest(BaseModel):
    """Request schema for saving server node overrides (PUT body).

    Matches the frontend PUT body ``{ nodes: ServerNodeOverridePayload[] }``.
    Validates Requirements 3.1, 3.2, 3.3.
    """
    nodes: list[ServerNodePayload]
