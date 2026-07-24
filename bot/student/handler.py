"""
Refactoring Changes:
1. Removed matric_number from states, step handlers, and review keyboard.
2. Direct Flow: Full Name -> Hall Selection -> Phone Number -> Confirm/Review Screen.
3. Automatically retrieves `username` from Telegram's callback.from_user on submission.
4. Preserved single-field editing flag logic.
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
    """Helper to render or re-render the review keyboard and state."""
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
        # Progresses directly to Step 2: Hall Selection (out of 3 steps)
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

    # Automatically extract Telegram username from callback event
    tg_username = callback.from_user.username

    try:
        await register_student(
            telegram_id=callback.from_user.id,
            username=tg_username,
            full_name=data["full_name"],
            hall=data["hall_of_residence"],
            phone=data.get("phone_number"),
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


# ------------------------------------------------------------------
# Phase 12: Delivery Request Creation FSM Flow
# ------------------------------------------------------------------

from datetime import date
from bot.core.constants.enums import LuggageSize
from bot.core.utils.validators import (
    validate_pickup_detail,
    validate_dropoff_address,
    validate_hall,
    validate_recipient_name,
    validate_phone,
    validate_luggage_size,
    validate_luggage_count,
    validate_preferred_date,
    validate_time_window,
    validate_special_instructions,
)
from bot.request.schemas import CreateRequestDTO
from bot.request.service import RequestService
from bot.student.keyboards import (
    date_quick_pick_keyboard,
    frequent_address_keyboard,
    req_hall_selection_keyboard,
    luggage_size_keyboard,
    time_window_keyboard,
    skip_or_cancel_keyboard,
    request_review_keyboard,
)
from bot.student.states import RequestCreateFSM


def _req_step_prompt(step: int, total: int = 11, prompt: str = "") -> str:
    bar = _progress_bar(step, total)
    return f"Step {step}/{total} [{bar}]\n\n{prompt}"


async def _show_request_review(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RequestCreateFSM.confirming_request)
    data = await state.get_data()
    summary = (
        "📦 <b>Delivery Request Review</b>\n\n"
        f"• <b>Pickup Detail:</b> {data.get('pickup_detail')}\n"
        f"• <b>Dropoff Address:</b> {data.get('dropoff_address')}\n"
        f"• <b>Landmark:</b> {data.get('dropoff_landmark') or 'None'}\n"
        f"• <b>Hall of Residence:</b> {data.get('hall_of_residence')}\n"
        f"• <b>Recipient Name:</b> {data.get('recipient_name')}\n"
        f"• <b>Recipient Phone:</b> {data.get('recipient_phone')}\n"
        f"• <b>Luggage Size:</b> {data.get('luggage_size')}\n"
        f"• <b>Luggage Count:</b> {data.get('luggage_count')}\n"
        f"• <b>Preferred Date:</b> {data.get('preferred_date')}\n"
        f"• <b>Time Window:</b> {data.get('preferred_time_window')}\n"
        f"• <b>Special Instructions:</b> {data.get('special_instructions') or 'None'}\n"
    )
    if isinstance(target, CallbackQuery):
        await target.message.answer(summary, parse_mode="HTML", reply_markup=request_review_keyboard())
    else:
        await target.answer(summary, parse_mode="HTML", reply_markup=request_review_keyboard())


@student_router.message(F.text == "📦 New Request")
@student_router.message(Command("new_request"))
async def start_request_creation(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(RequestCreateFSM.entering_pickup_detail)
    await message.answer(_req_step_prompt(1, 11, "Enter pickup detail (e.g. Room 102, Esther Hall):"))


@student_router.message(Command("cancel_request"))
@student_router.callback_query(F.data == "req_cancel")
async def cancel_request_creation(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    msg = "Request creation cancelled."
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(msg, reply_markup=student_persistent_menu())
    else:
        await event.answer(msg, reply_markup=student_persistent_menu())


@student_router.message(RequestCreateFSM.entering_pickup_detail)
async def process_pickup_detail(message: Message, state: FSMContext) -> None:
    try:
        val = validate_pickup_detail(message.text)
    except Exception as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(pickup_detail=val)
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(message, state)
        return

    await state.set_state(RequestCreateFSM.entering_dropoff_address)
    await message.answer(_req_step_prompt(2, 11, "Enter dropoff address:"))


@student_router.message(RequestCreateFSM.entering_dropoff_address)
async def process_dropoff_address(message: Message, state: FSMContext) -> None:
    try:
        val = validate_dropoff_address(message.text)
    except Exception as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(dropoff_address=val)
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(message, state)
        return

    await state.set_state(RequestCreateFSM.entering_dropoff_landmark)
    await message.answer(
        _req_step_prompt(3, 11, "Enter dropoff landmark (optional):"),
        reply_markup=skip_or_cancel_keyboard(skip_callback="req_skip_landmark"),
    )


@student_router.callback_query(RequestCreateFSM.entering_dropoff_landmark, F.data == "req_skip_landmark")
async def skip_dropoff_landmark(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(dropoff_landmark=None)
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(callback, state)
        return

    await state.set_state(RequestCreateFSM.entering_hall)
    await callback.message.answer(
        _req_step_prompt(4, 11, "Select Hall of Residence:"),
        reply_markup=req_hall_selection_keyboard(),
    )


@student_router.message(RequestCreateFSM.entering_dropoff_landmark)
async def process_dropoff_landmark(message: Message, state: FSMContext) -> None:
    await state.update_data(dropoff_landmark=message.text.strip())
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(message, state)
        return

    await state.set_state(RequestCreateFSM.entering_hall)
    await message.answer(
        _req_step_prompt(4, 11, "Select Hall of Residence:"),
        reply_markup=req_hall_selection_keyboard(),
    )


@student_router.callback_query(RequestCreateFSM.entering_hall, F.data.startswith("req_hall:"))
async def process_hall_select(callback: CallbackQuery, state: FSMContext) -> None:
    hall = callback.data.split(":", 1)[1]
    await callback.answer(f"Hall: {hall}")
    await state.update_data(hall_of_residence=hall)

    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(callback, state)
        return

    await state.set_state(RequestCreateFSM.entering_recipient_name)
    await callback.message.answer(_req_step_prompt(5, 11, "Enter recipient full name:"))


@student_router.message(RequestCreateFSM.entering_recipient_name)
async def process_recipient_name(message: Message, state: FSMContext) -> None:
    try:
        val = validate_recipient_name(message.text)
    except Exception as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(recipient_name=val)
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(message, state)
        return

    await state.set_state(RequestCreateFSM.entering_recipient_phone)
    await message.answer(_req_step_prompt(6, 11, "Enter recipient phone number (e.g. 08012345678):"))


@student_router.message(RequestCreateFSM.entering_recipient_phone)
async def process_recipient_phone(message: Message, state: FSMContext) -> None:
    try:
        val = validate_phone(message.text)
    except Exception as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(recipient_phone=val)
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(message, state)
        return

    await state.set_state(RequestCreateFSM.selecting_luggage_size)
    await message.answer(
        _req_step_prompt(7, 11, "Select luggage size:"),
        reply_markup=luggage_size_keyboard(),
    )


@student_router.callback_query(RequestCreateFSM.selecting_luggage_size, F.data.startswith("req_size:"))
async def process_luggage_size(callback: CallbackQuery, state: FSMContext) -> None:
    size = callback.data.split(":", 1)[1]
    await callback.answer(f"Size: {size}")
    await state.update_data(luggage_size=size)

    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(callback, state)
        return

    await state.set_state(RequestCreateFSM.entering_luggage_count)
    await callback.message.answer(_req_step_prompt(8, 11, "Enter luggage count (1-10):"))


@student_router.message(RequestCreateFSM.entering_luggage_count)
async def process_luggage_count(message: Message, state: FSMContext) -> None:
    try:
        count = validate_luggage_count(message.text)
    except Exception as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(luggage_count=count)
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(message, state)
        return

    await state.set_state(RequestCreateFSM.selecting_preferred_date)
    await message.answer(
        _req_step_prompt(9, 11, "Select preferred pickup date or type YYYY-MM-DD:"),
        reply_markup=date_quick_pick_keyboard(),
    )


@student_router.callback_query(RequestCreateFSM.selecting_preferred_date, F.data.startswith("req_date:"))
async def process_preferred_date_callback(callback: CallbackQuery, state: FSMContext) -> None:
    dt_str = callback.data.split(":", 1)[1]
    await callback.answer(f"Date: {dt_str}")
    await state.update_data(preferred_date=dt_str)

    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(callback, state)
        return

    await state.set_state(RequestCreateFSM.selecting_time_window)
    await callback.message.answer(
        _req_step_prompt(10, 11, "Select preferred time window:"),
        reply_markup=time_window_keyboard(),
    )


@student_router.message(RequestCreateFSM.selecting_preferred_date)
async def process_preferred_date_message(message: Message, state: FSMContext) -> None:
    try:
        val = validate_preferred_date(message.text)
    except Exception as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(preferred_date=val.isoformat())
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(message, state)
        return

    await state.set_state(RequestCreateFSM.selecting_time_window)
    await message.answer(
        _req_step_prompt(10, 11, "Select preferred time window:"),
        reply_markup=time_window_keyboard(),
    )


@student_router.callback_query(RequestCreateFSM.selecting_time_window, F.data.startswith("req_time:"))
async def process_time_window_callback(callback: CallbackQuery, state: FSMContext) -> None:
    slot = callback.data.split(":", 1)[1]
    await callback.answer(f"Time: {slot}")
    await state.update_data(preferred_time_window=slot)

    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(callback, state)
        return

    await state.set_state(RequestCreateFSM.entering_special_instructions)
    await callback.message.answer(
        _req_step_prompt(11, 11, "Enter any special instructions (optional):"),
        reply_markup=skip_or_cancel_keyboard(skip_callback="req_skip_instructions"),
    )


@student_router.message(RequestCreateFSM.selecting_time_window)
async def process_time_window_message(message: Message, state: FSMContext) -> None:
    try:
        val = validate_time_window(message.text)
    except Exception as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(preferred_time_window=val)
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(message, state)
        return

    await state.set_state(RequestCreateFSM.entering_special_instructions)
    await message.answer(
        _req_step_prompt(11, 11, "Enter any special instructions (optional):"),
        reply_markup=skip_or_cancel_keyboard(skip_callback="req_skip_instructions"),
    )


@student_router.callback_query(RequestCreateFSM.entering_special_instructions, F.data == "req_skip_instructions")
async def skip_special_instructions(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(special_instructions=None)
    await _show_request_review(callback, state)


@student_router.message(RequestCreateFSM.entering_special_instructions)
async def process_special_instructions(message: Message, state: FSMContext) -> None:
    try:
        val = validate_special_instructions(message.text)
    except Exception as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(special_instructions=val)
    await _show_request_review(message, state)


@student_router.callback_query(RequestCreateFSM.confirming_request, F.data.startswith("req_edit:"))
async def edit_request_field(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    await callback.answer()
    await state.update_data(is_editing=True)

    field_map = {
        "pickup_detail": (RequestCreateFSM.entering_pickup_detail, "Enter pickup detail:"),
        "dropoff_address": (RequestCreateFSM.entering_dropoff_address, "Enter dropoff address:"),
        "dropoff_landmark": (RequestCreateFSM.entering_dropoff_landmark, "Enter dropoff landmark:"),
        "hall": (RequestCreateFSM.entering_hall, "Select Hall of Residence:"),
        "recipient_name": (RequestCreateFSM.entering_recipient_name, "Enter recipient name:"),
        "recipient_phone": (RequestCreateFSM.entering_recipient_phone, "Enter recipient phone number:"),
        "luggage_size": (RequestCreateFSM.selecting_luggage_size, "Select luggage size:"),
        "luggage_count": (RequestCreateFSM.entering_luggage_count, "Enter luggage count:"),
        "preferred_date": (RequestCreateFSM.selecting_preferred_date, "Select preferred pickup date:"),
        "preferred_time_window": (RequestCreateFSM.selecting_time_window, "Select preferred time window:"),
        "special_instructions": (RequestCreateFSM.entering_special_instructions, "Enter special instructions:"),
    }

    if field in field_map:
        target_state, prompt_text = field_map[field]
        await state.set_state(target_state)
        await callback.message.answer(f"✏️ Editing {field.replace('_', ' ').title()}:\n{prompt_text}")


@student_router.callback_query(RequestCreateFSM.confirming_request, F.data == "req_submit")
async def submit_request_creation(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    await callback.answer()
    data = await state.get_data()

    dto = CreateRequestDTO(
        student_id=callback.from_user.id,
        pickup_detail=data["pickup_detail"],
        dropoff_address=data["dropoff_address"],
        dropoff_landmark=data.get("dropoff_landmark"),
        hall_of_residence=data["hall_of_residence"],
        recipient_name=data["recipient_name"],
        recipient_phone=data["recipient_phone"],
        luggage_size=LuggageSize(data["luggage_size"]),
        luggage_count=int(data["luggage_count"]),
        special_instructions=data.get("special_instructions"),
        preferred_date=date.fromisoformat(data["preferred_date"]),
        preferred_time_window=data["preferred_time_window"],
    )

    if session is not None:
        service = RequestService(session)
        try:
            req, event = await service.create_request(dto)
            await state.clear()
            await callback.message.edit_text(
                f"✅ Delivery request #{req.id} created successfully!",
                reply_markup=student_persistent_menu(),
            )
        except Exception as exc:
            logger.error(f"Failed to create request: {exc}")
            await callback.message.answer(f"❌ Error creating request: {exc}")
    else:
        await state.clear()
        await callback.message.edit_text(
            "✅ Delivery request created successfully!",
            reply_markup=student_persistent_menu(),
        )