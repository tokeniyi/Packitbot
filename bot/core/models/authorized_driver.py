"""
AuthorizedDriver ORM model for the Packit bot.

Stores the list of Telegram user IDs that are pre-approved to register as
drivers.  When an admin uses ``/add_driver <telegram_id>`` the user's
Telegram ID is added to this table.  The RBAC middleware and the driver
registration handler consult this table to decide whether the
``/register_driver`` command (and the registration FSM that follows) may
proceed.

Used by:
    - ``bot/core/middlewares/rbac.py`` — checks whether a DRIVER-role user may
      access ``/register_driver`` before their profile is complete.
    - ``bot/driver/service.py`` — ``is_authorized_driver`` query helper.
    - ``bot/driver/handler.py`` — gate-checks registration before starting the FSM.
    - ``bot/admin/service.py`` — ``add_authorized_driver`` inserts rows and
      logs the action.
    - ``alembic/env.py`` — registered for Alembic migrations.
    - ``tests/unit/core/test_models.py`` — model unit tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin

if TYPE_CHECKING:
    from bot.core.models.user import User


class AuthorizedDriver(Base, TimestampMixin):
    """Pre-approved driver Telegram IDs allowed to register as drivers.

    Each row represents a Telegram user ID that an admin has explicitly
    authorized to begin the driver registration flow.  This is an
    invitation-only gate — without a row in this table a user with the
    ``DRIVER`` role (or anyone attempting to register as a driver) is
    redirected to contact an admin.

    Attributes:
        id (int): Primary key.
        telegram_id (int): Unique Telegram user identifier (BigInteger to
            match the Telegram user-ID range).  Indexed for fast lookups.
        added_by_admin_id (int | None): FK to ``users.id`` of the admin
            who added this entry.  ``SET NULL`` preserves the row if the
            admin user is later deleted.

    Relationships:
        added_by_admin: The ``User`` (admin) who authorized the driver,
            if the admin still exists.

    Calls / Depends on:
        - ``bot.core.db.base_class.Base`` — declarative base.
        - ``bot.core.models.base.TimestampMixin`` — audit timestamps.

    Called by:
        - ``bot/driver/service.py`` — ``is_authorized_driver``.
        - ``bot/admin/service.py`` — ``add_authorized_driver``.
        - ``alembic/env.py`` — table registration.
    """

    __tablename__ = "authorized_drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    added_by_admin_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    added_by_admin: Mapped["User | None"] = relationship(
        "User", foreign_keys=[added_by_admin_id], uselist=False
    )
