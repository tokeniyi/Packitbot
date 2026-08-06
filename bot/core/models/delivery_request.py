"""
DeliveryRequest ORM model for the Packit bot.

Represents a student-initiated parcel delivery request, tracking it from
creation through assignment, acceptance, transit, and final delivery (or
cancellation).  Status transitions are governed by the finite-state-machine
in ``bot/request/state_machine.py`` and are audited via
``RequestStatusLog``.

Used by:
    - ``bot/request/service.py`` — full lifecycle of requests (create,
      assign, cancel, transition, feedback).
    - ``bot/request/repository.py`` — CRUD and query operations.
    - ``bot/request/business_rules.py`` — read-only eligibility checks.
    - ``bot/admin/service.py`` — pending-request listing and stats.
    - ``bot/admin/handler.py`` — displays request details.
    - ``bot/student/handler.py`` and ``bot/student/handler_requests.py`` —
      student request views and edits.
    - ``bot/driver/handler.py`` — driver request views and status updates.
    - ``alembic/env.py`` — registered for Alembic migrations.
    - ``tests/unit/core/test_models.py`` — model unit tests.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import CancelledBy, LuggageSize, RequestStatus
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin

if TYPE_CHECKING:
    from bot.core.models.feedback import Feedback
    from bot.core.models.status_log import RequestStatusLog
    from bot.core.models.user import User


class DeliveryRequest(Base, TimestampMixin):
    """Student delivery request with pickup, dropoff, and tracking details.

    The request's lifecycle is driven by ``RequestStatus`` enum values,
    transitioning through ``PENDING → ASSIGNED → ACCEPTED → EN_ROUTE_TO_PICKUP
    → PICKED_UP → IN_TRANSIT → DELIVERED`` (or ``CANCELLED`` / ``FAILED``).
    Each transition is audited in ``request.status_logs``.

    Attributes:
        id (int): Primary key.
        student_id (int): FK to ``users.id`` — the requesting student.
            ``ondelete="RESTRICT"`` prevents deleting a user who has
            requests, preserving referential integrity.
        driver_id (int | None): FK to ``users.id`` — the assigned driver.
            ``ondelete="SET NULL"`` clears the assignment if the driver is
            deleted rather than blocking deletion.
        pickup_detail (str): Pickup location description.
        dropoff_address (str): Delivery destination address.
        dropoff_landmark (str | None): Nearby landmark for navigation.
        hall_of_residence (str): Student's hall (indexed for filtering
            by delivery zones).
        recipient_name (str): Name of the package recipient.
        recipient_phone (str): Contact phone for the recipient.
        luggage_size (LuggageSize): ``small``, ``medium``, or ``large``.
        luggage_count (int): Number of luggage pieces.
        special_instructions (str | None): Optional delivery notes.
        preferred_date (date): Date the student wants the delivery.
        preferred_time_window (str): Time slot preference (e.g. "09:00-12:00").
        status (RequestStatus): Current lifecycle state. Defaults to
            ``PENDING``.
        cancelled_by (CancelledBy | None): Who initiated cancellation.
        cancellation_reason (str | None): Free-text reason for cancellation.

    Relationships:
        student: The ``User`` who created the request (via ``student_id``).
        driver: The ``User`` assigned to deliver (via ``driver_id``).
        status_logs: Ordered list of ``RequestStatusLog`` audit entries.
        feedback: Optional ``Feedback`` record (one-to-one).

    Calls / Depends on:
        - ``bot.core.db.base_class.Base`` — declarative base.
        - ``bot.core.models.base.TimestampMixin`` — audit timestamps.
        - ``bot.core.constants.enums`` — ``RequestStatus``, ``CancelledBy``,
          ``LuggageSize``.

    Called by:
        - ``bot/request/service.py`` — ``RequestService`` queries and mutates
          requests throughout the lifecycle.
        - ``bot/request/repository.py`` — ``RequestRepository`` wraps DB
          access.
        - ``bot/admin/service.py`` — counts and lists ``PENDING`` requests.
        - ``bot/student/handler_requests.py`` — displays request details.
        - ``bot/driver/handler.py`` — displays assigned requests.
        - ``alembic/env.py`` — table registration.
    """

    __tablename__ = "delivery_requests"

    id: Mapped[int] = mapped_column(primary_key=True)


    student_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


    driver_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    pickup_detail: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    dropoff_address: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    dropoff_landmark: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    hall_of_residence: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    recipient_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    recipient_phone: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    luggage_size: Mapped[LuggageSize] = mapped_column(
        Enum(LuggageSize), nullable=False
    )
    luggage_count: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    special_instructions: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    preferred_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    preferred_time_window: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus),
        default=RequestStatus.PENDING,
        nullable=False,
        index=True,
    )
    cancelled_by: Mapped[CancelledBy | None] = mapped_column(
        Enum(CancelledBy), nullable=True, index=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Relationships use explicit ``foreign_keys`` to disambiguate the two
    # FKs that both point at ``users.id`` (student_id and driver_id).
    student: Mapped[User] = relationship(
        foreign_keys=[student_id],
        back_populates="requests_made",
    )
    driver: Mapped[User | None] = relationship(
        foreign_keys=[driver_id],
        back_populates="requests_driven",
    )
    status_logs: Mapped[list[RequestStatusLog]] = relationship(
        back_populates="request",
        # cascade="all, delete-orphan" ensures status log entries are
        # removed automatically when the parent request is deleted,
        # preventing orphaned audit records.
        cascade="all, delete-orphan",
    )
    feedback: Mapped[Feedback | None] = relationship(
        back_populates="request",
        uselist=False,
        # One-to-one: a single request can have at most one feedback record.
        cascade="all, delete-orphan",
    )
