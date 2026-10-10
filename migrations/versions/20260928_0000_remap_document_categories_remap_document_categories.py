"""remap document categories to the new three-value set

Replaces the legacy document category enum (``STATUTES``, ``MINUTES``,
``FINANCIAL_REPORTS``, ``OTHER``) with the new set (``documents``, ``scripts``,
``links``). The ``category`` column is a non-native ``SQLEnum`` stored as
VARCHAR holding the enum *member name*, so this is a data update rather than a
DDL type change.

``upgrade()`` remaps every existing row to the ``documents`` member name
(``DOCUMENTS``), covering all four legacy categories in a single statement
regardless of casing. After the model's enum only knows ``DOCUMENTS``,
``SCRIPTS``, ``LINKS``, so every remapped row round-trips as ``documents``.

``downgrade()`` is lossy: the original per-row categories are destroyed by the
remap, so it resets all rows to the previous default ``OTHER``.

Revision ID: remap_document_categories
Revises: add_openstack_credential_config
Create Date: 2026-09-28 00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remap_document_categories'
down_revision = 'add_openstack_credential_config'
branch_labels = None
depends_on = None


# Documented for clarity: every possible legacy stored form (member-name and
# defensive value form). The unconditional UPDATE below covers all of them.
OLD_VALUES = (
    'STATUTES', 'MINUTES', 'FINANCIAL_REPORTS', 'OTHER',   # member-name form
    'statutes', 'minutes', 'financial_reports', 'other',   # value form (defensive)
)


def upgrade() -> None:
    # Requirement 6.2 / 6.3: every existing row becomes `documents`.
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE documents SET category = :new").bindparams(new='DOCUMENTS')
    )


def downgrade() -> None:
    # Best-effort reversal: prior category information is lost by the remap,
    # so restore all rows to the previous default `OTHER` (lossy).
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE documents SET category = :old").bindparams(old='OTHER')
    )
