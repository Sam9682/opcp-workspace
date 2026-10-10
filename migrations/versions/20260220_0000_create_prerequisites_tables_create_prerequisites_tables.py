"""create prerequisites tables

Revision ID: create_prerequisites_tables
Revises: add_membership_status_col
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'create_prerequisites_tables'
down_revision = 'add_membership_status_col'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # prerequisite_content: static content keyed by slug (slug is the primary key)
    op.create_table(
        'prerequisite_content',
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('slug')
    )
    op.create_index(op.f('ix_prerequisite_content_slug'), 'prerequisite_content', ['slug'], unique=False)

    # prerequisite_answers: client answers keyed by (slug, row_id)
    op.create_table(
        'prerequisite_answers',
        sa.Column('id', sa.Uuid(), server_default=text('gen_random_uuid()'), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('row_id', sa.String(length=255), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', 'row_id', name='uq_prerequisite_answers_slug_row')
    )
    op.create_index(op.f('ix_prerequisite_answers_slug'), 'prerequisite_answers', ['slug'], unique=False)
    op.create_index(op.f('ix_prerequisite_answers_row_id'), 'prerequisite_answers', ['row_id'], unique=False)
    op.create_index('idx_prerequisite_answers_slug', 'prerequisite_answers', ['slug'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_prerequisite_answers_slug', table_name='prerequisite_answers')
    op.drop_index(op.f('ix_prerequisite_answers_row_id'), table_name='prerequisite_answers')
    op.drop_index(op.f('ix_prerequisite_answers_slug'), table_name='prerequisite_answers')
    op.drop_table('prerequisite_answers')

    op.drop_index(op.f('ix_prerequisite_content_slug'), table_name='prerequisite_content')
    op.drop_table('prerequisite_content')
