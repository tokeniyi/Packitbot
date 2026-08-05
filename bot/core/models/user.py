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