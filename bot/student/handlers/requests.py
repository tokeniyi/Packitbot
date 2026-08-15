"""Student delivery request handlers for creation, history, editing, and cancellation."""

import logging
from datetime import date
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.core.constants.commands import CMD_MY_REQUESTS, CMD_NEW_REQUEST
from bot.core.constants.enums import (
    CancelledBy,
    DriverAvailability,
    LuggageSize,
    RequestStatus,
)
from bot.core.constants.messages import (
    ErrorMessages,
    MSG_EMPTY_STATE_REQUESTS,
    MSG_STATUS_ACCEPTED,
    MSG_STATUS_ASSIGNED,
    MSG_STATUS_CANCELLED,
    MSG_STATUS_DELIVERED,
    MSG_STATUS_EN_ROUTE_TO_PICKUP,
    MSG_STATUS_FAILED,
    MSG_STATUS_IN_TRANSIT,
    MSG_STATUS_PENDING,
    MSG_STATUS_PICKED_UP,
    MSG_STATUS_REJECTED_BY_DRIVER,
    RequestMessages,
    SuccessMessages,
)
from bot.core.constants.quick_replies import BTN_MY_REQUESTS
from bot.core.exceptions import (
    InvalidStatusTransitionError,
    NotFoundError,
    PackitbotError,
    PermissionDeniedError,
    ValidationError,
)
from bot.core.keyboards.common_kb import HomeButton
from bot.core.models.driver_profile import DriverProfile
from bot.core.utils.formatters import format_step_prompt
from bot.core.utils.pagination import paginate
from bot.core.utils.validators import (
    validate_dropoff_address,
    validate_luggage_count,
    validate_phone,
    validate_pickup_detail,
    validate_preferred_date,
    validate_recipient_name,
    validate_special_instructions,
    validate_time_window,
)
from bot.request.repository import RequestRepository
from bot.request.schemas import CancelRequestDTO, CreateRequestDTO, UpdateRequestDTO
from bot.request.service import RequestService
from bot.student.keyboards import (
    date_quick_pick_keyboard,
    luggage_size_keyboard,
    my_requests_list_keyboard,
    req_hall_selection_keyboard,
    request_cancel_confirm_keyboard,
    request_detail_keyboard,
    request_edit_confirm_keyboard,
    request_edit_fields_keyboard,
    request_review_keyboard,
    skip_or_cancel_keyboard,
    student_persistent_menu,
    time_window_keyboard,
)
from bot.student.service import resolve_user_id
from bot.student.states import RequestCreateFSM, RequestUpdateFSM

logger = logging.getLogger(__name__)
requests_router = Router()

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


def _req_step_prompt(step: int, total: int = 11, prompt: str = "") -> str:
    """Format step prompt with embedded progress bar."""
    return format_step_prompt(step, total, prompt)


async def _show_request_review(target: Message | CallbackQuery, state: FSMContext) -> None:
    """Render the summary review screen for a new delivery request."""
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
        if target.message:
            await target.message.answer(summary, parse_mode="HTML", reply_markup=request_review_keyboard())
    else:
        await target.answer(summary, parse_mode="HTML", reply_markup=request_review_keyboard())


def _format_request_detail(req) -> str:
    """Format single request detail for display."""
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


# ==============================================================================
# 1. Request Creation Handlers
# ==============================================================================

@requests_router.message(F.text == "📦 Request Delivery")
@requests_router.message(F.text == "📦 New Request")
@requests_router.message(Command(CMD_NEW_REQUEST))
async def start_request_creation(message: Message, state: FSMContext) -> None:
    """Start the multi-step request creation wizard."""
    await state.clear()
    await state.set_state(RequestCreateFSM.entering_pickup_detail)
    await message.answer(
        _req_step_prompt(1, 11, RequestMessages.ENTER_PICKUP_DETAIL_PROMPT)
    )


@requests_router.message(Command("cancel_request"))
@requests_router.callback_query(F.data == "req_cancel")
async def cancel_request_creation(event: Message | CallbackQuery, state: FSMContext) -> None:
    """Cancel the delivery request creation flow."""
    await state.clear()
    msg = SuccessMessages.ACTION_CANCELLED

    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.edit_text(msg)
            await event.message.answer("Main Menu:", reply_markup=student_persistent_menu())
    else:
        await event.answer(msg, reply_markup=student_persistent_menu())


@requests_router.message(RequestCreateFSM.entering_pickup_detail)
async def process_pickup_detail(message: Message, state: FSMContext) -> None:
    """Validate and store pickup detail."""
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
    await message.answer(_req_step_prompt(2, 11, RequestMessages.ENTER_DROPOFF_ADDRESS))


@requests_router.message(RequestCreateFSM.entering_dropoff_address)
async def process_dropoff_address(message: Message, state: FSMContext) -> None:
    """Validate and store dropoff address."""
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
        _req_step_prompt(3, 11, RequestMessages.ENTER_DROPOFF_LANDMARK),
        reply_markup=skip_or_cancel_keyboard(skip_callback="req_skip_landmark"),
    )


@requests_router.callback_query(RequestCreateFSM.entering_dropoff_landmark, F.data == "req_skip_landmark")
async def skip_dropoff_landmark(callback: CallbackQuery, state: FSMContext) -> None:
    """Skip landmark entry."""
    await callback.answer()
    await state.update_data(dropoff_landmark=None)
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(callback, state)
        return

    await state.set_state(RequestCreateFSM.entering_hall)
    if callback.message:
        await callback.message.answer(
            _req_step_prompt(4, 11, RequestMessages.SELECT_HALL),
            reply_markup=req_hall_selection_keyboard(),
        )


@requests_router.message(RequestCreateFSM.entering_dropoff_landmark)
async def process_dropoff_landmark(message: Message, state: FSMContext) -> None:
    """Store landmark entry."""
    await state.update_data(dropoff_landmark=message.text.strip())
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(message, state)
        return

    await state.set_state(RequestCreateFSM.entering_hall)
    await message.answer(
        _req_step_prompt(4, 11, RequestMessages.SELECT_HALL),
        reply_markup=req_hall_selection_keyboard(),
    )


@requests_router.callback_query(RequestCreateFSM.entering_hall, F.data.startswith("req_hall:"))
async def process_hall_select(callback: CallbackQuery, state: FSMContext) -> None:
    """Select pickup hall."""
    hall = callback.data.split(":", 1)[1]
    await callback.answer(f"Hall: {hall}")
    await state.update_data(hall_of_residence=hall)

    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(callback, state)
        return

    await state.set_state(RequestCreateFSM.entering_recipient_name)
    if callback.message:
        await callback.message.answer(_req_step_prompt(5, 11, RequestMessages.ENTER_RECIPIENT_NAME))


@requests_router.message(RequestCreateFSM.entering_recipient_name)
async def process_recipient_name(message: Message, state: FSMContext) -> None:
    """Validate and store recipient name."""
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
    await message.answer(_req_step_prompt(6, 11, RequestMessages.ENTER_RECIPIENT_PHONE))


@requests_router.message(RequestCreateFSM.entering_recipient_phone)
async def process_recipient_phone(message: Message, state: FSMContext) -> None:
    """Validate and store recipient phone number."""
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
        _req_step_prompt(7, 11, RequestMessages.CHOOSE_LUGGAGE_SIZE),
        reply_markup=luggage_size_keyboard(),
    )


@requests_router.callback_query(RequestCreateFSM.selecting_luggage_size, F.data.startswith("req_size:"))
async def process_luggage_size(callback: CallbackQuery, state: FSMContext) -> None:
    """Select luggage size."""
    size = callback.data.split(":", 1)[1]
    await callback.answer(f"Size: {size}")
    await state.update_data(luggage_size=size)

    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(callback, state)
        return

    await state.set_state(RequestCreateFSM.entering_luggage_count)
    if callback.message:
        await callback.message.answer(_req_step_prompt(8, 11, RequestMessages.ENTER_LUGGAGE_COUNT.format(min=1, max=10)))


@requests_router.message(RequestCreateFSM.entering_luggage_count)
async def process_luggage_count(message: Message, state: FSMContext) -> None:
    """Validate and store luggage count."""
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
        _req_step_prompt(9, 11, RequestMessages.ENTER_PREFERRED_DATE),
        reply_markup=date_quick_pick_keyboard(),
    )


@requests_router.callback_query(RequestCreateFSM.selecting_preferred_date, F.data.startswith("req_date:"))
async def process_preferred_date_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Select preferred pickup date via callback."""
    dt_str = callback.data.split(":", 1)[1]
    await callback.answer(f"Date: {dt_str}")
    await state.update_data(preferred_date=dt_str)

    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(callback, state)
        return

    await state.set_state(RequestCreateFSM.selecting_time_window)
    if callback.message:
        await callback.message.answer(
            _req_step_prompt(10, 11, RequestMessages.CHOOSE_TIME_WINDOW),
            reply_markup=time_window_keyboard(),
        )


@requests_router.message(RequestCreateFSM.selecting_preferred_date)
async def process_preferred_date_message(message: Message, state: FSMContext) -> None:
    """Select preferred pickup date via typed text."""
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
        _req_step_prompt(10, 11, RequestMessages.CHOOSE_TIME_WINDOW),
        reply_markup=time_window_keyboard(),
    )


@requests_router.callback_query(RequestCreateFSM.selecting_time_window, F.data.startswith("req_time:"))
async def process_time_window_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Select delivery time window via button."""
    slot = callback.data.split(":", 1)[1]
    await callback.answer(f"Time: {slot}")
    await state.update_data(preferred_time_window=slot)

    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_request_review(callback, state)
        return

    await state.set_state(RequestCreateFSM.entering_special_instructions)
    if callback.message:
        await callback.message.answer(
            _req_step_prompt(11, 11, RequestMessages.ENTER_SPECIAL_INSTRUCTIONS),
            reply_markup=skip_or_cancel_keyboard(skip_callback="req_skip_instructions"),
        )


@requests_router.message(RequestCreateFSM.selecting_time_window)
async def process_time_window_message(message: Message, state: FSMContext) -> None:
    """Select delivery time window via typed text."""
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
        _req_step_prompt(11, 11, RequestMessages.ENTER_SPECIAL_INSTRUCTIONS),
        reply_markup=skip_or_cancel_keyboard(skip_callback="req_skip_instructions"),
    )


@requests_router.callback_query(RequestCreateFSM.entering_special_instructions, F.data == "req_skip_instructions")
async def skip_special_instructions(callback: CallbackQuery, state: FSMContext) -> None:
    """Skip special instructions."""
    await callback.answer()
    await state.update_data(special_instructions=None)
    await _show_request_review(callback, state)


@requests_router.message(RequestCreateFSM.entering_special_instructions)
async def process_special_instructions(message: Message, state: FSMContext) -> None:
    """Save special instructions."""
    try:
        val = validate_special_instructions(message.text)
    except Exception as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(special_instructions=val)
    await _show_request_review(message, state)


@requests_router.callback_query(RequestCreateFSM.confirming_request, F.data.startswith("req_edit:"))
async def edit_request_field(callback: CallbackQuery, state: FSMContext) -> None:
    """Edit specific field from review screen."""
    field = callback.data.split(":", 1)[1]
    await callback.answer()
    await state.update_data(is_editing=True)

    field_map = {
        "pickup_detail": (RequestCreateFSM.entering_pickup_detail, "Enter pickup detail:"),
        "dropoff_address": (RequestCreateFSM.entering_dropoff_address, "Enter dropoff address:"),
        "dropoff_landmark": (RequestCreateFSM.entering_dropoff_landmark, "Enter dropoff landmark:"),
        "hall": (RequestCreateFSM.entering_hall, RequestMessages.SELECT_HALL),
        "recipient_name": (RequestCreateFSM.entering_recipient_name, "Enter recipient name:"),
        "recipient_phone": (RequestCreateFSM.entering_recipient_phone, "Enter recipient phone number:"),
        "luggage_size": (RequestCreateFSM.selecting_luggage_size, "Select luggage size:"),
        "luggage_count": (RequestCreateFSM.entering_luggage_count, "Enter luggage count:"),
        "preferred_date": (RequestCreateFSM.selecting_preferred_date, "Select preferred pickup date:"),
        "preferred_time_window": (RequestCreateFSM.selecting_time_window, RequestMessages.CHOOSE_TIME_WINDOW),
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

        if callback.message:
            await callback.message.answer(
                f"✏️ Editing {field.replace('_', ' ').title()}:\n{prompt_text}",
                reply_markup=reply_markup,
            )


@requests_router.callback_query(RequestCreateFSM.confirming_request, F.data == "req_submit")
async def submit_request_creation(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    """Submit the completed delivery request creation form."""
    await callback.answer()
    data = await state.get_data()

    if session is None:
        if callback.message:
            await callback.message.answer(ErrorMessages.SESSION_UNAVAILABLE, reply_markup=student_persistent_menu())
        return

    user_id = await resolve_user_id(callback.from_user.id, session)
    if user_id is None:
        if callback.message:
            await callback.message.answer(ErrorMessages.USER_NOT_FOUND, reply_markup=student_persistent_menu())
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
        if callback.message:
            await callback.message.answer(
                f"✅ Delivery request #{req.id} created successfully!",
                reply_markup=student_persistent_menu(),
            )
    except Exception as exc:
        logger.error("Failed to create delivery request: %s", exc)
        if callback.message:
            await callback.message.answer(f"❌ Error creating request: {exc}")


# ==============================================================================
# 2. Request Listing & Details
# ==============================================================================

@requests_router.message(F.text == BTN_MY_REQUESTS)
@requests_router.message(Command(CMD_MY_REQUESTS))
async def show_my_requests_list(message: Message, session=None, page: int = 1) -> None:
    """Display student's delivery requests history."""
    if session is None:
        await message.answer(MSG_EMPTY_STATE_REQUESTS, reply_markup=student_persistent_menu())
        return

    repo = RequestRepository(session)
    user_id = await resolve_user_id(message.from_user.id, session)
    if user_id is None:
        await message.answer(ErrorMessages.USER_NOT_FOUND, reply_markup=student_persistent_menu())
        return
    requests = await repo.get_history_for_student(student_id=user_id, page=page)

    if not requests:
        await message.answer(MSG_EMPTY_STATE_REQUESTS, reply_markup=student_persistent_menu())
        return

    paginated_page = paginate(requests, page=page)
    kb = my_requests_list_keyboard(paginated_page.items, page=paginated_page.page, total_pages=paginated_page.total_pages)
    await message.answer(RequestMessages.REQUESTS_LIST_TITLE, parse_mode="HTML", reply_markup=kb)


@requests_router.callback_query(F.data == "my_reqs_list")
@requests_router.callback_query(F.data.startswith("my_reqs_page:"))
async def my_requests_page_callback(callback: CallbackQuery, session=None) -> None:
    """Handle pagination callback for student requests list."""
    await callback.answer()
    page = 1
    if ":" in callback.data:
        try:
            page = int(callback.data.split(":")[1])
        except ValueError:
            page = 1

    if session is None:
        if callback.message:
            await callback.message.answer(MSG_EMPTY_STATE_REQUESTS, reply_markup=student_persistent_menu())
        return

    repo = RequestRepository(session)
    user_id = await resolve_user_id(callback.from_user.id, session)
    if user_id is None:
        if callback.message:
            await callback.message.answer(ErrorMessages.USER_NOT_FOUND, reply_markup=student_persistent_menu())
        return
    requests = await repo.get_history_for_student(student_id=user_id, page=page)

    if not requests:
        if callback.message:
            await callback.message.answer(MSG_EMPTY_STATE_REQUESTS, reply_markup=student_persistent_menu())
        return

    paginated_page = paginate(requests, page=page)
    kb = my_requests_list_keyboard(paginated_page.items, page=paginated_page.page, total_pages=paginated_page.total_pages)
    if callback.message:
        await callback.message.edit_text(RequestMessages.REQUESTS_LIST_TITLE, parse_mode="HTML", reply_markup=kb)


@requests_router.callback_query(F.data.startswith("my_req_detail:"))
async def show_request_detail(callback: CallbackQuery, session=None) -> None:
    """Display full details of a specific delivery request."""
    await callback.answer()
    req_id_str = callback.data.split(":")[1]
    try:
        req_id = int(req_id_str)
    except ValueError:
        if callback.message:
            await callback.message.answer(ErrorMessages.INVALID_REQUEST_ID, reply_markup=HomeButton())
        return

    if session is None:
        if callback.message:
            await callback.message.answer(ErrorMessages.SESSION_UNAVAILABLE, reply_markup=HomeButton())
        return

    repo = RequestRepository(session)
    req = await repo.get_by_id(req_id)

    user_id = await resolve_user_id(callback.from_user.id, session)
    if not req or req.student_id != user_id:
        if callback.message:
            await callback.message.answer(ErrorMessages.REQUEST_NOT_FOUND, reply_markup=HomeButton())
        return

    text = _format_request_detail(req)
    kb = request_detail_keyboard(req)
    if callback.message:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@requests_router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    """No-operation handler for non-clickable header buttons."""
    await callback.answer()


# ==============================================================================
# 3. Request Edit Handlers
# ==============================================================================

@requests_router.callback_query(F.data.startswith("my_req_edit:"))
async def start_request_edit(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    """Initiate editing an existing PENDING request."""
    await callback.answer()
    req_id_str = callback.data.split(":")[1]
    try:
        req_id = int(req_id_str)
    except ValueError:
        if callback.message:
            await callback.message.answer(ErrorMessages.INVALID_REQUEST_ID)
        return

    if session is None:
        if callback.message:
            await callback.message.answer(ErrorMessages.SESSION_UNAVAILABLE)
        return

    repo = RequestRepository(session)
    req = await repo.get_by_id(req_id)

    user_id = await resolve_user_id(callback.from_user.id, session)
    if not req or req.student_id != user_id:
        if callback.message:
            await callback.message.answer(ErrorMessages.REQUEST_NOT_FOUND)
        return

    if req.status != RequestStatus.PENDING:
        if callback.message:
            await callback.message.answer(ErrorMessages.REQUEST_EDIT_NOT_ALLOWED)
        return

    await state.clear()
    await state.set_state(RequestUpdateFSM.selecting_field)
    await state.update_data(request_id=req_id, changes={})

    kb = request_edit_fields_keyboard(req_id)
    if callback.message:
        await callback.message.edit_text(
            f"✏️ <b>Edit Request #{req_id}</b>\n\nSelect a field to modify:",
            parse_mode="HTML",
            reply_markup=kb,
        )


@requests_router.callback_query(RequestUpdateFSM.selecting_field, F.data.startswith("req_update_field:"))
async def select_field_to_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Select a specific field to edit on the request."""
    await callback.answer()
    parts = callback.data.split(":")
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

    if callback.message:
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


@requests_router.callback_query(RequestUpdateFSM.editing_value, F.data.startswith("req_hall:"))
async def process_edit_hall_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Store edited hall field."""
    hall = callback.data.split(":", 1)[1]
    await callback.answer(f"Selected Hall: {hall}")
    await _store_field_change(callback, state, "hall_of_residence", hall)


@requests_router.callback_query(RequestUpdateFSM.editing_value, F.data.startswith("req_size:"))
async def process_edit_size_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Store edited size field."""
    size = callback.data.split(":", 1)[1]
    await callback.answer(f"Selected Size: {size}")
    await _store_field_change(callback, state, "luggage_size", LuggageSize(size))


@requests_router.callback_query(RequestUpdateFSM.editing_value, F.data.startswith("req_date:"))
async def process_edit_date_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Store edited preferred date field."""
    dt_str = callback.data.split(":", 1)[1]
    await callback.answer(f"Selected Date: {dt_str}")
    dt = date.fromisoformat(dt_str)
    await _store_field_change(callback, state, "preferred_date", dt)


@requests_router.callback_query(RequestUpdateFSM.editing_value, F.data.startswith("req_time:"))
async def process_edit_time_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Store edited time window field."""
    slot = callback.data.split(":", 1)[1]
    await callback.answer(f"Selected Time: {slot}")
    await _store_field_change(callback, state, "preferred_time_window", slot)


@requests_router.message(RequestUpdateFSM.editing_value)
async def process_edit_value_message(message: Message, state: FSMContext) -> None:
    """Validate and store edited text field."""
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
    """Store updated value in FSM changes dictionary and show confirmation prompt."""
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
        if target.message:
            await target.message.answer(prompt, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(prompt, parse_mode="HTML", reply_markup=kb)


@requests_router.callback_query(RequestUpdateFSM.confirming_update, F.data.startswith("req_update_confirm:"))
async def confirm_request_update(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    """Apply the accumulated changes to the request via RequestService."""
    await callback.answer()
    data = await state.get_data()
    req_id = data["request_id"]
    changes = data.get("changes", {})

    if not changes:
        if callback.message:
            await callback.message.answer(SuccessMessages.NO_CHANGES_TO_SAVE)
        await state.clear()
        return

    if session is None:
        if callback.message:
            await callback.message.answer(ErrorMessages.SESSION_UNAVAILABLE)
        return

    actor_id = await resolve_user_id(callback.from_user.id, session)
    if actor_id is None:
        if callback.message:
            await callback.message.answer(ErrorMessages.USER_NOT_FOUND)
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
        if callback.message:
            await callback.message.answer(
                f"✅ Request #{updated_req.id} updated successfully!",
                reply_markup=student_persistent_menu(),
            )
    except PermissionDeniedError:
        await state.clear()
        if callback.message:
            await callback.message.answer(
                "⚠️ Request can no longer be edited because its status is no longer PENDING.",
                reply_markup=student_persistent_menu(),
            )
    except (NotFoundError, ValidationError, PackitbotError) as exc:
        if callback.message:
            await callback.message.answer(f"❌ Failed to update request: {exc}")


# ==============================================================================
# 4. Request Cancellation Handlers
# ==============================================================================

@requests_router.callback_query(F.data.startswith("my_req_cancel:"))
async def prompt_cancel_request(callback: CallbackQuery, session=None) -> None:
    """Prompt the student for confirmation before cancelling a request."""
    await callback.answer()
    req_id_str = callback.data.split(":")[1]
    try:
        req_id = int(req_id_str)
    except ValueError:
        if callback.message:
            await callback.message.answer(ErrorMessages.INVALID_REQUEST_ID)
        return

    if session is None:
        if callback.message:
            await callback.message.answer(ErrorMessages.SESSION_UNAVAILABLE)
        return

    repo = RequestRepository(session)
    req = await repo.get_by_id(req_id)

    user_id = await resolve_user_id(callback.from_user.id, session)
    if not req or req.student_id != user_id:
        if callback.message:
            await callback.message.answer(ErrorMessages.REQUEST_NOT_FOUND)
        return

    if req.status not in (RequestStatus.PENDING, RequestStatus.ASSIGNED, RequestStatus.ACCEPTED):
        if callback.message:
            await callback.message.answer(ErrorMessages.REQUEST_CANCEL_NOT_ALLOWED)
        return

    kb = request_cancel_confirm_keyboard(req_id)
    if callback.message:
        await callback.message.edit_text(
            f"⚠️ <b>Are you sure you want to cancel Request #{req_id}?</b>\n\nThis action cannot be undone.",
            parse_mode="HTML",
            reply_markup=kb,
        )


@requests_router.callback_query(F.data.startswith("my_req_cancel_confirm:"))
async def confirm_cancel_request(callback: CallbackQuery, session=None) -> None:
    """Confirm and execute cancellation of a delivery request."""
    await callback.answer()
    req_id_str = callback.data.split(":")[1]
    try:
        req_id = int(req_id_str)
    except ValueError:
        if callback.message:
            await callback.message.answer(ErrorMessages.INVALID_REQUEST_ID)
        return

    if session is None:
        if callback.message:
            await callback.message.answer(ErrorMessages.SESSION_UNAVAILABLE)
        return

    actor_id = await resolve_user_id(callback.from_user.id, session)
    if actor_id is None:
        if callback.message:
            await callback.message.answer(ErrorMessages.USER_NOT_FOUND)
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

        if callback.message:
            await callback.message.answer(
                f"🚫 Request #{updated_req.id} has been cancelled successfully.",
                reply_markup=student_persistent_menu(),
            )
    except (PermissionDeniedError, InvalidStatusTransitionError) as exc:
        if callback.message:
            await callback.message.answer(
                f"⚠️ Request cancellation failed: {exc}",
                reply_markup=student_persistent_menu(),
            )
    except (NotFoundError, ValidationError, PackitbotError) as exc:
        if callback.message:
            await callback.message.answer(f"❌ Failed to cancel request: {exc}")
