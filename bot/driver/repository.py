"""Repository layer for driver profile persistence.

This module provides the :class:`DriverRepository`, a thin async repository
wrapping SQLAlchemy queries against the ``DriverProfile`` model. It extends
the generic :class:`BaseRepository` with driver-specific lookups used by
the service layer to detect duplicate plate or license numbers, and to
fetch a driver's profile by associated user ID.

Classes
-------
- ``DriverRepository`` -> CRUD + lookup helpers for ``DriverProfile``.

Depends on
----------
SQLAlchemy async session, ``bot.core.models.driver_profile``, ``bot.core.models.user``,
``bot.core.repositories.base_repository``.

Called by
---------
``bot/driver/service.py`` -> ``register_driver`` (via ``get_by_plate_number`` / ``get_by_license_number`` uniqueness checks).
"""

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models.driver_profile import DriverProfile
from bot.core.models.user import User
from bot.core.repositories.base_repository import BaseRepository


class DriverRepository(BaseRepository[DriverProfile]):
    """Async repository for querying and persisting :class:`DriverProfile` records.

    Extends :class:`~bot.core.repositories.base_repository.BaseRepository` with
    driver-specific lookup methods. The base class supplies generic CRUD
    operations (``get_by_id``, ``add``, ``update``, ``delete``); this subclass
    adds the uniqueness lookups required during driver registration.

    Args:
        session: The SQLAlchemy ``AsyncSession`` used to execute queries.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, DriverProfile)

    async def get_by_user_id(self, user_id: int) -> Optional[DriverProfile]:
        """Retrieve the driver profile associated with a given user ID.

        Args:
            user_id: The primary key of the ``User`` record (not the Telegram ID).

        Returns:
            The matching :class:`DriverProfile`, or ``None`` if no profile exists.

        Calls / Depends on:
            ``self.session`` (inherited from ``BaseRepository``).
        """
        stmt = select(DriverProfile).where(DriverProfile.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_plate_number(self, plate_number: str) -> Optional[DriverProfile]:
        """Retrieve a driver profile by vehicle plate number.

        Used to detect duplicate plate numbers during registration.

        Args:
            plate_number: The vehicle registration plate number to search for.

        Returns:
            The matching :class:`DriverProfile`, or ``None`` if none exists.

        Called by:
            ``bot/driver/service.py`` -> ``register_driver`` (uniqueness check).
        """
        stmt = select(DriverProfile).where(DriverProfile.plate_number == plate_number)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_license_number(self, license_number: str) -> Optional[DriverProfile]:
        """Retrieve a driver profile by driver's license number.

        Used to detect duplicate license numbers during registration.

        Args:
            license_number: The driver's license number to search for.

        Returns:
            The matching :class:`DriverProfile`, or ``None`` if none exists.

        Called by:
            ``bot/driver/service.py`` -> ``register_driver`` (uniqueness check).
        """
        stmt = select(DriverProfile).where(DriverProfile.license_number == license_number)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
