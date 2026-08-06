"""Common keyboard builders for the Packitbot Telegram bot.

This module provides factory functions for reusable
inline and reply keyboard markups used across
multiple handler modules.

Function Calls:
    - YesNoKeyboard() -> InlineKeyboardMarkup
    - ConfirmKeyboard() -> InlineKeyboardMarkup
    - BackKeyboard() -> InlineKeyboardMarkup
    - HomeButton() -> InlineKeyboardMarkup
    - PaginationKeyboard(page, total_pages, callback_prefix) -> InlineKeyboardMarkup
    - CancelKeyboard() -> InlineKeyboardMarkup
    - HomeBackKeyboard() -> InlineKeyboardMarkup
    - SkipKeyboard() -> InlineKeyboardMarkup

Cross-References:
    - Depends on: aiogram.types, bot.core.constants.quick_replies
    - Imported by: bot/core/middlewares/auth.py, bot/common/*.py,
        bot/student/handler.py, bot/student/handler_requests.py
"""

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
    """Return a yes/no inline keyboard.

    Returns:
        An InlineKeyboardMarkup with Yes and No buttons.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_YES, callback_data="yes")],
            [InlineKeyboardButton(text=BTN_NO, callback_data="no")],
        ]
    )


def ConfirmKeyboard() -> InlineKeyboardMarkup:
    """Return a confirm/cancel inline keyboard.

    Returns:
        An InlineKeyboardMarkup with Confirm and Cancel buttons.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_YES, callback_data="confirm")],
            [InlineKeyboardButton(text=BTN_NO, callback_data="cancel")],
        ]
    )


def BackKeyboard() -> InlineKeyboardMarkup:
    """Return a back button inline keyboard.

    Returns:
        An InlineKeyboardMarkup with a Back button.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_BACK, callback_data="back")],
        ]
    )


def HomeButton() -> InlineKeyboardMarkup:
    """Return a home button inline keyboard.

    Returns:
        An InlineKeyboardMarkup with a Home button.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_HOME, callback_data="home")],
        ]
    )


def PaginationKeyboard(page: int, total_pages: int, callback_prefix: str = "page") -> InlineKeyboardMarkup:
    """Return a pagination inline keyboard with prev/next buttons.

    Args:
        page: The current page number.
        total_pages: The total number of pages.
        callback_prefix: The prefix for pagination callback data.

    Returns:
        An InlineKeyboardMarkup with pagination controls and a Home button.
    """
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"{callback_prefix}:{page-1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"{callback_prefix}:{page+1}"))
    
    return InlineKeyboardMarkup(
        inline_keyboard=[buttons, [InlineKeyboardButton(text=BTN_HOME, callback_data="home")]]
    )


def CancelKeyboard() -> InlineKeyboardMarkup:
    """Return a cancel button inline keyboard.

    Returns:
        An InlineKeyboardMarkup with a Cancel button.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_CANCEL, callback_data="cancel")],
        ]
    )


def HomeBackKeyboard() -> InlineKeyboardMarkup:
    """Return a back and home inline keyboard.

    Returns:
        An InlineKeyboardMarkup with Back and Home buttons.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_BACK, callback_data="back")],
            [InlineKeyboardButton(text=BTN_HOME, callback_data="home")],
        ]
    )


def SkipKeyboard() -> InlineKeyboardMarkup:
    """Return a skip button inline keyboard.

    Returns:
        An InlineKeyboardMarkup with a Skip button.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_SKIP, callback_data="skip")],
        ]
    )