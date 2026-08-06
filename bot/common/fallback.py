"""Fallback handlers for unrecognized commands and inputs.

This module catches any messages or callback queries that
are not handled by other routers, providing a consistent
user experience with a Home button for navigation.

Function Calls:
    - cmd_cancel(message, state) -> None
    - _send_fallback_response(update) -> None
    - catch_all_message(message) -> None
    - catch_all_callback(callback) -> None

Cross-References:
    - Depends on: aiogram Router, bot.core.constants.messages.MSG_INVALID_INPUT,
        bot.core.keyboards.common_kb.HomeButton
    - Imported by: bot/main.py (via fallback_router, always last)
"""

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.core.constants.messages import MSG_INVALID_INPUT
from bot.core.keyboards.common_kb import HomeButton

logger = logging.getLogger(__name__)
fallback_router = Router()


@fallback_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state):
    """Handle the /cancel command by clearing FSM state.

    Args:
        message: The incoming Message object.
        state: The FSM context for managing conversation state.
    """
    await state.clear()
    markup = HomeButton()
    await message.answer("Action cancelled.", reply_markup=markup)


async def _send_fallback_response(update):
    """Send a fallback response with a Home button for unrecognized input.

    Args:
        update: The incoming Update object (Message or CallbackQuery).
    """
    markup = HomeButton()
    text = MSG_INVALID_INPUT
    if isinstance(update, Message):
        try:
            await update.answer(text, reply_markup=markup)
        except TelegramBadRequest as exc:
            logger.warning("TelegramBadRequest while sending fallback message: %s", exc)
    elif isinstance(update, CallbackQuery):
        try:
            await update.answer(text, show_alert=True)
        except TelegramBadRequest as exc:
            logger.info("Stale or invalid callback query in fallback: %s", exc)
        if update.message:
            try:
                await update.message.answer(text, reply_markup=markup)
            except TelegramBadRequest as exc:
                logger.warning("Failed to send fallback message on callback update: %s", exc)
    else:
        logger.warning("Unhandled update type in fallback: %s", type(update))


@fallback_router.message()
async def catch_all_message(message: Message):
    """Catch-all handler for unrecognized text messages.

    Args:
        message: The incoming Message object.
    """
    await _send_fallback_response(message)


@fallback_router.callback_query()
async def catch_all_callback(callback: CallbackQuery):
    """Catch-all handler for unrecognized callback queries.

    Args:
        callback: The incoming CallbackQuery object.
    """
    await _send_fallback_response(callback)