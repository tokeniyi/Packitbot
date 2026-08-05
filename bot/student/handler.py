"""
Refactoring Changes:
1. Removed matric_number from states, step handlers, and review keyboard.
2. Direct Flow: Full Name -> Hall Selection -> Phone Number -> Confirm/Review Screen.
3. Automatically retrieves `username` from Telegram's callback.from_user on submission.
4. Preserved single-field editing flag logic.
"""

from aiogram.filters import state
from bot.core.constants.quick_replies import BTN_MY_REQUESTS, BTN_HELP, BTN_MY_PROFILE
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.student_profile import StudentProfile
from bot.student.states import StudentRegistrationFSM, StudentProfileFSM
from bot.core.models.user import User
from bot.core.constants.commands import CMD_NEW_REQUEST, CMD_MY_REQUESTS, CMD_PROFILE
from bot.core.constants.enums import AccountStatus, RequestStatus, VerificationStatus
import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select

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
    MSG_HELP,
)
from bot.core.keyboards.common_kb import HomeButton
from bot.core.utils.validators import validate_full_name, validate_phone
from bot.student.keyboards import hall_selection_keyboard, student_persistent_menu
from bot.student.service import register_student
from bot.student.states import StudentRegistrationFSM

logger = logging.getLogger(__name__)
student_router = Router()


async def _resolve_user_id(telegram_id: int, session) -> int | None:
    """Resolves a Telegram user ID to the internal users.id."""
    from sqlalchemy import select
    from bot.core.models.user import User

    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    return user.id if user else None


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

    # Safely retrieve full_name checking common key variations or falling back to Telegram full name
    full_name = (
        data.get("full_name") 
        or data.get("name") 
        or callback.from_user.full_name
    )

    # Safely retrieve hall checking common key variations
    hall = data.get("hall_of_residence") or data.get("hall") or "Unknown Hall"

    # Automatically extract Telegram username from callback event
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


# ------------------------------------------------------------------
# Phase 12: Delivery Request Creation FSM Flow  request
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


# 1. Start Request Handler
@student_router.message(F.text == "📦 Request Delivery")  # Matched persistent keyboard text
@student_router.message(F.text == "📦 New Request")      # Kept as alias
@student_router.message(Command(CMD_NEW_REQUEST))
async def start_request_creation(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(RequestCreateFSM.entering_pickup_detail)
    await message.answer(
        _req_step_prompt(1, 11, "Enter pickup detail (e.g. Room 102, Esther Hall):")
    )


# 2. Cancel Request Handler
@student_router.message(Command("cancel_request"))
@student_router.callback_query(F.data == "req_cancel")
async def cancel_request_creation(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    msg = "Request creation cancelled."

    if isinstance(event, CallbackQuery):
        await event.answer()
        # Edit the inline message to remove old buttons and show cancellation message
        await event.message.edit_text(msg)
        # Send persistent reply keyboard menu
        await event.message.answer("Main Menu:", reply_markup=student_persistent_menu())
    else:
        # Standard text message command response
        await event.answer(msg, reply_markup=student_persistent_menu())


@student_router.message(F.text == BTN_HELP)
async def show_help(message: Message) -> None:
    await message.answer(
        MSG_HELP,
        parse_mode="HTML",
        reply_markup=student_persistent_menu()
    )

@student_router.message(Command(CMD_PROFILE))
@student_router.message(F.text == BTN_MY_PROFILE)
async def _show_profile(target: Message | CallbackQuery, state: FSMContext, session=None, user_id: int | None = None) -> None:
    """Renders the student profile view. Used by show_profile and after profile updates."""
    if session is None:
        markup = student_persistent_menu()
        if isinstance(target, CallbackQuery):
            await target.message.answer("Something went wrong. Please try again.", reply_markup=markup)
        else:
            await target.answer("Something went wrong. Please try again.", reply_markup=markup)
        return

    uid = user_id or (target.from_user.id if isinstance(target, CallbackQuery) else target.from_user.id)

    result = await session.execute(select(User).where(User.telegram_id == uid))
    user = result.scalar_one_or_none()

    if user is None:
        markup = student_persistent_menu()
        if isinstance(target, CallbackQuery):
            await target.message.answer("Profile not found.", reply_markup=markup)
        else:
            await target.answer("Profile not found.", reply_markup=markup)
        return

    result = await session.execute(select(StudentProfile).where(StudentProfile.user_id == user.id))
    profile = result.scalar_one_or_none()

    if user.account_status == AccountStatus.BANNED:
        status_text = "🔴 Suspended"
    elif profile is None or profile.verification_status == VerificationStatus.UNVERIFIED:
        status_text = "🟡 Pending Verification"
    else:
        status_text = "🟢 Active"

    phone = user.phone_number or "Not Set"
    default_hall = profile.hall_of_residence if profile else "Not Set"

    full_name = user.full_name or "Not Set"
    first_name = full_name.split(" ")[0] if full_name != "Not Set" else "N/A"
    last_name = " ".join(full_name.split(" ")[1:]) if full_name != "Not Set" and len(full_name.split(" ")) > 1 else ""
    name_display = f"{first_name} {last_name}".strip() if last_name else first_name

    result = await session.execute(
        select(func.count(DeliveryRequest.id))
        .where(
            DeliveryRequest.student_id == user.id,
            DeliveryRequest.status.in_(
                {
                    RequestStatus.PENDING,
                    RequestStatus.ASSIGNED,
                    RequestStatus.ACCEPTED,
                    RequestStatus.EN_ROUTE_TO_PICKUP,
                    RequestStatus.PICKED_UP,
                    RequestStatus.IN_TRANSIT,
                }
            ),
        )
    )
    active_requests = result.scalar() or 0

    result = await session.execute(
        select(func.count(DeliveryRequest.id))
        .where(
            DeliveryRequest.student_id == user.id,
            DeliveryRequest.status == RequestStatus.DELIVERED,
        )
    )
    completed_deliveries = result.scalar() or 0

    result = await session.execute(
        select(func.count(DeliveryRequest.id))
        .where(
            DeliveryRequest.student_id == user.id,
            DeliveryRequest.status == RequestStatus.CANCELLED,
        )
    )
    cancelled_requests = result.scalar() or 0

    text = (
        "👤 <b>Student Profile</b>\n\n"
        f"• <b>Name:</b> {name_display}\n"
        f"• <b>Telegram ID:</b> <code>{uid}</code>\n"
        f"• <b>Phone Number:</b> {phone}\n"
        f"• <b>Default Hall:</b> {default_hall}\n"
        f"• <b>Status:</b> {status_text}\n\n"
        "📊 <b>Delivery Stats:</b>\n"
        f"• Active Requests: {active_requests}\n"
        f"• Completed Deliveries: {completed_deliveries}\n"
        f"• Cancelled Requests: {cancelled_requests}\n\n"
        "──────────────────"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Edit Phone", callback_data="profile_edit_phone"),
                InlineKeyboardButton(text="🏢 Set Default Hall", callback_data="profile_set_hall"),
            ],
            [
                InlineKeyboardButton(text="📦 My Requests", callback_data="my_reqs_list"),
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="home"),
            ],
        ]
    )

    if isinstance(target, CallbackQuery):
        await target.message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


@student_router.message(Command(CMD_PROFILE))
@student_router.message(F.text == BTN_MY_PROFILE)
async def show_profile(message: Message, state: FSMContext, session=None) -> None:
    await state.clear()
    await _show_profile(message, state, session=session)


# @student_router.message(StudentProfileFSM.editing_phone)
@student_router.callback_query(F.data == "profile_edit_phone")
async def profile_edit_phone(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(StudentProfileFSM.editing_phone)
    await callback.message.answer("✏️ Enter your new phone number (e.g. 08012345678):")


@student_router.callback_query(F.data == "profile_set_hall")
async def profile_set_hall(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(StudentProfileFSM.editing_hall)
    await callback.message.answer("🏢 Select your default Hall of Residence:", reply_markup=req_hall_selection_keyboard())


@student_router.message(StudentProfileFSM.editing_phone)
async def process_profile_phone_edit(message: Message, state: FSMContext, session=None) -> None:
    from bot.core.utils.validators import validate_phone
    from bot.core.models.user import User

    try:
        phone = validate_phone(message.text)
    except Exception as exc:
        await message.answer(f"❌ {exc}")
        return

    if session is None:
        await message.answer("Something went wrong. Please try again.", reply_markup=student_persistent_menu())
        return

    user_id = message.from_user.id
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        await message.answer("Profile not found.", reply_markup=student_persistent_menu())
        await state.clear()
        return

    user.phone_number = phone
    await session.commit()
    await state.clear()
    await message.answer("✅ Phone number updated successfully.", reply_markup=student_persistent_menu())
    await _show_profile(message, state, session=session, user_id=user_id)


@student_router.callback_query(StudentProfileFSM.editing_hall, F.data.startswith("req_hall:"))
async def process_profile_hall_edit(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    from bot.core.models.student_profile import StudentProfile
    from bot.core.models.user import User

    hall = callback.data.split(":", 1)[1]
    await callback.answer(f"Selected Hall: {hall}")

    if session is None:
        await callback.message.answer("Something went wrong. Please try again.", reply_markup=student_persistent_menu())
        return

    user_id = callback.from_user.id

    # Fetch the User to get the student profile
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        await callback.message.answer("Profile not found.", reply_markup=student_persistent_menu())
        await state.clear()
        return

    # Fetch the StudentProfile
    result = await session.execute(select(StudentProfile).where(StudentProfile.user_id == user.id))
    profile = result.scalar_one_or_none()

    if profile is None:
        await callback.message.answer("Student profile not found.", reply_markup=student_persistent_menu())
        await state.clear()
        return

    profile.hall_of_residence = hall
    await session.commit()
    await state.clear()
    await callback.message.answer("✅ Default hall updated successfully.", reply_markup=student_persistent_menu())
    await _show_profile(callback, state, session=session, user_id=user_id)


# await callback.message.edit_text(MSG_EMPTY_STATE_REQUESTS, reply_markup=student_persistent_menu())
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

#  profile_my_requests
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

        keyboard_map = {
            "hall": req_hall_selection_keyboard(),
            "luggage_size": luggage_size_keyboard(),
            "preferred_date": date_quick_pick_keyboard(),
            "preferred_time_window": time_window_keyboard(),
            "special_instructions": skip_or_cancel_keyboard(skip_callback="req_skip_instructions"),
            "dropoff_landmark": skip_or_cancel_keyboard(skip_callback="req_skip_landmark"),
        }
        reply_markup = keyboard_map.get(field)

        await callback.message.answer(
            f"✏️ Editing {field.replace('_', ' ').title()}:\n{prompt_text}",
            reply_markup=reply_markup,
        )


@student_router.callback_query(RequestCreateFSM.confirming_request, F.data == "req_submit")
async def submit_request_creation(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    await callback.answer()
    data = await state.get_data()

    if session is None:
        await callback.message.answer("Something went wrong. Please try again.", reply_markup=student_persistent_menu())
        return

    # Look up the user's internal id from the users table
    from sqlalchemy import select
    from bot.core.models.user import User

    user_id = await _resolve_user_id(callback.from_user.id, session)
    if user_id is None:
        await callback.message.answer("User profile not found.", reply_markup=student_persistent_menu())
        return

    dto = CreateRequestDTO(
        student_id=user_id,
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

    service = RequestService(session)
    try:
        req, event = await service.create_request(dto)
        await state.clear()
        await callback.message.answer(
            f"✅ Delivery request #{req.id} created successfully!",
            reply_markup=student_persistent_menu(),
        )
    except Exception as exc:
        logger.error(f"Failed to create request: {exc}")
        await callback.message.answer(f"❌ Error creating request: {exc}")


# ------------------------------------------------------------------
# Phase 13: Student Request View & Detail Handlers
# ------------------------------------------------------------------

from bot.core.constants.messages import (
    MSG_EMPTY_STATE_REQUESTS,
    MSG_STATUS_PENDING,
    MSG_STATUS_ASSIGNED,
    MSG_STATUS_ACCEPTED,
    MSG_STATUS_REJECTED_BY_DRIVER,
    MSG_STATUS_EN_ROUTE_TO_PICKUP,
    MSG_STATUS_PICKED_UP,
    MSG_STATUS_IN_TRANSIT,
    MSG_STATUS_DELIVERED,
    MSG_STATUS_CANCELLED,
    MSG_STATUS_FAILED,
)
from bot.core.utils.pagination import paginate
from bot.request.repository import RequestRepository
from bot.student.keyboards import my_requests_list_keyboard, request_detail_keyboard

STATUS_DISPLAY_MAP = {
    "pending": MSG_STATUS_PENDING,
    "assigned": MSG_STATUS_ASSIGNED,
    "accepted": MSG_STATUS_ACCEPTED,
    "rejected_by_driver": MSG_STATUS_REJECTED_BY_DRIVER,
    "en_route_to_pickup": MSG_STATUS_EN_ROUTE_TO_PICKUP,
    "picked_up": MSG_STATUS_PICKED_UP,
    "in_transit": MSG_STATUS_IN_TRANSIT,
    "delivered": MSG_STATUS_DELIVERED,
    "cancelled": MSG_STATUS_CANCELLED,
    "failed": MSG_STATUS_FAILED,
}

STATUS_PROGRESS_INDICATORS = {
    "pending": "📝 Step 1/6 • We've received your request",
    "assigned": "👤 Step 2/6 • A driver has been assigned",
    "accepted": "✅ Step 3/6 • Your driver accepted the request",
    "en_route_to_pickup": "🚗 Step 4/6 • Your driver is on the way to pick up your package",
    "picked_up": "📦 Step 5/6 • Your package has been picked up",
    "in_transit": "🛣️ Step 6/6 • Your package is on its way",
    "delivered": "🎉 Completed • Your package has been delivered",
    "cancelled": "❌ This request was cancelled",
    "failed": "⚠️ Delivery couldn't be completed",
}


def _format_request_detail(req) -> str:
    status_key = req.status.value if hasattr(req.status, "value") else str(req.status)
    status_label = STATUS_DISPLAY_MAP.get(status_key, status_key.replace("_", " ").title())
    progress = STATUS_PROGRESS_INDICATORS.get(status_key, "")

    driver_info = "Not assigned yet"
    if req.driver:
        d_name = req.driver.full_name or "Driver"
        d_phone = req.driver.phone_number or "N/A"
        driver_info = f"{d_name} ({d_phone})"
        if hasattr(req.driver, "driver_profile") and req.driver.driver_profile:
            dp = req.driver.driver_profile
            driver_info += f"\n  Vehicle: {dp.vehicle_type} ({dp.plate_number})"

    luggage_size_str = req.luggage_size.value if hasattr(req.luggage_size, "value") else str(req.luggage_size)

    text = (
        f"📋 <b>Request Detail #{req.id}</b>\n\n"
        f"<b>Status:</b> {status_label}\n"
        f"<b>Progress:</b> {progress}\n\n"
        f"📍 <b>Pickup Detail:</b> {req.pickup_detail}\n"
        f"🏛️ <b>Hall of Residence:</b> {req.hall_of_residence}\n"
        f"🎯 <b>Dropoff Address:</b> {req.dropoff_address}\n"
        f"🗺️ <b>Landmark:</b> {req.dropoff_landmark or 'None'}\n\n"
        f"👤 <b>Recipient:</b> {req.recipient_name} ({req.recipient_phone})\n"
        f"📦 <b>Luggage:</b> {req.luggage_count}x {luggage_size_str.title()}\n"
        f"📅 <b>Preferred Date:</b> {req.preferred_date}\n"
        f"⏰ <b>Time Window:</b> {req.preferred_time_window}\n"
        f"📝 <b>Special Instructions:</b> {req.special_instructions or 'None'}\n\n"
        f"🚗 <b>Driver Details:</b> {driver_info}\n"
    )
    if req.cancelled_by:
        cancelled_by_str = req.cancelled_by.value if hasattr(req.cancelled_by, "value") else str(req.cancelled_by)
        text += f"\n🚫 <b>Cancelled By:</b> {cancelled_by_str.title()}"
        if req.cancellation_reason:
            text += f"\n<b>Reason:</b> {req.cancellation_reason}"

    return text


@student_router.message(F.text == BTN_MY_REQUESTS)
@student_router.message(Command(CMD_MY_REQUESTS))
async def show_my_requests_list(message: Message, session=None, page: int = 1) -> None:
    if session is None:
        await message.answer(MSG_EMPTY_STATE_REQUESTS, reply_markup=student_persistent_menu())
        return

    repo = RequestRepository(session)
    user_id = await _resolve_user_id(message.from_user.id, session)
    if user_id is None:
        await message.answer("User profile not found.", reply_markup=student_persistent_menu())
        return
    requests = await repo.get_history_for_student(student_id=user_id, page=page)

    if not requests:
        await message.answer(MSG_EMPTY_STATE_REQUESTS, reply_markup=student_persistent_menu())
        return

    paginated_page = paginate(requests, page=page)
    kb = my_requests_list_keyboard(paginated_page.items, page=paginated_page.page, total_pages=paginated_page.total_pages)
    await message.answer("📋 <b>Your Delivery Requests:</b>", parse_mode="HTML", reply_markup=kb)


@student_router.callback_query(F.data == "my_reqs_list")
@student_router.callback_query(F.data.startswith("my_reqs_page:"))
async def my_requests_page_callback(callback: CallbackQuery, session=None) -> None:
    await callback.answer()
    page = 1
    if ":" in callback.data:
        try:
            page = int(callback.data.split(":")[1])
        except ValueError:
            page = 1

    if session is None:
        await callback.message.answer(MSG_EMPTY_STATE_REQUESTS, reply_markup=student_persistent_menu())
        return

    repo = RequestRepository(session)
    user_id = await _resolve_user_id(callback.from_user.id, session)
    if user_id is None:
        await callback.message.answer("User profile not found.", reply_markup=student_persistent_menu())
        return
    requests = await repo.get_history_for_student(student_id=user_id, page=page)

    if not requests:
        await callback.message.answer(MSG_EMPTY_STATE_REQUESTS, reply_markup=student_persistent_menu())
        return

    paginated_page = paginate(requests, page=page)
    kb = my_requests_list_keyboard(paginated_page.items, page=paginated_page.page, total_pages=paginated_page.total_pages)
    await callback.message.edit_text("📋 <b>Your Delivery Requests:</b>", parse_mode="HTML", reply_markup=kb)


@student_router.callback_query(F.data.startswith("my_req_detail:"))
async def show_request_detail(callback: CallbackQuery, session=None) -> None:
    await callback.answer()
    req_id_str = callback.data.split(":")[1]
    try:
        req_id = int(req_id_str)
    except ValueError:
        await callback.message.answer("⚠️ Invalid request ID.", reply_markup=HomeButton())
        return

    if session is None:
        await callback.message.answer("⚠️ Session unavailable.", reply_markup=HomeButton())
        return

    repo = RequestRepository(session)
    req = await repo.get_by_id(req_id)

    user_id = await _resolve_user_id(callback.from_user.id, session)
    if not req or req.student_id != user_id:
        await callback.message.answer("⚠️ Request not found or permission denied.", reply_markup=HomeButton())
        return

    text = _format_request_detail(req)
    kb = request_detail_keyboard(req)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@student_router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()


# ------------------------------------------------------------------
# Phase 14: Student Request Edit Flow (RequestUpdateFSM)
# ------------------------------------------------------------------

from bot.core.exceptions import (
    InvalidStatusTransitionError,
    NotFoundError,
    PackitbotError,
    PermissionDeniedError,
    ValidationError,
)
from bot.request.schemas import UpdateRequestDTO
from bot.student.keyboards import (
    request_edit_fields_keyboard,
    request_edit_confirm_keyboard,
)
from bot.student.states import RequestUpdateFSM


@student_router.callback_query(F.data.startswith("my_req_edit:"))
async def start_request_edit(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    await callback.answer()
    req_id_str = callback.data.split(":")[1]
    try:
        req_id = int(req_id_str)
    except ValueError:
        await callback.message.answer("Invalid request ID.")
        return

    if session is None:
        await callback.message.answer("Session unavailable.")
        return

    repo = RequestRepository(session)
    req = await repo.get_by_id(req_id)

    user_id = await _resolve_user_id(callback.from_user.id, session)
    if not req or req.student_id != user_id:
        await callback.message.answer("Request not found or permission denied.")
        return

    if req.status != RequestStatus.PENDING:
        await callback.message.answer("⚠️ Only requests in PENDING status can be edited.")
        return

    await state.clear()
    await state.set_state(RequestUpdateFSM.selecting_field)
    await state.update_data(request_id=req_id, changes={})

    kb = request_edit_fields_keyboard(req_id)
    await callback.message.edit_text(
        f"✏️ <b>Edit Request #{req_id}</b>\n\nSelect a field to modify:",
        parse_mode="HTML",
        reply_markup=kb,
    )


@student_router.callback_query(RequestUpdateFSM.selecting_field, F.data.startswith("req_update_field:"))
async def select_field_to_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    req_id = int(parts[1])
    field_name = parts[2]

    await state.update_data(current_field=field_name)
    await state.set_state(RequestUpdateFSM.editing_value)

    field_prompts = {
        "pickup_detail": ("Pickup Detail", "Enter new pickup detail:"),
        "dropoff_address": ("Dropoff Address", "Enter new dropoff address:"),
        "dropoff_landmark": ("Dropoff Landmark", "Enter new dropoff landmark (or type 'none' to clear):"),
        "hall_of_residence": ("Hall of Residence", "Select new Hall of Residence:"),
        "recipient_name": ("Recipient Name", "Enter new recipient full name:"),
        "recipient_phone": ("Recipient Phone", "Enter new recipient phone number:"),
        "luggage_size": ("Luggage Size", "Select new luggage size:"),
        "luggage_count": ("Luggage Count", "Enter new luggage count (1-10):"),
        "preferred_date": ("Preferred Date", "Select new preferred date or type YYYY-MM-DD:"),
        "preferred_time_window": ("Preferred Time Window", "Select new time window:"),
        "special_instructions": ("Special Instructions", "Enter new special instructions (or type 'none' to clear):"),
    }

    title, prompt = field_prompts.get(field_name, (field_name.replace("_", " ").title(), "Enter new value:"))

    if field_name == "hall_of_residence":
        await callback.message.answer(f"✏️ <b>Editing {title}</b>\n\n{prompt}", parse_mode="HTML", reply_markup=req_hall_selection_keyboard())
    elif field_name == "luggage_size":
        await callback.message.answer(f"✏️ <b>Editing {title}</b>\n\n{prompt}", parse_mode="HTML", reply_markup=luggage_size_keyboard())
    elif field_name == "preferred_date":
        await callback.message.answer(f"✏️ <b>Editing {title}</b>\n\n{prompt}", parse_mode="HTML", reply_markup=date_quick_pick_keyboard())
    elif field_name == "preferred_time_window":
        await callback.message.answer(f"✏️ <b>Editing {title}</b>\n\n{prompt}", parse_mode="HTML", reply_markup=time_window_keyboard())
    else:
        await callback.message.answer(f"✏️ <b>Editing {title}</b>\n\n{prompt}", parse_mode="HTML")


@student_router.callback_query(RequestUpdateFSM.editing_value, F.data.startswith("req_hall:"))
async def process_edit_hall_callback(callback: CallbackQuery, state: FSMContext) -> None:
    hall = callback.data.split(":", 1)[1]
    await callback.answer(f"Selected Hall: {hall}")
    await _store_field_change(callback, state, "hall_of_residence", hall)


@student_router.callback_query(RequestUpdateFSM.editing_value, F.data.startswith("req_size:"))
async def process_edit_size_callback(callback: CallbackQuery, state: FSMContext) -> None:
    size = callback.data.split(":", 1)[1]
    await callback.answer(f"Selected Size: {size}")
    await _store_field_change(callback, state, "luggage_size", LuggageSize(size))


@student_router.callback_query(RequestUpdateFSM.editing_value, F.data.startswith("req_date:"))
async def process_edit_date_callback(callback: CallbackQuery, state: FSMContext) -> None:
    dt_str = callback.data.split(":", 1)[1]
    await callback.answer(f"Selected Date: {dt_str}")
    dt = date.fromisoformat(dt_str)
    await _store_field_change(callback, state, "preferred_date", dt)


@student_router.callback_query(RequestUpdateFSM.editing_value, F.data.startswith("req_time:"))
async def process_edit_time_callback(callback: CallbackQuery, state: FSMContext) -> None:
    slot = callback.data.split(":", 1)[1]
    await callback.answer(f"Selected Time: {slot}")
    await _store_field_change(callback, state, "preferred_time_window", slot)


@student_router.message(RequestUpdateFSM.editing_value)
async def process_edit_value_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field_name = data.get("current_field")
    text = message.text.strip() if message.text else ""

    parsed_value = None
    try:
        if field_name == "pickup_detail":
            parsed_value = validate_pickup_detail(text)
        elif field_name == "dropoff_address":
            parsed_value = validate_dropoff_address(text)
        elif field_name == "dropoff_landmark":
            parsed_value = None if text.lower() == "none" else text
        elif field_name == "recipient_name":
            parsed_value = validate_recipient_name(text)
        elif field_name == "recipient_phone":
            parsed_value = validate_phone(text)
        elif field_name == "luggage_count":
            parsed_value = validate_luggage_count(text)
        elif field_name == "preferred_date":
            parsed_value = validate_preferred_date(text)
        elif field_name == "preferred_time_window":
            parsed_value = validate_time_window(text)
        elif field_name == "special_instructions":
            parsed_value = None if text.lower() == "none" else validate_special_instructions(text)
        else:
            parsed_value = text
    except Exception as exc:
        await message.answer(f"❌ {exc}")
        return

    await _store_field_change(message, state, field_name, parsed_value)


async def _store_field_change(
    target: Message | CallbackQuery,
    state: FSMContext,
    field_name: str,
    new_value: object,
) -> None:
    data = await state.get_data()
    changes = data.get("changes", {})
    changes[field_name] = new_value

    await state.update_data(changes=changes)
    await state.set_state(RequestUpdateFSM.confirming_update)

    req_id = data["request_id"]
    formatted_diff = []
    for f_name, val in changes.items():
        val_str = val.value if hasattr(val, "value") else str(val)
        formatted_diff.append(f"• <b>{f_name.replace('_', ' ').title()}:</b> {val_str}")

    diff_text = "\n".join(formatted_diff)
    prompt = (
        f"📝 <b>Confirm Changes for Request #{req_id}</b>\n\n"
        f"<b>Proposed Changes:</b>\n{diff_text}\n\n"
        "Do you want to apply these changes?"
    )

    kb = request_edit_confirm_keyboard(req_id)
    if isinstance(target, CallbackQuery):
        await target.message.answer(prompt, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(prompt, parse_mode="HTML", reply_markup=kb)


@student_router.callback_query(RequestUpdateFSM.confirming_update, F.data.startswith("req_update_confirm:"))
async def confirm_request_update(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    await callback.answer()
    data = await state.get_data()
    req_id = data["request_id"]
    changes = data.get("changes", {})

    if not changes:
        await callback.message.answer("No changes to save.")
        await state.clear()
        return

    if session is None:
        await callback.message.answer("Session unavailable.")
        return

    actor_id = await _resolve_user_id(callback.from_user.id, session)
    if actor_id is None:
        await callback.message.answer("User profile not found.")
        await state.clear()
        return

    service = RequestService(session)
    dto = UpdateRequestDTO(
        request_id=req_id,
        actor_id=actor_id,
        changed_fields=changes,
    )

    try:
        updated_req = await service.update_request(dto)
        await state.clear()
        await callback.message.answer(
            f"✅ Request #{updated_req.id} updated successfully!",
            reply_markup=student_persistent_menu(),
        )
    except PermissionDeniedError:
        await state.clear()
        await callback.message.answer(
            "⚠️ Request can no longer be edited because its status is no longer PENDING.",
            reply_markup=student_persistent_menu(),
        )
    except (NotFoundError, ValidationError, PackitbotError) as exc:
        await callback.message.answer(f"❌ Failed to update request: {exc}")


# ------------------------------------------------------------------
# Phase 15: Student Request Cancellation Flow
# ------------------------------------------------------------------

from bot.core.constants.enums import CancelledBy, DriverAvailability
from bot.core.models.driver_profile import DriverProfile
from bot.request.schemas import CancelRequestDTO
from bot.student.keyboards import request_cancel_confirm_keyboard


@student_router.callback_query(F.data.startswith("my_req_cancel:"))
async def prompt_cancel_request(callback: CallbackQuery, session=None) -> None:
    await callback.answer()
    req_id_str = callback.data.split(":")[1]
    try:
        req_id = int(req_id_str)
    except ValueError:
        await callback.message.answer("Invalid request ID.")
        return

    if session is None:
        await callback.message.answer("Session unavailable.")
        return

    repo = RequestRepository(session)
    req = await repo.get_by_id(req_id)

    user_id = await _resolve_user_id(callback.from_user.id, session)
    if not req or req.student_id != user_id:
        await callback.message.answer("Request not found or permission denied.")
        return

    if req.status not in (RequestStatus.PENDING, RequestStatus.ASSIGNED, RequestStatus.ACCEPTED):
        await callback.message.answer("⚠️ Request cannot be cancelled in its current status.")
        return

    kb = request_cancel_confirm_keyboard(req_id)
    await callback.message.edit_text(
        f"⚠️ <b>Are you sure you want to cancel Request #{req_id}?</b>\n\nThis action cannot be undone.",
        parse_mode="HTML",
        reply_markup=kb,
    )


@student_router.callback_query(F.data.startswith("my_req_cancel_confirm:"))
async def confirm_cancel_request(callback: CallbackQuery, session=None) -> None:
    await callback.answer()
    req_id_str = callback.data.split(":")[1]
    try:
        req_id = int(req_id_str)
    except ValueError:
        await callback.message.answer("Invalid request ID.")
        return

    if session is None:
        await callback.message.answer("Session unavailable.")
        return

    actor_id = await _resolve_user_id(callback.from_user.id, session)
    if actor_id is None:
        await callback.message.answer("User profile not found.")
        await state.clear()
        return

    service = RequestService(session)
    dto = CancelRequestDTO(
        request_id=req_id,
        actor_id=actor_id,
        cancelled_by=CancelledBy.STUDENT,
        cancellation_reason="Cancelled by student via bot",
    )

    try:
        updated_req, event = await service.cancel_request(dto)

        # Restore driver availability if request had assigned/accepted driver
        if updated_req.driver_id is not None:
            driver = await session.get(DriverProfile, updated_req.driver_id)
            if driver:
                driver.availability = DriverAvailability.AVAILABLE
                await session.flush()

        await callback.message.answer(
            f"🚫 Request #{updated_req.id} has been cancelled successfully.",
            reply_markup=student_persistent_menu(),
        )
    except (PermissionDeniedError, InvalidStatusTransitionError) as exc:
        await callback.message.answer(
            f"⚠️ Request cancellation failed: {exc}",
            reply_markup=student_persistent_menu(),
        )
    except (NotFoundError, ValidationError, PackitbotError) as exc:
        await callback.message.answer(f"❌ Failed to cancel request: {exc}")


# ------------------------------------------------------------------
# Phase 22: Feedback Flow Handlers & Driver Rating Recalculation
# ------------------------------------------------------------------

from sqlalchemy import func, select
from bot.core.models.feedback import Feedback
from bot.request.schemas import CreateFeedbackDTO
from bot.student.keyboards import feedback_rating_keyboard, feedback_comment_skip_keyboard
from bot.student.states import FeedbackFSM


async def _recalculate_driver_rating(session, driver_id: int) -> None:
    """Recalculates driver's running average rating and total deliveries count."""
    driver_profile = await session.get(DriverProfile, driver_id)
    if not driver_profile:
        return

    stmt = (
        select(func.avg(Feedback.rating), func.count(Feedback.id))
        .join(DeliveryRequest, Feedback.request_id == DeliveryRequest.id)
        .where(DeliveryRequest.driver_id == driver_id)
    )
    res = await session.execute(stmt)
    avg_rating, total_count = res.one()

    driver_profile.rating_avg = round(float(avg_rating or 0.0), 2)
    driver_profile.total_deliveries = total_count or 0
    await session.flush()


@student_router.callback_query(F.data.startswith("my_req_rate:"))
async def prompt_feedback_rating(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    await callback.answer()
    req_id_str = callback.data.split(":")[1]
    try:
        req_id = int(req_id_str)
    except ValueError:
        await callback.message.answer("Invalid request ID.")
        return

    if session is None:
        await callback.message.answer("Session unavailable.")
        return

    repo = RequestRepository(session)
    req = await repo.get_by_id(req_id)

    user_id = await _resolve_user_id(callback.from_user.id, session)
    if not req or req.student_id != user_id:
        await callback.message.answer("Request not found or permission denied.")
        return

    if req.status != RequestStatus.DELIVERED:
        await callback.message.answer("⚠️ Only DELIVERED requests can be rated.")
        return

    existing_feedback = await repo.session.execute(
        select(Feedback).where(Feedback.request_id == req_id)
    )
    if existing_feedback.scalar_one_or_none():
        await callback.message.answer("⚠️ You have already submitted feedback for this delivery.")
        return

    await state.clear()
    await state.set_state(FeedbackFSM.selecting_rating)
    await state.update_data(request_id=req_id)

    kb = feedback_rating_keyboard(req_id)
    await callback.message.edit_text(
        f"⭐ <b>Rate Delivery #{req_id}</b>\n\n"
        "How would you rate your driver's service? (1-5 stars)",
        parse_mode="HTML",
        reply_markup=kb,
    )


@student_router.callback_query(FeedbackFSM.selecting_rating, F.data.startswith("rate:"))
async def process_rating_selection(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    req_id = int(parts[1])
    rating = int(parts[2])

    await state.update_data(request_id=req_id, rating=rating)
    await state.set_state(FeedbackFSM.entering_comment)

    kb = feedback_comment_skip_keyboard(req_id)
    await callback.message.edit_text(
        f"⭐ <b>Rating: {'⭐' * rating} ({rating}/5)</b>\n\n"
        "Would you like to leave an optional comment for your driver?\n"
        "Type your comment below or click <b>Skip</b>.",
        parse_mode="HTML",
        reply_markup=kb,
    )


@student_router.callback_query(FeedbackFSM.entering_comment, F.data.startswith("feedback_skip_comment:"))
async def process_feedback_skip_comment(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    await callback.answer()
    await _finalize_feedback_submission(callback, state, session, comment=None)


@student_router.message(FeedbackFSM.entering_comment)
async def process_feedback_comment_message(message: Message, state: FSMContext, session=None) -> None:
    comment = message.text.strip() if message.text else None
    await _finalize_feedback_submission(message, state, session, comment=comment)


async def _finalize_feedback_submission(
    target: Message | CallbackQuery,
    state: FSMContext,
    session,
    comment: str | None,
) -> None:
    data = await state.get_data()
    req_id = data.get("request_id")
    rating = data.get("rating")

    if not req_id or not rating:
        await state.clear()
        err_msg = "Feedback session expired or invalid state."
        if isinstance(target, CallbackQuery):
            await target.message.answer(err_msg)
        else:
            await target.answer(err_msg)
        return

    if session is None:
        err_msg = "Session unavailable."
        if isinstance(target, CallbackQuery):
            await target.message.answer(err_msg)
        else:
            await target.answer(err_msg)
        return

    service = RequestService(session)
    user_id = await _resolve_user_id(target.from_user.id, session)
    if user_id is None:
        err_msg = "User profile not found."
        if isinstance(target, CallbackQuery):
            await target.message.answer(err_msg, reply_markup=student_persistent_menu())
        else:
            await target.answer(err_msg, reply_markup=student_persistent_menu())
        return
    dto = CreateFeedbackDTO(
        request_id=req_id,
        student_id=user_id,
        rating=rating,
        comment=comment,
    )

    try:
        feedback, event = await service.submit_feedback(dto)

        # Retrieve request to get driver_id and recalculate running average rating
        req_repo = RequestRepository(session)
        req = await req_repo.get_by_id(req_id)
        if req and req.driver_id:
            await _recalculate_driver_rating(session, req.driver_id)

        await state.clear()
        success_msg = f"🎉 <b>Thank you!</b> Your feedback for Request #{req_id} has been submitted."

        if isinstance(target, CallbackQuery):
            await target.message.answer(success_msg, parse_mode="HTML", reply_markup=student_persistent_menu())
        else:
            await target.answer(success_msg, parse_mode="HTML", reply_markup=student_persistent_menu())

    except (PermissionDeniedError, ValidationError, PackitbotError) as exc:
        await state.clear()
        err_msg = f"❌ Failed to submit feedback: {exc}"
        if isinstance(target, CallbackQuery):
            await target.message.answer(err_msg, reply_markup=student_persistent_menu())
        else:
            await target.answer(err_msg, reply_markup=student_persistent_menu())