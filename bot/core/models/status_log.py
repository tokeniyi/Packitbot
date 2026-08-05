from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import RequestStatus
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin

if TYPE_CHECKING:
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.user import User


class RequestStatusLog(Base, TimestampMixin):
    """Audit log for delivery request status transitions."""

    __tablename__ = "request_status_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status: Mapped[RequestStatus | None] = mapped_column(
        Enum(RequestStatus), nullable=True
    )
    new_status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), nullable=False, index=True
    )
    changed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    request: Mapped[DeliveryRequest] = relationship(
        back_populates="status_logs"
    )
    changed_by_user: Mapped[User | None] = relationship(
        back_populates="status_changes"
    )

