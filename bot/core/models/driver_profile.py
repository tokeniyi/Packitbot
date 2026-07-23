from datetime import datetime
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import DriverAvailability, DriverStatus
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin
from bot.core.models.user import User


class DriverProfile(Base, TimestampMixin):
    __tablename__ = "driver_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False)
    plate_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    license_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[DriverStatus] = mapped_column(Enum(DriverStatus), default=DriverStatus.PENDING_APPROVAL, nullable=False)
    availability: Mapped[DriverAvailability] = mapped_column(Enum(DriverAvailability), default=DriverAvailability.OFFLINE, nullable=False)
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_deliveries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    approved_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="driver_profile", foreign_keys=[user_id])
    approved_by_admin: Mapped[User | None] = relationship(foreign_keys=[approved_by_admin_id])
