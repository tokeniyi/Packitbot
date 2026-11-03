"""Callback message guard middleware.

Telegram delivers a ``CallbackQuery`` whose ``message`` is either a regular
:class:`~aiogram.types.Message`, an :class:`~aiogram.types.InaccessibleMessage`
(the originating message is older than 48 hours or was deleted), or ``None``
(inline-mode callbacks). Only a real ``Message`` supports ``edit_text`` and
``delete``; ``InaccessibleMessage`` is truthy but has no ``edit_text``, so a
plain ``if callback.message:`` check does not protect a handler.

This middleware runs on the callback-query observer, after the update-level
middlewares (logging, DB session, throttling, auth, RBAC). When the message is
not a ``Message``, it answers the callback with an alert and stops the chain,
so no handler is invoked with an unusable message.

Classes:
    - CallbackMessageGuardMiddleware: aiogram BaseMiddleware for callback queries.

Cross-References:
    - Depends on: aiogram BaseMiddleware, aiogram.types.Message, CallbackQuery
    - Registered in: bot/main.py (``dp.callback_query.outer_middleware``)
    - Message text: bot/core/constants/messages.py (ErrorMessages.MESSAGE_EXPIRED)
"""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.core.constants.messages import ErrorMessages

logger = logging.getLogger(__name__)


class CallbackMessageGuardMiddleware(BaseMiddleware):
    """Block callback queries whose message cannot be edited or replied to."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Forward usable callbacks; answer and drop the rest.

        Args:
            handler: The next handler in the chain.
            event: The incoming event (a ``CallbackQuery`` for this observer).
            data: Handler keyword data.

        Returns:
            The handler's return value, or ``None`` when the callback was blocked.
        """
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)

        if isinstance(event.message, Message):
            return await handler(event, data)

        logger.info(
            "Blocked callback with unusable message (user=%s, data=%s, type=%s)",
            event.from_user.id if event.from_user else None,
            event.data,
            type(event.message).__name__,
        )
        await event.answer(ErrorMessages.MESSAGE_EXPIRED, show_alert=True)
        return None
