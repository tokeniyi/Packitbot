import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.core.constants.messages import (
    MSG_REG_EDIT,
    MSG_REG_ENTER_FULL_NAME,
    MSG_REG_ENTER_HALL,
    MSG_REG_ENTER_PHONE,
    MSG_REG_INVALID_FULL_NAME,
    MSG_REG_INVALID_PHONE,
    MSG_REG_REVIEW_TITLE,
    MSG_REG_STEP_PROMPT,
    MSG_REG_SUBMIT,
    MSG_REG_SUCCESS,
)
from bot.core.keyboards.common_kb import HomeButton
from bot.core.utils.validators import validate_full_name, validate_phone
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


async def _show_review_screen(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(StudentRegistrationFSM.confirming_registration)
    if isinstance(target, CallbackQuery):
        await target.message.answer(
            MSG_REG_REVIEW_TITLE,
            reply_markup=_review_keyboard(),
        )
    else:
        await target.answer(
            MSG_REG_REVIEW_TITLE,
            reply_markup=_review_keyboard(),
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

    data = await state.get_data()
    await state.update_data(full_name=message.text.strip())

    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_review_screen(message, state)
    else:
        await message.answer(
            _step_prompt(2, 3, MSG_REG_ENTER_HALL),
            reply_markup=hall_selection_keyboard(),
        )
        await state.set_state(StudentRegistrationFSM.entering_hall)


@student_router.callback_query(
    StudentRegistrationFSM.entering_hall,
    F.data.startswith("hall_select:"),
)
async def select_hall(callback: CallbackQuery, state: FSMContext) -> None:
    hall = callback.data.split(":", 1)[1] if ":" in callback.data else callback.data
    await state.update_data(hall_of_residence=hall)
    await callback.answer(f"Selected Hall: {hall}")

    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_review_screen(callback, state)
    else:
        await state.set_state(StudentRegistrationFSM.entering_phone_number)
        await callback.message.answer(_step_prompt(3, 3, MSG_REG_ENTER_PHONE))


@student_router.message(StudentRegistrationFSM.entering_phone_number)
async def receive_phone(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip():
        try:
            validate_phone(message.text)
        except Exception:
            await message.answer(MSG_REG_INVALID_PHONE)
            return
        await state.update_data(phone_number=message.text.strip())
    else:
        await state.update_data(phone_number=None)

    await state.update_data(is_editing=False)
    await _show_review_screen(message, state)


@student_router.callback_query(F.data == "review_edit_full_name")
async def edit_full_name(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(is_editing=True)
    await callback.message.answer(
        _step_prompt(1, 3, MSG_REG_ENTER_FULL_NAME),
        reply_markup=None,
    )
    await state.set_state(StudentRegistrationFSM.entering_full_name)


@student_router.callback_query(F.data == "review_edit_phone_number")
async def edit_phone(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(is_editing=True)
    await callback.message.answer(
        _step_prompt(3, 3, MSG_REG_ENTER_PHONE),
        reply_markup=None,
    )
    await state.set_state(StudentRegistrationFSM.entering_phone_number)


@student_router.callback_query(F.data == "review_submit")
async def submit_registration(callback: CallbackQuery, state: FSMContext) -> None:
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
        logger.error(f"Failed to register student: {e}")
        await callback.message.edit_text(f"Registration error: {str(e)}")
        return

    await state.clear()
    await callback.message.answer(
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