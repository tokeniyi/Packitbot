"""Database session middleware for the Packitbot Telegram bot.

This middleware manages the lifecycle of an async SQLAlchemy
session for each incoming update. It opens a session, injects
it into the handler data, commits on success, rolls back on
exception, and always closes the session in a finally block.

Classes:
    - DbSessionMiddleware: aiogram BaseMiddleware subclass for DB session management.

Function Calls:
    - __call__(handler, event, data) -> Any

Cross-References:
    - Depends on: aiogram BaseMiddleware, bot.core.db.session.async_session,
        bot.core.exceptions.PermissionDeniedError
    - Imported by: bot/main.py
"""

from typing import Any, Callable

from aiogram import types
from aiogram.dispatcher.middlewares.base import BaseMiddleware

from bot.core.db.session import async_session
from bot.core.exceptions import PermissionDeniedError


class DbSessionMiddleware(BaseMiddleware):
    """Middleware that manages an async SQLAlchemy session per update.

    Opens a session before the handler runs, injects it into
    ``data["session"]``, commits the transaction if the handler
    succeeds, rolls back on any exception, and always closes
    the session in the finally block.
    """

    async def __call__(
        self,
        handler: Callable[[types.Update, dict[str, Any]], Any],
        event: types.Update,
        data: dict[str, Any],
    ) -> Any:
        """Open a DB session, invoke the handler, and manage transaction lifecycle.

        Args:
            handler: The next handler in the middleware chain.
            event: The incoming aiogram Update object.
            data: The handler data dict to pass along.

        Returns:
            The result of the downstream handler.

        Raises:
            Exception: Re-raises any exception from the handler after
                rolling back the transaction.
        """
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