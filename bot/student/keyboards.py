from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from bot.core.constants.halls import CU_HALLS
from bot.core.constants.quick_replies import (
    BTN_HOME,
    BTN_BACK,
    BTN_CANCEL,
)


def hall_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=hall, callback_data=f"hall_select:{hall}")]
        for hall in CU_HALLS
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def student_persistent_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="\U0001F4E6 New Request"),
                KeyboardButton(text="\U0001F4CB My Requests"),
            ],
            [
                KeyboardButton(text="\U0001F464 Profile"),
                KeyboardButton(text="\U0001F6C8 Help"),
            ],
        ],
        resize_keyboard=True,
    )