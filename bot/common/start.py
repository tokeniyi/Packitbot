"""
Refactoring Summary:
1. Dynamically sets chat-specific command menus upon user arrival based on role.
2. Cleaned duplicate BTN_HOME condition in or_f filter.
3. Clears FSM state unconditionally on home/start navigation.
4. Added Bot instance dependency injection to update commands dynamically.
"""

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter, or_f
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.core.constants.commands import (
    ADMIN_COMMANDS,
    DRIVER_COMMANDS,
    STUDENT_COMMANDS,
)
from bot.core.constants.enums import UserRole
from bot.core.constants.messages import (
    MSG_DRIVER_WELCOME,
    MSG_REG_ENTER_FULL_NAME,
    MSG_REG_STEP_PROMPT,
    MSG_START_ADMIN_WELCOME,
    MSG_START_ROLE_SELECTION,
    MSG_START_ROLE_SELECTION_DRIVER,
    MSG_START_ROLE_SELECTION_STUDENT,
    MSG_STUDENT_WELCOME,
    MSG_WELCOME_GENERAL,
)
from bot.core.constants.quick_replies import BTN_HOME
from bot.core.models.user import User
from bot.student.states import StudentRegistrationFSM

logger = logging.getLogger(__name__)
start_router = Router()


async def _set_user_menu(bot: Bot, chat_id: int, commands: list[BotCommand]) -> None:
    """Helper to update user command scopes on the fly."""
    try:
        await bot.set_my_commands(
            commands=commands, scope=BotCommandScopeChat(chat_id=chat_id)
        )
    except Exception as e:
        logger.warning(f"Failed to set custom menu for chat_id={chat_id}: {e}")


def _progress_bar(current: int, total: int) -> str:
    filled = "\u2588" * current
    empty = "\u2591" * (total - current)
    return f"{filled}{empty}"


def _step_prompt(step: int, total: int, prompt: str) -> str:
    bar = _progress_bar(step, total)
    return MSG_REG_STEP_PROMPT.format(
        current=step, total=total, progress_bar=bar, prompt=prompt
    )


@start_router.message(
    StateFilter("*"),
    or_f(
        Command("start"),
        Command("home"),
        F.text == BTN_HOME,
        F.text.contains(BTN_HOME),
    ),
)
async def cmd_start(
    message: Message,
    state: FSMContext,
    bot: Bot,
    user: User | None = None,  # Injected directly from AuthMiddleware
) -> None:
    await state.clear()

    if user is None:
        await message.answer("Something went wrong. Please try again.")
        return

    # Role-based dispatch & dynamic command menu setup
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
        await _set_user_menu(bot, message.chat.id, STUDENT_COMMANDS)
        await message.answer(MSG_STUDENT_WELCOME)

    elif user.role == UserRole.DRIVER:
        await _set_user_menu(bot, message.chat.id, DRIVER_COMMANDS)
        await message.answer(MSG_DRIVER_WELCOME)

    elif user.role == UserRole.ADMIN:
        await _set_user_menu(bot, message.chat.id, ADMIN_COMMANDS)
        await message.answer(MSG_START_ADMIN_WELCOME)

    else:
        await message.answer(MSG_WELCOME_GENERAL)


@start_router.callback_query(F.data == "role:student")
async def process_role_student(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(StudentRegistrationFSM.entering_full_name)
    await callback.message.answer(_step_prompt(1, 3, MSG_REG_ENTER_FULL_NAME))


@start_router.callback_query(F.data == "role:driver")
async def process_role_driver(callback: CallbackQuery) -> None:
    await callback.answer("Driver registration coming soon!", show_alert=True)