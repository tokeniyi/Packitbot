"""Logging middleware for the Packitbot Telegram bot.

This middleware logs every inbound update with sanitized
content (PII such as phone numbers and matric numbers are
masked) before passing the update to the next handler.

Classes:
    - LoggingMiddleware: aiogram BaseMiddleware subclass for update logging.

Function Calls:
    - sanitize_pii(text) -> str | None
    - __call__(handler, event, data) -> Any

Cross-References:
    - Depends on: aiogram BaseMiddleware, aiogram.types.Update, re
    - Imported by: bot/main.py
"""

import logging
import re
from aiogram import BaseMiddleware
from aiogram.types import Update

logger = logging.getLogger(__name__)

PHONE_PII_REGEX = re.compile(r"(?:\+?234|0)[7-9]\d{9}")
MATRIC_PII_REGEX = re.compile(r"\b\d{2}/?[A-Za-z0-9]{4,6}\b", re.IGNORECASE)


def sanitize_pii(text: str | None) -> str | None:
    """Mask phone numbers and matric numbers in text to prevent PII leakage in logs.

    Replaces Nigerian phone numbers and matriculation numbers
    with placeholder tokens before logging.

    Args:
        text: The raw text to sanitize, or None.

    Returns:
        The sanitized text with PII masked, or None if input was None.
    """
    if not text:
        return text
    sanitized = PHONE_PII_REGEX.sub("[PHONE MASKED]", text)
    sanitized = MATRIC_PII_REGEX.sub("[MATRIC MASKED]", sanitized)
    return sanitized


class LoggingMiddleware(BaseMiddleware):
    """Middleware that logs inbound updates with PII sanitization.

    Extracts user ID, update type, timestamp, and content from
    each incoming update, sanitizes PII from the content, and
    logs the information before forwarding to the next handler.
    """

    async def __call__(self, handler, event: Update, data: dict):
        """Log the inbound update and forward it to the next handler.

        Args:
            handler: The next handler in the middleware chain.
            event: The incoming aiogram Update object.
            data: The handler data dict to pass along.

        Returns:
            The result of the downstream handler.
        """
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

