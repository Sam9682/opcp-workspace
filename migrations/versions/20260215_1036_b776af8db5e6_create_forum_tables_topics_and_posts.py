"""Create forum tables (topics and posts)

Revision ID: b776af8db5e6
Revises: f8102700349c
Create Date: 2026-02-15 10:36:19.176575

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'b776af8db5e6'
down_revision = 'f8102700349c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create forum_topics table
    op.create_table('forum_topics',
        sa.Column('id', sa.Uuid(), server_default=text('gen_random_uuid()'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('author_id', sa.Uuid(), nullable=False),
        sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_locked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], )
    )
    
    # Create forum_posts table
    op.create_table('forum_posts',
        sa.Column('id', sa.Uuid(), server_default=text('gen_random_uuid()'), nullable=False),
        sa.Column('topic_id', sa.Uuid(), nullable=False),
        sa.Column('author_id', sa.Uuid(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['topic_id'], ['forum_topics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], )
    )
    
    # Create indexes for efficient queries
    op.create_index('idx_posts_topic', 'forum_posts', ['topic_id'], unique=False)
    op.create_index('idx_posts_author', 'forum_posts', ['author_id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_posts_author', table_name='forum_posts')
    op.drop_index('idx_posts_topic', table_name='forum_posts')
    
    # Drop tables
    op.drop_table('forum_posts')
    op.drop_table('forum_topics')
