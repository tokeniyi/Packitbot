# bot/driver/handler.py
import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.core.constants.enums import DriverStatus
from bot.core.keyboards.common_kb import HomeButton
from bot.core.utils.validators import (
    ValidationError,
    validate_full_name,
    validate_license_number,
    validate_phone,
    validate_plate_number,
    validate_vehicle_type,
)
from bot.driver.keyboards import (
    driver_pending_menu,
    driver_persistent_menu,
    driver_registration_review_keyboard,
    vehicle_type_keyboard,
)
from bot.driver.schemas import RegisterDriverDTO
from bot.driver.service import get_driver_profile_by_telegram_id, register_driver
from bot.driver.states import DriverRegistrationFSM

logger = logging.getLogger(__name__)
driver_router = Router()


def _progress_bar(current: int, total: int = 5) -> str:
    filled = "█" * current
    empty = "░" * (total - current)
    return f"{filled}{empty}"


def _step_prompt(step: int, total: int, prompt: str) -> str:
    bar = _progress_bar(step, total)
    return f"Step {step}/{total} [{bar}]\n\n{prompt}"


async def _show_review_screen(target: Message | CallbackQuery, state: FSMContext) -> None:
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
    # Check if driver is already registered
    profile = await get_driver_profile_by_telegram_id(message.from_user.id, session=session)
    if profile:
        if profile.status == DriverStatus.APPROVED:
            await message.answer(
                "✅ You are already registered and approved as a driver!",
                reply_markup=driver_persistent_menu(profile.availability),
            )
            return
        elif profile.status == DriverStatus.PENDING_APPROVAL:
            await message.answer(
                "⏳ Your driver registration is currently <b>PENDING APPROVAL</b>.\n"
                "Please wait for an administrator to review your application.",
                parse_mode="HTML",
                reply_markup=driver_pending_menu(),
            )
            return

    await state.clear()
    await state.set_state(DriverRegistrationFSM.entering_full_name)
    await message.answer(_step_prompt(1, 5, "Enter your full name (First and Last name):"))


@driver_router.message(Command("cancel_driver_reg"))
@driver_router.callback_query(F.data == "driver_cancel_reg")
async def cancel_driver_registration(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    msg = "Driver registration cancelled."
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(msg, reply_markup=HomeButton())
    else:
        await event.answer(msg, reply_markup=HomeButton())


@driver_router.message(DriverRegistrationFSM.entering_full_name)
async def process_full_name(message: Message, state: FSMContext) -> None:
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
    await message.answer(_step_prompt(2, 5, "Enter your phone number (e.g., 08012345678):"))


@driver_router.message(DriverRegistrationFSM.entering_phone_number)
async def process_phone_number(message: Message, state: FSMContext) -> None:
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
        _step_prompt(3, 5, "Select your vehicle type:"),
        reply_markup=vehicle_type_keyboard(),
    )


@driver_router.callback_query(DriverRegistrationFSM.selecting_vehicle_type, F.data.startswith("driver_vtype:"))
async def process_vehicle_type(callback: CallbackQuery, state: FSMContext) -> None:
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
    await callback.message.answer(_step_prompt(4, 5, "Enter vehicle plate number (e.g. ABC-123DE):"))


@driver_router.message(DriverRegistrationFSM.entering_plate_number)
async def process_plate_number(message: Message, state: FSMContext) -> None:
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
    await message.answer(_step_prompt(5, 5, "Enter driver's license number:"))


@driver_router.message(DriverRegistrationFSM.entering_license_number)
async def process_license_number(message: Message, state: FSMContext) -> None:
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
    field = callback.data.split(":", 1)[1]
    await callback.answer()
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
    await callback.answer()
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
        await register_driver(dto, session=session)
    except Exception as exc:
        logger.error(f"Failed driver registration for user {callback.from_user.id}: {exc}")
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
    profile = await get_driver_profile_by_telegram_id(message.from_user.id, session=session)
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
