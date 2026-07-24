from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.db.base_class import Base
from bot.core.models.student_profile import StudentProfile
from bot.core.models.user import User
from bot.core.repositories.base_repository import BaseRepository


class StudentRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StudentProfile)

    async def get_by_user_id(self, user_id: int) -> Optional[StudentProfile]:
        stmt = select(StudentProfile).where(StudentProfile.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_matric(self, matric_number: str) -> Optional[StudentProfile]:
        stmt = select(StudentProfile).where(
            StudentProfile.matric_number == matric_number
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()