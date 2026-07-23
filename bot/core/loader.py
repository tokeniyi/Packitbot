from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from bot.core.config import Settings

_bot: Bot | None = None
_dispatch: Dispatcher | None = None
_storage: RedisStorage | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        settings = Settings()
        _bot = Bot(token=settings.bot_token)
    return _bot


def get_dispatch() -> Dispatcher:
    global _dispatch
    if _dispatch is None:
        _dispatch = Dispatcher()
    return _dispatch


def get_storage() -> RedisStorage:
    global _storage
    if _storage is None:
        settings = Settings()
        _storage = RedisStorage.from_url(settings.redis_url)
    return _storage
