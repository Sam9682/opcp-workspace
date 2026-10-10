"""add prerequisite_credential_config table (OpenStack credentials)

Introduces the ``prerequisite_credential_config`` table backing the
per-installation OpenStack credential configuration for the servers-nodes
prerequisite tab. Holds the non-secret connection details (Auth URL,
Credential ID, Nova endpoint) plus a write-only, Fernet-encrypted credential
secret. One config row per installation (unique on ``installation_id``); the
encrypted secret is a nullable column so a config can exist before a secret is
supplied.

Aligns the database schema with the CredentialConfig model
(app/models/credential_config.py).

Revision ID: add_openstack_credential_config
Revises: add_event_assignments
Create Date: 2026-09-27 00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_openstack_credential_config'
down_revision = 'add_event_assignments'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prerequisite_credential_config",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "auth_url",
            sa.String(length=1000),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "credential_id",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "nova_endpoint",
            sa.String(length=1000),
            nullable=False,
            server_default="",
        ),
        sa.Column("credential_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["installation_id"],
            ["installations.id"],
            name="fk_credential_config_installation_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "installation_id",
            name="uq_credential_config_installation",
        ),
    )
    op.create_index(
        "ix_credential_config_installation_id",
        "prerequisite_credential_config",
        ["installation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_credential_config_installation_id",
        table_name="prerequisite_credential_config",
    )
    op.drop_table("prerequisite_credential_config")
