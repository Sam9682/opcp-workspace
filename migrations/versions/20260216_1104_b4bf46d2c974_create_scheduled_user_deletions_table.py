"""create_scheduled_user_deletions_table

Revision ID: b4bf46d2c974
Revises: 8eeea7d8cf37
Create Date: 2026-02-16 11:04:17.160540

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4bf46d2c974'
down_revision = '8eeea7d8cf37'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'scheduled_user_deletions',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('user_full_name', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('scheduled_user_deletions')
