"""create tasks and task_assignments tables

Introduces the Manage Tasks feature backend storage, mirroring the Events
feature with three deltas:
- No ``max_participants`` column and no registration concept.
- A mandatory single ``owner_id`` FK (NOT nullable).
- Assignments live in a dedicated ``task_assignments`` join table; an empty
  assignment set does NOT make a task public (private-by-default visibility is
  enforced at the router level).

Revision ID: add_tasks
Revises: add_server_node_overrides
Create Date: 2026-10-02 00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'add_tasks'
down_revision = 'add_server_node_overrides'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tasks',
        sa.Column('id', sa.Uuid(), server_default=text('gen_random_uuid()'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('SCHEDULED', 'CANCELLED', 'COMPLETED', name='task_status', native_enum=False),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_tasks_start_date', 'tasks', ['start_date'], unique=False)
    op.create_index('idx_tasks_owner', 'tasks', ['owner_id'], unique=False)

    op.create_table(
        'task_assignments',
        sa.Column('id', sa.Uuid(), server_default=text('gen_random_uuid()'), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'user_id', name='uq_task_user_assignment'),
    )
    op.create_index('idx_task_assignments_task', 'task_assignments', ['task_id'], unique=False)
    op.create_index('idx_task_assignments_user', 'task_assignments', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_task_assignments_user', table_name='task_assignments')
    op.drop_index('idx_task_assignments_task', table_name='task_assignments')
    op.drop_table('task_assignments')
    op.drop_index('idx_tasks_owner', table_name='tasks')
    op.drop_index('idx_tasks_start_date', table_name='tasks')
    op.drop_table('tasks')
