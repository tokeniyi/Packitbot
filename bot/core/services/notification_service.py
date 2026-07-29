# bot/core/services/notification_service.py
import logging
from typing import Optional
from aiogram import Bot
from bot.core.constants.messages import (
    MSG_NOTIFY_DRIVER_APPROVED,
    MSG_NOTIFY_DRIVER_REJECTED,
)

logger = logging.getLogger(__name__)


async def notify_driver_approval_status(
    bot: Bot,
    telegram_id: int,
    approved: bool,
    reason: Optional[str] = None,
) -> bool:
    """Sends immediate notification to driver on approval or rejection."""
    if approved:
        text = MSG_NOTIFY_DRIVER_APPROVED
    else:
        text = MSG_NOTIFY_DRIVER_REJECTED
        if reason:
            text += f"\n\n**Reason:** {reason}"

    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="Markdown")
        return True
    except Exception as e:
        logger.error(f"Failed to send driver notification to {telegram_id}: {e}")
        return False


async def send_broadcast_message(
    bot: Bot,
    telegram_id: int,
    text: str,
) -> bool:
    """Sends a broadcast notification message to a user."""
    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="Markdown")
        return True
    except Exception as e:
        logger.error(f"Failed to send broadcast message to {telegram_id}: {e}")
        return False

