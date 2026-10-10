"""add ai_provider_config table (AI Oracle provider enablement)

Introduces the ``ai_provider_config`` table backing the per-provider
enable/disable flags for the AI Oracle "AI provider" dropdown. One row per
canonical provider id (``shai``, ``kiro``, ``openai``, ``opcp_companion``),
with a boolean ``enabled`` column.

The table is seeded so that ``shai`` is enabled (it is always available and
cannot be disabled) while the other providers default to disabled, meaning they
are absent from the dropdown until an administrator enables them.

Aligns the database schema with the AIProviderConfig model
(app/models/ai_provider_config.py).

Revision ID: add_ai_provider_config
Revises: add_credential_ca_certificate
Create Date: 2026-09-30 00:00

"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_ai_provider_config'
down_revision = 'add_credential_ca_certificate'
branch_labels = None
depends_on = None


def upgrade() -> None:
    ai_provider_config = op.create_table(
        "ai_provider_config",
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("provider"),
    )

    # Seed one row per canonical provider. shai is enabled and always-on; the
    # rest default to disabled (absent from the dropdown until enabled).
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        ai_provider_config,
        [
            {"provider": "shai", "enabled": True, "updated_at": now},
            {"provider": "kiro", "enabled": False, "updated_at": now},
            {"provider": "openai", "enabled": False, "updated_at": now},
            {"provider": "opcp_companion", "enabled": False, "updated_at": now},
        ],
    )


def downgrade() -> None:
    op.drop_table("ai_provider_config")
