from typing import Any, Callable

from aiogram import types
from aiogram.dispatcher.middlewares.base import BaseMiddleware

from bot.core.db.session import async_session
from bot.core.exceptions import PermissionDeniedError


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.Update, dict[str, Any]], Any],
        event: types.Update,
        data: dict[str, Any],
    ) -> Any:
        session = None
        try:
            session = async_session()
            data["session"] = session

            result = await handler(event, data)

            if session.in_transaction():
                await session.commit()
            return result
        except Exception:
            if session:
                await session.rollback()
            raise
        finally:
            if session:
                await session.close()