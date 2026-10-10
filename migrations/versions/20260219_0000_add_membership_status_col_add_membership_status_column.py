"""add membership_status column to users

Revision ID: add_membership_status_col
Revises: add_oracle_queries
Create Date: 2026-02-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_membership_status_col'
down_revision = 'add_oracle_queries'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add membership_status column to users table
    op.add_column('users', sa.Column('membership_status', sa.String(20), nullable=True))


def downgrade() -> None:
    # Remove membership_status column from users table
    op.drop_column('users', 'membership_status')
