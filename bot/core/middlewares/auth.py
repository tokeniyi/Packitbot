import logging
from typing import Any, Callable

from aiogram import types
from aiogram.dispatcher.middlewares.base import BaseMiddleware

from sqlalchemy import select

from bot.core.config import Settings
from bot.core.db.session import async_session
from bot.core.keyboards.common_kb import HomeButton
from bot.core.constants.enums import AccountStatus, UserRole

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.home = HomeButton()

    async def _get_or_create_user(self, session, telegram_id: int):
        from bot.core.models.user import User

        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(telegram_id=telegram_id)
            session.add(user)
            await session.flush()
            logger.info(f"Created new user with telegram_id={telegram_id}")

        return user

    async def _ensure_admin_profile(self, session, user_id: int):
        from bot.core.models.admin_profile import AdminProfile

        stmt = select(AdminProfile).where(AdminProfile.user_id == user_id)
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        if admin is None:
            admin = AdminProfile(user_id=user_id)
            session.add(admin)
            logger.info(f"Created admin profile for user_id={user_id}")

        return admin

    async def __call__(
        self,
        handler: Callable[[types.Update, dict[str, Any]], Any],
        event: types.Update,
        data: dict[str, Any],
    ) -> Any:
        session = data.get("session")
        if session is None:
            raise RuntimeError("Database session not provided to AuthMiddleware")

        user_telegram_id = None
        if event.message:
            user_telegram_id = event.message.from_user.id
        elif event.callback_query:
            user_telegram_id = event.callback_query.from_user.id
        elif event.inline_query:
            user_telegram_id = event.inline_query.from_user.id
        elif event.poll_answer:
            user_telegram_id = event.poll_answer.user.id
        elif event.my_chat_member:
            user_telegram_id = event.my_chat_member.from_user.id
        elif event.chat_member:
            user_telegram_id = event.chat_member.from_user.id
        elif event.chosen_inline_result:
            user_telegram_id = event.chosen_inline_result.from_user.id
        elif event.shipping_query:
            user_telegram_id = event.shipping_query.from_user.id
        elif event.pre_checkout_query:
            user_telegram_id = event.pre_checkout_query.from_user.id

        if user_telegram_id is None:
            return await handler(event, data)

        user = await self._get_or_create_user(session, user_telegram_id)

        if user.account_status == AccountStatus.BANNED:
            logger.warning(f"Banned user {user.id} attempted to use bot")
            msg = "You are banned from using this bot. Contact an admin for help."
            if event.message:
                await event.message.answer(msg, reply_markup=self.home)
            elif event.callback_query:
                await event.callback_query.answer(msg, show_alert=True)
            return

        data["user"] = user

        if user_telegram_id in str(self.settings.seed_admin_telegram_ids).split(","):
            if user.role != UserRole.ADMIN:
                user.role = UserRole.ADMIN
                logger.info(f"Promoted user {user.id} to admin via seed")
            await self._ensure_admin_profile(session, user.id)

        return await handler(event, data)