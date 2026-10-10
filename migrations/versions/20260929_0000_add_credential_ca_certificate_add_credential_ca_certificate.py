"""add ca_certificate column to prerequisite_credential_config

Adds an optional, non-secret ``ca_certificate`` column to the
``prerequisite_credential_config`` table. The column holds a PEM-encoded
certificate authority certificate used to verify TLS on outbound OpenStack
calls (Keystone token acquisition and the Nova server list). It is stored in
plaintext (unlike the Fernet-encrypted credential secret) and is nullable: a
NULL/empty value means "use the system default trust store" for verification.

``Text`` matches the multi-line, unbounded nature of PEM content (certificate
chains) and mirrors the type used for ``credential_secret_encrypted``.

Aligns the database schema with the CredentialConfig model
(app/models/credential_config.py).

Revision ID: add_credential_ca_certificate
Revises: remap_document_categories
Create Date: 2026-09-29 00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_credential_ca_certificate'
down_revision = 'remap_document_categories'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prerequisite_credential_config",
        sa.Column("ca_certificate", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("prerequisite_credential_config", "ca_certificate")
