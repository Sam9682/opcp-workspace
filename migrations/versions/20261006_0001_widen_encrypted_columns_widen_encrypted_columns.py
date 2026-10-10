"""widen encrypted free-text columns to TEXT

The columns now using ``EncryptedString`` must hold Fernet ciphertext, which is
substantially longer than the former bounded ``VARCHAR`` plaintext. This widens
the previously length-bounded columns to ``TEXT`` so encrypted values fit:

- ``forum_topics.title``   (was VARCHAR(255))
- ``users.first_name``     (was VARCHAR(100))
- ``users.last_name``      (was VARCHAR(100))

The other in-scope columns (``forum_posts.content``, ``notifications.content``,
``events.description``, ``tasks.description``) were already ``TEXT`` and need no
change.

Downgrade narrows the columns back to their original bounds. This is only safe
when the data has first been decrypted (plaintext fits the original bounds);
run the encryption migration script in "disable" mode before downgrading.

Revision ID: widen_encrypted_columns
Revises: add_encryption_config
Create Date: 2026-10-06 00:01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'widen_encrypted_columns'
down_revision = 'add_encryption_config'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "forum_topics", "title",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "users", "first_name",
        existing_type=sa.String(length=100),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "users", "last_name",
        existing_type=sa.String(length=100),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Only safe when the affected columns hold plaintext that fits the bounds.
    op.alter_column(
        "users", "last_name",
        existing_type=sa.Text(),
        type_=sa.String(length=100),
        existing_nullable=False,
    )
    op.alter_column(
        "users", "first_name",
        existing_type=sa.Text(),
        type_=sa.String(length=100),
        existing_nullable=False,
    )
    op.alter_column(
        "forum_topics", "title",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
