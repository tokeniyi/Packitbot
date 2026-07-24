from typing import Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from bot.core.constants.quick_replies import (
    BTN_HOME,
    BTN_BACK,
    BTN_CANCEL,
    BTN_YES,
    BTN_NO,
    BTN_SKIP,
    BTN_EDIT,
    BTN_SUBMIT,
    BTN_CHANGE,
    BTN_USE_PROFILE,
)


def YesNoKeyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_YES, callback_data="yes")],
            [InlineKeyboardButton(text=BTN_NO, callback_data="no")],
        ]
    )


def ConfirmKeyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_YES, callback_data="confirm")],
            [InlineKeyboardButton(text=BTN_NO, callback_data="cancel")],
        ]
    )


def BackKeyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_BACK, callback_data="back")],
        ]
    )


def HomeButton() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_HOME, callback_data="home")],
        ]
    )


def PaginationKeyboard(page: int, total_pages: int, callback_prefix: str = "page") -> InlineKeyboardMarkup:
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"{callback_prefix}:{page-1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"{callback_prefix}:{page+1}"))
    
    return InlineKeyboardMarkup(
        inline_keyboard=[buttons, [InlineKeyboardButton(text=BTN_HOME, callback_data="home")]]
    )


def CancelKeyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_CANCEL, callback_data="cancel")],
        ]
    )


def HomeBackKeyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_BACK, callback_data="back")],
            [InlineKeyboardButton(text=BTN_HOME, callback_data="home")],
        ]
    )


def SkipKeyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_SKIP, callback_data="skip")],
        ]
    )