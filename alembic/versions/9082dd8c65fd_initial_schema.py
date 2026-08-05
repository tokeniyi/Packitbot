"""initial schema

Revision ID: 9082dd8c65fd
Revises: 3ec380728795
Create Date: 2026-07-23 18:12:54.343781

"""
# ---------------------------------------------------------------------------
# Code Logic:
#   This Alembic migration establishes the foundational database schema for the
#   PackitBot application. It creates the core tables, foreign key relationships,
#   indexes, and PostgreSQL ENUM types required for users, drivers, students,
#   delivery requests, admin actions, feedbacks, and status change logs.
#
# Function Calls:
#   - upgrade() -> applies all schema changes in order
#   - downgrade() -> reverses the upgrade by dropping tables and types
#
# Cross-References:
#   - Depends on: alembic op utilities, sqlalchemy types
#   - Imported by: alembic runtime when migrating the database
# ---------------------------------------------------------------------------
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Revision identifiers, used by Alembic.
# ---------------------------------------------------------------------------
revision: str = '9082dd8c65fd'
down_revision: Union[str, None] = '3ec380728795'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------------------
    # Enum type: userrole
    # Values: STUDENT, DRIVER, ADMIN
    # ---------------------------------------------------------------------------
    userrole_enum = sa.Enum('STUDENT', 'DRIVER', 'ADMIN', name='userrole')

    # ---------------------------------------------------------------------------
    # Enum type: accountstatus
    # Values: ACTIVE, BANNED
    # ---------------------------------------------------------------------------
    accountstatus_enum = sa.Enum('ACTIVE', 'BANNED', name='accountstatus')

    # ---------------------------------------------------------------------------
    # Table: users
    # ---------------------------------------------------------------------------
    op.create_table(
        'users',
        # Column: id - primary key
        sa.Column('id', sa.Integer(), nullable=False),
        # Column: telegram_id - unique Telegram user identifier
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        # Column: username - optional Telegram username
        sa.Column('username', sa.String(length=255), nullable=True),
        # Column: full_name - required display name
        sa.Column('full_name', sa.String(length=255), nullable=False),
        # Column: phone_number - optional contact number
        sa.Column('phone_number', sa.String(length=20), nullable=True),
        # Column: role - user role enum (STUDENT, DRIVER, ADMIN)
        sa.Column('role', userrole_enum, nullable=False),
        # Column: account_status - active or banned status enum
        sa.Column('account_status', accountstatus_enum, nullable=False),
        # Column: banned_reason - optional text explaining ban reason
        sa.Column('banned_reason', sa.String(length=500), nullable=True),
        # Column: banned_at - timestamp when ban was applied
        sa.Column('banned_at', sa.DateTime(), nullable=True),
        # Column: created_at - row creation timestamp with server default
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Column: updated_at - row update timestamp with server default
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Constraint: primary key on id
        sa.PrimaryKeyConstraint('id')
    )
    # Unique index on telegram_id for fast user lookups
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)

    # ---------------------------------------------------------------------------
    # Table: admin_profiles
    # ---------------------------------------------------------------------------
    op.create_table(
        'admin_profiles',
        # Column: id - primary key
        sa.Column('id', sa.Integer(), nullable=False),
        # Column: user_id - foreign key to users.id (CASCADE delete)
        sa.Column('user_id', sa.Integer(), nullable=False),
        # Column: added_by_admin_id - foreign key to users.id (the admin who created this)
        sa.Column('added_by_admin_id', sa.Integer(), nullable=True),
        # Column: created_at - row creation timestamp
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Column: updated_at - row update timestamp
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Foreign key: added_by_admin_id references users.id
        sa.ForeignKeyConstraint(['added_by_admin_id'], ['users.id'], ),
        # Foreign key: user_id references users.id with CASCADE delete
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        # Constraint: primary key on id
        sa.PrimaryKeyConstraint('id'),
        # Constraint: unique user_id (each user can have at most one admin profile)
        sa.UniqueConstraint('user_id')
    )

    # ---------------------------------------------------------------------------
    # Table: delivery_requests
    # ---------------------------------------------------------------------------
    op.create_table(
        'delivery_requests',
        # Column: id - primary key
        sa.Column('id', sa.Integer(), nullable=False),
        # Column: student_id - foreign key to users.id
        sa.Column('student_id', sa.Integer(), nullable=False),
        # Column: driver_id - nullable foreign key to users.id
        sa.Column('driver_id', sa.Integer(), nullable=True),
        # Column: pickup_detail - description of pickup location
        sa.Column('pickup_detail', sa.String(length=255), nullable=False),
        # Column: dropoff_address - delivery destination address
        sa.Column('dropoff_address', sa.String(length=255), nullable=False),
        # Column: dropoff_landmark - optional landmark near destination
        sa.Column('dropoff_landmark', sa.String(length=255), nullable=True),
        # Column: hall_of_residence - student's hall of residence
        sa.Column('hall_of_residence', sa.String(length=100), nullable=False),
        # Column: recipient_name - name of the package recipient
        sa.Column('recipient_name', sa.String(length=255), nullable=False),
        # Column: recipient_phone - phone number of the recipient
        sa.Column('recipient_phone', sa.String(length=20), nullable=False),
        # Column: luggage_size - enum for package size (SMALL, MEDIUM, LARGE)
        sa.Column('luggage_size', sa.Enum('SMALL', 'MEDIUM', 'LARGE', name='luggagesize'), nullable=False),
        # Column: luggage_count - number of packages/luggage items
        sa.Column('luggage_count', sa.Integer(), nullable=False),
        # Column: special_instructions - optional delivery instructions
        sa.Column('special_instructions', sa.String(length=500), nullable=True),
        # Column: preferred_date - date the student wants delivery
        sa.Column('preferred_date', sa.Date(), nullable=False),
        # Column: preferred_time_window - time window string for delivery
        sa.Column('preferred_time_window', sa.String(length=50), nullable=False),
        # Column: status - request lifecycle enum (PENDING, ASSIGNED, etc.)
        sa.Column('status', sa.Enum('PENDING', 'ASSIGNED', 'ACCEPTED', 'REJECTED_BY_DRIVER', 'EN_ROUTE_TO_PICKUP', 'PICKED_UP', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED', 'FAILED', name='requeststatus'), nullable=False),
        # Column: cancelled_by - enum indicating who cancelled (STUDENT, ADMIN, SYSTEM)
        sa.Column('cancelled_by', sa.Enum('STUDENT', 'ADMIN', 'SYSTEM', name='cancelledby'), nullable=True),
        # Column: cancellation_reason - optional reason text for cancellation
        sa.Column('cancellation_reason', sa.String(length=255), nullable=True),
        # Column: created_at - row creation timestamp
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Column: updated_at - row update timestamp
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Foreign key: driver_id references users.id
        sa.ForeignKeyConstraint(['driver_id'], ['users.id'], ),
        # Foreign key: student_id references users.id
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ),
        # Constraint: primary key on id
        sa.PrimaryKeyConstraint('id')
    )

    # ---------------------------------------------------------------------------
    # Table: driver_profiles
    # ---------------------------------------------------------------------------
    op.create_table(
        'driver_profiles',
        # Column: id - primary key
        sa.Column('id', sa.Integer(), nullable=False),
        # Column: user_id - foreign key to users.id with CASCADE delete
        sa.Column('user_id', sa.Integer(), nullable=False),
        # Column: vehicle_type - type of vehicle used for deliveries
        sa.Column('vehicle_type', sa.String(length=50), nullable=False),
        # Column: plate_number - vehicle registration plate number
        sa.Column('plate_number', sa.String(length=20), nullable=False),
        # Column: license_number - driver's license number
        sa.Column('license_number', sa.String(length=50), nullable=False),
        # Column: status - driver approval status enum
        sa.Column('status', sa.Enum('PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'SUSPENDED', name='driverstatus'), nullable=False),
        # Column: availability - current availability state enum
        sa.Column('availability', sa.Enum('AVAILABLE', 'BUSY', 'OFFLINE', name='driveravailability'), nullable=False),
        # Column: rating_avg - average rating from student feedback
        sa.Column('rating_avg', sa.Float(), nullable=False),
        # Column: total_deliveries - count of completed deliveries
        sa.Column('total_deliveries', sa.Integer(), nullable=False),
        # Column: approved_by_admin_id - foreign key to users.id (admin who approved)
        sa.Column('approved_by_admin_id', sa.Integer(), nullable=True),
        # Column: approved_at - timestamp when driver was approved
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        # Column: created_at - row creation timestamp
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Column: updated_at - row update timestamp
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Foreign key: approved_by_admin_id references users.id
        sa.ForeignKeyConstraint(['approved_by_admin_id'], ['users.id'], ),
        # Foreign key: user_id references users.id with CASCADE delete
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        # Constraint: primary key on id
        sa.PrimaryKeyConstraint('id'),
        # Constraint: unique plate_number (no duplicate registrations)
        sa.UniqueConstraint('plate_number'),
        # Constraint: unique user_id (each user can have at most one driver profile)
        sa.UniqueConstraint('user_id')
    )

    # ---------------------------------------------------------------------------
    # Table: student_profiles
    # ---------------------------------------------------------------------------
    op.create_table(
        'student_profiles',
        # Column: id - primary key
        sa.Column('id', sa.Integer(), nullable=False),
        # Column: user_id - foreign key to users.id with CASCADE delete
        sa.Column('user_id', sa.Integer(), nullable=False),
        # Column: matric_number - student matriculation number
        sa.Column('matric_number', sa.String(length=50), nullable=False),
        # Column: hall_of_residence - student's hall of residence
        sa.Column('hall_of_residence', sa.String(length=100), nullable=False),
        # Column: room_number - optional room number
        sa.Column('room_number', sa.String(length=20), nullable=True),
        # Column: verification_status - enum for verification state
        sa.Column('verification_status', sa.Enum('UNVERIFIED', 'VERIFIED', name='verificationstatus'), nullable=False),
        # Column: created_at - row creation timestamp
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Column: updated_at - row update timestamp
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Foreign key: user_id references users.id with CASCADE delete
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        # Constraint: primary key on id
        sa.PrimaryKeyConstraint('id'),
        # Constraint: unique user_id (each user can have at most one student profile)
        sa.UniqueConstraint('user_id')
    )
    # Unique index on matric_number for fast student lookups
    op.create_index(op.f('ix_student_profiles_matric_number'), 'student_profiles', ['matric_number'], unique=True)

    # ---------------------------------------------------------------------------
    # Table: admin_action_logs
    # ---------------------------------------------------------------------------
    op.create_table(
        'admin_action_logs',
        # Column: id - primary key
        sa.Column('id', sa.Integer(), nullable=False),
        # Column: admin_id - foreign key to users.id (performing admin)
        sa.Column('admin_id', sa.Integer(), nullable=False),
        # Column: action_type - enum describing the admin action taken
        sa.Column('action_type', sa.Enum('APPROVE_DRIVER', 'REJECT_DRIVER', 'SUSPEND_DRIVER', 'BAN_USER', 'UNBAN_USER', 'ASSIGN_REQUEST', 'CANCEL_REQUEST', 'PROMOTE_ADMIN', 'BROADCAST', name='adminactiontype'), nullable=False),
        # Column: target_user_id - optional foreign key to users.id (affected user)
        sa.Column('target_user_id', sa.Integer(), nullable=True),
        # Column: target_request_id - optional foreign key to delivery_requests.id
        sa.Column('target_request_id', sa.Integer(), nullable=True),
        # Column: details - optional text details about the action
        sa.Column('details', sa.String(length=500), nullable=True),
        # Column: created_at - row creation timestamp
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Column: updated_at - row update timestamp
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Foreign key: admin_id references users.id
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ),
        # Foreign key: target_request_id references delivery_requests.id
        sa.ForeignKeyConstraint(['target_request_id'], ['delivery_requests.id'], ),
        # Foreign key: target_user_id references users.id
        sa.ForeignKeyConstraint(['target_user_id'], ['users.id'], ),
        # Constraint: primary key on id
        sa.PrimaryKeyConstraint('id')
    )

    # ---------------------------------------------------------------------------
    # Table: feedbacks
    # ---------------------------------------------------------------------------
    op.create_table(
        'feedbacks',
        # Column: id - primary key
        sa.Column('id', sa.Integer(), nullable=False),
        # Column: request_id - foreign key to delivery_requests.id with CASCADE delete
        sa.Column('request_id', sa.Integer(), nullable=False),
        # Column: student_id - foreign key to users.id
        sa.Column('student_id', sa.Integer(), nullable=False),
        # Column: rating - integer rating value
        sa.Column('rating', sa.Integer(), nullable=False),
        # Column: comment - optional feedback text
        sa.Column('comment', sa.String(length=500), nullable=True),
        # Column: created_at - row creation timestamp
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Column: updated_at - row update timestamp
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Foreign key: request_id references delivery_requests.id with CASCADE delete
        sa.ForeignKeyConstraint(['request_id'], ['delivery_requests.id'], ondelete='CASCADE'),
        # Foreign key: student_id references users.id
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ),
        # Constraint: primary key on id
        sa.PrimaryKeyConstraint('id'),
        # Constraint: unique request_id (one feedback per delivery request)
        sa.UniqueConstraint('request_id')
    )

    # ---------------------------------------------------------------------------
    # Table: request_status_logs
    # ---------------------------------------------------------------------------
    op.create_table(
        'request_status_logs',
        # Column: id - primary key
        sa.Column('id', sa.Integer(), nullable=False),
        # Column: request_id - foreign key to delivery_requests.id with CASCADE delete
        sa.Column('request_id', sa.Integer(), nullable=False),
        # Column: old_status - previous request status enum
        sa.Column('old_status', sa.Enum('PENDING', 'ASSIGNED', 'ACCEPTED', 'REJECTED_BY_DRIVER', 'EN_ROUTE_TO_PICKUP', 'PICKED_UP', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED', 'FAILED', name='requeststatus'), nullable=True),
        # Column: new_status - new request status enum
        sa.Column('new_status', sa.Enum('PENDING', 'ASSIGNED', 'ACCEPTED', 'REJECTED_BY_DRIVER', 'EN_ROUTE_TO_PICKUP', 'PICKED_UP', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED', 'FAILED', name='requeststatus'), nullable=False),
        # Column: changed_by_user_id - foreign key to users.id (actor)
        sa.Column('changed_by_user_id', sa.Integer(), nullable=True),
        # Column: note - optional text note about the transition
        sa.Column('note', sa.String(length=255), nullable=True),
        # Column: created_at - row creation timestamp
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Column: updated_at - row update timestamp
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Foreign key: changed_by_user_id references users.id
        sa.ForeignKeyConstraint(['changed_by_user_id'], ['users.id'], ),
        # Foreign key: request_id references delivery_requests.id with CASCADE delete
        sa.ForeignKeyConstraint(['request_id'], ['delivery_requests.id'], ondelete='CASCADE'),
        # Constraint: primary key on id
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.execute(sa.text('DROP TABLE IF EXISTS request_status_logs CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS feedbacks CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS admin_action_logs CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS student_profiles CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS driver_profiles CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS delivery_requests CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS admin_profiles CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS users CASCADE'))
    # Drop enum types after tables that depend on them are removed
    op.execute(sa.text('DROP TYPE IF EXISTS adminactiontype, cancelledby, requeststatus, luggagesize, verificationstatus, driveravailability, driverstatus, accountstatus, userrole'))
