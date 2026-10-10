"""create_token_blacklist_table

Revision ID: 8eeea7d8cf37
Revises: f93a24e82d55
Create Date: 2026-02-15 14:37:51.204041

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8eeea7d8cf37'
down_revision = 'f93a24e82d55'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create token_blacklist table
    op.create_table(
        'token_blacklist',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient lookups
    op.create_index('ix_token_blacklist_token', 'token_blacklist', ['token'], unique=True)
    op.create_index('ix_token_blacklist_user_id', 'token_blacklist', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_token_blacklist_user_id', table_name='token_blacklist')
    op.drop_index('ix_token_blacklist_token', table_name='token_blacklist')
    
    # Drop table
    op.drop_table('token_blacklist')
