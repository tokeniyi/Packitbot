"""
StudentProfile ORM model for the Packit bot.

Stores student-specific information such as hall of residence, room number,
and verification status.  A student profile is created when a user completes
the student registration flow (see ``bot.student.service.register_student``).

Used by:
    - ``bot/student/service.py`` — creates and updates student profiles.
    - ``bot/student/repository.py`` — repository wrapper for profile queries.
    - ``bot/student/handler.py`` — displays student profiles in Telegram.
    - ``bot/request/repository.py`` — may join on student profiles for
      request history.
    - ``alembic/env.py`` — registered for Alembic migrations.
    - ``tests/unit/core/test_models.py`` — model unit tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import VerificationStatus
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin

if TYPE_CHECKING:
    from bot.core.models.user import User


class StudentProfile(Base, TimestampMixin):
    """Student profile with hall/room details and verification status.

    Verification status defaults to ``UNVERIFIED``.  Verification is
    typically granted by an admin (see ``AdminActionType`` enum) or via
    integration with the university's student records.

    Attributes:
        id (int): Primary key.
        user_id (int): FK to ``users.id`` (one-to-one). ``CASCADE`` ensures
            the profile is removed if the user is deleted.
        hall_of_residence (str): Student's residence hall (indexed for
            zone-based delivery matching).
        room_number (str | None): Room number within the hall.
        verification_status (VerificationStatus): ``UNVERIFIED`` or
            ``VERIFIED``.

    Relationships:
        user: The ``User`` this profile belongs to.

    Calls / Depends on:
        - ``bot.core.db.base_class.Base`` — declarative base.
        - ``bot.core.models.base.TimestampMixin`` — audit timestamps.
        - ``bot.core.constants.enums.VerificationStatus`` — column enum type.

    Called by:
        - ``bot/student/service.py`` — ``register_student`` creates and
          updates profiles.
        - ``alembic/env.py`` — table registration.
    """

    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    hall_of_residence: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    room_number: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
        index=True,
    )

    user: Mapped[User] = relationship(
        back_populates="student_profile",
        uselist=False,
    )
