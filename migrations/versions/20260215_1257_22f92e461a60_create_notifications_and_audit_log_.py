"""create_notifications_and_audit_log_tables

Revision ID: 22f92e461a60
Revises: e584fabb7760
Create Date: 2026-02-15 12:57:57.743449

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '22f92e461a60'
down_revision = 'e584fabb7760'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create notifications table
    op.create_table('notifications',
    sa.Column('id', sa.Uuid(), server_default=text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.Enum('FORUM_REPLY', 'EVENT_REMINDER', 'MEMBERSHIP_EXPIRY', 'ANNOUNCEMENT', 'PAYMENT_CONFIRMATION', name='notification_type', native_enum=False), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_notifications_user', 'notifications', ['user_id'], unique=False)
    
    # Create notification_preferences table
    op.create_table('notification_preferences',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('email_notifications', sa.Boolean(), nullable=False),
    sa.Column('forum_notifications', sa.Boolean(), nullable=False),
    sa.Column('event_notifications', sa.Boolean(), nullable=False),
    sa.Column('announcement_notifications', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    
    # Create audit_log table
    op.create_table('audit_log',
    sa.Column('id', sa.Uuid(), server_default=text('gen_random_uuid()'), nullable=False),
    sa.Column('admin_id', sa.Uuid(), nullable=False),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('target_type', sa.String(length=50), nullable=True),
    sa.Column('target_id', sa.Uuid(), nullable=True),
    sa.Column('details', sa.JSON(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_admin', 'audit_log', ['admin_id'], unique=False)
    op.create_index('idx_audit_timestamp', 'audit_log', ['timestamp'], unique=False)


def downgrade() -> None:
    # Drop audit_log table
    op.drop_index('idx_audit_timestamp', table_name='audit_log')
    op.drop_index('idx_audit_admin', table_name='audit_log')
    op.drop_table('audit_log')
    
    # Drop notification_preferences table
    op.drop_table('notification_preferences')
    
    # Drop notifications table
    op.drop_index('idx_notifications_user', table_name='notifications')
    op.drop_table('notifications')
