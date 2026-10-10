"""add event_assignments join table (multi-user assignment)

Introduces a many-to-many ``event_assignments`` table linking events to the
users they are assigned to. An event with no assignment rows is a public event
(visible to every authenticated user); administrators always see every event.

Existing single-user assignments stored in ``events.assigned_user_id`` are
backfilled into the new table so no assignment is lost. The legacy column is
kept in place for backward compatibility.

Revision ID: add_event_assignments
Revises: add_event_assigned_user
Create Date: 2026-09-26 10:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_event_assignments'
down_revision = 'add_event_assigned_user'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'event_assignments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('event_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column(
            'assigned_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'user_id', name='uq_event_user_assignment'),
    )
    op.create_index('idx_assignments_event', 'event_assignments', ['event_id'], unique=False)
    op.create_index('idx_assignments_user', 'event_assignments', ['user_id'], unique=False)

    # Backfill: copy existing single-user assignments into the join table.
    op.execute(
        """
        INSERT INTO event_assignments (id, event_id, user_id, assigned_at)
        SELECT gen_random_uuid(), id, assigned_user_id, now()
        FROM events
        WHERE assigned_user_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index('idx_assignments_user', table_name='event_assignments')
    op.drop_index('idx_assignments_event', table_name='event_assignments')
    op.drop_table('event_assignments')
