"""per user prerequisite answers

Revision ID: per_user_prerequisite_answers
Revises: create_prerequisites_tables
Create Date: 2026-02-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'per_user_prerequisite_answers'
down_revision = 'create_prerequisites_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 6.2: legacy rows have no owner and are placeholder data — discard them.
    op.execute("DELETE FROM prerequisite_answers")

    # Drop the old shared uniqueness constraint + slug index.
    op.drop_constraint('uq_prerequisite_answers_slug_row', 'prerequisite_answers', type_='unique')
    op.drop_index('idx_prerequisite_answers_slug', table_name='prerequisite_answers')

    # 6.1: add the per-user owner column (non-null; table is now empty).
    op.add_column(
        'prerequisite_answers',
        sa.Column('user_id', sa.Uuid(), nullable=False),
    )
    op.create_foreign_key(
        'fk_prerequisite_answers_user_id', 'prerequisite_answers',
        'users', ['user_id'], ['id'],
    )
    op.create_index(
        'idx_prerequisite_answers_user_slug', 'prerequisite_answers',
        ['user_id', 'slug'], unique=False,
    )
    op.create_unique_constraint(
        'uq_prerequisite_answers_user_slug_row', 'prerequisite_answers',
        ['user_id', 'slug', 'row_id'],
    )


def downgrade() -> None:
    # 6.3: restore the prior (slug, row_id) schema.
    # Per-user rows cannot be represented in a shared schema — discard them.
    op.execute("DELETE FROM prerequisite_answers")

    op.drop_constraint('uq_prerequisite_answers_user_slug_row', 'prerequisite_answers', type_='unique')
    op.drop_index('idx_prerequisite_answers_user_slug', table_name='prerequisite_answers')
    op.drop_constraint('fk_prerequisite_answers_user_id', 'prerequisite_answers', type_='foreignkey')
    op.drop_column('prerequisite_answers', 'user_id')

    op.create_index('idx_prerequisite_answers_slug', 'prerequisite_answers', ['slug'], unique=False)
    op.create_unique_constraint(
        'uq_prerequisite_answers_slug_row', 'prerequisite_answers',
        ['slug', 'row_id'],
    )
