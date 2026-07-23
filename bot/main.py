import asyncio
import logging
import sys

from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from bot.core.config import get_settings
from bot.core.loader import get_dispatch, get_storage
from bot.core.middlewares.logging import LoggingMiddleware

logging.basicConfig(
    level="INFO",
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def _run_polling(dp: Dispatcher, storage: RedisStorage) -> None:
    await dp.start_polling(storage=storage)


async def _run_webhook(dp: Dispatcher, storage: RedisStorage) -> None:
    raise NotImplementedError("Webhook mode is not implemented yet.")


def main() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)

    dp = get_dispatch()
    storage = get_storage()

    dp.update.outer_middleware(LoggingMiddleware())

    if settings.webhook_url:
        asyncio.run(_run_webhook(dp, storage))
    else:
        asyncio.run(_run_polling(dp, storage))


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
