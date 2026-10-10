"""Startup seeding of repository docs/ files into the Document system.
Feature: docs-auto-seed-and-documents-page
Validates Requirements 1-6.
"""
import hashlib
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.document import Document, DocumentCategory, AccessLevel
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

# Extension -> MIME mapping (Requirement 3.1-3.4)
MIME_BY_EXTENSION: dict[str, str] = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
}
DEFAULT_MIME = "application/octet-stream"

def resolve_mime_type(filename: str) -> str:
    """Resolve MIME type from the file extension (Requirement 3.1-3.4)."""
    ext = Path(filename).suffix.lower()
    return MIME_BY_EXTENSION.get(ext, DEFAULT_MIME)


# Originating subfolder -> DocumentCategory. The four content subfolders of
# ``docs/to_publish`` each map to the category whose value equals the subfolder
# name (Requirement 2.2, 2.4).
CATEGORY_BY_SUBFOLDER: dict[str, DocumentCategory] = {
    "docs": DocumentCategory.DOCS,
    "links": DocumentCategory.LINKS,
    "scripts": DocumentCategory.SCRIPTS,
    "trainings": DocumentCategory.TRAININGS,
}


def infer_category(subfolder: str) -> DocumentCategory:
    """Infer DocumentCategory from a seeded file's originating subfolder.

    Files are discovered from the four content subfolders of ``docs/to_publish``
    (``docs``, ``links``, ``scripts``, ``trainings``) and grouped by that
    originating subfolder (Requirement 2.2, 2.4). Any unrecognised subfolder
    falls back to ``DOCUMENTS`` for backward compatibility.
    """
    return CATEGORY_BY_SUBFOLDER.get(subfolder, DocumentCategory.DOCUMENTS)


def compute_hash(content: bytes) -> str:
    """Deterministic sha256 over byte content (Content_Hash)."""
    return hashlib.sha256(content).hexdigest()


def resolve_seeding_admin(db: Session) -> Optional[User]:
    """Resolve the Seeding_Admin (Requirement 1.2, 1.3).

    Prefer admin@opcp-psmc.com; otherwise the first ADMINISTRATOR user.
    Returns None if no administrator exists.
    """
    admin = db.query(User).filter(User.email == "admin@opcp-psmc.com").first()
    if admin and admin.role == UserRole.ADMINISTRATOR:
        return admin
    return (
        db.query(User)
        .filter(User.role == UserRole.ADMINISTRATOR)
        .order_by(User.created_at.asc())
        .first()
    )


# Content subfolders of ``docs/to_publish`` that map to categories, in a
# deterministic order. Files under any other subfolder (e.g. ``movies``,
# ``images``) are intentionally excluded from discovery (Requirement 2.4).
CONTENT_SUBFOLDERS: tuple[str, ...] = ("docs", "links", "scripts", "trainings")


def discover_source_files(docs_dir: Path) -> list[tuple[Path, str]]:
    """Enumerate files within the four content subfolders of ``docs/to_publish``.

    Walks each of ``docs``, ``links``, ``scripts``, ``trainings`` (recursively)
    and returns each discovered file paired with its originating subfolder name
    (Requirement 2.4). Non-content subfolders such as ``movies`` and ``images``
    are excluded. The result is sorted for a deterministic seeding order.
    """
    if not docs_dir.exists() or not docs_dir.is_dir():
        return []

    discovered: list[tuple[Path, str]] = []
    for subfolder in CONTENT_SUBFOLDERS:
        subdir = docs_dir / subfolder
        if not subdir.is_dir():
            continue
        for path in subdir.rglob("*"):
            if path.is_file():
                discovered.append((path, subfolder))

    return sorted(discovered, key=lambda entry: (entry[1], entry[0].name))


def _seed_single_file(db: Session, admin: User, source: Path, subfolder: str = "") -> None:
    """Seed or re-sync one Source_File. Raises on unexpected error (caller logs).

    ``subfolder`` is the originating content subfolder of ``docs/to_publish``
    and determines the category for newly created documents (Requirement 2.2, 2.4).
    An empty/unknown subfolder falls back to the ``DOCUMENTS`` category.
    """
    content = source.read_bytes()
    size = len(content)

    # Requirement 2.3: skip oversized files.
    if size > settings.MAX_UPLOAD_SIZE:
        logger.warning(
            "Skipping %s: size %d exceeds MAX_UPLOAD_SIZE %d",
            source.name, size, settings.MAX_UPLOAD_SIZE,
        )
        return

    source_hash = compute_hash(content)
    mime_type = resolve_mime_type(source.name)
    category = infer_category(subfolder)

    # Requirement 6.1: match existing record by original_name.
    existing = (
        db.query(Document)
        .filter(Document.original_name == source.name)
        .first()
    )

    if existing is None:
        # Requirement 6.2: create one Document + one Stored_File.
        unique_filename, _ = storage_service.save_file(content, source.name)
        document = Document(
            filename=unique_filename,
            original_name=source.name,
            mime_type=mime_type,
            size=size,
            category=category,
            access_level=AccessLevel.MEMBERS,   # Requirement 5.1
            uploaded_by=admin.id,               # Requirement 1.2
            download_count=0,
        )
        db.add(document)
        logger.info("Seeded new document: %s (%s, %s)", source.name, category.value, mime_type)
        return

    # Requirement 6.3/6.4: compare source hash against the currently Stored_File.
    stored_path = storage_service.get_file_path(existing.filename)
    stored_hash = compute_hash(stored_path.read_bytes()) if stored_path else None

    if stored_hash == source_hash and existing.size == size:
        # Unchanged: leave record and stored file untouched (Requirement 6.3).
        logger.debug("Unchanged document, skipping re-sync: %s", source.name)
        return

    # Changed: overwrite the SAME stored file, update the SAME row (Requirement 6.4).
    if stored_path is not None:
        stored_path.write_bytes(content)          # overwrite in place, keeps filename/id stable
    else:
        # Stored file missing on disk — re-create and repoint filename.
        unique_filename, _ = storage_service.save_file(content, source.name)
        existing.filename = unique_filename
    existing.size = size
    existing.mime_type = mime_type
    # category left as-is on re-sync to respect any manual reclassification; size/mime/updated_at change.
    logger.info("Re-synced changed document (same id=%s): %s", existing.id, source.name)


def seed_docs_folder(docs_dir: Optional[Path] = None) -> None:
    """Entry point invoked from the FastAPI lifespan after create_default_admin().

    Validates Requirements 1, 2, 3, 4, 5.1, 6.
    """
    resolved_dir = docs_dir or Path(settings.DOCS_SEED_DIR)

    db: Session = SessionLocal()
    try:
        admin = resolve_seeding_admin(db)
        if admin is None:
            # Requirement 1.3: no administrator => no-op + warning.
            logger.warning("Docs seeding skipped: no administrator user found.")
            return

        files = discover_source_files(resolved_dir)
        if not files:
            # Requirement 2.2: missing folder (or empty) => no-op + log.
            logger.info("Docs seeding: no files found in %s", resolved_dir)
            return

        # discover_source_files yields (Path, originating_subfolder) tuples; the
        # subfolder is threaded into seeding so each new Document.category
        # reflects its originating subfolder (Requirement 2.2, 2.4).
        for source, subfolder in files:
            try:
                _seed_single_file(db, admin, source, subfolder)
            except Exception:  # Requirement: one bad file must not abort the whole seed.
                logger.exception("Docs seeding failed for file: %s", source)
                db.rollback()

        db.commit()
        logger.info("Docs seeding complete (%d file(s) processed).", len(files))
    except Exception:
        db.rollback()
        logger.exception("Docs seeding aborted due to unexpected error.")
    finally:
        db.close()
