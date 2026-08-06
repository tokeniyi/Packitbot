"""
AdminActionLog ORM model for the Packit bot.

Immutable audit trail for administrative actions (driver approval/rejection,
user ban/unban, request assignment/cancellation, admin promotion, broadcast).
Each row records who performed the action, the action type, and the target
(if applicable).

Used by:
    - ``bot/admin/service.py`` — ``approve_driver``, ``reject_driver``,
      ``ban_user``, ``unban_user``, ``promote_admin`` all write log entries.
    - ``alembic/env.py`` — registered for Alembic migrations.
    - ``tests/unit/admin/test_service.py`` — asserts log entries are created.
    - ``tests/unit/core/test_models.py`` — model unit tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import AdminActionType
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin

if TYPE_CHECKING:
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.user import User


class AdminActionLog(Base, TimestampMixin):
    """Immutable audit trail for administrative actions.

    Unlike ``RequestStatusLog`` (which tracks request status changes),
    this table tracks all admin-initiated actions across the system.
    Entries are append-only — they are never updated or deleted.

    Attributes:
        id (int): Primary key.
        admin_id (int): FK to ``users.id`` of the admin who acted.
            ``RESTRICT`` prevents deleting a user who has audit records,
            preserving the audit trail.
        action_type (AdminActionType): The kind of action taken (e.g.
            ``APPROVE_DRIVER``, ``BAN_USER``).
        target_user_id (int | None): FK to ``users.id`` of the affected
            user, if applicable. ``SET NULL`` preserves the log if the
            target user is later deleted.
        target_request_id (int | None): FK to
            ``delivery_requests.id`` of the affected request, if applicable.
            ``SET NULL`` for the same reason.
        details (str | None): Free-text context (e.g. rejection reason,
            ban reason).

    Relationships:
        admin: The ``User`` who performed the action.
        target_user: The ``User`` affected by the action (may be
            ``None`` for admin-only actions like ``BROADCAST``).
        target_request: The ``DeliveryRequest`` affected by the action
            (may be ``None``).

    Calls / Depends on:
        - ``bot.core.db.base_class.Base`` — declarative base.
        - ``bot.core.models.base.TimestampMixin`` — audit timestamps.
        - ``bot.core.constants.enums.AdminActionType`` — column enum type.

    Called by:
        - ``bot/admin/service.py`` — ``approve_driver``,
          ``reject_driver``, ``ban_user``, ``unban_user``,
          ``promote_admin``.
        - ``alembic/env.py`` — table registration.
    """

    __tablename__ = "admin_action_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # admin_id uses RESTRICT so that a user with audit records cannot be
    # deleted, preserving the integrity of the audit trail.
    admin_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[AdminActionType] = mapped_column(
        Enum(AdminActionType), nullable=False, index=True
    )
    # Both target_user_id and target_request_id use SET NULL so that if the
    # target entity is deleted, the audit log is preserved (the FK
    # reference becomes NULL, clearly marking it as a deleted target).
    target_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_request_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("delivery_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    admin: Mapped[User] = relationship(
        foreign_keys=[admin_id],
        uselist=False,
    )
    target_user: Mapped[User | None] = relationship(
        foreign_keys=[target_user_id],
        uselist=False,
    )
    target_request: Mapped[DeliveryRequest | None] = relationship(
        foreign_keys=[target_request_id],
        uselist=False,
    )
