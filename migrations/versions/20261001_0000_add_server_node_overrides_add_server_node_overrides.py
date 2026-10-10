"""add prerequisite_server_node table (server node overrides)

Introduces the ``prerequisite_server_node`` table backing the per-installation
server node overrides for the servers-nodes prerequisite tab. Stores, per
installation, only the node rows edited from the hardcoded default inventory
(``SERVER_NODES`` on the frontend), keyed by ``node_uuid``. Defaults remain
authoritative for which rows exist; this table is purely an override store of
the five editable field values (serial number, instance uuid, power state,
provision state, remark). One row per ``(installation_id, node_uuid)`` pair;
rows are removed with their installation (ON DELETE CASCADE). Mirrors the
per-installation, last-write-wins structure of ``prerequisite_answers`` /
``prerequisite_credential_config``.

Aligns the database schema with the ServerNodeOverride model
(app/models/prerequisite.py).

Revision ID: add_server_node_overrides
Revises: add_ai_provider_config
Create Date: 2026-10-01 00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_server_node_overrides'
down_revision = 'add_ai_provider_config'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prerequisite_server_node",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("node_uuid", sa.String(length=255), nullable=False),
        sa.Column(
            "serial_number",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "instance_uuid",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "power_state",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "provision_state",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "remark",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["installation_id"],
            ["installations.id"],
            name="fk_server_node_installation_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "installation_id",
            "node_uuid",
            name="uq_server_node_installation_node",
        ),
    )
    op.create_index(
        "ix_server_node_installation_id",
        "prerequisite_server_node",
        ["installation_id"],
        unique=False,
    )
    # Supporting index on node_uuid (matches the model's indexed node_uuid column)
    op.create_index(
        "ix_prerequisite_server_node_node_uuid",
        "prerequisite_server_node",
        ["node_uuid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_prerequisite_server_node_node_uuid",
        table_name="prerequisite_server_node",
    )
    op.drop_index(
        "ix_server_node_installation_id",
        table_name="prerequisite_server_node",
    )
    op.drop_table("prerequisite_server_node")
