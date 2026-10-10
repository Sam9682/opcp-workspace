"""Bug condition exploration test for the documents-page-categories bugfix.

Feature: documents-page-categories (BUGFIX)
Property 1: Bug Condition - Files Grouped By Originating Subfolder
Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4

CRITICAL: This test MUST FAIL on the current unfixed code. The failure CONFIRMS
the bug exists (files published from docs/to_publish are collapsed into a single
``documents`` category and subfolder files are not discovered recursively). This
is the SUCCESS case for this exploration task. DO NOT fix the code or the test.

The property is scoped to the concrete originating subfolders
``{docs, links, scripts, trainings}``: for each subfolder, a seeded file must
end up with ``category == originatingSubfolder`` (design Bug Condition
``isBugCondition(input)``). Files under ``movies``/``images`` must be excluded.
"""
import pytest

from app.models.user import User, UserRole
from app.models.document import Document, DocumentCategory
from app.services import document_seed_service
from app.services.document_seed_service import (
    discover_source_files,
    seed_docs_folder,
)


# The four content subfolders each map to a category equal to their name, plus
# a representative file with a plausible extension for that subfolder.
CONTENT_SUBFOLDERS = {
    "docs": "spec.pdf",
    "links": "useful-links.links",
    "scripts": "deploy.sh",
    "trainings": "onboarding.md",
}

# Non-content subfolders that MUST NOT become categories (design Scope).
EXCLUDED_SUBFOLDERS = {
    "movies": "intro.md",
    "images": "logo.pdf",
}


@pytest.fixture()
def seed_admin(db_session):
    """An administrator so ``resolve_seeding_admin`` returns a user."""
    admin = User(
        email="admin@opcp-psmc.com",
        password_hash="hashed",
        first_name="Seed",
        last_name="Admin",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture()
def to_publish(tmp_path):
    """Build a temporary ``docs/to_publish`` fixture with one file per subfolder.

    Layout::

        to_publish/
          docs/spec.pdf
          links/useful-links.links
          scripts/deploy.sh
          trainings/onboarding.md
          movies/intro.md      (excluded)
          images/logo.pdf      (excluded)
    """
    root = tmp_path / "to_publish"
    for subfolder, filename in {**CONTENT_SUBFOLDERS, **EXCLUDED_SUBFOLDERS}.items():
        folder = root / subfolder
        folder.mkdir(parents=True)
        (folder / filename).write_bytes(f"content of {subfolder}/{filename}".encode())
    return root


@pytest.fixture()
def isolated_storage(tmp_path, monkeypatch):
    """Point storage at a temp upload dir so seeding writes are isolated."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(
        document_seed_service.storage_service, "upload_dir", upload_dir
    )
    return upload_dir


@pytest.fixture(autouse=True)
def _use_test_session(db_session, monkeypatch):
    """Make ``seed_docs_folder`` use the test session instead of SessionLocal."""
    monkeypatch.setattr(
        document_seed_service, "SessionLocal", lambda: db_session
    )
    # Prevent seed_docs_folder from closing the shared test session.
    monkeypatch.setattr(db_session, "close", lambda: None)


# ---------------------------------------------------------------------------
# Backend: recursive discovery surfaces subfolder files and excludes movies/images.
# Requirements 1.4, 2.4
# ---------------------------------------------------------------------------

def test_discover_source_files_recurses_into_subfolders(to_publish):
    """discover_source_files SHALL surface files inside the four content
    subfolders (e.g. trainings/onboarding.md) and SHALL NOT surface files under
    movies/images.

    On UNFIXED code this FAILS: discovery is non-recursive (iterdir over the top
    level only), so subfolder files are never found. (Requirements 1.4, 2.4)
    """
    discovered = discover_source_files(to_publish)

    # Normalise to the set of discovered file names regardless of return shape
    # (bare Path today; (Path, subfolder) tuples after the fix).
    def _name(entry):
        if isinstance(entry, tuple):
            return entry[0].name
        return entry.name

    names = {_name(e) for e in discovered}

    # The trainings file (and every content-subfolder file) must be discovered.
    assert "onboarding.md" in names, (
        "discover_source_files omits subfolder files: docs/to_publish/trainings/"
        "onboarding.md was not discovered (non-recursive iterdir)."
    )
    for filename in CONTENT_SUBFOLDERS.values():
        assert filename in names, f"content-subfolder file not discovered: {filename}"

    # movies/images files must NOT be surfaced.
    for filename in EXCLUDED_SUBFOLDERS.values():
        assert filename not in names, (
            f"excluded-subfolder file was surfaced: {filename}"
        )


# ---------------------------------------------------------------------------
# Backend (scoped PBT): each seeded file's category == its originating subfolder.
# Requirements 1.1, 1.2, 2.1, 2.2
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "subfolder,filename",
    sorted(CONTENT_SUBFOLDERS.items()),
)
def test_seeded_category_equals_originating_subfolder(
    subfolder, filename, to_publish, seed_admin, isolated_storage, db_session
):
    """Scoped property: for each subfolder in {docs, links, scripts, trainings},
    the seeded file persists with ``category == originatingSubfolder``.

    On UNFIXED code this FAILS: infer_category hard-codes DocumentCategory.DOCUMENTS
    (and DocumentCategory has no ``trainings``/``docs`` members), so every
    discovered file persists with category == documents. (Requirements 1.1, 1.2, 2.1, 2.2)
    """
    seed_docs_folder(to_publish)

    doc = (
        db_session.query(Document)
        .filter(Document.original_name == filename)
        .first()
    )

    assert doc is not None, (
        f"file under {subfolder} was not seeded at all "
        f"(discover_source_files is non-recursive): {filename}"
    )
    assert doc.category.value == subfolder, (
        f"file under {subfolder} persisted with category="
        f"{doc.category.value} instead of {subfolder}"
    )


def test_excluded_subfolder_files_are_not_seeded(
    to_publish, seed_admin, isolated_storage, db_session
):
    """Files under movies/images MUST NOT be seeded (they are not categories).

    Requirements 1.3 (exclusion), design Scope.
    """
    seed_docs_folder(to_publish)

    for filename in EXCLUDED_SUBFOLDERS.values():
        doc = (
            db_session.query(Document)
            .filter(Document.original_name == filename)
            .first()
        )
        assert doc is None, f"excluded-subfolder file was seeded: {filename}"


def test_trainings_category_is_representable():
    """The category domain MUST be able to represent ``trainings``.

    On UNFIXED code this FAILS: DocumentCategory only defines documents/scripts/
    links, so there is no member whose value is ``trainings``. (Requirement 2.2)
    """
    values = {c.value for c in DocumentCategory}
    assert "trainings" in values, (
        "DocumentCategory has no 'trainings' member — the originating subfolder "
        "cannot be represented or persisted."
    )
    assert "docs" in values, "DocumentCategory has no 'docs' member."
