import asyncio
import logging
import sys

from aiogram.client.bot import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

# 1. Register all SQLAlchemy models before running any DB queries
import bot.core.models  # noqa: F401
from bot.admin.handler import admin_router
from bot.common.fallback import fallback_router
from bot.common.help import help_router
from bot.common.start import start_router
from bot.core.config import get_settings
from bot.core.constants.commands import *
from bot.core.loader import get_bot, get_dispatch
from bot.core.middlewares.auth import AuthMiddleware
from bot.core.middlewares.db_session import DbSessionMiddleware
from bot.core.middlewares.logging import LoggingMiddleware, logger
from bot.core.middlewares.throttling import ThrottlingMiddleware
from bot.student.handler import student_router


def get_admin_chats_from_settings() -> list[int]:
    """Reads admin telegram IDs directly from settings as a fallback/helper."""
    settings = get_settings()
    if not settings.seed_admin_telegram_ids:
        return []

    raw_ids = str(settings.seed_admin_telegram_ids).split(",")
    return [int(uid.strip()) for uid in raw_ids if uid.strip().isdigit()]


async def _seed_admins() -> None:
    from sqlalchemy import select

    settings = get_settings()
    if not settings.seed_admin_telegram_ids:
        return

    from bot.core.constants.enums import AccountStatus, UserRole
    from bot.core.db.session import async_session as make_session
    from bot.core.models.admin_profile import AdminProfile
    from bot.core.models.user import User

    async with make_session() as session:
        try:
            for telegram_id in str(settings.seed_admin_telegram_ids).split(","):
                telegram_id = telegram_id.strip()
                if not telegram_id:
                    continue

                result = await session.execute(
                    select(User).where(User.telegram_id == int(telegram_id))
                )
                user = result.scalar_one_or_none()

                if user is None:
                    user = User(
                        telegram_id=int(telegram_id),
                        full_name="System Admin",
                        role=UserRole.ADMIN,
                        account_status=AccountStatus.ACTIVE,
                    )
                    session.add(user)
                    await session.flush()
                    logger.info(f"Seeded admin user telegram_id={telegram_id}")

                if user.role != UserRole.ADMIN:
                    user.role = UserRole.ADMIN
                    logger.info(f"Promoted user id={user.id} to admin")

                result = await session.execute(
                    select(AdminProfile).where(AdminProfile.user_id == user.id)
                )
                admin = result.scalar_one_or_none()
                if admin is None:
                    admin = AdminProfile(user_id=user.id)
                    session.add(admin)
                    logger.info(f"Created AdminProfile for user_id={user.id}")

            await session.commit()
        except Exception:
            await session.rollback()
            raise


def setup_routers(dp) -> None:
    """FIXED: Feature routers FIRST, Catch-all (fallback_router) LAST."""
    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(help_router)
    dp.include_router(student_router)

    # ALWAYS KEEP FALLBACK ROUTER LAST!
    dp.include_router(fallback_router)


async def set_bot_commands(bot: Bot) -> None:
    # Default global commands
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="help", description="Get help"),
        BotCommand(command="cancel", description="Cancel current action"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

    # Admin-specific commands
    admin_commands = ADMIN_COMMANDS

    admin_chats = get_admin_chats_from_settings()
    for chat_id in admin_chats:
        try:
            await bot.set_my_commands(
                admin_commands, scope=BotCommandScopeChat(chat_id=chat_id)
            )
        except Exception as e:
            logger.warning(f"Failed to set admin commands for chat_id={chat_id}: {e}")


async def _run_polling(dp, bot: Bot) -> None:
    await _seed_admins()        # 1. Seed admins first
    await set_bot_commands(bot) # 2. Set bot commands after admins exist
    await dp.start_polling(bot)


async def _run_webhook(dp, bot: Bot) -> None:
    await _seed_admins()        # 1. Seed admins first
    await set_bot_commands(bot) # 2. Set bot commands after admins exist
    raise NotImplementedError("Webhook mode is not implemented yet.")


def main() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)

    dp = get_dispatch()
    bot = get_bot()

    setup_routers(dp)

    # Middleware Order (Inflow order: Logging -> DbSession -> Throttling -> Auth)
    dp.update.outer_middleware(LoggingMiddleware())
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(ThrottlingMiddleware(settings))
    dp.update.outer_middleware(AuthMiddleware(settings))

    try:
        if settings.webhook_url:
            asyncio.run(_run_webhook(dp, bot))
        else:
            asyncio.run(_run_polling(dp, bot))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped cleanly.")


if __name__ == "__main__":
    main()