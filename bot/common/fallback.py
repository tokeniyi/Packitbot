import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.core.constants.messages import MSG_SOMETHING_WENT_WRONG, MSG_NO_PERMISSION, MSG_INVALID_INPUT
from bot.core.keyboards.common_kb import HomeButton

logger = logging.getLogger(__name__)
fallback_router = Router()


@fallback_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state):
    await state.clear()
    markup = HomeButton()
    await message.answer("Action cancelled.", reply_markup=markup)


async def _send_home(update):
    markup = HomeButton()
    text = MSG_INVALID_INPUT
    if hasattr(update, "answer") and hasattr(update, "chat"):
        await update.answer(text, reply_markup=markup)
    elif hasattr(update, "answer") and hasattr(update, "message"):
        await update.answer(text)
        if update.message:
            await update.message.edit_reply_markup(reply_markup=markup)
    else:
        logger.warning(f"Unhandled update type in fallback: {type(update)}")


@fallback_router.message()
async def catch_all_message(message: Message, state):
    await _send_home(message)


@fallback_router.callback_query()
async def catch_all_callback(callback: CallbackQuery):
    await _send_home(callback)