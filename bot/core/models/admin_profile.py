"""
AdminProfile ORM model for the Packit bot.

Stores admin-specific metadata linked to ``User`` records.  Every user whose
Telegram ID appears in ``Settings.seed_admin_telegram_ids`` is automatically
granted an ``AdminProfile`` by ``AuthMiddleware`` on first contact.

Used by:
    - ``bot/core/middlewares/auth.py`` — auto-creates admin profiles for seed
      admins.
    - ``bot/admin/handler.py`` and ``bot/admin/service.py`` — admin management
      endpoints (ban, unban, promote).
    - ``alembic/env.py`` — registered for Alembic migrations.
    - ``tests/unit/core/test_models.py`` — model unit tests.
"""

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin
from bot.core.models.user import User


class AdminProfile(Base, TimestampMixin):
    """One-to-one profile representing an administrative user.

    Unlike ``StudentProfile`` and ``DriverProfile``, this model imports
    ``User`` directly (rather than deferring via ``TYPE_CHECKING``) because
    ``user.py`` only references ``AdminProfile`` under ``TYPE_CHECKING``,
    so there is no circular-import risk.

    Attributes:
        id (int): Primary key.
        user_id (int): FK to ``users.id`` (one-to-one). ``CASCADE`` ensures
            the profile is removed if the user is deleted.
        added_by_admin_id (int | None): FK to ``users.id`` of the admin
            who promoted this user. ``SET NULL`` is implicit (no explicit
            ``ondelete`` — the DB default applies).

    Relationships:
        user: The ``User`` this admin profile belongs to.
        added_by_admin: The ``User`` who granted admin status, if recorded.

    Calls / Depends on:
        - ``bot.core.db.base_class.Base`` — declarative base.
        - ``bot.core.models.base.TimestampMixin`` — audit timestamps.
        - ``bot.core.models.user.User`` — for the relationship type.

    Called by:
        - ``bot/core/middlewares/auth.py`` — ``_ensure_admin_profile``.
        - ``alembic/env.py`` — table registration.
    """

    __tablename__ = "admin_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    # user_id is unique because each user can hold at most one admin profile.
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    added_by_admin_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)

    user: Mapped[User] = relationship(back_populates="admin_profile", foreign_keys=[user_id])
    added_by_admin: Mapped[User | None] = relationship(foreign_keys=[added_by_admin_id])
