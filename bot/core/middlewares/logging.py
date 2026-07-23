import logging
from aiogram import BaseMiddleware
from aiogram.types import Update

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        user_id = None
        update_type = None
        timestamp = None

        if event.message:
            user_id = event.message.from_user.id if event.message.from_user else None
            update_type = "message"
            timestamp = event.message.date
        elif event.callback_query:
            user_id = event.callback_query.from_user.id if event.callback_query.from_user else None
            update_type = "callback_query"
            timestamp = event.callback_query.message.date if event.callback_query.message else None

        logger.info(
            "Inbound update received",
            extra={"user_id": user_id, "update_type": update_type, "timestamp": timestamp},
        )
        return await handler(event, data)
