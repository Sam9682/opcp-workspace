"""Bug condition exploration test for the prerequisites 404 bug, migrated to the
installation-scoped contract.

Bugfix spec: .kiro/specs/basics-prerequisites-404-fix
Migrated by: .kiro/specs/vcf-prerequisites-update (task 6.1)

This test ENCODES the EXPECTED behavior (Property 1 in design.md) for the
prerequisites route family. The parent spec ``multi-instance-opcp-prerequisites``
re-scoped the family under an installation, so the served paths are now:

    /api/prerequisites/installations/{installation_id}/{slug}/content
    /api/prerequisites/installations/{installation_id}/{slug}/answers
    /api/prerequisites/installations/{installation_id}/{slug}/answers/{rowId}

The single-instance ``/{slug}/content`` and ``/{slug}/answers`` routes were
removed. Known slugs (under a valid installation) return 200 with the correct
shape; unknown slugs return a resource-specific ``PREREQUISITE_SLUG_NOT_FOUND``
404, and unknown installations return ``INSTALLATION_NOT_FOUND`` (Requirements
2.1-2.6, 7.1-7.7).

isBugCondition(request): any request whose path matches
    /api/prerequisites/installations/{id}/{slug}/content
    /api/prerequisites/installations/{id}/{slug}/answers
    /api/prerequisites/installations/{id}/{slug}/answers/{rowId}

Validates: Requirements 9.3, 7.7 (and, unchanged in intent, 1.1-1.5, 2.1-2.6)

Property 1: Bug Condition - Prerequisites API is served, not 404
"""
import pytest
from fastapi import status

from app.models import User, UserRole
from app.auth.token import create_access_token


# --- Known slug sets (kept in sync with the frontend PREREQ_NAV_ITEMS) ---
STATIC_SLUGS = ("basics", "network-flux")
QA_SLUGS = ("network-checklist", "core-control-plane", "cloudstore", "vcf")


@pytest.fixture
def admin_user(db_session):
    """Create an administrator user (allowed to PUT static content)."""
    user = User(
        email="admin@prereq.test",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def member_user(db_session):
    """Create a member user (allowed to read and to PUT answers)."""
    user = User(
        email="member@prereq.test",
        password_hash="hashed_password",
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _headers(user):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# isBugCondition encoding: the concrete served paths/verbs of the installation-
# scoped contract. A request is in the family iff its path matches
#   /api/prerequisites/installations/{id}/{slug}/content
#   /api/prerequisites/installations/{id}/{slug}/answers[/{rowId}]
# ---------------------------------------------------------------------------
def _is_bug_condition(method: str, path: str) -> bool:
    """Return True if the request targets the prerequisites API contract."""
    parts = [p for p in path.split("/") if p]
    # api / prerequisites / installations / {id} / {slug} / {resource}[/{row}]
    if len(parts) < 6:
        return False
    if parts[0] != "api" or parts[1] != "prerequisites" or parts[2] != "installations":
        return False
    resource = parts[5]
    if resource == "content" and len(parts) == 6:
        return True
    if resource == "answers" and len(parts) in (6, 7):
        return True
    return False


# ---------------------------------------------------------------------------
# Property 1: every request in the family is served, not an unmatched-route 404.
# ---------------------------------------------------------------------------

def test_get_basics_content_is_served(client, member_user, installation_id):
    """GET .../{id}/basics/content -> 200 {slug, content, updated_at?}.

    Reported "Basics" symptom (Requirement 2.1). Never an unmatched 404.
    """
    path = f"/api/prerequisites/installations/{installation_id}/basics/content"
    assert _is_bug_condition("GET", path)
    resp = client.get(path, headers=_headers(member_user))

    assert resp.status_code != status.HTTP_404_NOT_FOUND, (
        f"COUNTEREXAMPLE: GET {path} -> 404 unmatched route "
        f"instead of 200 {{slug, content}} (bug confirmed)"
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["slug"] == "basics"
    assert "content" in body


def test_get_network_flux_content_is_served(client, member_user, installation_id):
    """GET .../{id}/network-flux/content -> 200 (Req 2.3)."""
    path = f"/api/prerequisites/installations/{installation_id}/network-flux/content"
    assert _is_bug_condition("GET", path)
    resp = client.get(path, headers=_headers(member_user))

    assert resp.status_code != status.HTTP_404_NOT_FOUND, (
        f"COUNTEREXAMPLE: GET {path} -> 404 unmatched route "
        f"instead of 200 {{slug, content}} (bug confirmed)"
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["slug"] == "network-flux"
    assert "content" in body


def test_get_answers_is_served(client, member_user, installation_id):
    """GET .../{id}/network-checklist/answers -> 200 {slug, answers} (Req 2.4)."""
    path = f"/api/prerequisites/installations/{installation_id}/network-checklist/answers"
    assert _is_bug_condition("GET", path)
    resp = client.get(path, headers=_headers(member_user))

    assert resp.status_code != status.HTTP_404_NOT_FOUND, (
        f"COUNTEREXAMPLE: GET {path} -> 404 unmatched route "
        f"instead of 200 {{slug, answers}} (bug confirmed)"
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["slug"] == "network-checklist"
    assert isinstance(body["answers"], dict)


def test_put_static_content_is_served(client, admin_user, installation_id):
    """PUT .../{id}/basics/content persists (Req 2.5)."""
    path = f"/api/prerequisites/installations/{installation_id}/basics/content"
    assert _is_bug_condition("PUT", path)
    resp = client.put(
        path,
        json={"content": "<p>hello</p>"},
        headers=_headers(admin_user),
    )

    assert resp.status_code != status.HTTP_404_NOT_FOUND, (
        f"COUNTEREXAMPLE: PUT {path} -> 404 unmatched route "
        f"instead of a success status (bug confirmed, change not persisted)"
    )
    assert resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)


def test_put_answer_is_served(client, member_user, installation_id):
    """PUT .../{id}/cloudstore/answers/cs-subnet-cidr persists (Req 2.5)."""
    path = (
        f"/api/prerequisites/installations/{installation_id}"
        f"/cloudstore/answers/cs-subnet-cidr"
    )
    assert _is_bug_condition("PUT", path)
    resp = client.put(
        path,
        json={"answer": "10.0.0.0/24"},
        headers=_headers(member_user),
    )

    assert resp.status_code != status.HTTP_404_NOT_FOUND, (
        f"COUNTEREXAMPLE: PUT {path} -> 404 unmatched route "
        f"instead of a success status (bug confirmed, answer not persisted)"
    )
    assert resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)


def test_unknown_slug_content_is_resource_specific_404(
    client, member_user, installation_id
):
    """Edge: GET .../{id}/does-not-exist/content under a valid installation.

    A resource-specific 404 carries a structured ErrorResponse
    (``PREREQUISITE_SLUG_NOT_FOUND``), unlike FastAPI's default unmatched-route
    body ``{"detail": "Not Found"}`` (Requirement 2.6 / 7.7).
    """
    path = f"/api/prerequisites/installations/{installation_id}/does-not-exist/content"
    assert _is_bug_condition("GET", path)
    resp = client.get(path, headers=_headers(member_user))

    assert resp.status_code == status.HTTP_404_NOT_FOUND
    body = resp.json()
    assert body != {"detail": "Not Found"}, (
        f"COUNTEREXAMPLE: GET {path} -> unmatched-route 404 "
        f'{{"detail": "Not Found"}} instead of a resource-specific ErrorResponse'
    )
    code = (
        body.get("error", {}).get("code")
        if isinstance(body.get("error"), dict)
        else body.get("detail", {}).get("error", {}).get("code")
    )
    assert code == "PREREQUISITE_SLUG_NOT_FOUND"


def test_unknown_installation_content_is_installation_not_found(
    client, member_user, unknown_installation_id
):
    """GET content under an unknown installation -> INSTALLATION_NOT_FOUND (Req 7.6).

    New coverage for the installation-scoped contract: an installation id that
    matches no Installation yields a structured ``INSTALLATION_NOT_FOUND`` 404
    even for a known static slug.
    """
    path = (
        f"/api/prerequisites/installations/{unknown_installation_id}/basics/content"
    )
    assert _is_bug_condition("GET", path)
    resp = client.get(path, headers=_headers(member_user))

    assert resp.status_code == status.HTTP_404_NOT_FOUND
    body = resp.json()
    assert body != {"detail": "Not Found"}
    code = (
        body.get("error", {}).get("code")
        if isinstance(body.get("error"), dict)
        else body.get("detail", {}).get("error", {}).get("code")
    )
    assert code == "INSTALLATION_NOT_FOUND"
