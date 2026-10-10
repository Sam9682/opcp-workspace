"""OpenStack credential configuration model for the servers-nodes prerequisite tab"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CredentialConfig(Base):
    """Per-installation OpenStack credential configuration for live node status retrieval

    Maps the ``prerequisite_credential_config`` table. Holds the non-secret
    connection details (Auth URL, Credential ID, Nova endpoint) plus a
    write-only, Fernet-encrypted credential secret. One config row per
    installation (unique on ``installation_id``); the encrypted secret is a
    nullable column so a config can exist before a secret is supplied.

    Validates Requirements 3.1, 3.4:
    - Persists the Auth URL, Credential ID, and Nova endpoint scoped by installation
    - Provides the persisted model backing the credential config table
    """
    __tablename__ = "prerequisite_credential_config"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )

    # Owning installation. Non-null: every config row belongs to exactly one
    # installation and is removed with it (ON DELETE CASCADE).
    installation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "installations.id",
            name="fk_credential_config_installation_id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    # OpenStack Keystone base URL (OS_AUTH_URL)
    auth_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        default=""
    )

    # OpenStack application credential identifier
    credential_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default=""
    )

    # OpenStack Nova compute service base URL
    nova_endpoint: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        default=""
    )

    # OpenStack CA certificate (PEM). Non-secret, optional; NULL/empty means
    # "use the system default trust store" for TLS verification. Intentionally
    # NOT encrypted (contrast with credential_secret_encrypted).
    ca_certificate: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Encrypted (Fernet) write-only secret; NULL when never provided.
    credential_secret_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Editor tracking
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    # Owning installation relationship
    installation = relationship("Installation", back_populates="credential_config")

    # Unique constraint and supporting index (names match the migration)
    __table_args__ = (
        UniqueConstraint(
            "installation_id",
            name="uq_credential_config_installation"
        ),
        Index("ix_credential_config_installation_id", "installation_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<CredentialConfig(id={self.id}, "
            f"installation_id={self.installation_id})>"
        )
