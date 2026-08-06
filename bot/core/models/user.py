"""
User ORM model for the Packit bot.

Defines the central ``User`` entity, which represents every Telegram user
interacting with the bot (students, drivers, and admins).  A ``User`` record
is created lazily by ``AuthMiddleware`` on first contact, even before the
user selects a role.

The model establishes one-to-one relationships with ``StudentProfile``,
``DriverProfile``, and ``AdminProfile`` (the active relationship depends on
the user's ``role``), and one-to-many relationships with
``DeliveryRequest`` (via ``requests_made`` and ``requests_driven``).

Used by:
    - ``bot/core/middlewares/auth.py`` — creates/fetches ``User`` on every
      update; promotes seed admins.
    - ``bot/common/start.py`` — dispatches role-based welcome messages.
    - ``bot/student/service.py`` — registers students, queries by role.
    - ``bot/driver/service.py`` — registers drivers, queries by telegram_id.
    - ``bot/admin/service.py`` — searches users, bans/unbans, promotes admins.
    - ``bot/admin/handler.py``, ``bot/student/handler.py``,
      ``bot/student/handler_requests.py``, ``bot/driver/handler.py`` —
      resolve and display user data in Telegram.
    - ``bot/request/service.py`` — reads ``student_id`` / ``driver_id``
      on delivery requests.
    - ``alembic/env.py`` — registered for Alembic migrations.
    - ``tests/unit/core/test_models.py`` — model unit tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.core.models.admin_profile import AdminProfile
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.driver_profile import DriverProfile
    from bot.core.models.status_log import RequestStatusLog
    from bot.core.models.student_profile import StudentProfile

from sqlalchemy import BigInteger, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import AccountStatus, UserRole
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin


class User(Base, TimestampMixin):
    """Core user entity representing a Telegram account within the bot.

    ``role`` is nullable so that a user record can exist before the user
    chooses a role on the welcome screen (handled in ``start.py``).
    ``account_status`` defaults to ``ACTIVE``; setting it to ``BANNED``
    blocks access via ``AuthMiddleware``.

    Attributes:
        id (int): Primary key (BigInteger — matches Telegram ID range).
        telegram_id (int): Unique, indexed Telegram user identifier.
        username (str | None): Telegram @username, if the user has one set.
        full_name (str | None): Display name from Telegram.
        phone_number (str | None): Contact phone number, collected during
            registration.
        role (UserRole | None): ``student``, ``driver``, or ``admin``.
            Nullable until the user completes onboarding.
        account_status (AccountStatus): ``active`` or ``banned``.
        banned_reason (str | None): Human-readable reason for a ban.
        banned_at (datetime | None): When the ban was applied.

    Relationships:
        student_profile: One-to-one ``StudentProfile`` for students.
        driver_profile: One-to-one ``DriverProfile`` for drivers
            (uses explicit ``foreign_keys`` to disambiguate the
            dual FK-to-``users.id`` pattern on ``DriverProfile``).
        admin_profile: One-to-one ``AdminProfile`` for admins
            (uses explicit ``foreign_keys`` for the same reason).
        requests_made: All delivery requests created by this user as the
            student (FK ``DeliveryRequest.student_id``).
        requests_driven: All delivery requests assigned to this user as the
            driver (FK ``DeliveryRequest.driver_id``).
        status_changes: All ``RequestStatusLog`` rows attributed to this
            user via ``changed_by_user_id``.

    Calls / Depends on:
        - ``bot.core.db.base_class.Base`` — declarative base.
        - ``bot.core.models.base.TimestampMixin`` — provides
          ``created_at`` / ``updated_at``.
        - ``bot.core.constants.enums.UserRole`` / ``AccountStatus`` — column
          enum types.

    Called by:
        - ``alembic/env.py`` — imports the module to register the table.
        - All service-layer and handler modules listed in the file header.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    username: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    full_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    phone_number: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    # CHANGED: Allow nullable=True so new users can exist before choosing a role
    role: Mapped[UserRole | None] = mapped_column(
        Enum(UserRole), nullable=True, index=True
    )
    account_status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus),
        default=AccountStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    banned_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    banned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Relationships
    #
    # The driver_profile and admin_profile relationships each specify an
    # explicit ``foreign_keys`` argument because DriverProfile and
    # AdminProfile both contain multiple FKs to ``users.id`` (user_id and
    # approved_by_admin_id / added_by_admin_id).  Without the explicit hint,
    # SQLAlchemy could resolve the wrong FK for the relationship join.
    student_profile: Mapped[StudentProfile | None] = relationship(
        "StudentProfile", back_populates="user", uselist=False
    )
    driver_profile: Mapped[DriverProfile | None] = relationship(
        "DriverProfile",
        foreign_keys="DriverProfile.user_id",
        back_populates="user",
        uselist=False,
    )
    admin_profile: Mapped[AdminProfile | None] = relationship(
        "AdminProfile",
        foreign_keys="AdminProfile.user_id",
        back_populates="user",
        uselist=False,
    )
    requests_made: Mapped[list[DeliveryRequest]] = relationship(
        "DeliveryRequest",
        foreign_keys="DeliveryRequest.student_id",
        back_populates="student",
    )
    requests_driven: Mapped[list[DeliveryRequest]] = relationship(
        "DeliveryRequest",
        foreign_keys="DeliveryRequest.driver_id",
        back_populates="driver",
    )
    status_changes: Mapped[list[RequestStatusLog]] = relationship(
        "RequestStatusLog", back_populates="changed_by_user"
    )
