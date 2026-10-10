"""Orchestrator and DB-touching tests for document_seed_service.

Feature: docs-auto-seed-and-documents-page

Covers the seeding orchestrator (`seed_docs_folder`) and the per-file
worker (`_seed_single_file`) against a real (in-memory SQLite) session:

  - Property 3: Seeded records are always members-level and admin-owned
  - Property 4: Non-recursive oversized-aware discovery and skipping
  - Property 5: Idempotency across repeated runs
  - Property 6: Content-change detection re-syncs the same record
  - Unit / example tests (Task 2.9): compute_hash, resolve_seeding_admin,
    missing-folder no-op, no-admin no-op + warning, oversized boundary,
    and `.md` seeding despite text/markdown not being an allowed upload MIME.

DB-touching property tests call the lower-level `_seed_single_file` directly
with the test `db_session` (committing via `db_session`) which gives reliable
assertions. The `seed_docs_folder` no-op tests monkeypatch the module-level
`SessionLocal` to return the test session so its own-session behaviour is
exercised.
"""
import logging
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from app.config import settings as app_settings
from app.models.document import Document, DocumentCategory, AccessLevel
from app.models.user import User, UserRole
from app.services import document_seed_service as seed_mod
from app.services.document_seed_service import (
    _seed_single_file,
    seed_docs_folder,
    discover_source_files,
    resolve_seeding_admin,
    compute_hash,
)
from app.services.storage_service import storage_service, ALLOWED_MIME_TYPES


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_admin(db, email="admin@opcp-psmc.com"):
    """Create and persist an ADMINISTRATOR user."""
    admin = User(
        email=email,
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture()
def isolated_storage(tmp_path, monkeypatch):
    """Point the module-level storage_service singleton at a temp uploads dir."""
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(storage_service, "upload_dir", uploads)
    return uploads


# A safe filename strategy: non-empty, no path separators / dots / control chars,
# so names are distinct valid single-segment filenames. We append a known ext.
_name_alphabet = st.characters(
    whitelist_categories=("Ll", "Lu", "Nd"),
)
filename_stem_strategy = st.text(alphabet=_name_alphabet, min_size=1, max_size=20)
content_strategy = st.binary(min_size=0, max_size=2048)


# ---------------------------------------------------------------------------
# Property 3: Seeded records are always members-level and admin-owned
# Feature: docs-auto-seed-and-documents-page
# Validates: Requirements 1.2, 5.1
# ---------------------------------------------------------------------------

@pytest.mark.property
@settings(max_examples=100, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    stems=st.lists(filename_stem_strategy, min_size=1, max_size=8, unique=True),
    contents=st.lists(content_strategy, min_size=1, max_size=8),
)
def test_property_seeded_records_are_members_and_admin_owned(
    db_session, isolated_storage, stems, contents
):
    """Property 3: every seeded (non-oversized) record is members-level and
    owned by the resolving admin.

    Validates Requirements 1.2, 5.1.
    """
    # Clean slate for this generated example (function-scoped session is reused
    # across Hypothesis examples).
    db_session.query(Document).delete()
    db_session.commit()

    admin = resolve_seeding_admin(db_session)
    if admin is None:
        admin = _make_admin(db_session)

    tmp_dir = isolated_storage.parent / "docs_p3"
    tmp_dir.mkdir(exist_ok=True)

    created_names = []
    for i, stem in enumerate(stems):
        content = contents[i % len(contents)]
        source = tmp_dir / f"{stem}.txt"
        source.write_bytes(content)
        _seed_single_file(db_session, admin, source)
        created_names.append(source.name)
    db_session.commit()

    docs = db_session.query(Document).all()
    assert len(docs) == len(set(created_names))
    for doc in docs:
        assert doc.access_level == AccessLevel.MEMBERS
        assert doc.uploaded_by == admin.id


# ---------------------------------------------------------------------------
# Property 4: Recursive, subfolder-aware, oversized-aware discovery
# Feature: documents-page-categories (BUGFIX) — supersedes the former
#          non-recursive contract.
# Validates: Requirements 2.4 (bugfix); Requirement 2.3 (oversize skip)
#
# NOTE (documents-page-categories bugfix): discover_source_files was changed to
# recurse into the four content subfolders (docs, links, scripts, trainings) of
# docs/to_publish and return (Path, originating_subfolder) tuples, EXCLUDING
# top-level files and non-content subfolders (movies/images). The former test
# asserted the opposite (only top-level files, nested never discovered) — that
# behavior was deliberately removed, so this test now asserts the new contract.
# ---------------------------------------------------------------------------

@pytest.mark.property
@settings(max_examples=100, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    content_stems=st.lists(filename_stem_strategy, min_size=0, max_size=6, unique=True),
    top_level=st.lists(filename_stem_strategy, min_size=0, max_size=6, unique=True),
    sizes=st.lists(st.integers(min_value=0, max_value=40), min_size=0, max_size=6),
)
def test_property_discovery_is_recursive_subfolder_and_oversize_aware(
    db_session, isolated_storage, monkeypatch, content_stems, top_level, sizes
):
    """Property 4: discover_source_files walks the four content subfolders and
    pairs each file with its originating subfolder, excludes top-level files and
    non-content subfolders; seeding registers exactly non-oversized files.

    Validates Requirements 2.3, 2.4.
    """
    db_session.query(Document).delete()
    db_session.commit()

    admin = resolve_seeding_admin(db_session)
    if admin is None:
        admin = _make_admin(db_session)

    # Small MAX to make oversized cases cheap.
    max_size = 20
    monkeypatch.setattr(app_settings, "MAX_UPLOAD_SIZE", max_size)

    docs_dir = isolated_storage.parent / "docs_p4"
    if docs_dir.exists():
        for child in docs_dir.rglob("*"):
            if child.is_file():
                child.unlink()
    docs_dir.mkdir(exist_ok=True)

    # Place each content file under a rotating content subfolder so discovery
    # must recurse into subfolders to find them.
    subfolders = ("docs", "links", "scripts", "trainings")
    for sf in subfolders:
        (docs_dir / sf).mkdir(exist_ok=True)
    (docs_dir / "movies").mkdir(exist_ok=True)
    (docs_dir / "images").mkdir(exist_ok=True)

    expected_pairs = set()       # (name, subfolder) discovery should surface
    expected_registered = set()  # names seeding should persist (size <= max)
    for i, stem in enumerate(content_stems):
        size = sizes[i % len(sizes)] if sizes else 0
        subfolder = subfolders[i % len(subfolders)]
        name = f"{stem}.txt"
        (docs_dir / subfolder / name).write_bytes(b"x" * size)
        expected_pairs.add((name, subfolder))
        if size <= max_size:
            expected_registered.add(name)

    # Top-level files and non-content-subfolder files must NOT be discovered.
    for stem in top_level:
        (docs_dir / f"{stem}.txt").write_bytes(b"t" * 5)
    for stem in top_level:
        (docs_dir / "movies" / f"{stem}.mp4").write_bytes(b"m" * 5)
        (docs_dir / "images" / f"{stem}.png").write_bytes(b"i" * 5)

    # Discovery is recursive within content subfolders and returns tuples of
    # (Path, originating_subfolder).
    discovered = discover_source_files(docs_dir)
    assert {(p.name, sf) for p, sf in discovered} == expected_pairs
    # Every discovered file lives under its reported content subfolder.
    for path, sf in discovered:
        assert sf in subfolders
        assert path.parent == docs_dir / sf

    # Seeding registers exactly the non-oversized content-subfolder files.
    for source, subfolder in discovered:
        _seed_single_file(db_session, admin, source, subfolder)
    db_session.commit()

    registered = {d.original_name for d in db_session.query(Document).all()}
    assert registered == expected_registered


# ---------------------------------------------------------------------------
# Property 5: Idempotency across repeated runs
# Feature: docs-auto-seed-and-documents-page
# Validates: Requirements 6.1, 6.2, 6.3, 6.5
# ---------------------------------------------------------------------------

@pytest.mark.property
@settings(max_examples=50, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    stems=st.lists(filename_stem_strategy, min_size=1, max_size=6, unique=True),
    contents=st.lists(content_strategy, min_size=1, max_size=6),
    runs=st.integers(min_value=2, max_value=4),
)
def test_property_idempotency_across_repeated_runs(
    db_session, isolated_storage, stems, contents, runs
):
    """Property 5: repeated seeding over unchanged content yields at most one
    record and one stored file per original_name; re-runs create nothing new.

    Validates Requirements 6.1, 6.2, 6.3, 6.5.
    """
    db_session.query(Document).delete()
    db_session.commit()
    # Clean the uploads dir between examples.
    for f in isolated_storage.iterdir():
        if f.is_file():
            f.unlink()

    admin = resolve_seeding_admin(db_session)
    if admin is None:
        admin = _make_admin(db_session)

    docs_dir = isolated_storage.parent / "docs_p5"
    docs_dir.mkdir(exist_ok=True)
    # Clean any prior content (files nested under content subfolders too).
    for f in docs_dir.rglob("*"):
        if f.is_file():
            f.unlink()

    # Files live under content subfolders so the recursive, subfolder-aware
    # discovery (documents-page-categories bugfix) surfaces them.
    subfolders = ("docs", "links", "scripts", "trainings")
    for sf in subfolders:
        (docs_dir / sf).mkdir(exist_ok=True)

    names = []
    for i, stem in enumerate(stems):
        name = f"{stem}.txt"
        subfolder = subfolders[i % len(subfolders)]
        (docs_dir / subfolder / name).write_bytes(contents[i % len(contents)])
        names.append(name)
    unique_names = set(names)

    # First run. discover_source_files yields (Path, subfolder) tuples.
    for source, subfolder in discover_source_files(docs_dir):
        _seed_single_file(db_session, admin, source, subfolder)
    db_session.commit()

    first_docs = db_session.query(Document).all()
    assert len(first_docs) == len(unique_names)
    id_by_name = {d.original_name: d.id for d in first_docs}
    stored_files_after_first = {p.name for p in isolated_storage.iterdir() if p.is_file()}

    # Additional runs must not create new rows or stored files.
    for _ in range(runs - 1):
        for source, subfolder in discover_source_files(docs_dir):
            _seed_single_file(db_session, admin, source, subfolder)
        db_session.commit()

    final_docs = db_session.query(Document).all()
    assert len(final_docs) == len(unique_names)
    # At most one record per original_name and ids unchanged.
    for d in final_docs:
        assert d.id == id_by_name[d.original_name]
    stored_files_after = {p.name for p in isolated_storage.iterdir() if p.is_file()}
    assert stored_files_after == stored_files_after_first
    assert len(stored_files_after) == len(unique_names)


# ---------------------------------------------------------------------------
# Property 6: Content-change detection re-syncs the same record
# Feature: docs-auto-seed-and-documents-page
# Validates: Requirements 6.3, 6.4, 6.5
# ---------------------------------------------------------------------------

@pytest.mark.property
@settings(max_examples=50, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    stem=filename_stem_strategy,
    original=content_strategy,
    changed=content_strategy,
)
def test_property_content_change_resyncs_same_record(
    db_session, isolated_storage, stem, original, changed
):
    """Property 6: identical re-seed leaves the record/stored bytes untouched;
    a content change updates the SAME record id and rewrites stored bytes.

    Validates Requirements 6.3, 6.4, 6.5.
    """
    db_session.query(Document).delete()
    db_session.commit()
    for f in isolated_storage.iterdir():
        if f.is_file():
            f.unlink()

    admin = resolve_seeding_admin(db_session)
    if admin is None:
        admin = _make_admin(db_session)

    docs_dir = isolated_storage.parent / "docs_p6"
    docs_dir.mkdir(exist_ok=True)
    for f in docs_dir.iterdir():
        if f.is_file():
            f.unlink()

    source = docs_dir / f"{stem}.txt"
    source.write_bytes(original)

    # Initial seed.
    _seed_single_file(db_session, admin, source)
    db_session.commit()
    doc = db_session.query(Document).filter_by(original_name=source.name).one()
    original_id = doc.id
    stored_filename = doc.filename
    original_size = doc.size
    stored_path = storage_service.get_file_path(stored_filename)
    assert stored_path is not None
    assert stored_path.read_bytes() == original

    # Re-seed with identical content: unchanged (same id, same bytes, same size).
    _seed_single_file(db_session, admin, source)
    db_session.commit()
    doc = db_session.query(Document).filter_by(original_name=source.name).one()
    assert doc.id == original_id
    assert doc.size == original_size
    assert doc.filename == stored_filename
    assert storage_service.get_file_path(stored_filename).read_bytes() == original

    # Change bytes and re-seed only if content actually differs.
    if changed != original:
        source.write_bytes(changed)
        _seed_single_file(db_session, admin, source)
        db_session.commit()
        doc = db_session.query(Document).filter_by(original_name=source.name).one()
        assert doc.id == original_id                # same record
        assert doc.size == len(changed)             # updated size
        # Only one row and one stored file remain.
        assert db_session.query(Document).filter_by(original_name=source.name).count() == 1
        new_path = storage_service.get_file_path(doc.filename)
        assert new_path is not None
        assert new_path.read_bytes() == changed     # stored bytes == new content


# ---------------------------------------------------------------------------
# Task 2.9 — Unit and example tests
# Feature: docs-auto-seed-and-documents-page
# Validates: Requirements 1.3, 2.2, 2.3, 3.5
# ---------------------------------------------------------------------------

@pytest.mark.property
@settings(max_examples=200)
@given(a=st.binary(max_size=512), b=st.binary(max_size=512))
def test_property_compute_hash_determinism(a, b):
    """compute_hash: same bytes -> same hash; different bytes -> different hash.

    Validates Requirement 6 change-detection primitive.
    """
    assert compute_hash(a) == compute_hash(a)
    if a == b:
        assert compute_hash(a) == compute_hash(b)
    else:
        assert compute_hash(a) != compute_hash(b)


def test_compute_hash_examples():
    """compute_hash is a sha256 hexdigest; deterministic across calls."""
    assert compute_hash(b"") == compute_hash(b"")
    assert compute_hash(b"hello") == compute_hash(b"hello")
    assert compute_hash(b"hello") != compute_hash(b"world")
    assert len(compute_hash(b"hello")) == 64  # sha256 hexdigest length


def test_resolve_seeding_admin_prefers_default_email(db_session):
    """resolve_seeding_admin prefers admin@opcp-psmc.com when present.

    Validates Requirement 1.2 selection order.
    """
    # A non-default admin created first.
    other = _make_admin(db_session, email="other-admin@example.com")
    default = _make_admin(db_session, email="admin@opcp-psmc.com")
    resolved = resolve_seeding_admin(db_session)
    assert resolved is not None
    assert resolved.id == default.id


def test_resolve_seeding_admin_falls_back_to_first_administrator(db_session):
    """Without the default email, the first ADMINISTRATOR by created_at wins.

    Validates Requirement 1.2 fallback order.
    """
    first = _make_admin(db_session, email="first-admin@example.com")
    _make_admin(db_session, email="second-admin@example.com")
    resolved = resolve_seeding_admin(db_session)
    assert resolved is not None
    assert resolved.id == first.id


def test_resolve_seeding_admin_returns_none_when_no_admin(db_session):
    """No administrator -> None.

    Validates Requirement 1.3.
    """
    # Create a non-admin member only.
    member = User(
        email="member@example.com",
        password_hash="hashed_password",
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(member)
    db_session.commit()
    assert resolve_seeding_admin(db_session) is None


def test_missing_folder_is_noop(db_session, isolated_storage, monkeypatch, caplog):
    """seed_docs_folder over a non-existent dir creates no rows and logs.

    Validates Requirement 2.2.
    """
    _make_admin(db_session)
    monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db_session)
    missing = isolated_storage.parent / "does_not_exist"

    with caplog.at_level(logging.INFO):
        seed_docs_folder(docs_dir=missing)

    assert db_session.query(Document).count() == 0
    assert any("no files found" in r.message.lower() for r in caplog.records)


def test_no_admin_is_noop_with_warning(db_session, isolated_storage, monkeypatch, caplog, tmp_path):
    """seed with no admin present creates no rows and logs a warning.

    Validates Requirement 1.3.
    """
    monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db_session)
    docs_dir = tmp_path / "docs_noadmin"
    docs_dir.mkdir()
    (docs_dir / "statutes.txt").write_bytes(b"content")

    with caplog.at_level(logging.WARNING):
        seed_docs_folder(docs_dir=docs_dir)

    assert db_session.query(Document).count() == 0
    assert any(
        "no administrator" in r.message.lower() for r in caplog.records
    )


def test_oversized_skip_boundary_at_max_upload_size(
    db_session, isolated_storage, monkeypatch, tmp_path
):
    """size == MAX is allowed; size == MAX + 1 is skipped.

    Validates Requirement 2.3 boundary.
    """
    admin = _make_admin(db_session)
    max_size = 16
    monkeypatch.setattr(app_settings, "MAX_UPLOAD_SIZE", max_size)

    docs_dir = tmp_path / "docs_boundary"
    docs_dir.mkdir()
    at_max = docs_dir / "at_max.txt"
    over_max = docs_dir / "over_max.txt"
    at_max.write_bytes(b"a" * max_size)
    over_max.write_bytes(b"b" * (max_size + 1))

    _seed_single_file(db_session, admin, at_max)
    _seed_single_file(db_session, admin, over_max)
    db_session.commit()

    names = {d.original_name for d in db_session.query(Document).all()}
    assert "at_max.txt" in names       # size == MAX allowed
    assert "over_max.txt" not in names  # size == MAX + 1 skipped


def test_markdown_seeds_despite_not_allowed_upload_mime(
    db_session, isolated_storage, tmp_path
):
    """A .md file seeds successfully even though text/markdown is NOT in
    storage_service.ALLOWED_MIME_TYPES (seeding bypasses validate_file).

    Validates Requirement 3.5.
    """
    # Precondition: text/markdown really is not an allowed upload MIME type.
    assert "text/markdown" not in ALLOWED_MIME_TYPES

    admin = _make_admin(db_session)
    docs_dir = tmp_path / "docs_md"
    docs_dir.mkdir()
    md = docs_dir / "statutes.md"
    md.write_bytes(b"# Statutes\n")

    _seed_single_file(db_session, admin, md)
    db_session.commit()

    doc = db_session.query(Document).filter_by(original_name="statutes.md").one()
    assert doc.mime_type == "text/markdown"
    assert doc.access_level == AccessLevel.MEMBERS
    # The stored file exists and holds the source bytes.
    stored = storage_service.get_file_path(doc.filename)
    assert stored is not None
    assert stored.read_bytes() == b"# Statutes\n"
