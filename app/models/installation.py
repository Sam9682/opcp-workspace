"""Installation persistence model for the prerequisites route family"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Installation(Base):
    """A named OPCP prerequisites instance that owns its content and answers

    Maps the ``installations`` table created by the multi-instance migration
    (``20260223_0000_multi_instance_opcp_prerequisites``).

    Validates Requirements 5.1, 5.2, 5.3:
    - Maps the ``installations`` table created by the multi-instance migration
    - Defines the UUID id, project_name, timestamps, and editor references
    - Is importable through the ``app.models`` package alongside existing models
    """
    __tablename__ = "installations"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )

    # Human-readable title of the installation
    project_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    # Timestamps
    #
    # Use Python-side defaults (matching User/Topic/Post) rather than a DB
    # ``server_default``. The multi-instance migration created these columns as
    # NOT NULL *without* a ``DEFAULT now()`` server default, so relying on a
    # server default here made every INSERT emit NULL and hit a
    # NotNullViolation. Populating the value in Python keeps the model working
    # against the existing schema and matches the rest of the codebase.
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

    # Editor tracking
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    # Relationships (back_populates targets added on the prerequisite models
    # in task 2.x; referenced by string here)
    content: Mapped[list["PrerequisiteContent"]] = relationship(
        "PrerequisiteContent",
        back_populates="installation",
        cascade="all, delete-orphan"
    )
    answers: Mapped[list["PrerequisiteAnswer"]] = relationship(
        "PrerequisiteAnswer",
        back_populates="installation",
        cascade="all, delete-orphan"
    )
    credential_config: Mapped["CredentialConfig"] = relationship(
        "CredentialConfig",
        back_populates="installation",
        cascade="all, delete-orphan",
        uselist=False
    )
    server_node_overrides: Mapped[list["ServerNodeOverride"]] = relationship(
        "ServerNodeOverride",
        back_populates="installation",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Installation(id={self.id}, project_name={self.project_name})>"
