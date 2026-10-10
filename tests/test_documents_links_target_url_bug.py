"""Bug condition exploration tests for the "documents-links-html-link" bugfix.

Property 1 (Bug Condition): Links render as an anchor to the target URL. The
backend half of that property is that the document list endpoint exposes the
target URL of a `links` document via a `target_url` field so the frontend has
an `href` to render at load time.

    isBugCondition(doc) === (doc.category == 'links')

These tests are run against the UNFIXED code and are EXPECTED TO FAIL — the
failure confirms the bug: `GET /api/documents` returns no `target_url` (the
field is absent from `DocumentResponse` today), so the URL contained in the
`.links` file is never surfaced to the client.

Storage is isolated by monkeypatching the shared ``storage_service.upload_dir``
singleton at a ``tmp_path`` and writing the seeded document's ``.links`` file
there; the router imports that same singleton, so ``get_file_path`` resolves it.

Validates: Requirements 2.3
"""
import pytest
from fastapi import status

from app.models import User, Document
from app.models.document import DocumentCategory, AccessLevel
from app.auth.token import create_access_token
from app.services.storage_service import storage_service


TARGET_URL = "https://console.aws.amazon.com"


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    """Point the shared storage singleton at an isolated temp upload dir."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(storage_service, "upload_dir", upload_dir)
    return upload_dir


@pytest.fixture
def admin_user(db_session):
    user = User(
        email="admin@test.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role="administrator",
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(admin_user):
    token = create_access_token({"sub": str(admin_user.id)})
    return {"Authorization": f"Bearer {token}"}


def _seed_links_document(db_session, admin_user, upload_dir, url: str) -> Document:
    """Persist a links document and write its .links file containing `url`."""
    filename = "aws-console.links"
    (upload_dir / filename).write_text(url + "\n", encoding="utf-8")

    document = Document(
        filename=filename,
        original_name="AWS Console",
        mime_type="text/plain",
        size=len(url),
        category=DocumentCategory.LINKS,
        access_level=AccessLevel.PUBLIC,
        uploaded_by=admin_user.id,
        download_count=0,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_list_exposes_target_url_for_links_document(
    client, admin_headers, db_session, admin_user, isolated_storage
):
    """A links document's list entry exposes target_url equal to the .links URL.

    EXPECTED TO FAIL on unfixed code: DocumentResponse has no `target_url` field,
    so the URL from the `.links` file is absent from the response.
    """
    _seed_links_document(db_session, admin_user, isolated_storage, TARGET_URL)

    response = client.get("/api/documents", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["total"] == 1
    doc = data["documents"][0]
    assert doc["category"] == DocumentCategory.LINKS.value

    # The core assertion: the list surfaces the link target so the frontend can
    # render an anchor without hitting the download endpoint.
    assert "target_url" in doc, "DocumentResponse should expose target_url for links"
    assert doc["target_url"] == TARGET_URL
