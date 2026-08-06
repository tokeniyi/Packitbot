"""Start and home command handlers for the Packitbot Telegram bot.

This module handles the /start, /home, and home button
interactions, presenting role selection for new users
and navigating existing users back to the main menu.
It also dynamically sets command menus based on the
user's role.

Function Calls:
    - cmd_start(message, state, bot, user) -> None
    - home_callback(callback, state, bot, user) -> None
    - process_role_student(callback, state) -> None
    - process_role_driver(callback) -> None

Cross-References:
    - Depends on: aiogram Router, FSMContext, Bot, sqlalchemy,
        bot.student.states.StudentRegistrationFSM, bot.core.constants.*,
        bot.core.keyboards.common_kb.HomeButton, bot.core.models.user.User
    - Imported by: bot/main.py (via start_router)
"""

from aiogram.exceptions import TelegramBadRequest
from bot.student.keyboards import student_persistent_menu
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

from bot.core.constants_commands import (
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
    """Helper to update user command scopes on the fly.

    Args:
        bot: The aiogram Bot instance.
        chat_id: The Telegram chat ID.
        commands: The list of BotCommand objects to set.
    """
    try:
        await bot.set_my_commands(
            commands=commands, scope=BotCommandScopeChat(chat_id=chat_id)
        )
    except Exception as e:
        logger.warning(f"Failed to set custom menu for chat_id={chat_id}: {e}")


def _progress_bar(current: int, total: int) -> str:
    """Render a text-based progress bar.

    Args:
        current: The current step number (1-indexed).
        total: The total number of steps.

    Returns:
        A string of block characters representing progress.
    """
    filled = "\u2588" * current
    empty = "\u2591" * (total - current)
    return f"{filled}{empty}"


def _step_prompt(step: int, total: int, prompt: str) -> str:
    """Format a step prompt with a progress bar.

    Args:
        step: The current step number.
        total: The total number of steps.
        prompt: The prompt text for the current step.

    Returns:
        A formatted string with step indicator and progress bar.
    """
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
    """Handle the /start and /home commands and home button presses.

    Clears the FSM state, then dispatches the user to
    the appropriate welcome flow based on their role.
    For users with no role, presents a role selection
    keyboard. For known roles, sends a role-specific
    welcome message and updates the command menu.

    Args:
        message: The incoming Message object.
        state: The FSM context for managing conversation state.
        bot: The aiogram Bot instance for setting command menus.
        user: The resolved User object from AuthMiddleware.
    """
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


@start_router.callback_query(F.data == "home")
async def home_callback(callback: CallbackQuery, state: FSMContext, bot: Bot, user: User | None = None) -> None:
    """Handle the home button callback.

    Clears FSM state, deletes the current message, and
    dispatches the user to the appropriate welcome flow
    based on their role.

    Args:
        callback: The incoming CallbackQuery object.
        state: The FSM context for managing conversation state.
        bot: The aiogram Bot instance for setting command menus.
        user: The resolved User object from AuthMiddleware.
    """
    await callback.answer()
    await state.clear()

    if callback.message is None:
        return

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    if user is None:
        await callback.message.answer("Something went wrong. Please try again.", reply_markup=student_persistent_menu())
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
        await callback.message.answer(MSG_START_ROLE_SELECTION, reply_markup=keyboard)

    elif user.role == UserRole.STUDENT:
        await _set_user_menu(bot, callback.message.chat.id, STUDENT_COMMANDS)
        await callback.message.answer(MSG_STUDENT_WELCOME)

    elif user.role == UserRole.DRIVER:
        await _set_user_menu(bot, callback.message.chat.id, DRIVER_COMMANDS)
        await callback.message.answer(MSG_DRIVER_WELCOME)

    elif user.role == UserRole.ADMIN:
        await _set_user_menu(bot, callback.message.chat.id, ADMIN_COMMANDS)
        await callback.message.answer(MSG_START_ADMIN_WELCOME)

    else:
        await callback.message.answer(MSG_WELCOME_GENERAL)


@start_router.callback_query(F.data == "role:student")
async def process_role_student(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle the student role selection callback.

    Sets the FSM state to the registration flow and
    prompts the user for their full name.

    Args:
        callback: The incoming CallbackQuery object.
        state: The FSM context for managing conversation state.
    """
    await callback.answer()
    await state.set_state(StudentRegistrationFSM.entering_full_name)
    await callback.message.answer(_step_prompt(1, 3, MSG_REG_ENTER_FULL_NAME))


@start_router.callback_query(F.data == "role:driver")
async def process_role_driver(callback: CallbackQuery) -> None:
    """Handle the driver role selection callback.

    Currently shows an alert that driver registration
    is not yet available.

    Args:
        callback: The incoming CallbackQuery object.
    """
    await callback.answer("Driver registration coming soon!", show_alert=True)