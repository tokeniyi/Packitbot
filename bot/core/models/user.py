from __future__ import annotations


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.admin_profile import AdminProfile
    from bot.core.models.driver_profile import DriverProfile
    from bot.core.models.student_profile import StudentProfile


from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import AccountStatus, UserRole
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    account_status: Mapped[AccountStatus] = mapped_column(Enum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False)
    banned_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banned_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    student_profile: Mapped[StudentProfile | None] = relationship(back_populates="user", uselist=False)
    driver_profile: Mapped[DriverProfile | None] = relationship(back_populates="user", uselist=False, foreign_keys="DriverProfile.user_id")
    admin_profile: Mapped[AdminProfile | None] = relationship(back_populates="user", uselist=False, foreign_keys="AdminProfile.user_id")
    requests_made: Mapped[list[DeliveryRequest]] = relationship(foreign_keys="DeliveryRequest.student_id", back_populates="student")
    requests_driven: Mapped[list[DeliveryRequest]] = relationship(foreign_keys="DeliveryRequest.driver_id", back_populates="driver")
