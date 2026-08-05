import asyncio
import logging

from aiogram.client.bot import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, ErrorEvent
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

# 1. Register all SQLAlchemy models before running any DB queries
import bot.core.models  # noqa: F401
from bot.admin.handler import admin_router
from bot.common.fallback import fallback_router
from bot.common.help import help_router
from bot.common.start import start_router
from bot.core.config import get_settings
from bot.core.constants.commands import (
    ADMIN_COMMANDS,
    DEFAULT_COMMANDS,
    DRIVER_COMMANDS,
    STUDENT_COMMANDS,
)
from bot.core.constants.enums import AccountStatus, UserRole
from bot.core.constants.messages import MSG_SOMETHING_WENT_WRONG
from bot.core.db.base_class import Base
from bot.core.db.session import async_session as make_session
from bot.core.db.session import engine
from bot.core.exceptions import PackitbotError
from bot.core.keyboards.common_kb import HomeButton
from bot.core.loader import get_bot, get_dispatch
from bot.core.middlewares.auth import AuthMiddleware
from bot.core.middlewares.db_session import DbSessionMiddleware
from bot.core.middlewares.logging import LoggingMiddleware, logger
from bot.core.middlewares.throttling import ThrottlingMiddleware
from bot.core.models.admin_profile import AdminProfile
from bot.core.models.user import User
from bot.student.handler import student_router


async def _init_db() -> None:
    """Ensures database tables are created before operations run."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_admin_chats_from_settings() -> list[int]:
    """Reads admin telegram IDs directly from settings as a fallback/helper."""
    settings = get_settings()
    if not settings.seed_admin_telegram_ids:
        return []

    raw_ids = str(settings.seed_admin_telegram_ids).split(",")
    return [int(uid.strip()) for uid in raw_ids if uid.strip().isdigit()]


async def get_user_chats_by_role(role: UserRole) -> list[int]:
    """Fetches Telegram IDs for active users with a given role."""
    async with make_session() as session:
        stmt = select(User.telegram_id).where(User.role == role)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def _seed_admins() -> None:
    settings = get_settings()
    if not settings.seed_admin_telegram_ids:
        return

    async with make_session() as session:
        try:
            for telegram_id in str(settings.seed_admin_telegram_ids).split(","):
                telegram_id = telegram_id.strip()
                if not telegram_id or not telegram_id.isdigit():
                    continue

                tg_id = int(telegram_id)
                result = await session.execute(
                    select(User).where(User.telegram_id == tg_id)
                )
                user = result.scalar_one_or_none()

                if user is None:
                    user = User(
                        telegram_id=tg_id,
                        full_name="System Admin",
                        role=UserRole.ADMIN,
                        account_status=AccountStatus.ACTIVE,
                    )
                    session.add(user)
                    await session.flush()
                    logger.info(f"Seeded admin user telegram_id={tg_id}")

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
    """Feature routers FIRST, Catch-all (fallback_router) LAST."""
    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(help_router)
    dp.include_router(student_router)

    # ALWAYS KEEP FALLBACK ROUTER LAST!
    dp.include_router(fallback_router)


def setup_error_handlers(dp) -> None:
    """Global exception handler for Packitbot domain errors, IntegrityError, and stale callback queries."""

    @dp.errors()
    async def global_error_handler(event: ErrorEvent) -> bool:
        exception = event.exception
        update = event.update

        message = update.message if update else None
        callback_query = update.callback_query if update else None

        if isinstance(exception, PackitbotError):
            logger.warning("Domain exception caught by global handler: %s", exception)
            user_msg = str(exception) or MSG_SOMETHING_WENT_WRONG
            markup = HomeButton()
            if callback_query:
                try:
                    await callback_query.answer(user_msg, show_alert=True)
                except TelegramBadRequest as exc:
                    logger.info("Stale callback query in PackitbotError handler: %s", exc)
                if callback_query.message:
                    try:
                        await callback_query.message.answer(user_msg, reply_markup=markup)
                    except TelegramBadRequest:
                        pass
            elif message:
                try:
                    await message.answer(user_msg, reply_markup=markup)
                except TelegramBadRequest:
                    pass
            return True

        if isinstance(exception, IntegrityError):
            logger.error("Database IntegrityError caught by global handler: %s", exception, exc_info=True)
            user_msg = "A database error occurred or resource already exists. Please try again."
            markup = HomeButton()
            if callback_query:
                try:
                    await callback_query.answer(user_msg, show_alert=True)
                except TelegramBadRequest:
                    pass
                if callback_query.message:
                    try:
                        await callback_query.message.answer(user_msg, reply_markup=markup)
                    except TelegramBadRequest:
                        pass
            elif message:
                try:
                    await message.answer(user_msg, reply_markup=markup)
                except TelegramBadRequest:
                    pass
            return True

        if isinstance(exception, TelegramBadRequest):
            err_msg = str(exception).lower()
            if (
                "query is too old" in err_msg
                or "query id is invalid" in err_msg
                or "message is not modified" in err_msg
                or "message to edit not found" in err_msg
            ):
                logger.warning("Handled stale or invalid TelegramBadRequest smoothly: %s", exception)
                if callback_query:
                    try:
                        await callback_query.answer("This request or button has expired.", show_alert=True)
                    except Exception:
                        pass
                return True
            logger.error("Unhandled TelegramBadRequest caught by global handler: %s", exception, exc_info=True)
            return True

        logger.error("Unhandled exception caught by global handler: %s", exception, exc_info=True)
        markup = HomeButton()
        if callback_query:
            try:
                await callback_query.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)
            except Exception:
                pass
            if callback_query.message:
                try:
                    await callback_query.message.answer(MSG_SOMETHING_WENT_WRONG, reply_markup=markup)
                except Exception:
                    pass
        elif message:
            try:
                await message.answer(MSG_SOMETHING_WENT_WRONG, reply_markup=markup)
            except Exception:
                pass
        return True


async def set_bot_commands(bot: Bot) -> None:
    """Sets role-tailored command menus across Telegram."""
    # 1. Global default fallback menu for guests/unregistered users
    await bot.set_my_commands(DEFAULT_COMMANDS, scope=BotCommandScopeDefault())

    async def _apply_menu_for_chats(
        chat_ids: list[int], commands: list[BotCommand], role_label: str
    ) -> None:
        for chat_id in chat_ids:
            try:
                await bot.set_my_commands(
                    commands, scope=BotCommandScopeChat(chat_id=chat_id)
                )
                if bot.set_my_commands():
                    print(f"Successfully set {role_label} commands for chat_id={chat_id}")
                else:
                    print(f"Failed to set {role_label} commands for chat_id={chat_id}")
            except Exception as e:
                logger.warning(
                    f"Failed to set {role_label} commands for chat_id={chat_id}: {e}"
                )

    # 2. Student Specific Commands
    student_chats = await get_user_chats_by_role(UserRole.STUDENT)
    await _apply_menu_for_chats(student_chats, STUDENT_COMMANDS, "student")

    # 3. Driver Specific Commands
    driver_chats = await get_user_chats_by_role(UserRole.DRIVER)
    await _apply_menu_for_chats(driver_chats, DRIVER_COMMANDS, "driver")

    # 4. Admin Specific Commands
    db_admin_chats = await get_user_chats_by_role(UserRole.ADMIN)
    env_admin_chats = get_admin_chats_from_settings()
    all_admin_chats = list(set(db_admin_chats + env_admin_chats))
    await _apply_menu_for_chats(all_admin_chats, ADMIN_COMMANDS, "admin")


async def _run_polling(dp, bot: Bot) -> None:
    await _init_db()
    await _seed_admins()
    await set_bot_commands(bot)
    await dp.start_polling(bot)


async def _run_webhook(dp, bot: Bot) -> None:
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    from aiohttp import web

    settings = get_settings()
    await _init_db()
    await _seed_admins()
    await set_bot_commands(bot)

    await bot.set_webhook(
        url=f"{settings.webhook_url}",
        secret_token=settings.webhook_secret,
        drop_pending_updates=True,
    )

    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.webhook_secret,
    )
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    # Clean lifecycle handling
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=settings.port)
    await site.start()

    logger.info(f"Webhook server running on port {settings.port}")
    
    # Wait until interrupted by Ctrl+C / SystemExit
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()



    
def main() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)

    dp = get_dispatch()
    bot = get_bot()

    setup_routers(dp)
    setup_error_handlers(dp)

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