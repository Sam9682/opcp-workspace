"""add assigned_user_id to events

Adds a nullable ``assigned_user_id`` foreign key on the ``events`` table
pointing at ``users.id`` (private-event owner; NULL => public event), together
with the supporting FK constraint and index. This aligns the database schema
with the Event model (app/models/event.py).

Existing rows get ``assigned_user_id = NULL`` and are therefore treated as
public events; no data backfill is required.

Revision ID: add_event_assigned_user
Revises: multi_instance_opcp_prereq
Create Date: 2026-09-25 13:33

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_event_assigned_user'
down_revision = 'multi_instance_opcp_prereq'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'events',
        sa.Column('assigned_user_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_events_assigned_user_id_users',
        'events',
        'users',
        ['assigned_user_id'],
        ['id'],
    )
    op.create_index(
        'idx_events_assigned_user',
        'events',
        ['assigned_user_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_events_assigned_user', table_name='events')
    op.drop_constraint(
        'fk_events_assigned_user_id_users',
        'events',
        type_='foreignkey',
    )
    op.drop_column('events', 'assigned_user_id')
