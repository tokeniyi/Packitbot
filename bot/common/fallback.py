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
    - Depends on: aiogram Router, bot.core.constants.messages,
        bot.core.keyboards.common_kb.HomeButton
    - Imported by: bot/main.py (via fallback_router, always last)
"""

import logging
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.core.constants.messages import ErrorMessages, LogMessages, SuccessMessages
from bot.core.keyboards.common_kb import HomeButton

logger = logging.getLogger(__name__)
fallback_router = Router()


@fallback_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state):
    """Handle /cancel command by resetting FSM state."""
    await state.clear()
    await message.answer(SuccessMessages.ACTION_CANCELLED, reply_markup=HomeButton())


async def _send_fallback_response(update):
    """Send fallback response with a Home navigation button."""
    markup = HomeButton()
    text = ErrorMessages.INVALID_INPUT
    if isinstance(update, Message):
        try:
            await update.answer(text, reply_markup=markup)
        except TelegramBadRequest as exc:
            logger.warning(LogMessages.FALLBACK_TELEGRAM_ERROR, exc)
    elif isinstance(update, CallbackQuery):
        try:
            await update.answer(text, show_alert=True)
        except TelegramBadRequest as exc:
            logger.info(LogMessages.STALE_CALLBACK, exc)
        if update.message:
            try:
                await update.message.answer(text, reply_markup=markup)
            except TelegramBadRequest as exc:
                logger.warning(LogMessages.FALLBACK_TELEGRAM_ERROR, exc)
    else:
        logger.warning(LogMessages.UNHANDLED_UPDATE, type(update))


@fallback_router.message()
async def catch_all_message(message: Message):
    """Catch-all handler for unrecognized text messages."""
    await _send_fallback_response(message)


@fallback_router.callback_query()
async def catch_all_callback(callback: CallbackQuery):
    """Catch-all handler for unrecognized callback queries."""
    await _send_fallback_response(callback)