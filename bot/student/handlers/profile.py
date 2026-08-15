"""Student profile view and edit handlers."""

import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.core.constants.commands import CMD_PROFILE
from bot.core.constants.enums import AccountStatus, VerificationStatus
from bot.core.constants.messages import ErrorMessages, SuccessMessages
from bot.core.constants.quick_replies import BTN_MY_PROFILE
from bot.core.exceptions import NotFoundError, ValidationError
from bot.core.utils.validators import validate_phone
from bot.student.keyboards import req_hall_selection_keyboard, student_persistent_menu
from bot.student.service import (
    get_student_profile_with_stats,
    update_student_hall,
    update_student_phone,
)
from bot.student.states import StudentProfileFSM

logger = logging.getLogger(__name__)
profile_router = Router()


async def _show_profile(
    target: Message | CallbackQuery,
    state: FSMContext,
    session=None,
    user_id: int | None = None,
) -> None:
    """Renders the student profile view with statistics."""
    uid = user_id or (target.from_user.id if isinstance(target, CallbackQuery) else target.from_user.id)
    user, profile, active_requests, completed_deliveries, cancelled_requests = (
        await get_student_profile_with_stats(uid, session=session)
    )

    markup = student_persistent_menu()
    if user is None:
        if isinstance(target, CallbackQuery):
            if target.message:
                await target.message.answer(ErrorMessages.USER_NOT_FOUND, reply_markup=markup)
        else:
            await target.answer(ErrorMessages.USER_NOT_FOUND, reply_markup=markup)
        return

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
        if target.message:
            await target.message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


@profile_router.message(Command(CMD_PROFILE))
@profile_router.message(F.text == BTN_MY_PROFILE)
async def show_profile(message: Message, state: FSMContext, session=None) -> None:
    """Show the student's profile."""
    await state.clear()
    await _show_profile(message, state, session=session)


@profile_router.callback_query(F.data == "profile_edit_phone")
async def profile_edit_phone(callback: CallbackQuery, state: FSMContext) -> None:
    """Initiate editing the student's phone number."""
    await callback.answer()
    await state.set_state(StudentProfileFSM.editing_phone)
    if callback.message:
        await callback.message.answer("✏️ Enter your new phone number (e.g. 08012345678):")


@profile_router.callback_query(F.data == "profile_set_hall")
async def profile_set_hall(callback: CallbackQuery, state: FSMContext) -> None:
    """Initiate selecting a new default hall of residence."""
    await callback.answer()
    await state.set_state(StudentProfileFSM.editing_hall)
    if callback.message:
        await callback.message.answer(
            "🏢 Select your default Hall of Residence:",
            reply_markup=req_hall_selection_keyboard(),
        )


@profile_router.message(StudentProfileFSM.editing_phone)
async def process_profile_phone_edit(message: Message, state: FSMContext, session=None) -> None:
    """Validate and update the student's phone number."""
    try:
        phone = validate_phone(message.text)
    except ValidationError as exc:
        await message.answer(f"❌ {exc}")
        return
    except Exception:
        await message.answer("⚠️ Please enter a valid Nigerian phone number.")
        return

    user_id = message.from_user.id
    try:
        await update_student_phone(user_id, phone, session=session)
    except NotFoundError:
        await message.answer(ErrorMessages.USER_NOT_FOUND, reply_markup=student_persistent_menu())
        await state.clear()
        return

    await state.clear()
    await message.answer("✅ Phone number updated successfully.", reply_markup=student_persistent_menu())
    await _show_profile(message, state, session=session, user_id=user_id)


@profile_router.callback_query(StudentProfileFSM.editing_hall, F.data.startswith("req_hall:"))
async def process_profile_hall_edit(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    """Validate and update the student's default hall."""
    hall = callback.data.split(":", 1)[1]
    await callback.answer(f"Selected Hall: {hall}")

    user_id = callback.from_user.id
    try:
        await update_student_hall(user_id, hall, session=session)
    except NotFoundError:
        if callback.message:
            await callback.message.answer(ErrorMessages.USER_NOT_FOUND, reply_markup=student_persistent_menu())
        await state.clear()
        return

    await state.clear()
    if callback.message:
        await callback.message.answer("✅ Default hall updated successfully.", reply_markup=student_persistent_menu())
    await _show_profile(callback, state, session=session, user_id=user_id)
