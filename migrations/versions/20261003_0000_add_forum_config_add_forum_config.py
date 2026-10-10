"""add forum_config table (home page "View" button toggle)

Introduces the ``forum_config`` table backing forum-related feature toggles
stored as key/value rows. Currently holds a single setting,
``view_button_enabled``, controlling whether the read-only "View" button is
displayed to logged-out visitors on the home page.

The setting uses non-inverted semantics (``enabled=True`` means the button is
shown) and is seeded ON so today's behavior is preserved by default.

Aligns the database schema with the ForumConfig model
(app/models/forum_config.py).

Revision ID: add_forum_config
Revises: add_tasks
Create Date: 2026-10-03 00:00

"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_forum_config'
down_revision = 'add_tasks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    forum_config = op.create_table(
        "forum_config",
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("key"),
    )

    # Seed the single known setting ON so the "View" button remains visible by
    # default, preserving today's behavior.
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        forum_config,
        [
            {"key": "view_button_enabled", "enabled": True, "updated_at": now},
        ],
    )


def downgrade() -> None:
    op.drop_table("forum_config")
