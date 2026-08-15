"""Driver module router - registration FSM, availability, and active delivery flows.

This module defines the aiogram Router for all driver-related conversation
flows and callback interactions. It handles driver registration (FSM-based),
approval status checks, availability toggling, and active delivery tracking
including accept/reject flows and step-by-step status updates.

Registered Handlers
-------------------
- ``start_driver_registration``       -> ``/register_driver`` command or text button
- ``cancel_driver_registration``      -> ``/cancel_driver_reg`` command or callback
- ``process_full_name``               -> FSM state: ``entering_full_name``
- ``process_phone_number``            -> FSM state: ``entering_phone_number``
- ``process_vehicle_type``            -> FSM state: ``selecting_vehicle_type``
- ``process_plate_number``            -> FSM state: ``entering_plate_number``
- ``process_license_number``          -> FSM state: ``entering_license_number``
- ``process_edit_field``              -> callback: ``driver_edit:<field>``
- ``process_submit_registration``     -> callback: ``driver_submit_reg``
- ``check_approval_status``           -> "Check Approval Status" text button
- ``toggle_availability_handler``     -> "Go Available/Offline" text button or ``/toggle_availability``
- ``process_driver_accept``           -> callback: ``driver_accept:<request_id>``
- ``active_delivery_dashboard_handler`` -> "Active Delivery" text button or ``/active_delivery``
- ``process_delivery_status_step``    -> callback: ``driver_step:<action>:<request_id>``
- ``process_driver_reject``           -> callback: ``driver_reject:<request_id>``

Depends on
----------
aiogram Router/FSM, ``bot.driver.keyboards``, ``bot.driver.service``,
``bot.driver.schemas``, ``bot.driver.states``, ``bot.core.utils.validators``,
``bot.core.constants.enums``, ``bot.core.constants.messages``, ``logging``.

Imported by
-----------
``bot/driver/__init__.py`` (router inclusion).
"""

import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.core.constants.enums import DriverAvailability, DriverStatus
from bot.core.keyboards.common_kb import HomeButton
from bot.core.utils.validators import (
    ValidationError,
    validate_full_name,
    validate_license_number,
    validate_phone,
    validate_plate_number,
    validate_vehicle_type,
)
from bot.core.constants.messages import (
    ErrorMessages,
    LogMessages,
    RegistrationMessages,
    SuccessMessages,
)
from bot.core.utils.formatters import format_step_prompt, render_progress_bar
from bot.driver.keyboards import (
    delivery_status_update_keyboard,
    driver_pending_menu,
    driver_persistent_menu,
    driver_registration_review_keyboard,
    vehicle_type_keyboard,
)
from bot.driver.schemas import RegisterDriverDTO
from bot.driver.service import get_driver_profile_by_telegram_id, register_driver, set_driver_availability
from bot.driver.states import DriverRegistrationFSM

logger = logging.getLogger(__name__)
driver_router = Router()


async def _show_review_screen(target: Message | CallbackQuery, state: FSMContext) -> None:
    """Present collected driver registration data for final review and confirmation.

    Reads all field values from FSM context data, formats them into a summary
    message, and sends it with the registration review keyboard. Works for
    both :class:`Message` and :class:`CallbackQuery` targets.

    Args:
        target: The triggering :class:`Message` or :class:`CallbackQuery`.
        state:  The FSM context holding collected registration data.

    Sets:
        Transitions FSM state to ``confirming_registration``.
    """
    await state.set_state(DriverRegistrationFSM.confirming_registration)
    data = await state.get_data()

    summary = (
        "🚗 <b>Driver Registration Review</b>\n\n"
        f"• <b>Full Name:</b> {data.get('full_name')}\n"
        f"• <b>Phone Number:</b> {data.get('phone_number')}\n"
        f"• <b>Vehicle Type:</b> {data.get('vehicle_type', '').upper()}\n"
        f"• <b>Plate Number:</b> {data.get('plate_number')}\n"
        f"• <b>License Number:</b> {data.get('license_number')}\n\n"
        "Please confirm your registration details."
    )

    kb = driver_registration_review_keyboard()
    if isinstance(target, CallbackQuery):
        await target.message.answer(summary, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(summary, parse_mode="HTML", reply_markup=kb)


@driver_router.message(Command("register_driver"))
@driver_router.message(F.text == "🚘 Register as Driver")
async def start_driver_registration(message: Message, state: FSMContext, session=None) -> None:
    """Initiate the driver registration flow or inform the user of their current status.

    Triggered by the ``/register_driver`` command or the "Register as Driver"
    text button. If the user already has an approved or pending profile, the
    appropriate menu is shown instead of restarting the FSM. Otherwise the
    FSM is cleared and set to ``entering_full_name``.

    Args:
        message: The incoming :class:`Message` (command or text trigger).
        state:   The FSM context to manage registration progress.
        session: Optional injected SQLAlchemy ``AsyncSession``.

    Calls / Depends on:
        :func:`get_driver_profile_by_telegram_id`, :func:`_step_prompt`,
        :class:`DriverRegistrationFSM`, :func:`driver_persistent_menu`,
        :func:`driver_pending_menu`.

    Registered on ``driver_router`` via ``Command("register_driver")``
    and ``F.text == "Register as Driver"``.
    """
    # Check if driver is already registered
    profile = await get_driver_profile_by_telegram_id(session, message.from_user.id)
    if profile:
        if profile.status == DriverStatus.APPROVED:
            await message.answer(
                "✅ You are already registered and approved as a driver!",
                reply_markup=driver_persistent_menu(profile.availability),
            )
            return
        elif profile.status == DriverStatus.PENDING_APPROVAL:
            await message.answer(
                ErrorMessages.DRIVER_PENDING_APPROVAL,
                parse_mode="HTML",
                reply_markup=driver_pending_menu(),
            )
            return

    # Check pre-authorization before starting the registration FSM.
    from bot.driver.service import is_authorized_driver

    if session is None:
        await message.answer(ErrorMessages.SESSION_UNAVAILABLE)
        return

    is_authorized = await is_authorized_driver(session, message.from_user.id)
    if not is_authorized:
        await message.answer(
            ErrorMessages.DRIVER_INVITATION_ONLY,
            reply_markup=HomeButton(),
        )
        return

    await state.clear()
    await state.set_state(DriverRegistrationFSM.entering_full_name)
    await message.answer(format_step_prompt(1, 5, RegistrationMessages.DRIVER_ENTER_FULL_NAME))


@driver_router.message(Command("cancel_driver_reg"))
@driver_router.callback_query(F.data == "driver_cancel_reg")
async def cancel_driver_registration(event: Message | CallbackQuery, state: FSMContext) -> None:
    """Cancel the driver registration process and reset the FSM.

    Clears all FSM data and sends a confirmation message with a Home button.
    Triggered by the ``/cancel_driver_reg`` command or the
    ``driver_cancel_reg`` callback.

    Args:
        event: The incoming :class:`Message` or :class:`CallbackQuery`.
        state: The FSM context to clear.

    Calls / Depends on:
        :func:`HomeButton` (from ``bot.core.keyboards.common_kb``).
    """
    await state.clear()
    msg = SuccessMessages.ACTION_CANCELLED
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(msg, reply_markup=HomeButton())
    else:
        await event.answer(msg, reply_markup=HomeButton())


@driver_router.message(DriverRegistrationFSM.entering_full_name)
async def process_full_name(message: Message, state: FSMContext) -> None:
    """Validate and store the driver's full name, then advance to phone number.

    If the FSM data contains ``is_editing=True``, the value is stored and
    the user is returned to the review screen instead of advancing.

    Args:
        message: The incoming :class:`Message` containing the full name text.
        state:   The FSM context (state: ``entering_full_name``).

    Calls / Depends on:
        :func:`validate_full_name`, :func:`_show_review_screen`,
        :func:`format_step_prompt`, :class:`DriverRegistrationFSM`.
    """
    try:
        val = validate_full_name(message.text)
    except ValidationError as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(full_name=val)
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_review_screen(message, state)
        return

    await state.set_state(DriverRegistrationFSM.entering_phone_number)
    await message.answer(format_step_prompt(2, 5, RegistrationMessages.DRIVER_ENTER_PHONE))


@driver_router.message(DriverRegistrationFSM.entering_phone_number)
async def process_phone_number(message: Message, state: FSMContext) -> None:
    """Validate and store the driver's phone number, then advance to vehicle type.

    If ``is_editing`` is set in FSM data, returns to the review screen
    instead of advancing.

    Args:
        message: The incoming :class:`Message` containing the phone number.
        state:   The FSM context (state: ``entering_phone_number``).

    Calls / Depends on:
        :func:`validate_phone`, :func:`_show_review_screen`,
        :func:`format_step_prompt`, :func:`vehicle_type_keyboard`,
        :class:`DriverRegistrationFSM`.
    """
    try:
        val = validate_phone(message.text)
    except ValidationError as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(phone_number=val)
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_review_screen(message, state)
        return

    await state.set_state(DriverRegistrationFSM.selecting_vehicle_type)
    await message.answer(
        format_step_prompt(3, 5, RegistrationMessages.DRIVER_CHOOSE_VEHICLE),
        reply_markup=vehicle_type_keyboard(),
    )


@driver_router.callback_query(DriverRegistrationFSM.selecting_vehicle_type, F.data.startswith("driver_vtype:"))
async def process_vehicle_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Validate and store the selected vehicle type, then advance to plate number.

    The callback data uses the ``driver_vtype:<type>`` schema; the type
    portion is extracted via ``split(":", 1)``. If ``is_editing`` is set,
    returns to the review screen.

    Args:
        callback: The incoming :class:`CallbackQuery` with ``driver_vtype:<type>`` data.
        state:    The FSM context (state: ``selecting_vehicle_type``).

    Calls / Depends on:
        :func:`validate_vehicle_type`, :func:`_show_review_screen`,
        :func:`format_step_prompt`, :class:`DriverRegistrationFSM`.
    """
    vtype = callback.data.split(":", 1)[1]
    try:
        val = validate_vehicle_type(vtype)
    except ValidationError as exc:
        await callback.answer(f"❌ {exc}", show_alert=True)
        return

    await callback.answer(f"Vehicle: {val.upper()}")
    await state.update_data(vehicle_type=val)
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_review_screen(callback, state)
        return

    await state.set_state(DriverRegistrationFSM.entering_plate_number)
    await callback.message.answer(format_step_prompt(4, 5, RegistrationMessages.DRIVER_ENTER_PLATE))


@driver_router.message(DriverRegistrationFSM.entering_plate_number)
async def process_plate_number(message: Message, state: FSMContext) -> None:
    """Validate and store the vehicle plate number, then advance to license number.

    If ``is_editing`` is set in FSM data, returns to the review screen
    instead of advancing.

    Args:
        message: The incoming :class:`Message` containing the plate number.
        state:   The FSM context (state: ``entering_plate_number``).

    Calls / Depends on:
        :func:`validate_plate_number`, :func:`_show_review_screen`,
        :func:`format_step_prompt`, :class:`DriverRegistrationFSM`.
    """
    try:
        val = validate_plate_number(message.text)
    except ValidationError as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(plate_number=val)
    data = await state.get_data()
    if data.get("is_editing"):
        await state.update_data(is_editing=False)
        await _show_review_screen(message, state)
        return

    await state.set_state(DriverRegistrationFSM.entering_license_number)
    await message.answer(format_step_prompt(5, 5, RegistrationMessages.DRIVER_ENTER_LICENSE))


@driver_router.message(DriverRegistrationFSM.entering_license_number)
async def process_license_number(message: Message, state: FSMContext) -> None:
    """Validate and store the driver's license number, then show the review screen.

    After storing the final field, ``is_editing`` is reset to ``False``
    and the review screen is displayed.

    Args:
        message: The incoming :class:`Message` containing the license number.
        state:   The FSM context (state: ``entering_license_number``).

    Calls / Depends on:
        :func:`validate_license_number`, :func:`_show_review_screen`,
        :class:`DriverRegistrationFSM`.
    """
    try:
        val = validate_license_number(message.text)
    except ValidationError as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.update_data(license_number=val)
    await state.update_data(is_editing=False)
    await _show_review_screen(message, state)


@driver_router.callback_query(DriverRegistrationFSM.confirming_registration, F.data.startswith("driver_edit:"))
async def process_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle inline edit requests for individual registration fields.

    Parses the ``driver_edit:<field>`` callback, sets ``is_editing=True`` in
    FSM data, and transitions to the appropriate input state so the user
    can re-enter the value. When the field-processing handler completes, it
    detects ``is_editing`` and returns to the review screen rather than
    advancing to the next step.

    Args:
        callback: The incoming :class:`CallbackQuery` with ``driver_edit:<field>`` data.
        state:    The FSM context (state: ``confirming_registration``).

    Calls / Depends on:
        :func:`vehicle_type_keyboard` (only for the ``vehicle_type`` field).

    Registered on ``driver_router`` for callback data starting with
    ``driver_edit:``.
    """
    # Extract the field name from the "driver_edit:<field>" callback payload.
    field = callback.data.split(":", 1)[1]
    await callback.answer()
    # Flag the FSM so the target handler returns to review after saving.
    await state.update_data(is_editing=True)

    field_map = {
        "full_name": (DriverRegistrationFSM.entering_full_name, "Enter your full name:"),
        "phone_number": (DriverRegistrationFSM.entering_phone_number, "Enter your phone number:"),
        "vehicle_type": (DriverRegistrationFSM.selecting_vehicle_type, "Select your vehicle type:"),
        "plate_number": (DriverRegistrationFSM.entering_plate_number, "Enter vehicle plate number:"),
        "license_number": (DriverRegistrationFSM.entering_license_number, "Enter driver's license number:"),
    }

    if field in field_map:
        target_state, prompt_text = field_map[field]
        await state.set_state(target_state)
        reply_kb = vehicle_type_keyboard() if field == "vehicle_type" else None
        await callback.message.answer(f"✏️ Editing {field.replace('_', ' ').title()}:\n{prompt_text}", reply_markup=reply_kb)


@driver_router.callback_query(DriverRegistrationFSM.confirming_registration, F.data == "driver_submit_reg")
async def process_submit_registration(callback: CallbackQuery, state: FSMContext, session=None) -> None:
    """Persist the driver registration DTO and clear the FSM on success.

    Reads all collected fields from FSM data, constructs a
    :class:`RegisterDriverDTO`, and calls :func:`register_driver` to
    persist the profile. On success, the FSM is cleared and the user is
    shown a confirmation message with the pending-menu keyboard.

    Args:
        callback: The incoming :class:`CallbackQuery` with ``driver_submit_reg`` data.
        state:    The FSM context (state: ``confirming_registration``).
        session:  Optional injected SQLAlchemy ``AsyncSession``.

    Calls / Depends on:
        :func:`register_driver`, :class:`RegisterDriverDTO`,
        :func:`driver_pending_menu`.

    Registered on ``driver_router`` for callback data ``driver_submit_reg``.
    """
    await callback.answer()
    # Read all collected fields from FSM context data.
    data = await state.get_data()

    dto = RegisterDriverDTO(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=data["full_name"],
        phone_number=data["phone_number"],
        vehicle_type=data["vehicle_type"],
        plate_number=data["plate_number"],
        license_number=data["license_number"],
    )

    try:
        await register_driver(session, dto)
    except Exception as exc:
        logger.error("Failed driver registration for user %s: %s", callback.from_user.id, exc)
        await callback.message.answer(f"❌ Registration failed: {exc}")
        return

    await state.clear()
    await callback.message.edit_text(
        "🎉 <b>Driver Registration Submitted!</b>\n\n"
        "Your registration is currently <b>PENDING APPROVAL</b>.\n"
        "An administrator will review your application soon.",
        parse_mode="HTML",
    )
    await callback.message.answer(
        "You can check your status anytime using the menu below:",
        reply_markup=driver_pending_menu(),
    )


@driver_router.message(F.text == "🔄 Check Approval Status")
async def check_approval_status(message: Message, session=None) -> None:
    """Display the current approval status for the requesting driver.

    Triggered by the "Check Approval Status" text button. Looks up the
    driver profile and presents a status-specific message with the
    appropriate menu (persistent for approved, pending for all other states).

    Args:
        message: The incoming :class:`Message` (text trigger).
        session: Optional injected SQLAlchemy ``AsyncSession``.

    Calls / Depends on:
        :func:`get_driver_profile_by_telegram_id`, :func:`driver_persistent_menu`,
        :func:`driver_pending_menu`, :class:`DriverStatus`.

    Registered on ``driver_router`` for ``F.text == "Check Approval Status"``.
    """
    profile = await get_driver_profile_by_telegram_id(session, message.from_user.id)
    if not profile:
        await message.answer("You have not registered as a driver yet. Use /register_driver to begin.")
        return

    if profile.status == DriverStatus.APPROVED:
        await message.answer(
            "🎉 <b>Congratulations!</b> Your driver registration has been APPROVED!",
            parse_mode="HTML",
            reply_markup=driver_persistent_menu(profile.availability),
        )
    elif profile.status == DriverStatus.PENDING_APPROVAL:
        await message.answer(
            "⏳ Your application is still <b>PENDING APPROVAL</b>. Please check back later.",
            parse_mode="HTML",
            reply_markup=driver_pending_menu(),
        )
    elif profile.status == DriverStatus.REJECTED:
        await message.answer(
            "❌ Your driver registration application was rejected by an admin.",
            reply_markup=driver_pending_menu(),
        )
    else:
        await message.answer(
            f"Your account status: <b>{profile.status.value.upper()}</b>",
            parse_mode="HTML",
        )


@driver_router.message(F.text.in_({"🟢 Go Available", "🔴 Go Offline"}))
@driver_router.message(Command("toggle_availability"))
async def toggle_availability_handler(message: Message, session=None) -> None:
    """Toggle the driver's availability between AVAILABLE and OFFLINE.

    Triggered by the "Go Available/Offline" text buttons or the
    ``/toggle_availability`` command. Rejects the request if the driver is
    not approved or is currently ``BUSY`` (system-managed during a delivery).

    Args:
        message: The incoming :class:`Message` (text or command trigger).
        session: Optional injected SQLAlchemy ``AsyncSession``.

    Calls / Depends on:
        :func:`get_driver_profile_by_telegram_id`, :func:`set_driver_availability`,
        :func:`driver_persistent_menu`, :class:`DriverStatus`,
        :class:`DriverAvailability`.

    Registered on ``driver_router`` for ``F.text.in_({"Go Available", "Go Offline"})``
    and ``Command("toggle_availability")``.
    """
    profile = await get_driver_profile_by_telegram_id(session, message.from_user.id)
    if not profile:
        await message.answer("You are not registered as a driver. Use /register_driver to get started.")
        return

    if profile.status != DriverStatus.APPROVED:
        await message.answer(
            "❌ Only approved drivers can change availability.",
            reply_markup=driver_pending_menu(),
        )
        return

    if profile.availability == DriverAvailability.BUSY:
        await message.answer(
            "⚠️ You are currently on an active delivery. Your status is system-managed (BUSY) until the delivery completes.",
            reply_markup=driver_persistent_menu(DriverAvailability.BUSY),
        )
        return

    target_status = (
        DriverAvailability.OFFLINE
        if profile.availability == DriverAvailability.AVAILABLE
        else DriverAvailability.AVAILABLE
    )

    try:
        updated_profile = await set_driver_availability(
            session,
            message.from_user.id,
            target_status,
        )
    except Exception as exc:
        logger.error("Error toggling availability for user %s: %s", message.from_user.id, exc)
        await message.answer(f"❌ Failed to update status: {exc}")
        return

    if updated_profile.availability == DriverAvailability.AVAILABLE:
        status_msg = "🟢 You are now <b>AVAILABLE</b> to receive delivery requests."
    else:
        status_msg = "🔴 You are now <b>OFFLINE</b> and will not receive new requests."

    await message.answer(
        status_msg,
        parse_mode="HTML",
        reply_markup=driver_persistent_menu(updated_profile.availability),
    )


@driver_router.callback_query(F.data.startswith("driver_accept:"))
async def process_driver_accept(callback: CallbackQuery, session=None) -> None:
    """Handle a driver accepting an assigned delivery request.

    Parses the ``driver_accept:<request_id>`` callback, resolves the driver
    :class:`User` by Telegram ID, transitions the request status to
    ``ACCEPTED`` via :class:`RequestService`, then edits the original
    message with delivery details and a status-update keyboard. A
    notification is also sent to the student.

    Args:
        callback: The incoming :class:`CallbackQuery` with ``driver_accept:<request_id>`` data.
        session:  Optional injected SQLAlchemy ``AsyncSession``.

    Calls / Depends on:
        :class:`RequestService` (``transition_status``), :class:`TransitionDTO`,
        :func:`delivery_status_update_keyboard`, :class:`PackitbotError`.

    Registered on ``driver_router`` for callback data starting with
    ``driver_accept:``.
    """
    # Extract request ID from the "driver_accept:<request_id>" callback payload.
    request_id = int(callback.data.split(":")[1])

    if session is None:
        await callback.answer("Session unavailable.", show_alert=True)
        return

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from bot.core.constants.enums import RequestStatus
    from bot.core.db.session import async_session
    from bot.core.exceptions import PackitbotError
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.user import User
    from bot.request.schemas import TransitionDTO
    from bot.request.service import RequestService

    try:
        # Fetch driver user
        driver_user_res = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        driver_user = driver_user_res.scalar_one_or_none()
        if not driver_user:
            await callback.answer("Driver profile not found.", show_alert=True)
            return

        req_service = RequestService(session)
        dto = TransitionDTO(
            request_id=request_id,
            new_status=RequestStatus.ACCEPTED,
            actor_id=driver_user.id,
            note=f"Accepted by driver {driver_user.id}",
        )
        updated_req, event = await req_service.transition_status(dto)
        await session.commit()

        # Re-fetch request with loaded student and driver relationships
        req_res = await session.execute(
            select(DeliveryRequest)
            .options(
                selectinload(DeliveryRequest.student),
                selectinload(DeliveryRequest.driver),
            )
            .where(DeliveryRequest.id == request_id)
        )
        req = req_res.scalar_one()

        student = req.student
        driver = req.driver

        student_phone = student.phone_number if student else "N/A"
        student_name = student.full_name if student else "Student"
        driver_phone = driver.phone_number if driver else (driver_user.phone_number or "N/A")
        driver_name = driver.full_name if driver else (driver_user.full_name or "Driver")

        # Edit original message for driver
        await callback.message.edit_text(
            f"✅ <b>Assignment Accepted!</b>\n\n"
            f"📦 <b>Request #{req.id}</b>\n"
            f"📍 Pickup: {req.pickup_detail} ({req.hall_of_residence})\n"
            f"🎯 Dropoff: {req.dropoff_address}\n"
            f"👤 Recipient: {req.recipient_name} ({req.recipient_phone})\n\n"
            f"📞 <b>Student Contact Details:</b>\n"
            f"• Name: {student_name}\n"
            f"• Phone: {student_phone}",
            parse_mode="HTML",
            reply_markup=delivery_status_update_keyboard(req.id, req.status),
        )
        await callback.answer("Request accepted!")

        # Send notification to student with driver details
        if student and student.telegram_id:
            try:
                await callback.bot.send_message(
                    chat_id=student.telegram_id,
                    text=(
                        f"🎉 <b>Driver Accepted Your Request!</b>\n\n"
                        f"📦 <b>Request #{req.id}</b>\n"
                        f"📞 <b>Driver Contact Details:</b>\n"
                        f"• Name: {driver_name}\n"
                        f"• Phone: {driver_phone}"
                    ),
                    parse_mode="HTML",
                )
            except Exception as notif_err:
                logger.error("Failed to notify student %s: %s", student.telegram_id, notif_err)

    except PackitbotError as exc:
        await session.rollback()
        await callback.answer(str(exc), show_alert=True)
    except Exception as exc:
        await session.rollback()
        logger.error("Error in driver_accept: %s", exc)
        await callback.answer("Something went wrong. Please try again.", show_alert=True)


@driver_router.message(F.text == "📊 Active Delivery")
@driver_router.message(Command("active_delivery"))
async def active_delivery_dashboard_handler(message: Message, session=None) -> None:
    """Display the active delivery dashboard for the requesting driver.

    Finds the most recent delivery request in an active status (ACCEPTED,
    EN_ROUTE_TO_PICKUP, PICKED_UP, or IN_TRANSIT) assigned to the driver.
    If none exists, shows an empty-state message; otherwise displays full
    request details with a status-update keyboard.

    Args:
        message: The incoming :class:`Message` (text or command trigger).
        session: Optional injected SQLAlchemy ``AsyncSession``.

    Calls / Depends on:
        :func:`delivery_status_update_keyboard`, :func:`driver_persistent_menu`,
        :class:`DriverAvailability`, :class:`RequestStatus`,
        ``MSG_EMPTY_STATE_DRIVER`` (from ``bot.core.constants.messages``).

    Registered on ``driver_router`` for ``F.text == "Active Delivery"``
    and ``Command("active_delivery")``.
    """
    if session is None:
        await message.answer("Session unavailable.")
        return

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from bot.core.constants.enums import RequestStatus
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.user import User

    try:
        driver_user_res = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        driver_user = driver_user_res.scalar_one_or_none()
        if not driver_user:
            await message.answer("Driver profile not found.")
            return

        active_statuses = [
            RequestStatus.ACCEPTED,
            RequestStatus.EN_ROUTE_TO_PICKUP,
            RequestStatus.PICKED_UP,
            RequestStatus.IN_TRANSIT,
        ]

        stmt = (
            select(DeliveryRequest)
            .options(selectinload(DeliveryRequest.student))
            .where(
                DeliveryRequest.driver_id == driver_user.id,
                DeliveryRequest.status.in_(active_statuses),
            )
            .order_by(DeliveryRequest.updated_at.desc())
        )
        res = await session.execute(stmt)
        active_req = res.scalars().first()

        if not active_req:
            from bot.core.constants.messages import MSG_EMPTY_STATE_DRIVER
            await message.answer(MSG_EMPTY_STATE_DRIVER, reply_markup=driver_persistent_menu(DriverAvailability.AVAILABLE))
            return

        student = active_req.student
        student_name = student.full_name if student else "Student"
        student_phone = student.phone_number if student else "N/A"

        dashboard_text = (
            f"📊 <b>Current Delivery Dashboard</b>\n\n"
            f"📦 <b>Request ID:</b> #{active_req.id}\n"
            f"📌 <b>Status:</b> {active_req.status.value.replace('_', ' ').title()}\n"
            f"📍 <b>Pickup:</b> {active_req.pickup_detail} ({active_req.hall_of_residence})\n"
            f"🎯 <b>Dropoff:</b> {active_req.dropoff_address} ({active_req.dropoff_landmark or 'N/A'})\n"
            f"👤 <b>Recipient:</b> {active_req.recipient_name} ({active_req.recipient_phone})\n"
            f"🧳 <b>Luggage:</b> {active_req.luggage_size.value.title()} x{active_req.luggage_count}\n"
            f"📝 <b>Instructions:</b> {active_req.special_instructions or 'None'}\n\n"
            f"📞 <b>Student Contact Details:</b>\n"
            f"• Name: {student_name}\n"
            f"• Phone: {student_phone}"
        )

        kb = delivery_status_update_keyboard(active_req.id, active_req.status)
        await message.answer(dashboard_text, parse_mode="HTML", reply_markup=kb)

    except Exception as exc:
        logger.error("Error loading active delivery dashboard: %s", exc)
        await message.answer("❌ Failed to retrieve active delivery details.")


@driver_router.callback_query(F.data.startswith("driver_step:"))
async def process_delivery_status_step(callback: CallbackQuery, session=None) -> None:
    """Handle a delivery status progression step from the driver.

    Parses the ``driver_step:<action>:<request_id>`` callback (3 parts),
    maps the action to a :class:`RequestStatus`, transitions the request
    via :class:`RequestService`, and on completion/failure resets the
    driver's availability to ``AVAILABLE``. The original message is edited
    with updated details and a contextual keyboard, and the student is
    notified.

    Args:
        callback: The incoming :class:`CallbackQuery` with
            ``driver_step:<action>:<request_id>`` data.
        session:  Optional injected SQLAlchemy ``AsyncSession``.

    Calls / Depends on:
        :class:`RequestService` (``transition_status``), :class:`TransitionDTO`,
        :func:`delivery_status_update_keyboard`, :class:`DriverProfile`,
        :class:`PackitbotError`.

    Registered on ``driver_router`` for callback data starting with
    ``driver_step:``.
    """
    # Split "driver_step:<action>:<request_id>" into exactly 3 parts.
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Invalid callback data.", show_alert=True)
        return

    action, request_id_str = parts[1], parts[2]
    request_id = int(request_id_str)

    if session is None:
        await callback.answer("Session unavailable.", show_alert=True)
        return

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from bot.core.constants.enums import DriverAvailability, RequestStatus
    from bot.core.exceptions import PackitbotError
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.driver_profile import DriverProfile
    from bot.core.models.user import User
    from bot.request.schemas import TransitionDTO
    from bot.request.service import RequestService

    action_to_status = {
        "en_route": RequestStatus.EN_ROUTE_TO_PICKUP,
        "picked_up": RequestStatus.PICKED_UP,
        "in_transit": RequestStatus.IN_TRANSIT,
        "delivered": RequestStatus.DELIVERED,
        "failed": RequestStatus.FAILED,
    }

    new_status = action_to_status.get(action)
    if not new_status:
        await callback.answer("Unknown status action.", show_alert=True)
        return

    try:
        driver_user_res = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        driver_user = driver_user_res.scalar_one_or_none()
        if not driver_user:
            await callback.answer("Driver user not found.", show_alert=True)
            return

        req_service = RequestService(session)
        dto = TransitionDTO(
            request_id=request_id,
            new_status=new_status,
            actor_id=driver_user.id,
            note=f"Status updated to {new_status.value} by driver {driver_user.id}",
        )
        updated_req, event = await req_service.transition_status(dto)

        # On delivery completion or failure, set driver availability back to AVAILABLE
        if new_status in (RequestStatus.DELIVERED, RequestStatus.FAILED):
            dp_res = await session.execute(
                select(DriverProfile).where(DriverProfile.user_id == driver_user.id)
            )
            dp = dp_res.scalar_one_or_none()
            if dp:
                dp.availability = DriverAvailability.AVAILABLE

        await session.commit()

        # Re-fetch request with loaded student
        req_res = await session.execute(
            select(DeliveryRequest)
            .options(selectinload(DeliveryRequest.student))
            .where(DeliveryRequest.id == request_id)
        )
        req = req_res.scalar_one()

        student = req.student
        student_name = student.full_name if student else "Student"
        student_phone = student.phone_number if student else "N/A"

        new_status_title = req.status.value.replace("_", " ").title()
        kb = delivery_status_update_keyboard(req.id, req.status)

        status_header = "✅ Delivery Completed!" if req.status == RequestStatus.DELIVERED else (
            "❌ Delivery Failed!" if req.status == RequestStatus.FAILED else f"🔄 Status Updated: {new_status_title}"
        )

        await callback.message.edit_text(
            f"<b>{status_header}</b>\n\n"
            f"📦 <b>Request ID:</b> #{req.id}\n"
            f"📌 <b>Current Status:</b> {new_status_title}\n"
            f"📍 <b>Pickup:</b> {req.pickup_detail} ({req.hall_of_residence})\n"
            f"🎯 <b>Dropoff:</b> {req.dropoff_address}\n"
            f"👤 <b>Recipient:</b> {req.recipient_name} ({req.recipient_phone})\n\n"
            f"📞 <b>Student Contact Details:</b>\n"
            f"• Name: {student_name}\n"
            f"• Phone: {student_phone}",
            parse_mode="HTML",
            reply_markup=kb,
        )
        await callback.answer(f"Status updated to {new_status_title}")

        # Notify student about status change
        if student and student.telegram_id:
            status_notif_msgs = {
                RequestStatus.EN_ROUTE_TO_PICKUP: f"🚗 Driver is en route to pickup location for Request #{req.id}.",
                RequestStatus.PICKED_UP: f"📦 Driver has picked up your package for Request #{req.id}.",
                RequestStatus.IN_TRANSIT: f"🚚 Your package for Request #{req.id} is now in transit!",
                RequestStatus.DELIVERED: f"🎉 Your delivery for Request #{req.id} has been completed!",
                RequestStatus.FAILED: f"⚠️ Delivery attempt failed for Request #{req.id}. Please contact support.",
            }
            notif_text = status_notif_msgs.get(req.status, f"Notice: Request #{req.id} status updated to {new_status_title}.")
            try:
                await callback.bot.send_message(
                    chat_id=student.telegram_id,
                    text=notif_text,
                )
            except Exception as notif_err:
                logger.error("Failed to notify student %s of status update: %s", student.telegram_id, notif_err)

    except PackitbotError as exc:
        await session.rollback()
        await callback.answer(str(exc), show_alert=True)
    except Exception as exc:
        await session.rollback()
        logger.error("Error processing delivery status step: %s", exc)
        await callback.answer("Failed to update status. Please try again.", show_alert=True)



@driver_router.callback_query(F.data.startswith("driver_reject:"))
async def process_driver_reject(callback: CallbackQuery, session=None) -> None:
    """Handle a driver rejecting an assigned delivery request.

    Parses the ``driver_reject:<request_id>`` callback, resets the request
    to ``PENDING`` status with ``driver_id`` cleared via
    :class:`RequestRepository`, edits the original message, and alerts all
    admins via direct message.

    Args:
        callback: The incoming :class:`CallbackQuery` with
            ``driver_reject:<request_id>`` data.
        session:  Optional injected SQLAlchemy ``AsyncSession``.

    Calls / Depends on:
        :class:`RequestRepository` (``update``), :class:`PackitbotError`.

    Registered on ``driver_router`` for callback data starting with
    ``driver_reject:``.
    """
    # Extract request ID from the "driver_reject:<request_id>" callback payload.
    request_id = int(callback.data.split(":")[1])

    if session is None:
        await callback.answer("Session unavailable.", show_alert=True)
        return

    from sqlalchemy import select
    from bot.core.constants.enums import RequestStatus, UserRole
    from bot.core.exceptions import PackitbotError
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.user import User
    from bot.request.repository import RequestRepository

    try:
        # Fetch driver user
        driver_user_res = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        driver_user = driver_user_res.scalar_one_or_none()
        if not driver_user:
            await callback.answer("Driver profile not found.", show_alert=True)
            return

        req_repo = RequestRepository(session)
        # Update request: set status back to PENDING and clear driver_id
        updated_req = await req_repo.update(
            request_id,
            status=RequestStatus.PENDING,
            driver_id=None,
        )
        await session.commit()

        await callback.message.edit_text(
            f"❌ <b>Assignment Rejected.</b>\nRequest #{request_id} has been returned to PENDING.",
            parse_mode="HTML",
        )
        await callback.answer("Request rejected.")

        # Alert admins about the rejected request
        admin_res = await session.execute(
            select(User).where(User.role == UserRole.ADMIN)
        )
        admins = admin_res.scalars().all()

        alert_text = (
            f"⚠️ <b>Request Assignment Rejected!</b>\n\n"
            f"📦 <b>Request #{request_id}</b> was rejected by Driver {driver_user.full_name or driver_user.id}.\n"
            f"Status has been reset to <b>PENDING</b> and requires reassignment."
        )

        for admin in admins:
            if admin.telegram_id:
                try:
                    await callback.bot.send_message(
                        chat_id=admin.telegram_id,
                        text=alert_text,
                        parse_mode="HTML",
                    )
                except Exception as notif_err:
                    logger.error("Failed to alert admin %s: %s", admin.telegram_id, notif_err)

    except PackitbotError as exc:
        await session.rollback()
        await callback.answer(str(exc), show_alert=True)
    except Exception as exc:
        await session.rollback()
        logger.error("Error in driver_reject: %s", exc)
        await callback.answer("Something went wrong. Please try again.", show_alert=True)
