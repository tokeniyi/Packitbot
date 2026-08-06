"""
DriverProfile ORM model for the Packitbot bot.

Stores driver-specific information that is only relevant once a user has
been promoted to the ``DRIVER`` role, including vehicle details, approval
status, availability, and aggregate rating metrics.

Used by:
    - ``bot/driver/service.py`` — registers drivers, sets availability,
      fetches profiles by telegram_id.
    - ``bot/driver/handler.py`` — displays driver registration, approval
      status, availability, and active-delivery dashboards.
    - ``bot/driver/repository.py`` — repository wrapper for profile queries.
    - ``bot/request/service.py`` — reads driver availability/approval during
      assignment.
    - ``bot/request/business_rules.py`` — eligibility checks via
      ``can_assign_driver``.
    - ``bot/admin/service.py`` — lists pending/approved drivers, computes
      system stats.
    - ``bot/student/handler_requests.py`` — looks up driver profiles for
      request display.
    - ``alembic/env.py`` — registered for Alembic migrations.
    - ``tests/unit/core/test_models.py`` — model unit tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import DriverAvailability, DriverStatus
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin

if TYPE_CHECKING:
    from bot.core.models.user import User


class DriverProfile(Base, TimestampMixin):
    """Driver profile with vehicle details, ratings, and approval metadata.

    A driver profile is created when a user registers as a driver (see
    ``bot.driver.service.register_driver``).  The profile starts in
    ``PENDING_APPROVAL`` status and ``OFFLINE`` availability until an admin
    approves it and the driver toggles availability.

    Attributes:
        id (int): Primary key.
        user_id (int): FK to ``users.id`` (one-to-one). ``CASCADE`` ensures
            the driver profile is removed if the user is deleted.
        vehicle_type (str): Type of vehicle (e.g. "motorcycle", "car").
        plate_number (str): License plate (unique — enforced at DB level).
        license_number (str): Driver's license number.
        status (DriverStatus): ``PENDING_APPROVAL``, ``APPROVED``,
            ``REJECTED``, or ``SUSPENDED``.
        availability (DriverAvailability): ``AVAILABLE``, ``BUSY``, or
            ``OFFLINE``.  ``BUSY`` is system-managed and cannot be set
            manually (enforced in ``set_driver_availability``).
        rating_avg (float): Rolling average of student feedback ratings.
        total_deliveries (int): Count of completed deliveries.
        approved_by_admin_id (int | None): FK to ``users.id`` of the admin
            who approved the driver. ``SET NULL`` on delete.
        approved_at (datetime | None): When the driver was approved.

    Relationships:
        user: The ``User`` this profile belongs to (via ``user_id``).
        approved_by_admin: The ``User`` who approved the driver
            (via ``approved_by_admin_id``).

    Calls / Depends on:
        - ``bot.core.db.base_class.Base`` — declarative base.
        - ``bot.core.models.base.TimestampMixin`` — audit timestamps.
        - ``bot.core.constants.enums`` — ``DriverStatus``,
          ``DriverAvailability``.

    Called by:
        - ``bot/driver/service.py`` — ``register_driver``,
          ``get_driver_profile_by_telegram_id``, ``set_driver_availability``.
        - ``bot/admin/service.py`` — ``get_available_drivers_ranked``,
          ``get_pending_drivers``, ``get_stats``, ``approve_driver``,
          ``reject_driver``.
        - ``alembic/env.py`` — table registration.
    """

    __tablename__ = "driver_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # plate_number is unique to prevent two drivers registering the same
    # vehicle plate (enforced by the database unique constraint).
    plate_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )
    license_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[DriverStatus] = mapped_column(
        Enum(DriverStatus),
        default=DriverStatus.PENDING_APPROVAL,
        nullable=False,
        index=True,
    )
    availability: Mapped[DriverAvailability] = mapped_column(
        Enum(DriverAvailability),
        default=DriverAvailability.OFFLINE,
        nullable=False,
        index=True,
    )
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_deliveries: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    # approved_by_admin_id uses SET NULL so that if an admin user is deleted,
    # the approval record is preserved (the FK reference just becomes NULL).
    approved_by_admin_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    user: Mapped[User] = relationship(
        back_populates="driver_profile",
        foreign_keys=[user_id],
        uselist=False,
    )
    approved_by_admin: Mapped[User | None] = relationship(
        foreign_keys=[approved_by_admin_id],
        uselist=False,
    )
