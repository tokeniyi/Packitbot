from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bot.core.models.delivery_request import DeliveryRequest

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin
from bot.core.models.user import User


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("delivery_requests.id", ondelete="CASCADE"), unique=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)

    request: Mapped["DeliveryRequest"] = relationship(back_populates="feedback")
    student: Mapped[User] = relationship()
