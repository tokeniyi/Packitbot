"""
RequestStatusLog ORM model for the Packit bot.

Immutable audit log capturing every status transition that a delivery request
undergoes.  Each row records the ``old_status``, ``new_status``, the user
who triggered the change (if any), and an optional note.

Used by:
    - ``bot/request/service.py`` — ``RequestService`` writes a
      ``RequestStatusLog`` row on every status change (create, assign,
      accept, transit, deliver, cancel).
    - ``bot/admin/service.py`` — computes average delivery duration by
      correlating ``ACCEPTED`` and ``DELIVERED`` log timestamps.
    - ``bot/request/repository.py`` — ``StatusLogRepository`` wraps DB
      access for log creation.
    - ``alembic/env.py`` — registered for Alembic migrations.
    - ``tests/unit/core/test_models.py`` — model unit tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import RequestStatus
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin

if TYPE_CHECKING:
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.user import User


class RequestStatusLog(Base, TimestampMixin):
    """Audit log for delivery request status transitions.

    Every transition of a ``DeliveryRequest``'s ``status`` field is
    recorded here as an immutable history entry.  The ``created_at``
    timestamp (inherited from ``TimestampMixin``) is the canonical time of
    the transition.

    Attributes:
        id (int): Primary key.
        request_id (int): FK to ``delivery_requests.id``. ``CASCADE``
            ensures logs are removed if the request is deleted.
        old_status (RequestStatus | None): Status before the transition.
            ``None`` for the initial log entry when a request is created.
        new_status (RequestStatus): Status after the transition.
        changed_by_user_id (int | None): FK to ``users.id`` of the actor
            who triggered the change. ``SET NULL`` preserves the log even if
            the user is later deleted.
        note (str | None): Optional human-readable description of the
            transition (e.g. "Assigned to driver 42").

    Relationships:
        request: The ``DeliveryRequest`` this log entry belongs to.
        changed_by_user: The ``User`` who triggered the transition
            (may be ``None`` for system-initiated transitions).

    Calls / Depends on:
        - ``bot.core.db.base_class.Base`` — declarative base.
        - ``bot.core.models.base.TimestampMixin`` — audit timestamps.
        - ``bot.core.constants.enums.RequestStatus`` — column enum type.

    Called by:
        - ``bot/request/service.py`` — ``RequestService`` appends log
          entries on every status change.
        - ``bot/admin/service.py`` — reads logs to compute average
          delivery duration in ``get_stats``.
        - ``alembic/env.py`` — table registration.
    """

    __tablename__ = "request_status_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # old_status is nullable because the first log entry for a request
    # (creation) has no prior status to record.
    old_status: Mapped[RequestStatus | None] = mapped_column(
        Enum(RequestStatus), nullable=True
    )
    new_status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), nullable=False, index=True
    )
    # changed_by_user_id uses SET NULL so that if the acting user is
    # deleted, the audit trail is preserved (the reference just becomes
    # NULL, clearly indicating a system or deleted-user action).
    changed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    request: Mapped[DeliveryRequest] = relationship(
        back_populates="status_logs"
    )
    changed_by_user: Mapped[User | None] = relationship(
        back_populates="status_changes"
    )
