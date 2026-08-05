from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.constants.enums import AdminActionType
from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin

if TYPE_CHECKING:
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.user import User


class AdminActionLog(Base, TimestampMixin):
    """Immutable audit trail for administrative actions."""

    __tablename__ = "admin_action_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[AdminActionType] = mapped_column(
        Enum(AdminActionType), nullable=False, index=True
    )
    target_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_request_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("delivery_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    admin: Mapped[User] = relationship(
        foreign_keys=[admin_id],
        uselist=False,
    )
    target_user: Mapped[User | None] = relationship(
        foreign_keys=[target_user_id],
        uselist=False,
    )
    target_request: Mapped[DeliveryRequest | None] = relationship(
        foreign_keys=[target_request_id],
        uselist=False,
    )
