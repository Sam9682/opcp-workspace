"""add http_proxy and https_proxy columns to prerequisite_credential_config

Adds optional, non-secret ``http_proxy`` and ``https_proxy`` columns used as
forward proxies for outbound OpenStack calls (Keystone and Nova). NULL/empty
means no per-installation proxy.

Revision ID: add_credential_proxy
Revises: widen_encrypted_columns
Create Date: 2026-10-07 00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_credential_proxy'
down_revision = 'widen_encrypted_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prerequisite_credential_config",
        sa.Column("http_proxy", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "prerequisite_credential_config",
        sa.Column("https_proxy", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("prerequisite_credential_config", "https_proxy")
    op.drop_column("prerequisite_credential_config", "http_proxy")
