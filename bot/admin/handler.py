# bot/admin/handler.py

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.admin.keyboards import (
    available_drivers_keyboard,
    driver_approval_keyboard,
    pending_drivers_list_keyboard,
    pending_requests_list_keyboard,
)
from bot.admin.schemas import ReviewDriverDTO
from bot.admin.service import (
    approve_driver,
    get_available_drivers_ranked,
    get_driver_application_detail,
    get_pending_drivers,
    get_pending_requests,
    get_stats,
    reject_driver,
)
from bot.core.constants.enums import UserRole
from bot.core.constants.messages import (
    MSG_MANAGEMENT_PORTAL,
    MSG_NO_PERMISSION,
    MSG_NOTIFY_DRIVER_ASSIGNED,
    MSG_SOMETHING_WENT_WRONG,
    MSG_STATS,
)
from bot.core.db.session import async_session
from bot.core.exceptions import PackitbotError
from bot.core.models.user import User
from bot.core.services.notification_service import notify_driver_approval_status
from bot.core.utils.callback_data import AdminAssign, AdminDriverApproval, PaginationNav
from bot.driver.repository import DriverRepository
from bot.request.repository import RequestRepository
from bot.request.schemas import AssignDriverDTO
from bot.request.service import RequestService

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


@admin_router.message(Command("stats"))
async def cmd_stats(
    message: Message,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Displays live delivery metrics and system statistics."""
    await state.clear()

    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        return

    try:
        stats = await get_stats()
        text = MSG_STATS.format(
            total_requests=stats.total_requests,
            pending_requests=stats.pending_requests,
            assigned_requests=stats.assigned_requests,
            accepted_requests=stats.accepted_requests,
            en_route_requests=stats.en_route_requests,
            picked_up_requests=stats.picked_up_requests,
            in_transit_requests=stats.in_transit_requests,
            delivered_requests=stats.delivered_requests,
            cancelled_requests=stats.cancelled_requests,
            failed_requests=stats.failed_requests,
            rejected_by_driver_requests=stats.rejected_by_driver_requests,
            total_users=stats.total_users,
            total_students=stats.total_students,
            total_drivers=stats.total_drivers,
            total_admins=stats.total_admins,
            approved_drivers=stats.approved_drivers,
            pending_drivers=stats.pending_drivers,
            rejected_drivers=stats.rejected_drivers,
            suspended_drivers=stats.suspended_drivers,
            total_feedbacks=stats.total_feedbacks,
            avg_rating=stats.avg_rating if stats.avg_rating is not None else "N/A",
        )
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        await message.answer(MSG_SOMETHING_WENT_WRONG)


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


@admin_router.message(Command("assign"))
@admin_router.message(Command("orders"))
async def cmd_pending_requests(
    message: Message,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Lists PENDING delivery requests for driver assignment."""
    await state.clear()

    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        return

    requests, total_pages = await get_pending_requests(page=1)
    if not requests:
        await message.answer("ℹ️ No pending delivery requests waiting for assignment.")
        return

    keyboard = pending_requests_list_keyboard(requests, page=1, total_pages=total_pages)
    await message.answer(
        "📦 **Pending Delivery Requests:**\nSelect a request to assign a driver:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


@admin_router.callback_query(F.data.startswith("admin_req_page:"))
async def handle_pending_requests_pagination(
    callback: CallbackQuery,
    user: User | None = None,
) -> None:
    """Handles pagination for pending requests list."""
    if not _is_admin(user):
        await callback.answer("⛔ Admin access required.", show_alert=True)
        return

    page = int(callback.data.split(":")[1])
    requests, total_pages = await get_pending_requests(page=page)
    if not requests:
        await callback.message.edit_text("ℹ️ No pending delivery requests waiting for assignment.")
        return

    keyboard = pending_requests_list_keyboard(requests, page=page, total_pages=total_pages)
    await callback.message.edit_text(
        "📦 **Pending Delivery Requests:**\nSelect a request to assign a driver:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_assign_req:"))
async def handle_select_request_for_assignment(
    callback: CallbackQuery,
    user: User | None = None,
) -> None:
    """Displays available drivers ranked by average rating for selection."""
    if not _is_admin(user):
        await callback.answer("⛔ Admin access required.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[1])
    drivers = await get_available_drivers_ranked()
    if not drivers:
        await callback.answer("⚠️ No active/available approved drivers found.", show_alert=True)
        return

    keyboard = available_drivers_keyboard(drivers, request_id=request_id)
    await callback.message.edit_text(
        f"🎯 **Assign Driver for Request #{request_id}**\n\n"
        f"Select an available driver ranked by rating:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    await callback.answer()


@admin_router.callback_query(AdminAssign.filter())
async def handle_confirm_driver_assignment(
    callback: CallbackQuery,
    callback_data: AdminAssign,
    user: User | None = None,
) -> None:
    """Executes driver assignment via RequestService and notifies the assigned driver."""
    if not _is_admin(user):
        await callback.answer("⛔ Admin access required.", show_alert=True)
        return

    async with async_session() as session:
        try:
            req_service = RequestService(session)
            driver_repo = DriverRepository(session)

            driver_profile = await driver_repo.get_by_id(callback_data.driver_id)
            if not driver_profile:
                await callback.answer("❌ Driver profile not found.", show_alert=True)
                return

            dto = AssignDriverDTO(
                request_id=callback_data.request_id,
                driver_id=callback_data.driver_id,
                admin_id=user.id,
            )
            updated_req, event = await req_service.assign_driver(dto, driver_profile)
            await session.commit()

            # Notify driver
            if driver_profile.user and driver_profile.user.telegram_id:
                try:
                    from bot.driver.keyboards import driver_assignment_response_keyboard
                    await callback.bot.send_message(
                        chat_id=driver_profile.user.telegram_id,
                        text=f"{MSG_NOTIFY_DRIVER_ASSIGNED}\n\n📦 **Request #{updated_req.id}**\n📍 Pickup: {updated_req.hall_of_residence}\n🎯 Dropoff: {updated_req.dropoff_address}",
                        reply_markup=driver_assignment_response_keyboard(updated_req.id),
                        parse_mode="Markdown",
                    )
                except Exception as notif_err:
                    logger.error(f"Failed to notify driver {driver_profile.user.telegram_id}: {notif_err}")

            await callback.message.edit_text(
                f"✅ **Request #{updated_req.id} assigned successfully!**\n\n"
                f"👤 **Driver ID:** {callback_data.driver_id}\n"
                f"📌 **Status:** ASSIGNED",
                parse_mode="Markdown",
            )
            await callback.answer("Driver assigned successfully!")

        except PackitbotError as e:
            await session.rollback()
            await callback.answer(str(e), show_alert=True)
        except Exception as e:
            await session.rollback()
            logger.error(f"Error assigning driver: {e}")
            await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(F.data == "admin_pending_req_back")
async def handle_back_to_pending_requests(
    callback: CallbackQuery,
    user: User | None = None,
) -> None:
    """Navigates back to the pending requests list."""
    if not _is_admin(user):
        await callback.answer("⛔ Admin access required.", show_alert=True)
        return

    requests, total_pages = await get_pending_requests(page=1)
    if not requests:
        await callback.message.edit_text("ℹ️ No pending delivery requests waiting for assignment.")
        return

    keyboard = pending_requests_list_keyboard(requests, page=1, total_pages=total_pages)
    await callback.message.edit_text(
        "📦 **Pending Delivery Requests:**\nSelect a request to assign a driver:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    await callback.answer()


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