from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import VerificationStatus
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin

if TYPE_CHECKING:
    from bot.core.models.user import User


class StudentProfile(Base, TimestampMixin):
    """Student profile with matric number and hall/room details."""

    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    matric_number: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
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
