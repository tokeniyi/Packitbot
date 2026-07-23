from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import AdminActionType
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin
from bot.core.models.user import User


class AdminActionLog(Base, TimestampMixin):
    __tablename__ = "admin_action_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action_type: Mapped[AdminActionType] = mapped_column(Enum(AdminActionType), nullable=False)
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    target_request_id: Mapped[int | None] = mapped_column(ForeignKey("delivery_requests.id"), nullable=True)
    details: Mapped[str | None] = mapped_column(String(500), nullable=True)

    admin: Mapped[User] = relationship(foreign_keys=[admin_id])
    target_user: Mapped[User | None] = relationship(foreign_keys=[target_user_id])
    target_request: Mapped["DeliveryRequest | None"] = relationship(foreign_keys=[target_request_id])
