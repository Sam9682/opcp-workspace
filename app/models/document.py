"""Document model for document management system"""
import enum
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import String, Integer, DateTime, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class DocumentCategory(str, enum.Enum):
    """Document category enumeration.

    Members map to originating subfolders of ``docs/to_publish`` for
    subfolder-based grouping (``docs``, ``links``, ``scripts``, ``trainings``).
    ``DOCUMENTS`` is retained for backward compatibility with already-seeded
    rows and extension-based uploads. Because the column uses
    ``SQLEnum(..., native_enum=False)``, values are stored as strings, so
    adding members requires no native DB enum ALTER / migration.
    """
    DOCUMENTS = "documents"
    SCRIPTS = "scripts"
    LINKS = "links"
    DOCS = "docs"
    TRAININGS = "trainings"


# Category_Mapping: file extension (lowercase, no dot) -> DocumentCategory
CATEGORY_MAPPING: dict[str, DocumentCategory] = {
    "pdf": DocumentCategory.DOCUMENTS,
    "doc": DocumentCategory.DOCUMENTS,
    "docx": DocumentCategory.DOCUMENTS,
    "md": DocumentCategory.DOCUMENTS,
    "txt": DocumentCategory.DOCUMENTS,
    "sh": DocumentCategory.SCRIPTS,
    "sql": DocumentCategory.SCRIPTS,
    "py": DocumentCategory.SCRIPTS,
    "links": DocumentCategory.LINKS,
}


def classify_extension(filename: str) -> "DocumentCategory | None":
    """Return the category for a filename's extension, or None if unmapped.

    The extension is taken from the last suffix, lowercased, dot stripped.
    Returns None when the extension is absent or not in CATEGORY_MAPPING so
    the caller can reject the upload.
    """
    ext = Path(filename).suffix.lower().lstrip(".")
    return CATEGORY_MAPPING.get(ext) if ext else None


class AccessLevel(str, enum.Enum):
    """Access level enumeration for document permissions"""
    PUBLIC = "public"
    MEMBERS = "members"
    ADMINISTRATORS = "administrators"


class Document(Base):
    """Document model for file management
    
    Validates Requirements 5.1, 5.2, 5.4:
    - Stores document metadata and file information
    - Manages document categories and access levels
    - Tracks upload information and download statistics
    """
    __tablename__ = "documents"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # File information
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    original_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    size: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    # Document classification
    category: Mapped[DocumentCategory] = mapped_column(
        SQLEnum(DocumentCategory, name="document_category", native_enum=False),
        nullable=False
    )
    
    # Access control
    access_level: Mapped[AccessLevel] = mapped_column(
        SQLEnum(AccessLevel, name="access_level", native_enum=False),
        nullable=False
    )
    
    # Upload tracking
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Usage statistics
    download_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_documents_category', 'category'),
        Index('idx_documents_access', 'access_level'),
    )
    
    # Relationships
    uploader: Mapped["User"] = relationship("User")
    
    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename}, category={self.category}, access_level={self.access_level})>"
