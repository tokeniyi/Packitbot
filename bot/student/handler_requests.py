from bot.core.utils.validators import (
    validate_dropoff_address,
    validate_pickup_detail,
    validate_preferred_date,
    validate_recipient_name,
    validate_special_instructions,
    validate_luggage_count,
    validate_phone,
    validate_time_window,
)
import logging
from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from bot.core.constants.enums import (
    CancelledBy,
    DriverAvailability,
    LuggageSize,
    RequestStatus,
)
from bot.core.constants.commands import CMD_MY_REQUESTS
from bot.core.constants.messages import (
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
)
from bot.core.exceptions import (
    InvalidStatusTransitionError,
    NotFoundError,
    PackitbotError,
    PermissionDeniedError,
    ValidationError,
)
from bot.core.keyboards.common_kb import HomeButton
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.feedback import Feedback
from bot.core.utils.pagination import paginate
from bot.request.repository import RequestRepository
from bot.request.schemas import CancelRequestDTO, CreateFeedbackDTO, UpdateRequestDTO
from bot.request.service import RequestService
from bot.student.keyboards import (
    date_quick_pick_keyboard,
    feedback_comment_skip_keyboard,
    feedback_rating_keyboard,
    luggage_size_keyboard,
    my_requests_list_keyboard,
    req_hall_selection_keyboard,
    request_cancel_confirm_keyboard,
    request_detail_keyboard,
    request_edit_confirm_keyboard,
    request_edit_fields_keyboard,
    student_persistent_menu,
    time_window_keyboard,
)
from bot.student.states import RequestUpdateFSM, FeedbackFSM

logger = logging.getLogger(__name__)
student_router = Router()


async def _resolve_user_id(telegram_id: int, session) -> int | None:
    """Resolves a Telegram user ID to the internal users.id."""
    from sqlalchemy import select
    from bot.core.models.user import User

    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    return user.id if user else None


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


@student_router.message(F.text == CMD_MY_REQUESTS)
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
        await callback.message.edit_text(MSG_EMPTY_STATE_REQUESTS, reply_markup=student_persistent_menu())
        return

    repo = RequestRepository(session)
    user_id = await _resolve_user_id(callback.from_user.id, session)
    if user_id is None:
        await callback.message.edit_text("User profile not found.", reply_markup=student_persistent_menu())
        return
    requests = await repo.get_history_for_student(student_id=user_id, page=page)

    if not requests:
        await callback.message.edit_text(MSG_EMPTY_STATE_REQUESTS, reply_markup=student_persistent_menu())
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
    _req_id = int(parts[1])
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

    service = RequestService(session)
    dto = UpdateRequestDTO(
        request_id=req_id,
        actor_id=callback.from_user.id,
        changed_fields=changes,
    )

    try:
        updated_req = await service.update_request(dto)
        await state.clear()
        await callback.message.edit_text(
            f"✅ Request #{updated_req.id} updated successfully!",
            reply_markup=student_persistent_menu(),
        )
    except PermissionDeniedError:
        await state.clear()
        await callback.message.edit_text(
            "⚠️ Request can no longer be edited because its status is no longer PENDING.",
            reply_markup=student_persistent_menu(),
        )
    except (NotFoundError, ValidationError, PackitbotError) as exc:
        await callback.message.answer(f"❌ Failed to update request: {exc}")


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

    service = RequestService(session)
    dto = CancelRequestDTO(
        request_id=req_id,
        actor_id=callback.from_user.id,
        cancelled_by=CancelledBy.STUDENT,
        cancellation_reason="Cancelled by student via bot",
    )

    try:
        updated_req, event = await service.cancel_request(dto)

        if updated_req.driver_id is not None:
            driver = await session.get(DriverProfile, updated_req.driver_id)
            if driver:
                driver.availability = DriverAvailability.AVAILABLE
                await session.flush()

        await callback.message.edit_text(
            f"🚫 Request #{updated_req.id} has been cancelled successfully.",
            reply_markup=student_persistent_menu(),
        )
    except (PermissionDeniedError, InvalidStatusTransitionError) as exc:
        await callback.message.edit_text(
            f"⚠️ Request cancellation failed: {exc}",
            reply_markup=student_persistent_menu(),
        )
    except (NotFoundError, ValidationError, PackitbotError) as exc:
        await callback.message.answer(f"❌ Failed to cancel request: {exc}")


async def _recalculate_driver_rating(session, driver_id: int) -> None:
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

    existing_feedback = await session.execute(
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
        await target.answer("User profile not found.", reply_markup=student_persistent_menu())
        return
    dto = CreateFeedbackDTO(
        request_id=req_id,
        student_id=user_id,
        rating=rating,
        comment=comment,
    )

    try:
        feedback, event = await service.submit_feedback(dto)

        req_repo = RequestRepository(session)
        req = await req_repo.get_by_id(req_id)
        if req and req.driver_id:
            await _recalculate_driver_rating(session, req.driver_id)

        await state.clear()
        success_msg = f"🎉 <b>Thank you!</b> Your feedback for Request #{req_id} has been submitted."

        if isinstance(target, CallbackQuery):
            await target.message.edit_text(success_msg, parse_mode="HTML", reply_markup=student_persistent_menu())
        else:
            await target.answer(success_msg, parse_mode="HTML", reply_markup=student_persistent_menu())

    except (PermissionDeniedError, ValidationError, PackitbotError) as exc:
        await state.clear()
        err_msg = f"❌ Failed to submit feedback: {exc}"
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(err_msg, reply_markup=student_persistent_menu())
        else:
            await target.answer(err_msg, reply_markup=student_persistent_menu())