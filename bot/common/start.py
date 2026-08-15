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
    - process_role_driver(callback, state, session) -> None

Cross-References:
    - Depends on: aiogram Router, FSMContext, Bot, sqlalchemy,
        bot.student.states.StudentRegistrationFSM, bot.core.constants.*,
        bot.core.keyboards.common_kb.HomeButton, bot.core.models.user.User
    - Imported by: bot/main.py (via start_router)
"""

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
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
from bot.core.constants.enums import DriverStatus, UserRole
from bot.core.constants.messages import (
    CommandResponses,
    ErrorMessages,
    LogMessages,
    RegistrationMessages,
    SuccessMessages,
)
from bot.core.constants.quick_replies import BTN_HOME
from bot.core.keyboards.common_kb import HomeButton
from bot.core.models.user import User
from bot.core.utils.formatters import format_step_prompt
from bot.driver.keyboards import driver_pending_menu, driver_persistent_menu
from bot.driver.service import get_driver_profile_by_telegram_id, is_authorized_driver
from bot.driver.states import DriverRegistrationFSM
from bot.student.keyboards import student_persistent_menu
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
        logger.warning(LogMessages.CUSTOM_MENU_FAILED, chat_id, e)


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
    """Handle the /start and /home commands and home button presses."""
    await state.clear()

    if user is None:
        await message.answer(ErrorMessages.SOMETHING_WENT_WRONG)
        return

    # Role-based dispatch & dynamic command menu setup
    if user.role is None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=CommandResponses.START_ROLE_SELECTION_STUDENT,
                        callback_data="role:student",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=CommandResponses.START_ROLE_SELECTION_DRIVER,
                        callback_data="role:driver",
                    )
                ],
            ]
        )
        await message.answer(CommandResponses.START_ROLE_SELECTION, reply_markup=keyboard)

    elif user.role == UserRole.STUDENT:
        await _set_user_menu(bot, message.chat.id, STUDENT_COMMANDS)
        await message.answer(CommandResponses.STUDENT_WELCOME)

    elif user.role == UserRole.DRIVER:
        await _set_user_menu(bot, message.chat.id, DRIVER_COMMANDS)
        await message.answer(CommandResponses.DRIVER_WELCOME)

    elif user.role == UserRole.ADMIN:
        await _set_user_menu(bot, message.chat.id, ADMIN_COMMANDS)
        await message.answer(CommandResponses.START_ADMIN_WELCOME)

    else:
        await message.answer(CommandResponses.WELCOME_GENERAL)


@start_router.callback_query(F.data == "home")
async def home_callback(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    user: User | None = None,
) -> None:
    """Handle the home button callback."""
    await callback.answer()
    await state.clear()

    if callback.message is None:
        return

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    if user is None:
        await callback.message.answer(
            ErrorMessages.SOMETHING_WENT_WRONG,
            reply_markup=student_persistent_menu(),
        )
        return

    if user.role is None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=CommandResponses.START_ROLE_SELECTION_STUDENT,
                        callback_data="role:student",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=CommandResponses.START_ROLE_SELECTION_DRIVER,
                        callback_data="role:driver",
                    )
                ],
            ]
        )
        await callback.message.answer(CommandResponses.START_ROLE_SELECTION, reply_markup=keyboard)

    elif user.role == UserRole.STUDENT:
        await _set_user_menu(bot, callback.message.chat.id, STUDENT_COMMANDS)
        await callback.message.answer(CommandResponses.STUDENT_WELCOME)

    elif user.role == UserRole.DRIVER:
        await _set_user_menu(bot, callback.message.chat.id, DRIVER_COMMANDS)
        await callback.message.answer(CommandResponses.DRIVER_WELCOME)

    elif user.role == UserRole.ADMIN:
        await _set_user_menu(bot, callback.message.chat.id, ADMIN_COMMANDS)
        await callback.message.answer(CommandResponses.START_ADMIN_WELCOME)

    else:
        await callback.message.answer(CommandResponses.WELCOME_GENERAL)


@start_router.callback_query(F.data == "role:student")
async def process_role_student(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle the student role selection callback."""
    await callback.answer()
    await state.set_state(StudentRegistrationFSM.entering_full_name)
    if callback.message:
        await callback.message.answer(
            format_step_prompt(1, 3, RegistrationMessages.STUDENT_ENTER_FULL_NAME)
        )


@start_router.callback_query(F.data == "role:driver")
async def process_role_driver(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    """Handle the driver role selection callback."""
    await callback.answer()
    if session is None:
        if callback.message:
            await callback.message.answer(ErrorMessages.SESSION_UNAVAILABLE)
        return

    telegram_id = callback.from_user.id

    # Check if driver is already registered
    profile = await get_driver_profile_by_telegram_id(session, telegram_id)
    if profile:
        if profile.status == DriverStatus.APPROVED:
            if callback.message:
                await callback.message.answer(
                    SuccessMessages.DRIVER_ALREADY_APPROVED,
                    reply_markup=driver_persistent_menu(profile.availability),
                )
            return
        elif profile.status == DriverStatus.PENDING_APPROVAL:
            if callback.message:
                await callback.message.answer(
                    ErrorMessages.DRIVER_PENDING_APPROVAL,
                    parse_mode="HTML",
                    reply_markup=driver_pending_menu(),
                )
            return

    # Check pre-authorization before starting the registration FSM.
    is_authorized = await is_authorized_driver(session, telegram_id)
    if not is_authorized:
        if callback.message:
            await callback.message.answer(
                ErrorMessages.DRIVER_INVITATION_ONLY,
                reply_markup=HomeButton(),
            )
        return

    await state.clear()
    await state.set_state(DriverRegistrationFSM.entering_full_name)
    if callback.message:
        await callback.message.answer(
            format_step_prompt(1, 5, RegistrationMessages.DRIVER_ENTER_FULL_NAME)
        )