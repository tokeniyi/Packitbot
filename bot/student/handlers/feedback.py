"""Student feedback and driver rating handlers."""

import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from bot.core.constants.enums import RequestStatus
from bot.core.constants.messages import ErrorMessages
from bot.core.exceptions import PackitbotError, PermissionDeniedError, ValidationError
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.feedback import Feedback
from bot.request.repository import RequestRepository
from bot.request.schemas import CreateFeedbackDTO
from bot.request.service import RequestService
from bot.student.keyboards import feedback_comment_skip_keyboard, feedback_rating_keyboard, student_persistent_menu
from bot.student.service import resolve_user_id
from bot.student.states import FeedbackFSM

logger = logging.getLogger(__name__)
feedback_router = Router()


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


@feedback_router.callback_query(F.data.startswith("my_req_rate:"))
async def prompt_feedback_rating(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    """Prompt the student to rate a completed delivery request."""
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

    if req.status != RequestStatus.DELIVERED:
        if callback.message:
            await callback.message.answer("⚠️ Only DELIVERED requests can be rated.")
        return

    existing_feedback = await repo.session.execute(
        select(Feedback).where(Feedback.request_id == req_id)
    )
    if existing_feedback.scalar_one_or_none():
        if callback.message:
            await callback.message.answer("⚠️ You have already submitted feedback for this delivery.")
        return

    await state.clear()
    await state.set_state(FeedbackFSM.selecting_rating)
    await state.update_data(request_id=req_id)

    kb = feedback_rating_keyboard(req_id)
    if callback.message:
        await callback.message.edit_text(
            f"⭐ <b>Rate Delivery #{req_id}</b>\n\n"
            "How would you rate your driver's service? (1-5 stars)",
            parse_mode="HTML",
            reply_markup=kb,
        )


@feedback_router.callback_query(FeedbackFSM.selecting_rating, F.data.startswith("rate:"))
async def process_rating_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Record the star rating selection and prompt for an optional comment."""
    await callback.answer()
    parts = callback.data.split(":")
    req_id = int(parts[1])
    rating = int(parts[2])

    await state.update_data(request_id=req_id, rating=rating)
    await state.set_state(FeedbackFSM.entering_comment)

    kb = feedback_comment_skip_keyboard(req_id)
    if callback.message:
        await callback.message.edit_text(
            f"⭐ <b>Rating: {'⭐' * rating} ({rating}/5)</b>\n\n"
            "Would you like to leave an optional comment for your driver?\n"
            "Type your comment below or click <b>Skip</b>.",
            parse_mode="HTML",
            reply_markup=kb,
        )


@feedback_router.callback_query(FeedbackFSM.entering_comment, F.data.startswith("feedback_skip_comment:"))
async def process_feedback_skip_comment(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    """Handle skipping the optional comment step."""
    await callback.answer()
    await _finalize_feedback_submission(callback, state, session, comment=None)


@feedback_router.message(FeedbackFSM.entering_comment)
async def process_feedback_comment_message(message: Message, state: FSMContext, session=None) -> None:
    """Handle the optional written comment and finalize submission."""
    comment = message.text.strip() if message.text else None
    await _finalize_feedback_submission(message, state, session, comment=comment)


async def _finalize_feedback_submission(
    target: Message | CallbackQuery,
    state: FSMContext,
    session,
    comment: str | None,
) -> None:
    """Helper to persist feedback and update the driver rating."""
    data = await state.get_data()
    req_id = data.get("request_id")
    rating = data.get("rating")

    if not req_id or not rating:
        await state.clear()
        err_msg = "Feedback session expired or invalid state."
        if isinstance(target, CallbackQuery):
            if target.message:
                await target.message.answer(err_msg)
        else:
            await target.answer(err_msg)
        return

    if session is None:
        err_msg = ErrorMessages.SESSION_UNAVAILABLE
        if isinstance(target, CallbackQuery):
            if target.message:
                await target.message.answer(err_msg)
        else:
            await target.answer(err_msg)
        return

    service = RequestService(session)
    user_id = await resolve_user_id(target.from_user.id, session)
    if user_id is None:
        err_msg = ErrorMessages.USER_NOT_FOUND
        if isinstance(target, CallbackQuery):
            if target.message:
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
            if target.message:
                await target.message.answer(success_msg, parse_mode="HTML", reply_markup=student_persistent_menu())
        else:
            await target.answer(success_msg, parse_mode="HTML", reply_markup=student_persistent_menu())

    except (PermissionDeniedError, ValidationError, PackitbotError) as exc:
        await state.clear()
        err_msg = f"❌ Failed to submit feedback: {exc}"
        if isinstance(target, CallbackQuery):
            if target.message:
                await target.message.answer(err_msg, reply_markup=student_persistent_menu())
        else:
            await target.answer(err_msg, reply_markup=student_persistent_menu())
