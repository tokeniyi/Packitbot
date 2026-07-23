"""initial schema

Revision ID: 9082dd8c65fd
Revises: 3ec380728795
Create Date: 2026-07-23 18:12:54.343781

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9082dd8c65fd'
down_revision: Union[str, None] = '3ec380728795'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('telegram_id', sa.BigInteger(), nullable=False),
    sa.Column('username', sa.String(length=255), nullable=True),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('phone_number', sa.String(length=20), nullable=True),
    sa.Column('role', sa.Enum('STUDENT', 'DRIVER', 'ADMIN', name='userrole'), nullable=False),
    sa.Column('account_status', sa.Enum('ACTIVE', 'BANNED', name='accountstatus'), nullable=False),
    sa.Column('banned_reason', sa.String(length=500), nullable=True),
    sa.Column('banned_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)
    op.create_table('admin_profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('added_by_admin_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['added_by_admin_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('delivery_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('driver_id', sa.Integer(), nullable=True),
    sa.Column('pickup_detail', sa.String(length=255), nullable=False),
    sa.Column('dropoff_address', sa.String(length=255), nullable=False),
    sa.Column('dropoff_landmark', sa.String(length=255), nullable=True),
    sa.Column('hall_of_residence', sa.String(length=100), nullable=False),
    sa.Column('recipient_name', sa.String(length=255), nullable=False),
    sa.Column('recipient_phone', sa.String(length=20), nullable=False),
    sa.Column('luggage_size', sa.Enum('SMALL', 'MEDIUM', 'LARGE', name='luggagesize'), nullable=False),
    sa.Column('luggage_count', sa.Integer(), nullable=False),
    sa.Column('special_instructions', sa.String(length=500), nullable=True),
    sa.Column('preferred_date', sa.Date(), nullable=False),
    sa.Column('preferred_time_window', sa.String(length=50), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'ASSIGNED', 'ACCEPTED', 'REJECTED_BY_DRIVER', 'EN_ROUTE_TO_PICKUP', 'PICKED_UP', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED', 'FAILED', name='requeststatus'), nullable=False),
    sa.Column('cancelled_by', sa.Enum('STUDENT', 'ADMIN', 'SYSTEM', name='cancelledby'), nullable=True),
    sa.Column('cancellation_reason', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['driver_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('driver_profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('vehicle_type', sa.String(length=50), nullable=False),
    sa.Column('plate_number', sa.String(length=20), nullable=False),
    sa.Column('license_number', sa.String(length=50), nullable=False),
    sa.Column('status', sa.Enum('PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'SUSPENDED', name='driverstatus'), nullable=False),
    sa.Column('availability', sa.Enum('AVAILABLE', 'BUSY', 'OFFLINE', name='driveravailability'), nullable=False),
    sa.Column('rating_avg', sa.Float(), nullable=False),
    sa.Column('total_deliveries', sa.Integer(), nullable=False),
    sa.Column('approved_by_admin_id', sa.Integer(), nullable=True),
    sa.Column('approved_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['approved_by_admin_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('plate_number'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('student_profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('matric_number', sa.String(length=50), nullable=False),
    sa.Column('hall_of_residence', sa.String(length=100), nullable=False),
    sa.Column('room_number', sa.String(length=20), nullable=True),
    sa.Column('verification_status', sa.Enum('UNVERIFIED', 'VERIFIED', name='verificationstatus'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_student_profiles_matric_number'), 'student_profiles', ['matric_number'], unique=True)
    op.create_table('admin_action_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('admin_id', sa.Integer(), nullable=False),
    sa.Column('action_type', sa.Enum('APPROVE_DRIVER', 'REJECT_DRIVER', 'SUSPEND_DRIVER', 'BAN_USER', 'UNBAN_USER', 'ASSIGN_REQUEST', 'CANCEL_REQUEST', 'PROMOTE_ADMIN', 'BROADCAST', name='adminactiontype'), nullable=False),
    sa.Column('target_user_id', sa.Integer(), nullable=True),
    sa.Column('target_request_id', sa.Integer(), nullable=True),
    sa.Column('details', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['target_request_id'], ['delivery_requests.id'], ),
    sa.ForeignKeyConstraint(['target_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('feedbacks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('request_id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('comment', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['request_id'], ['delivery_requests.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('request_id')
    )
    op.create_table('request_status_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('request_id', sa.Integer(), nullable=False),
    sa.Column('old_status', sa.Enum('PENDING', 'ASSIGNED', 'ACCEPTED', 'REJECTED_BY_DRIVER', 'EN_ROUTE_TO_PICKUP', 'PICKED_UP', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED', 'FAILED', name='requeststatus'), nullable=True),
    sa.Column('new_status', sa.Enum('PENDING', 'ASSIGNED', 'ACCEPTED', 'REJECTED_BY_DRIVER', 'EN_ROUTE_TO_PICKUP', 'PICKED_UP', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED', 'FAILED', name='requeststatus'), nullable=False),
    sa.Column('changed_by_user_id', sa.Integer(), nullable=True),
    sa.Column('note', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['changed_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['request_id'], ['delivery_requests.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.execute(sa.text('DROP TABLE IF EXISTS request_status_logs CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS feedbacks CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS admin_action_logs CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS student_profiles CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS driver_profiles CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS delivery_requests CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS admin_profiles CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS users CASCADE'))
    op.execute(sa.text('DROP TYPE IF EXISTS adminactiontype, cancelledby, requeststatus, luggagesize, verificationstatus, driveravailability, driverstatus, accountstatus, userrole'))
