"""add account security 2FA fields to users

Revision ID: add_account_security_2fa_fields
Revises: per_user_prerequisite_answers
Create Date: 2026-02-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_account_security_2fa_fields'
down_revision = 'per_user_prerequisite_answers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 5.6 / 6.2: add the two-factor authentication columns to users.
    # Booleans carry server_default="false" so existing rows backfill safely.
    op.add_column(
        'users',
        sa.Column('totp_secret', sa.String(64), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column(
            'totp_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'email_2fa_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )


def downgrade() -> None:
    # Remove the two-factor authentication columns from users.
    op.drop_column('users', 'email_2fa_enabled')
    op.drop_column('users', 'totp_enabled')
    op.drop_column('users', 'totp_secret')
