"""Authentication middleware for the Packitbot Telegram bot.

This middleware intercepts every incoming update, resolves the
Telegram user to an internal User record (creating one if
necessary), enforces banned-user restrictions, and injects the
user object into the handler data dict for downstream access.

Classes:
    - AuthMiddleware: aiogram BaseMiddleware subclass for user auth.

Function Calls:
    - __call__(handler, event, data) -> Any
    - _get_or_create_user(session, telegram_id) -> User
    - _ensure_admin_profile(session, user_id) -> AdminProfile

Cross-References:
    - Depends on: aiogram BaseMiddleware, sqlalchemy, bot.core.config.Settings,
        bot.core.db.session.async_session, bot.core.models.user.User,
        bot.core.models.admin_profile.AdminProfile, bot.core.keyboards.common_kb.HomeButton,
        bot.core.constants.enums.AccountStatus, bot.core.constants.enums.UserRole
    - Imported by: bot/main.py
"""

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
    """Middleware that authenticates users via Telegram ID and enforces access control.

    On each update, resolves the Telegram user to an internal User
    record, creates the record if it does not exist, blocks banned
    users, promotes seed-admin Telegram IDs to the Admin role, and
    ensures an AdminProfile exists for admin users. The resolved
    user is injected into ``data["user"]`` for downstream handlers.

    Attributes:
        settings: Application settings containing seed admin Telegram IDs.
        home: HomeButton keyboard markup used in user-facing error messages.
    """

    def __init__(self, settings: Settings):
        """Initialize the AuthMiddleware with application settings.

        Args:
            settings: The application Settings object providing
                seed_admin_telegram_ids for admin promotion.
        """
        self.settings = settings
        self.home = HomeButton()

    async def _get_or_create_user(self, session, telegram_id: int):
        """Fetch an existing User by telegram_id or create a new one.

        Args:
            session: The active async SQLAlchemy session.
            telegram_id: The Telegram user identifier.

        Returns:
            The User record, either existing or newly created.
        """
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
        """Ensure an AdminProfile record exists for the given user.

        Creates a new AdminProfile if one does not already exist.

        Args:
            session: The active async SQLAlchemy session.
            user_id: The internal user ID.

        Returns:
            The AdminProfile record.
        """
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
        """Process the incoming update, resolve the user, and enforce access rules.

        Extracts the Telegram user ID from the update, resolves or
        creates the internal User record, blocks banned users, promotes
        seed-admin IDs, and injects the user into handler data.

        Args:
            handler: The next handler in the middleware chain.
            event: The incoming aiogram Update object.
            data: The handler data dict to pass along.

        Returns:
            The result of the downstream handler, or None if the
            update was short-circuited (e.g., banned user).

        Raises:
            RuntimeError: If no database session is present in data.
        """
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