# bot/driver/repository.py
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models.driver_profile import DriverProfile
from bot.core.models.user import User
from bot.core.repositories.base_repository import BaseRepository


class DriverRepository(BaseRepository[DriverProfile]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, DriverProfile)

    async def get_by_user_id(self, user_id: int) -> Optional[DriverProfile]:
        stmt = select(DriverProfile).where(DriverProfile.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_plate_number(self, plate_number: str) -> Optional[DriverProfile]:
        stmt = select(DriverProfile).where(DriverProfile.plate_number == plate_number)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_license_number(self, license_number: str) -> Optional[DriverProfile]:
        stmt = select(DriverProfile).where(DriverProfile.license_number == license_number)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
