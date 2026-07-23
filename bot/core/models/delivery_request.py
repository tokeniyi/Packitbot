from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bot.core.models.feedback import Feedback


from bot.core.models.status_log import RequestStatusLog
from datetime import date, datetime
from sqlalchemy import Date, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import CancelledBy, LuggageSize, RequestStatus
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin
from bot.core.models.user import User


class DeliveryRequest(Base, TimestampMixin):
    __tablename__ = "delivery_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    pickup_detail: Mapped[str] = mapped_column(String(255), nullable=False)
    dropoff_address: Mapped[str] = mapped_column(String(255), nullable=False)
    dropoff_landmark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hall_of_residence: Mapped[str] = mapped_column(String(100), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    luggage_size: Mapped[LuggageSize] = mapped_column(Enum(LuggageSize), nullable=False)
    luggage_count: Mapped[int] = mapped_column(Integer, nullable=False)
    special_instructions: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preferred_date: Mapped[date] = mapped_column(Date, nullable=False)
    preferred_time_window: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), default=RequestStatus.PENDING, nullable=False)
    cancelled_by: Mapped[CancelledBy | None] = mapped_column(Enum(CancelledBy), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    student: Mapped[User] = relationship(foreign_keys=[student_id], back_populates="requests_made")
    driver: Mapped[User | None] = relationship(foreign_keys=[driver_id], back_populates="requests_driven")
    status_logs: Mapped["RequestStatusLog | None"] = relationship(back_populates="request", cascade="all, delete-orphan")
    feedback: Mapped["Feedback | None"] = relationship(back_populates="request", uselist=False, cascade="all, delete-orphan")
