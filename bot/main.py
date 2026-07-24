import asyncio
import logging
import sys

from aiogram.client.bot import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault

# 1. Register all SQLAlchemy models before running any DB queries
import bot.core.models  # noqa: F401

from bot.common.fallback import fallback_router
from bot.common.help import help_router
from bot.common.start import start_router
from bot.core.config import get_settings
from bot.core.loader import get_bot, get_dispatch
from bot.core.middlewares.auth import AuthMiddleware
from bot.core.middlewares.db_session import DbSessionMiddleware
from bot.core.middlewares.logging import LoggingMiddleware, logger
from bot.core.middlewares.throttling import ThrottlingMiddleware


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
                    # FIXED: Added full_name="System Admin" to satisfy NOT NULL constraint
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
    dp.include_router(start_router)
    dp.include_router(help_router)
    dp.include_router(fallback_router)


async def set_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="help", description="Get help"),
        BotCommand(command="about", description="About Packitbot"),
        BotCommand(command="cancel", description="Cancel current action"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def _run_polling(dp, bot: Bot) -> None:
    await set_bot_commands(bot)  # FIXED: Registered bot commands on Telegram
    await _seed_admins()
    await dp.start_polling(bot)


async def _run_webhook(dp, bot: Bot) -> None:
    await set_bot_commands(bot)
    await _seed_admins()
    raise NotImplementedError("Webhook mode is not implemented yet.")


def main() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)

    dp = get_dispatch()
    bot = get_bot()

    setup_routers(dp)

    # FIXED: Middleware Order (Inflow order: Logging -> DbSession -> Throttling -> Auth)
    dp.update.outer_middleware(LoggingMiddleware())
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(ThrottlingMiddleware(settings))
    dp.update.outer_middleware(AuthMiddleware(settings))

    if settings.webhook_url:
        asyncio.run(_run_webhook(dp, bot))
    else:
        asyncio.run(_run_polling(dp, bot))


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")