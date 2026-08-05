# bot/core/services/notification_service.py
# ---------------------------------------------------------------------------
# Code Logic:
#   This module provides two async functions for sending Telegram notifications
#   via the aiogram Bot instance:
#     1. notify_driver_approval_status() - sends a driver their approval or
#        rejection result, including an optional reason for rejection.
#     2. send_broadcast_message() - sends an arbitrary broadcast message to a
#        specific user by telegram_id.
#   Both functions return a boolean: True if the message was sent successfully,
#   False if an exception was caught and logged.
#
# Function Calls:
#   - notify_driver_approval_status() is called by bot/admin/handler.py
#     (handle_approve_driver, handle_reject_driver).
#   - send_broadcast_message() is called by bot/admin/handler.py (execute_broadcast).
#
# Cross-References:
#   - Depends on: aiogram.Bot, bot.core.constants.messages
#       (MSG_NOTIFY_DRIVER_APPROVED, MSG_NOTIFY_DRIVER_REJECTED), logging
#   - Imported by: bot/admin/handler.py
# ---------------------------------------------------------------------------

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
    """Sends immediate notification to driver on approval or rejection.

    Function Calls:
        - Called by bot/admin/handler.py (handle_approve_driver, handle_reject_driver).

    Cross-References:
        - Depends on: aiogram.Bot, bot.core.constants.messages
            (MSG_NOTIFY_DRIVER_APPROVED, MSG_NOTIFY_DRIVER_REJECTED), logging
        - Imported by: bot/admin/handler.py
    """
    # Select the appropriate message template based on approval status.
    if approved:
        text = MSG_NOTIFY_DRIVER_APPROVED
    else:
        text = MSG_NOTIFY_DRIVER_REJECTED
        # Append the rejection reason if one was provided.
        if reason:
            text += f"\n\n**Reason:** {reason}"

    # Attempt to send the message via the aiogram Bot instance.
    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="Markdown")
        return True
    except Exception as e:
        # Log the failure and return False so the caller can handle it.
        logger.error(f"Failed to send driver notification to {telegram_id}: {e}")
        return False


async def send_broadcast_message(
    bot: Bot,
    telegram_id: int,
    text: str,
) -> bool:
    """Sends a broadcast notification message to a user.

    Function Calls:
        - Called by bot/admin/handler.py (execute_broadcast).

    Cross-References:
        - Depends on: aiogram.Bot, logging
        - Imported by: bot/admin/handler.py
    """
    # Attempt to send the broadcast message via the aiogram Bot instance.
    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="Markdown")
        return True
    except Exception as e:
        # Log the failure and return False so the caller can handle it.
        logger.error(f"Failed to send broadcast message to {telegram_id}: {e}")
        return False
