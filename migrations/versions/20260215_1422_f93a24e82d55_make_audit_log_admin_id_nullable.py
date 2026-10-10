"""make_audit_log_admin_id_nullable

Revision ID: f93a24e82d55
Revises: 22f92e461a60
Create Date: 2026-02-15 14:22:41.919493

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f93a24e82d55'
down_revision = '22f92e461a60'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make admin_id nullable to support system events like failed login attempts
    op.alter_column('audit_log', 'admin_id',
                    existing_type=sa.UUID(),
                    nullable=True)


def downgrade() -> None:
    # Revert admin_id to non-nullable
    op.alter_column('audit_log', 'admin_id',
                    existing_type=sa.UUID(),
                    nullable=False)
