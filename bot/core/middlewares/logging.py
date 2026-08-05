import logging
import re
from aiogram import BaseMiddleware
from aiogram.types import Update

logger = logging.getLogger(__name__)

PHONE_PII_REGEX = re.compile(r"(?:\+?234|0)[7-9]\d{9}")
MATRIC_PII_REGEX = re.compile(r"\b\d{2}/?[A-Za-z0-9]{4,6}\b", re.IGNORECASE)


def sanitize_pii(text: str | None) -> str | None:
    if not text:
        return text
    sanitized = PHONE_PII_REGEX.sub("[PHONE MASKED]", text)
    sanitized = MATRIC_PII_REGEX.sub("[MATRIC MASKED]", sanitized)
    return sanitized


class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        user_id = None
        update_type = None
        timestamp = None
        content = None

        if event.message:
            user_id = event.message.from_user.id if event.message.from_user else None
            update_type = "message"
            timestamp = event.message.date
            content = event.message.text
        elif event.callback_query:
            user_id = event.callback_query.from_user.id if event.callback_query.from_user else None
            update_type = "callback_query"
            timestamp = event.callback_query.message.date if event.callback_query.message else None
            content = event.callback_query.data

        sanitized_content = sanitize_pii(content)

        logger.info(
            "Inbound update received",
            extra={
                "user_id": user_id,
                "update_type": update_type,
                "timestamp": timestamp,
                "content": sanitized_content,
            },
        )
        return await handler(event, data)

