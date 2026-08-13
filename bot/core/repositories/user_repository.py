from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models.user import User
from bot.core.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    """Async repository for querying and persisting User records."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Retrieve a user by their Telegram ID.

        Args:
            telegram_id: The Telegram user identifier.

        Returns:
            The matching User, or None if no user exists.
        """
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
