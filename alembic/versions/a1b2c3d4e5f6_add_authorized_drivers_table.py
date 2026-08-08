"""Add authorized_drivers table for pre-approved driver registration.

Revision ID: a1b2c3d4e5f6
Revises: 9082dd8c65fd
Create Date: 2026-08-07

Creates the ``authorized_drivers`` table which stores Telegram user IDs
that an admin has pre-approved to begin the driver registration flow.
Also adds the ``AUTHORIZE_DRIVER`` value to the existing PostgreSQL
``adminactiontype`` ENUM so that audit-log entries can be recorded.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9082dd8c65fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Add the AUTHORIZE_DRIVER value to the existing adminactiontype ENUM.
    # PostgreSQL's ALTER TYPE ... ADD VALUE is non-transactional on PG < 12,
    # so we commit the current transaction first.  On PG 12+ it is safe to
    # run inside a transaction.
    op.execute(sa.text("ALTER TYPE adminactiontype ADD VALUE 'AUTHORIZE_DRIVER'"))

    op.create_table(
        "authorized_drivers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("added_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["added_by_admin_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index(
        op.f("ix_authorized_drivers_telegram_id"),
        "authorized_drivers",
        ["telegram_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_authorized_drivers_telegram_id"), table_name="authorized_drivers")
    op.drop_table("authorized_drivers")

    # NOTE: PostgreSQL does not support removing individual ENUM values.
    # To fully reverse this migration the ENUM type must be recreated, which
    # is intentionally omitted here for safety (it would require migrating
    # existing rows that reference AUTHORIZE_DRIVER).
    pass
