"""Student registration handler module."""

import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.core.constants.messages import (
    ErrorMessages,
    MSG_REG_EDIT,
    MSG_REG_ENTER_FULL_NAME,
    MSG_REG_ENTER_HALL,
    MSG_REG_ENTER_PHONE,
    MSG_REG_INVALID_FULL_NAME,
    MSG_REG_INVALID_PHONE,
    MSG_REG_REVIEW_TITLE,
    MSG_REG_SUBMIT,
    RegistrationMessages,
    SuccessMessages,
)
from bot.core.keyboards.common_kb import HomeButton
from bot.core.utils.formatters import format_step_prompt
from bot.core.utils.validators import validate_full_name, validate_phone
from bot.student.keyboards import hall_selection_keyboard, student_persistent_menu
from bot.student.service import register_student
from bot.student.states import StudentRegistrationFSM

logger = logging.getLogger(__name__)
registration_router = Router()


def _review_keyboard() -> InlineKeyboardMarkup:
    """Build the inline keyboard for student registration review."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Full Name {MSG_REG_EDIT}",
                    callback_data="review_edit_full_name",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Phone Number {MSG_REG_EDIT}",
                    callback_data="review_edit_phone_number",
                )
            ],
            [
                InlineKeyboardButton(text=MSG_REG_SUBMIT, callback_data="review_submit"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
            ],
        ]
    )


async def _show_review_screen(target: Message | CallbackQuery, state: FSMContext) -> None:
    """Helper to render or re-render the review keyboard and state."""
    await state.set_state(StudentRegistrationFSM.confirming_registration)
    if isinstance(target, CallbackQuery):
        if target.message:
            await target.message.answer(
                MSG_REG_REVIEW_TITLE,
                reply_markup=_review_keyboard(),
            )
    else:
        await target.answer(
            MSG_REG_REVIEW_TITLE,
            reply_markup=_review_keyboard(),
        )


@registration_router.message(Command("cancel"))
@registration_router.callback_query(F.data == "cancel")
async def cancel_registration(event: Message | CallbackQuery, state: FSMContext) -> None:
    """Handle cancellation of the student registration process."""
    await state.clear()
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(SuccessMessages.ACTION_CANCELLED, reply_markup=HomeButton())
    else:
        await event.answer(SuccessMessages.ACTION_CANCELLED, reply_markup=HomeButton())


@registration_router.message(StudentRegistrationFSM.entering_full_name)
async def receive_full_name(message: Message, state: FSMContext) -> None:
    """Handle student full name input."""
    try:
        validate_full_name(message.text)
    except Exception:
        await message.answer(MSG_REG_INVALID_FULL_NAME)
        return

    data = await state.get_data()
    await state.update_data(full_name=message.text.strip())

    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_review_screen(message, state)
    else:
        await message.answer(
            format_step_prompt(2, 3, MSG_REG_ENTER_HALL),
            reply_markup=hall_selection_keyboard(),
        )
        await state.set_state(StudentRegistrationFSM.entering_hall)


@registration_router.callback_query(
    StudentRegistrationFSM.entering_hall,
    F.data.startswith("hall_select:"),
)
async def select_hall(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle student hall selection callback."""
    hall = callback.data.split(":", 1)[1] if ":" in callback.data else callback.data
    await state.update_data(hall_of_residence=hall)
    await callback.answer(f"Selected Hall: {hall}")

    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_review_screen(callback, state)
    else:
        await state.set_state(StudentRegistrationFSM.entering_phone_number)
        if callback.message:
            await callback.message.answer(format_step_prompt(3, 3, MSG_REG_ENTER_PHONE))


@registration_router.message(StudentRegistrationFSM.entering_phone_number)
async def receive_phone(message: Message, state: FSMContext) -> None:
    """Handle student phone number input."""
    try:
        validate_phone(message.text)
    except Exception:
        await message.answer(MSG_REG_INVALID_PHONE)
        return

    await state.update_data(phone_number=message.text.strip())
    await _show_review_screen(message, state)


@registration_router.callback_query(F.data == "review_edit_full_name")
async def edit_full_name(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle edit full name button on registration review screen."""
    await callback.answer()
    await state.update_data(is_editing=True)
    if callback.message:
        await callback.message.answer(
            format_step_prompt(1, 3, MSG_REG_ENTER_FULL_NAME),
            reply_markup=None,
        )
    await state.set_state(StudentRegistrationFSM.entering_full_name)


@registration_router.callback_query(F.data == "review_edit_phone_number")
async def edit_phone(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle edit phone button on registration review screen."""
    await callback.answer()
    await state.update_data(is_editing=True)
    if callback.message:
        await callback.message.answer(
            format_step_prompt(3, 3, MSG_REG_ENTER_PHONE),
            reply_markup=None,
        )
    await state.set_state(StudentRegistrationFSM.entering_phone_number)


@registration_router.callback_query(F.data == "review_submit")
async def submit_registration(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle final submission of student registration."""
    await callback.answer()
    data = await state.get_data()

    full_name = (
        data.get("full_name") 
        or data.get("name") 
        or callback.from_user.full_name
    )
    hall = data.get("hall_of_residence") or data.get("hall") or "Unknown Hall"
    tg_username = callback.from_user.username

    try:
        await register_student(
            telegram_id=callback.from_user.id,
            username=tg_username,
            full_name=full_name,
            hall=hall,
            phone=data.get("phone_number") or data.get("phone"),
        )
    except Exception as e:
        logger.error("Failed to register student: %s", e)
        if callback.message:
            await callback.message.edit_text(f"Registration error: {str(e)}")
        return

    await state.clear()
    if callback.message:
        await callback.message.answer(
            SuccessMessages.REGISTRATION_COMPLETE,
            reply_markup=student_persistent_menu(),
        )
