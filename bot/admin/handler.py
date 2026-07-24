# bot/admin/handler.py

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.admin.keyboards import driver_approval_keyboard, pending_drivers_list_keyboard
from bot.admin.schemas import ReviewDriverDTO
from bot.admin.service import (
    approve_driver,
    get_driver_application_detail,
    get_pending_drivers,
    reject_driver,
)
from bot.core.constants.enums import UserRole
from bot.core.constants.messages import (
    MSG_MANAGEMENT_PORTAL,
    MSG_NO_PERMISSION,
    MSG_SOMETHING_WENT_WRONG,
)
from bot.core.exceptions import PackitbotError
from bot.core.models.user import User
from bot.core.services.notification_service import notify_driver_approval_status
from bot.core.utils.callback_data import AdminDriverApproval, PaginationNav

logger = logging.getLogger(__name__)
admin_router = Router()


def _is_admin(user: User | None) -> bool:
    return user is not None and user.role == UserRole.ADMIN


@admin_router.message(Command("admin"))
async def cmd_admin_portal(
    message: Message,
    state: FSMContext,
    user: User | None = None,  # Injected via AuthMiddleware
) -> None:
    """Renders the Admin Management Portal (Admin-only)."""
    await state.clear()

    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        return

    await message.answer(
        MSG_MANAGEMENT_PORTAL,
        parse_mode="Markdown",
    )


@admin_router.message(Command("verify"))
async def cmd_verify_drivers(
    message: Message,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Displays pending driver applications for review."""
    await state.clear()

    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        return

    drivers, total_pages = await get_pending_drivers(page=1)
    if not drivers:
        await message.answer("ℹ️ No pending driver applications found.")
        return

    keyboard = pending_drivers_list_keyboard(drivers, page=1, total_pages=total_pages)
    await message.answer(
        "📋 **Pending Driver Applications:**\nSelect a driver below to review their profile:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


@admin_router.callback_query(AdminDriverApproval.filter(F.action == "view"))
async def handle_view_driver_detail(
    callback: CallbackQuery,
    callback_data: AdminDriverApproval,
    user: User | None = None,
) -> None:
    """Displays driver application details and approval buttons."""
    if not _is_admin(user):
        await callback.answer("⛔ Admin access required.", show_alert=True)
        return

    try:
        detail = await get_driver_application_detail(callback_data.driver_id)
        text = (
            f"🚘 **Driver Application Review**\n\n"
            f"👤 **Name:** {detail.full_name}\n"
            f"📱 **Phone:** {detail.phone_number}\n"
            f"🚗 **Vehicle:** {detail.vehicle_type.upper()}\n"
            f"🔢 **Plate Number:** {detail.plate_number}\n"
            f"🪪 **License Number:** {detail.license_number}\n"
            f"📌 **Status:** {detail.status.value.upper()}\n"
        )
        if detail.username:
            text += f"💬 **Telegram:** @{detail.username}\n"

        keyboard = driver_approval_keyboard(detail.driver_id)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()
    except PackitbotError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error(f"Error fetching driver detail: {e}")
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(AdminDriverApproval.filter(F.action == "approve"))
async def handle_approve_driver(
    callback: CallbackQuery,
    callback_data: AdminDriverApproval,
    user: User | None = None,
) -> None:
    """Handles driver approval action."""
    if not _is_admin(user):
        await callback.answer("⛔ Admin access required.", show_alert=True)
        return

    try:
        dto = ReviewDriverDTO(
            driver_id=callback_data.driver_id,
            admin_telegram_id=user.telegram_id,
        )
        approved_driver = await approve_driver(dto)

        # Trigger instant notification
        await notify_driver_approval_status(
            bot=callback.bot,
            telegram_id=approved_driver.telegram_id,
            approved=True,
        )

        await callback.message.edit_text(
            f"✅ **Driver Approved Successfully!**\n\n"
            f"👤 **Driver:** {approved_driver.full_name}\n"
            f"📱 **Phone:** {approved_driver.phone_number}\n"
            f"Status updated to `APPROVED`.",
            parse_mode="Markdown",
        )
        await callback.answer("Driver approved successfully!")
    except PackitbotError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error(f"Error approving driver: {e}")
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(AdminDriverApproval.filter(F.action == "reject"))
async def handle_reject_driver(
    callback: CallbackQuery,
    callback_data: AdminDriverApproval,
    user: User | None = None,
) -> None:
    """Handles driver rejection action."""
    if not _is_admin(user):
        await callback.answer("⛔ Admin access required.", show_alert=True)
        return

    try:
        dto = ReviewDriverDTO(
            driver_id=callback_data.driver_id,
            admin_telegram_id=user.telegram_id,
        )
        rejected_driver = await reject_driver(dto)

        # Trigger instant notification
        await notify_driver_approval_status(
            bot=callback.bot,
            telegram_id=rejected_driver.telegram_id,
            approved=False,
        )

        await callback.message.edit_text(
            f"❌ **Driver Application Rejected**\n\n"
            f"👤 **Driver:** {rejected_driver.full_name}\n"
            f"Status updated to `REJECTED`.",
            parse_mode="Markdown",
        )
        await callback.answer("Driver application rejected.")
    except PackitbotError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error(f"Error rejecting driver: {e}")
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(F.data == "admin_pending_drivers_back")
async def handle_back_to_pending_list(
    callback: CallbackQuery,
    user: User | None = None,
) -> None:
    """Navigates back to the pending drivers list."""
    if not _is_admin(user):
        await callback.answer("⛔ Admin access required.", show_alert=True)
        return

    drivers, total_pages = await get_pending_drivers(page=1)
    if not drivers:
        await callback.message.edit_text("ℹ️ No pending driver applications found.")
        return

    keyboard = pending_drivers_list_keyboard(drivers, page=1, total_pages=total_pages)
    await callback.message.edit_text(
        "📋 **Pending Driver Applications:**\nSelect a driver below to review their profile:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    await callback.answer()