"""OPCP prerequisites API endpoints

Feature: vcf-prerequisites-update (installation-scoped)

Mounts the ``/api/prerequisites/*`` route family so the frontend
``prerequisitesService.ts`` contract is satisfied. This module now exposes:

- Installations CRUD (``/installations`` and ``/installations/{installation_id}``)
- Installation-scoped static content
  (``/installations/{installation_id}/{slug}/content``)
- Installation-scoped client answers
  (``/installations/{installation_id}/{slug}/answers[/{row_id}]``)

The prior single-instance ``/{slug}/content`` and ``/{slug}/answers`` routes were
intentionally re-scoped under an installation by the parent spec
``multi-instance-opcp-prerequisites`` and are removed here.

Validates Requirements 6.1-6.7, 7.1-7.7, 8.1-8.4:
- Serves installations CRUD (list/create/update/delete) with admin-only mutations
- Serves installation-scoped static content GET/PUT and client-answer GET/PUT
- Answers are shared per installation (no ``user_id`` scoping), last-write-wins
- Returns a structured 404 for unknown installations (``INSTALLATION_NOT_FOUND``)
  and unknown slugs (``PREREQUISITE_SLUG_NOT_FOUND``)
- Reuses the existing auth dependencies so auth behavior matches other routers
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.installation import Installation
from app.models.prerequisite import (
    PrerequisiteContent,
    PrerequisiteAnswer,
    ServerNodeOverride,
)
from app.models.credential_config import CredentialConfig
from app.auth.dependencies import get_current_user
from app.forum.dependencies import get_administrator
from app.prerequisites.schemas import (
    StaticContentResponse,
    StaticContentUpdateRequest,
    ClientAnswersResponse,
    ClientAnswerUpdateRequest,
    PrerequisiteUpdateResponse,
    InstallationCreateRequest,
    InstallationUpdateRequest,
    InstallationResponse,
    InstallationListResponse,
    CredentialConfigResponse,
    CredentialConfigSaveRequest,
    NovaServerSchema,
    RetrieveServersResponse,
    ServerNodePayload,
    ServerNodesResponse,
    ServerNodesSaveRequest,
)
from app.prerequisites.security import encrypt_secret, decrypt_secret
from app.prerequisites.openstack import (
    OpenStackProxy,
    OpenStackAuthError,
    OpenStackConnectionError,
    OpenStackServiceError,
    OpenStackCACertificateError,
)
from app.auth.schemas import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prerequisites", tags=["prerequisites"])

# Known slug sets, kept in sync with the frontend PREREQ_NAV_ITEMS.
# Static slugs render editable static content; qa slugs render question/answer forms.
STATIC_SLUGS: frozenset[str] = frozenset({"basics", "network-flux"})
QA_SLUGS: frozenset[str] = frozenset(
    {"opcp-context", "network-checklist", "core-control-plane", "cloudstore", "vcf"}
)


def _slug_not_found(slug: str) -> HTTPException:
    """Build the structured, resource-specific 404 for an unknown slug.

    This intentionally differs from FastAPI's default unmatched-route
    ``{"detail": "Not Found"}`` body: the route IS served, but the requested
    slug is not a recognized prerequisite resource.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=ErrorResponse.create(
            code="PREREQUISITE_SLUG_NOT_FOUND",
            message="Unknown prerequisite slug",
            details={"slug": slug},
        ),
    )


def _get_installation_or_404(db: Session, installation_id: UUID) -> Installation:
    """Load the Installation by id or raise a structured 404.

    Raises:
        HTTPException 404: with an ``INSTALLATION_NOT_FOUND`` structured body
            when no Installation matches ``installation_id``.
    """
    installation = (
        db.query(Installation)
        .filter(Installation.id == installation_id)
        .first()
    )
    if installation is None:
        logger.warning(f"Unknown installation requested: {installation_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="INSTALLATION_NOT_FOUND",
                message="Unknown installation",
                details={"installation_id": str(installation_id)},
            ),
        )
    return installation


async def get_answering_member(
    current_user: User = Depends(get_current_user),
) -> User:
    """Authorize a user to save client answers.

    Mirrors the frontend ``canAnswer`` gate: any authenticated user
    (administrators included) may submit client answers. The dependency on
    ``get_current_user`` ensures unauthenticated or invalid-token requests are
    rejected with 401 before reaching this authorization step.
    """
    return current_user


# ---------------------------------------------------------------------------
# Installations CRUD (task 4.1)
# ---------------------------------------------------------------------------


@router.get(
    "/installations",
    response_model=InstallationListResponse,
    summary="List all installations",
)
async def list_installations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InstallationListResponse:
    """Return every Installation as ``{"installations": [...]}``."""
    rows = db.query(Installation).order_by(Installation.created_at).all()
    return InstallationListResponse(installations=rows)


@router.post(
    "/installations",
    response_model=InstallationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an installation (admin only)",
)
async def create_installation(
    payload: InstallationCreateRequest,
    current_user: User = Depends(get_administrator),
    db: Session = Depends(get_db),
) -> InstallationResponse:
    """Create a new Installation, recording ``created_by`` (admin only)."""
    try:
        installation = Installation(
            project_name=payload.project_name,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(installation)
        db.commit()
        db.refresh(installation)

        logger.info(f"Installation created: id={installation.id}")
        return InstallationResponse.model_validate(installation)

    except Exception as e:  # pragma: no cover - defensive DB error path
        db.rollback()
        logger.error(f"Failed to create installation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="DATABASE_ERROR",
                message="Failed to create installation",
                details={"error": str(e)},
            ),
        )


@router.put(
    "/installations/{installation_id}",
    response_model=InstallationResponse,
    summary="Update an installation (admin only)",
)
async def update_installation(
    installation_id: UUID,
    payload: InstallationUpdateRequest,
    current_user: User = Depends(get_administrator),
    db: Session = Depends(get_db),
) -> InstallationResponse:
    """Update an existing Installation's ``project_name`` (admin only)."""
    installation = _get_installation_or_404(db, installation_id)

    try:
        installation.project_name = payload.project_name
        installation.updated_by = current_user.id
        db.commit()
        db.refresh(installation)

        logger.info(f"Installation updated: id={installation.id}")
        return InstallationResponse.model_validate(installation)

    except Exception as e:  # pragma: no cover - defensive DB error path
        db.rollback()
        logger.error(
            f"Failed to update installation id={installation_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="DATABASE_ERROR",
                message="Failed to update installation",
                details={"error": str(e)},
            ),
        )


@router.delete(
    "/installations/{installation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an installation (admin only)",
)
async def delete_installation(
    installation_id: UUID,
    current_user: User = Depends(get_administrator),
    db: Session = Depends(get_db),
) -> None:
    """Delete an Installation and cascade its content and answers (admin only)."""
    installation = _get_installation_or_404(db, installation_id)

    try:
        db.delete(installation)
        db.commit()
        logger.info(f"Installation deleted: id={installation_id}")
    except Exception as e:  # pragma: no cover - defensive DB error path
        db.rollback()
        logger.error(
            f"Failed to delete installation id={installation_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="DATABASE_ERROR",
                message="Failed to delete installation",
                details={"error": str(e)},
            ),
        )


# ---------------------------------------------------------------------------
# Installation-scoped static content (task 5.1)
# ---------------------------------------------------------------------------


@router.get(
    "/installations/{installation_id}/{slug}/content",
    response_model=StaticContentResponse,
    summary="Get static prerequisite content for an installation and slug",
)
async def get_static_content(
    installation_id: UUID,
    slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StaticContentResponse:
    """Return the persisted static content for an installation and known static slug.

    Returns an empty-content default for a known static slug that has never been
    saved under the installation. Unknown installations return
    ``INSTALLATION_NOT_FOUND``; unknown slugs return ``PREREQUISITE_SLUG_NOT_FOUND``.
    """
    _get_installation_or_404(db, installation_id)

    if slug not in STATIC_SLUGS:
        logger.warning(f"Unknown static prerequisite slug requested: {slug}")
        raise _slug_not_found(slug)

    row = (
        db.query(PrerequisiteContent)
        .filter(
            PrerequisiteContent.installation_id == installation_id,
            PrerequisiteContent.slug == slug,
        )
        .first()
    )

    if row is None:
        # Known static slug never saved for this installation -> empty default.
        return StaticContentResponse(slug=slug, content="", updated_at=None)

    return StaticContentResponse.model_validate(row)


@router.put(
    "/installations/{installation_id}/{slug}/content",
    response_model=PrerequisiteUpdateResponse,
    summary="Save static prerequisite content for an installation and slug (admin only)",
)
async def update_static_content(
    installation_id: UUID,
    slug: str,
    payload: StaticContentUpdateRequest,
    current_user: User = Depends(get_administrator),
    db: Session = Depends(get_db),
) -> PrerequisiteUpdateResponse:
    """Upsert the static content row for an installation and known static slug (admin only).

    Upsert keys on ``(installation_id, slug)`` and records ``updated_by``.
    """
    _get_installation_or_404(db, installation_id)

    if slug not in STATIC_SLUGS:
        logger.warning(f"Unknown static prerequisite slug on save: {slug}")
        raise _slug_not_found(slug)

    try:
        row = (
            db.query(PrerequisiteContent)
            .filter(
                PrerequisiteContent.installation_id == installation_id,
                PrerequisiteContent.slug == slug,
            )
            .first()
        )

        if row is None:
            row = PrerequisiteContent(
                installation_id=installation_id,
                slug=slug,
                content=payload.content,
                updated_by=current_user.id,
            )
            db.add(row)
        else:
            row.content = payload.content
            row.updated_by = current_user.id

        db.commit()
        db.refresh(row)

        logger.info(
            f"Static prerequisite content saved for "
            f"installation_id={installation_id}, slug={slug}"
        )
        return PrerequisiteUpdateResponse(success=True, slug=slug)

    except Exception as e:  # pragma: no cover - defensive DB error path
        db.rollback()
        logger.error(
            f"Failed to save static prerequisite content for "
            f"installation_id={installation_id}, slug={slug}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="DATABASE_ERROR",
                message="Failed to save prerequisite content",
                details={"error": str(e)},
            ),
        )


# ---------------------------------------------------------------------------
# Installation-scoped client answers (task 5.2)
# ---------------------------------------------------------------------------


@router.get(
    "/installations/{installation_id}/{slug}/answers",
    response_model=ClientAnswersResponse,
    summary="Get client answers for an installation and slug",
)
async def get_answers(
    installation_id: UUID,
    slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClientAnswersResponse:
    """Return the ``{ row_id: answer }`` map for an installation and known qa slug.

    Answers are shared per installation (no ``user_id`` scoping). Unknown
    installations return ``INSTALLATION_NOT_FOUND``; unknown slugs return
    ``PREREQUISITE_SLUG_NOT_FOUND``.
    """
    _get_installation_or_404(db, installation_id)

    if slug not in QA_SLUGS:
        logger.warning(f"Unknown qa prerequisite slug requested: {slug}")
        raise _slug_not_found(slug)

    rows = (
        db.query(PrerequisiteAnswer)
        .filter(
            PrerequisiteAnswer.installation_id == installation_id,
            PrerequisiteAnswer.slug == slug,
        )
        .all()
    )

    answers = {row.row_id: row.answer for row in rows}
    return ClientAnswersResponse(slug=slug, answers=answers)


@router.put(
    "/installations/{installation_id}/{slug}/answers/{row_id}",
    response_model=PrerequisiteUpdateResponse,
    summary="Save a single client answer for an installation (any authenticated user)",
)
async def update_answer(
    installation_id: UUID,
    slug: str,
    row_id: str,
    payload: ClientAnswerUpdateRequest,
    current_user: User = Depends(get_answering_member),
    db: Session = Depends(get_db),
) -> PrerequisiteUpdateResponse:
    """Upsert the ``(installation_id, slug, row_id)`` answer row for a known qa slug.

    Answers are shared per installation (last-write-wins); ``updated_by`` records
    the last editor. Any authenticated user (administrators included) may save.
    Unknown installations return ``INSTALLATION_NOT_FOUND``; unknown slugs return
    ``PREREQUISITE_SLUG_NOT_FOUND``.
    """
    _get_installation_or_404(db, installation_id)

    if slug not in QA_SLUGS:
        logger.warning(f"Unknown qa prerequisite slug on save: {slug}")
        raise _slug_not_found(slug)

    try:
        row = (
            db.query(PrerequisiteAnswer)
            .filter(
                PrerequisiteAnswer.installation_id == installation_id,
                PrerequisiteAnswer.slug == slug,
                PrerequisiteAnswer.row_id == row_id,
            )
            .first()
        )

        if row is None:
            row = PrerequisiteAnswer(
                installation_id=installation_id,
                slug=slug,
                row_id=row_id,
                answer=payload.answer,
                updated_by=current_user.id,
            )
            db.add(row)
        else:
            row.answer = payload.answer
            row.updated_by = current_user.id

        db.commit()
        db.refresh(row)

        logger.info(
            f"Client answer saved for installation_id={installation_id}, "
            f"slug={slug}, row_id={row_id}"
        )
        return PrerequisiteUpdateResponse(success=True, slug=slug)

    except Exception as e:  # pragma: no cover - defensive DB error path
        db.rollback()
        logger.error(
            f"Failed to save client answer for installation_id={installation_id}, "
            f"slug={slug}, row_id={row_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="DATABASE_ERROR",
                message="Failed to save prerequisite answer",
                details={"error": str(e)},
            ),
        )


# ---------------------------------------------------------------------------
# Installation-scoped OpenStack credential config (servers-nodes tab, task 4.2)
# ---------------------------------------------------------------------------


def _credential_config_response(
    config: CredentialConfig | None,
) -> CredentialConfigResponse:
    """Map a ``CredentialConfig`` row (or absence) to the client response.

    The credential secret is NEVER serialized; ``secret_stored`` only reflects
    whether an encrypted secret is persisted. When ``config`` is ``None`` an
    empty default is returned (``secret_stored=False``). ``CredentialConfigResponse``
    is declared with ``from_attributes=False``, so fields are mapped explicitly.
    """
    if config is None:
        return CredentialConfigResponse(
            auth_url="",
            credential_id="",
            nova_endpoint="",
            ca_certificate="",
            secret_stored=False,
        )

    return CredentialConfigResponse(
        auth_url=config.auth_url,
        credential_id=config.credential_id,
        nova_endpoint=config.nova_endpoint,
        ca_certificate=config.ca_certificate or "",
        secret_stored=config.credential_secret_encrypted is not None,
    )


def _upsert_credential_config(
    db: Session,
    installation_id: UUID,
    payload: CredentialConfigSaveRequest,
    updated_by: UUID,
) -> CredentialConfig:
    """Upsert the credential config for an installation, keyed on ``installation_id``.

    The non-secret fields (Auth URL, Credential ID, Nova endpoint, CA
    certificate) are always written; an empty CA certificate is persisted as
    empty (it clears any previous value). The credential secret is encrypted
    and stored only when a ``credential_secret`` value is provided; when
    omitted, any previously stored secret is left untouched. This does NOT
    commit — the caller is responsible for the commit/rollback so the upsert
    can be composed with a retrieve.
    """
    config = (
        db.query(CredentialConfig)
        .filter(CredentialConfig.installation_id == installation_id)
        .first()
    )

    if config is None:
        config = CredentialConfig(
            installation_id=installation_id,
            auth_url=payload.auth_url,
            credential_id=payload.credential_id,
            nova_endpoint=payload.nova_endpoint,
            updated_by=updated_by,
        )
        db.add(config)
    else:
        config.auth_url = payload.auth_url
        config.credential_id = payload.credential_id
        config.nova_endpoint = payload.nova_endpoint
        config.updated_by = updated_by

    # Non-secret CA certificate is always written; "" clears it.
    config.ca_certificate = payload.ca_certificate

    # Encrypt and store the secret only when a value is provided; otherwise
    # preserve any previously stored secret.
    if payload.credential_secret:
        config.credential_secret_encrypted = encrypt_secret(
            payload.credential_secret
        )

    return config


@router.get(
    "/installations/{installation_id}/servers-nodes/credentials",
    response_model=CredentialConfigResponse,
    summary="Get the OpenStack credential config for an installation",
)
async def get_credential_config(
    installation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CredentialConfigResponse:
    """Return the stored credential config for an installation.

    The credential secret is never returned; ``secret_stored`` reflects whether
    an encrypted secret is persisted. When no config exists yet for the
    installation, an empty default (``secret_stored=False``) is returned.
    Unknown installations return ``INSTALLATION_NOT_FOUND``.
    """
    _get_installation_or_404(db, installation_id)

    config = (
        db.query(CredentialConfig)
        .filter(CredentialConfig.installation_id == installation_id)
        .first()
    )

    return _credential_config_response(config)


@router.put(
    "/installations/{installation_id}/servers-nodes/credentials",
    response_model=CredentialConfigResponse,
    summary="Save the OpenStack credential config for an installation",
)
async def save_credential_config(
    installation_id: UUID,
    payload: CredentialConfigSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CredentialConfigResponse:
    """Upsert the credential config for an installation, keyed on ``installation_id``.

    The non-secret fields (Auth URL, Credential ID, Nova endpoint) are always
    persisted. The credential secret is encrypted and stored only when a
    ``credential_secret`` value is provided; when omitted, any previously stored
    secret is left untouched. The secret is never returned in the response.
    Unknown installations return ``INSTALLATION_NOT_FOUND``.
    """
    _get_installation_or_404(db, installation_id)

    try:
        config = _upsert_credential_config(
            db, installation_id, payload, current_user.id
        )

        db.commit()
        db.refresh(config)

        logger.info(
            f"OpenStack credential config saved for "
            f"installation_id={installation_id}"
        )
        return _credential_config_response(config)

    except Exception as e:  # pragma: no cover - defensive DB error path
        db.rollback()
        logger.error(
            f"Failed to save credential config for "
            f"installation_id={installation_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="DATABASE_ERROR",
                message="Failed to save credential config",
                details={"error": str(e)},
            ),
        )


@router.post(
    "/installations/{installation_id}/servers-nodes/servers/retrieve",
    response_model=RetrieveServersResponse,
    summary="Persist config and retrieve the live OpenStack server list",
)
async def retrieve_servers(
    installation_id: UUID,
    payload: CredentialConfigSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RetrieveServersResponse:
    """Persist the credential config, resolve the secret, and list live servers.

    Flow:

    1. Verify the installation exists (``INSTALLATION_NOT_FOUND`` otherwise).
    2. Upsert the credential config (Auth URL, Credential ID, Nova endpoint),
       encrypting and storing the secret only when a ``credential_secret`` value
       is provided.
    3. Resolve the effective secret: the inline ``credential_secret`` when
       provided, otherwise the decrypted stored secret. If neither exists,
       return ``MISSING_CREDENTIAL_SECRET`` (400) — defense in depth behind the
       client-side validation.
    4. Run the two-step OpenStack flow via :class:`OpenStackProxy` and return the
       mapped ``{id, name, status}`` rows.

    The credential secret and the Keystone token are never included in any
    response, on success or on error. OpenStack failures map to:
    ``OpenStackCACertificateError`` -> 400 ``INVALID_CA_CERTIFICATE``,
    ``OpenStackAuthError`` -> 401 ``AUTH_FAILED``,
    ``OpenStackConnectionError`` -> 502 ``CONNECTION_FAILED``,
    ``OpenStackServiceError`` -> 502 ``OPENSTACK_ERROR``. DB failures roll back
    and return ``DATABASE_ERROR`` (500).
    """
    _get_installation_or_404(db, installation_id)

    # Persist the config first so subsequent loads prefill the non-secret fields.
    try:
        config = _upsert_credential_config(
            db, installation_id, payload, current_user.id
        )
        db.commit()
        db.refresh(config)
    except Exception as e:  # pragma: no cover - defensive DB error path
        db.rollback()
        logger.error(
            f"Failed to save credential config during retrieve for "
            f"installation_id={installation_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="DATABASE_ERROR",
                message="Failed to save credential config",
                details={"error": str(e)},
            ),
        )

    # Resolve the effective secret: inline value if provided, else the stored
    # (decrypted) secret. The plaintext exists only transiently here.
    if payload.credential_secret:
        secret = payload.credential_secret
    elif config.credential_secret_encrypted is not None:
        secret = decrypt_secret(config.credential_secret_encrypted)
    else:
        logger.warning(
            f"Retrieve requested with no secret available for "
            f"installation_id={installation_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="MISSING_CREDENTIAL_SECRET",
                message="No credential secret was provided or is stored.",
            ),
        )

    # Run the OpenStack flow. The secret and token stay inside the proxy call;
    # only mapped server rows are returned. Error bodies never carry the secret
    # or token — the exception messages and details reference non-sensitive
    # context only.
    try:
        servers = await OpenStackProxy().retrieve(
            auth_url=config.auth_url,
            credential_id=config.credential_id,
            secret=secret,
            nova_endpoint=config.nova_endpoint,
            ca_certificate=config.ca_certificate or "",
        )
    except OpenStackCACertificateError as e:
        # Non-secret, but the certificate content is never logged — only the
        # non-sensitive installation id is recorded.
        logger.warning(
            f"Invalid CA certificate for installation_id={installation_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code=e.code,
                message=str(e),
            ),
        )
    except OpenStackAuthError as e:
        logger.warning(
            f"OpenStack authentication failed for installation_id={installation_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse.create(
                code=e.code,
                message=str(e),
            ),
        )
    except OpenStackConnectionError as e:
        logger.error(
            f"OpenStack connection failed for installation_id={installation_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse.create(
                code=e.code,
                message=str(e),
            ),
        )
    except OpenStackServiceError as e:
        logger.error(
            f"OpenStack service error for installation_id={installation_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse.create(
                code=e.code,
                message=str(e),
            ),
        )

    logger.info(
        f"OpenStack server list retrieved for "
        f"installation_id={installation_id} ({len(servers)} servers)"
    )
    return RetrieveServersResponse(
        servers=[
            NovaServerSchema(id=s.id, name=s.name, status=s.status)
            for s in servers
        ]
    )


# ---------------------------------------------------------------------------
# Installation-scoped server node overrides (servers-nodes tab, task 9.1)
# ---------------------------------------------------------------------------


def _server_node_response(
    overrides: list[ServerNodeOverride],
) -> ServerNodesResponse:
    """Map stored ``ServerNodeOverride`` rows to the client response shape.

    Returns the stored overrides as ``{ nodes: [...] }`` (snake_case wire shape).
    The list is empty when no overrides are stored for the installation. The
    frontend layers these over its own default inventory (``SERVER_NODES``).
    """
    return ServerNodesResponse(
        nodes=[
            ServerNodePayload(
                node_uuid=row.node_uuid,
                serial_number=row.serial_number,
                instance_uuid=row.instance_uuid,
                power_state=row.power_state,
                provision_state=row.provision_state,
                remark=row.remark,
            )
            for row in overrides
        ]
    )


@router.get(
    "/installations/{installation_id}/servers-nodes/nodes",
    response_model=ServerNodesResponse,
    summary="Get the stored server node overrides for an installation",
)
async def get_server_nodes(
    installation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ServerNodesResponse:
    """Return the stored server node overrides for an installation.

    Returns the persisted override rows (keyed by ``node_uuid``) as
    ``ServerNodesResponse``; the list is empty when no overrides exist for the
    installation. Any authenticated user may read. Unknown installations return
    ``INSTALLATION_NOT_FOUND``. Validates Requirements 3.1, 3.3.
    """
    _get_installation_or_404(db, installation_id)

    overrides = (
        db.query(ServerNodeOverride)
        .filter(ServerNodeOverride.installation_id == installation_id)
        .all()
    )

    return _server_node_response(overrides)


@router.put(
    "/installations/{installation_id}/servers-nodes/nodes",
    response_model=ServerNodesResponse,
    summary="Save server node overrides for an installation (member/administrator)",
)
async def save_server_nodes(
    installation_id: UUID,
    payload: ServerNodesSaveRequest,
    current_user: User = Depends(get_answering_member),
    db: Session = Depends(get_db),
) -> ServerNodesResponse:
    """Upsert one server node override per ``node_uuid`` for an installation.

    Upserts keyed on ``(installation_id, node_uuid)`` (last-write-wins), commits,
    and returns the stored overrides. A member or administrator (any
    authenticated user, matching the answers write path via ``get_answering_member``)
    may save. Unknown installations return ``INSTALLATION_NOT_FOUND``; DB failures
    roll back and return ``DATABASE_ERROR`` (500). Validates Requirements 3.1, 3.2, 3.3, 3.4.
    """
    _get_installation_or_404(db, installation_id)

    try:
        existing = (
            db.query(ServerNodeOverride)
            .filter(ServerNodeOverride.installation_id == installation_id)
            .all()
        )
        by_uuid = {row.node_uuid: row for row in existing}

        for node in payload.nodes:
            row = by_uuid.get(node.node_uuid)
            if row is None:
                row = ServerNodeOverride(
                    installation_id=installation_id,
                    node_uuid=node.node_uuid,
                    serial_number=node.serial_number,
                    instance_uuid=node.instance_uuid,
                    power_state=node.power_state,
                    provision_state=node.provision_state,
                    remark=node.remark,
                    updated_by=current_user.id,
                )
                db.add(row)
                by_uuid[node.node_uuid] = row
            else:
                row.serial_number = node.serial_number
                row.instance_uuid = node.instance_uuid
                row.power_state = node.power_state
                row.provision_state = node.provision_state
                row.remark = node.remark
                row.updated_by = current_user.id

        db.commit()

        overrides = (
            db.query(ServerNodeOverride)
            .filter(ServerNodeOverride.installation_id == installation_id)
            .all()
        )

        logger.info(
            f"Server node overrides saved for installation_id={installation_id} "
            f"({len(payload.nodes)} rows)"
        )
        return _server_node_response(overrides)

    except Exception as e:  # pragma: no cover - defensive DB error path
        db.rollback()
        logger.error(
            f"Failed to save server node overrides for "
            f"installation_id={installation_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="DATABASE_ERROR",
                message="Failed to save server node overrides",
                details={"error": str(e)},
            ),
        )
