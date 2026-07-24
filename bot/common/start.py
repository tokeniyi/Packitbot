"""
Refactoring Summary:
1. Added `Command("home")` to the main navigation decorator alongside `Command("start")` 
   and `F.text.contains("Home")` with StateFilter("*") so sending `/home` resets state anywhere.
2. Updated student registration step prompt from (1, 5) to (1, 3) to match the removal of matric number.
3. Ensures state wiping via `await state.clear()` when going home or restarting.
"""

import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.core.constants.enums import UserRole
from bot.core.constants.messages import (
    MSG_REG_ENTER_FULL_NAME,
    MSG_REG_STEP_PROMPT,
    MSG_START_ADMIN_WELCOME,
    MSG_START_ROLE_SELECTION,
    MSG_START_ROLE_SELECTION_DRIVER,
    MSG_START_ROLE_SELECTION_STUDENT,
    MSG_WELCOME_GENERAL,
    MSG_STUDENT_WELCOME,
    MSG_DRIVER_WELCOME,
)
from bot.core.models.user import User
from bot.student.states import StudentRegistrationFSM

logger = logging.getLogger(__name__)
start_router = Router()


def _progress_bar(current: int, total: int) -> str:
    filled = "\u2588" * current
    empty = "\u2591" * (total - current)
    return f"{filled}{empty}"


def _step_prompt(step: int, total: int, prompt: str) -> str:
    bar = _progress_bar(step, total)
    return MSG_REG_STEP_PROMPT.format(
        current=step, total=total, progress_bar=bar, prompt=prompt
    )


@start_router.message(StateFilter("*"), Command("start"))
@start_router.message(StateFilter("*"), Command("home"))
@start_router.message(StateFilter("*"), F.text.contains("Home"))
async def cmd_start(
    message: Message,
    state: FSMContext,
    user: User | None = None,  # Inject user directly from AuthMiddleware
) -> None:
    await state.clear()

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
        await message.answer(MSG_STUDENT_WELCOME)
    elif user.role == UserRole.DRIVER:
        await message.answer(MSG_DRIVER_WELCOME)
    elif user.role == UserRole.ADMIN:
        await message.answer(MSG_START_ADMIN_WELCOME)
    else:
        await message.answer(MSG_WELCOME_GENERAL)


@start_router.callback_query(F.data == "role:student")
async def process_role_student(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(StudentRegistrationFSM.entering_full_name)
    # Updated total steps from 5 to 3
    await callback.message.answer(_step_prompt(1, 3, MSG_REG_ENTER_FULL_NAME))


@start_router.callback_query(F.data == "role:driver")
async def process_role_driver(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Driver registration coming soon!", show_alert=True)