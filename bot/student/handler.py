"""
Refactoring Changes:
1. Removed manual text checks: `if message.text and (message.text.startswith("/") or "Home" in message.text): return`
   from `receive_full_name`, `receive_matric`, and `receive_phone`.
   
   Why: Those `return` statements were silently swallowing navigation messages inside active states. 
   When a user clicked "Home", the state handler hit `return`, marking the event as handled 
   without executing `start_router`, which caused the bot to fall through to the global fallback message.
   Removing them allows `start_router` (equipped with `StateFilter("*")`) to take precedence.
"""

import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.core.constants.messages import (
    MSG_REG_EDIT,
    MSG_REG_ENTER_FULL_NAME,
    MSG_REG_ENTER_HALL,
    MSG_REG_ENTER_MATRIC,
    MSG_REG_ENTER_PHONE,
    MSG_REG_INVALID_FULL_NAME,
    MSG_REG_INVALID_MATRIC,
    MSG_REG_INVALID_PHONE,
    MSG_REG_REVIEW_TITLE,
    MSG_REG_STEP_PROMPT,
    MSG_REG_SUBMIT,
    MSG_REG_SUCCESS,
)
from bot.core.keyboards.common_kb import HomeButton
from bot.core.utils.validators import validate_full_name, validate_matric, validate_phone
from bot.student.keyboards import hall_selection_keyboard, student_persistent_menu
from bot.student.service import register_student
from bot.student.states import StudentRegistrationFSM

logger = logging.getLogger(__name__)
student_router = Router()


def _progress_bar(current: int, total: int) -> str:
    filled = "\u2588" * current
    empty = "\u2591" * (total - current)
    return f"{filled}{empty}"


def _step_prompt(step: int, total: int, prompt: str) -> str:
    bar = _progress_bar(step, total)
    return MSG_REG_STEP_PROMPT.format(
        current=step, total=total, progress_bar=bar, prompt=prompt
    )


@student_router.message(Command("cancel"))
@student_router.callback_query(F.data == "cancel")
async def cancel_registration(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer("Registration cancelled.", reply_markup=HomeButton())
    else:
        await event.answer("Registration cancelled.", reply_markup=HomeButton())


@student_router.message(StudentRegistrationFSM.entering_full_name)
async def receive_full_name(message: Message, state: FSMContext) -> None:
    try:
        validate_full_name(message.text)
    except Exception:
        await message.answer(MSG_REG_INVALID_FULL_NAME)
        return

    await state.update_data(full_name=message.text.strip())
    await message.answer(_step_prompt(2, 5, MSG_REG_ENTER_MATRIC))
    await state.set_state(StudentRegistrationFSM.entering_matric_number)


@student_router.message(StudentRegistrationFSM.entering_matric_number)
async def receive_matric(message: Message, state: FSMContext) -> None:
    try:
        validate_matric(message.text)
    except Exception:
        await message.answer(MSG_REG_INVALID_MATRIC)
        return

    await state.update_data(matric_number=message.text.strip())
    await message.answer(
        _step_prompt(3, 5, MSG_REG_ENTER_HALL),
        reply_markup=hall_selection_keyboard(),
    )
    await state.set_state(StudentRegistrationFSM.entering_hall)


@student_router.callback_query(
    StudentRegistrationFSM.entering_hall,
    F.data.startswith("hall_select:"), # <--- Expects "hall_select:..."
)
async def select_hall(callback: CallbackQuery, state: FSMContext) -> None:
    hall = callback.data.split(":", 1)[1]
    await state.update_data(hall_of_residence=hall)
    await callback.answer(f"Selected Hall: {hall}")
    
    await state.set_state(StudentRegistrationFSM.entering_phone_number)
    await callback.message.answer(_step_prompt(4, 5, MSG_REG_ENTER_PHONE))


@student_router.message(StudentRegistrationFSM.entering_phone_number)
async def receive_phone(message: Message, state: FSMContext) -> None:
    try:
        validate_phone(message.text)
    except Exception:
        await message.answer(MSG_REG_INVALID_PHONE)
        return

    await state.update_data(phone_number=message.text.strip())
    await state.set_state(StudentRegistrationFSM.confirming_registration)
    await message.answer(
        MSG_REG_REVIEW_TITLE,
        reply_markup=_review_keyboard(),
    )


@student_router.callback_query(F.data == "review_edit_full_name")
async def edit_full_name(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_text(
        _step_prompt(1, 5, MSG_REG_ENTER_FULL_NAME),
        reply_markup=None,
    )
    await state.set_state(StudentRegistrationFSM.entering_full_name)


@student_router.callback_query(F.data == "review_edit_matric_number")
async def edit_matric(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_text(
        _step_prompt(2, 5, MSG_REG_ENTER_MATRIC),
        reply_markup=None,
    )
    await state.set_state(StudentRegistrationFSM.entering_matric_number)


@student_router.callback_query(F.data == "review_edit_phone_number")
async def edit_phone(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_text(
        _step_prompt(4, 5, MSG_REG_ENTER_PHONE),
        reply_markup=None,
    )
    await state.set_state(StudentRegistrationFSM.entering_phone_number)


@student_router.callback_query(F.data == "review_submit")
async def submit_registration(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    try:
        await register_student(
            telegram_id=callback.from_user.id,
            full_name=data["full_name"],
            matric_number=data["matric_number"],
            hall=data["hall_of_residence"],
            phone=data["phone_number"],
        )
    except Exception as e:
        logger.error(f"Failed to register student: {e}")
        await callback.message.edit_text(f"Registration error: {str(e)}")
        return

    await state.clear()
    await callback.message.edit_text(
        MSG_REG_SUCCESS,
        reply_markup=student_persistent_menu(),
    )


def _review_keyboard() -> InlineKeyboardMarkup:
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
                    text=f"Matric Number {MSG_REG_EDIT}",
                    callback_data="review_edit_matric_number",
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