import logging
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.core.constants.enums import UserRole
from bot.core.constants.messages import (
    MSG_START_ADMIN_WELCOME,
    MSG_START_ROLE_SELECTION,
    MSG_START_ROLE_SELECTION_DRIVER,
    MSG_START_ROLE_SELECTION_STUDENT,
)
from bot.core.models.user import User

logger = logging.getLogger(__name__)
start_router = Router()


@start_router.message(Command("start"))
async def cmd_start(
    message: Message,
    user: User | None = None,  # Inject user directly from AuthMiddleware
) -> None:
    if user is None:
        await message.answer("Something went wrong. Please try again.")
        return

    if user.role is None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=MSG_START_ROLE_SELECTION_STUDENT,
                        callback_data="role:student",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=MSG_START_ROLE_SELECTION_DRIVER,
                        callback_data="role:driver",
                    )
                ],
            ]
        )
        await message.answer(MSG_START_ROLE_SELECTION, reply_markup=keyboard)
    elif user.role == UserRole.STUDENT:
        await message.answer("Welcome back, Student!")
    elif user.role == UserRole.DRIVER:
        await message.answer("Welcome back, Driver!")
    elif user.role == UserRole.ADMIN:
        await message.answer(MSG_START_ADMIN_WELCOME)
    else:
        await message.answer("Welcome to Packitbot!")