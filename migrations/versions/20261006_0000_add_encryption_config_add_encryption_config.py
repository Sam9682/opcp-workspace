"""add encryption_config table (database field encryption toggle)

Introduces the ``encryption_config`` single-row key/value table backing the
admin "Database encryption" toggle. Stores whether application-level field
encryption is enabled plus the salted PBKDF2 verification hash used to validate
the administrator's password key.

The ``enabled`` flag is seeded OFF so existing deployments are unaffected: data
remains in plaintext until an administrator opts in and runs the offline
migration script. The password key itself is never stored — only the salt and
verification hash are persisted, so a supplied key can be validated but not
recovered.

Aligns the database schema with the EncryptionConfig model
(app/models/encryption_config.py).

Revision ID: add_encryption_config
Revises: add_forum_config
Create Date: 2026-10-06 00:00

"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_encryption_config'
down_revision = 'add_forum_config'
branch_labels = None
depends_on = None


def upgrade() -> None:
    encryption_config = op.create_table(
        "encryption_config",
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("verification_hash", sa.String(length=255), nullable=True),
        sa.Column("salt", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("key"),
    )

    # Seed the single canonical row with encryption OFF and no key set,
    # preserving today's plaintext behavior by default.
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        encryption_config,
        [
            {
                "key": "db_field_encryption",
                "enabled": False,
                "verification_hash": None,
                "salt": None,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("encryption_config")
