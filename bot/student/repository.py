# bot/student/repository.py
# ---------------------------------------------------------------------------
# Code Logic:
#   This module provides the StudentRepository class for querying student profile
#   data. It extends BaseRepository with a StudentProfile-specific query method
#   for fetching a student profile by its associated user_id.
#
# Function Calls:
#   - get_by_user_id(user_id) -> returns StudentProfile or None for a given user
#   - (commented out) get_by_matric(matric_number) -> would return StudentProfile or None
#
# Cross-References:
#   - Depends on: sqlalchemy select, sqlalchemy.ext.asyncio.AsyncSession,
#       bot.core.db.base_class.Base, bot.core.models.student_profile.StudentProfile,
#       bot.core.models.user.User, bot.core.repositories.base_repository.BaseRepository
#   - Imported by: bot/student/service.py, bot/student/handler.py
# ---------------------------------------------------------------------------

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.db.base_class import Base
from bot.core.models.student_profile import StudentProfile
from bot.core.models.user import User
from bot.core.repositories.base_repository import BaseRepository


class StudentRepository(BaseRepository):
    """Repository class for StudentProfile database operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with an async database session and StudentProfile model."""
        super().__init__(session, StudentProfile)

    async def get_by_user_id(self, user_id: int) -> Optional[StudentProfile]:
        """Fetch a StudentProfile record by the associated user_id.

        Args:
            user_id: The primary key of the related User record.

        Returns:
            The matching StudentProfile if found, otherwise None.
        """
        stmt = select(StudentProfile).where(StudentProfile.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # async def get_by_matric(self, matric_number: str) -> Optional[StudentProfile]:
    #     """Fetch a StudentProfile record by matriculation number (currently commented out)."""
    #     stmt = select(StudentProfile).where(
    #         StudentProfile.matric_number == matric_number
    #     )
    #     result = await self.session.execute(stmt)
    #     return result.scalar_one_or_none()
