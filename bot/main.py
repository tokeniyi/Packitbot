import asyncio
import logging
import sys

from aiogram import Dispatcher

from bot.core.config import get_settings
from bot.core.loader import get_bot, get_dispatch
from bot.core.middlewares.logging import LoggingMiddleware

logging.basicConfig(
    level="INFO",
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def _run_polling(dp: Dispatcher, bot) -> None:
    await dp.start_polling(bot)


async def _run_webhook(dp: Dispatcher, bot) -> None:
    raise NotImplementedError("Webhook mode is not implemented yet.")


def main() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)

    dp = get_dispatch()
    bot = get_bot()

    dp.update.outer_middleware(LoggingMiddleware())

    if settings.webhook_url:
        asyncio.run(_run_webhook(dp, bot))
    else:
        asyncio.run(_run_polling(dp, bot))


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
