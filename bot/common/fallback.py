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
    await state.clear()
    markup = HomeButton()
    await message.answer("🛑 Action cancelled.", reply_markup=markup)


async def _send_fallback_response(update):
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
    await _send_fallback_response(message)


@fallback_router.callback_query()
async def catch_all_callback(callback: CallbackQuery):
    await _send_fallback_response(callback)