# bot/admin/handler.py

from bot.driver.repository import DriverRepository
from bot.core.db.session import async_session
from bot.core.constants.commands import CMD_DRIVERS
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from bot.admin.keyboards import (
    available_drivers_keyboard,
    broadcast_audience_keyboard,
    broadcast_confirm_keyboard,
    driver_approval_keyboard,
    driver_detail_keyboard,
    driver_edit_field_keyboard,
    driver_remove_confirm_keyboard,
    drivers_list_keyboard,
    pending_drivers_list_keyboard,
    pending_requests_list_keyboard,
    user_action_keyboard,
)
from sqlalchemy.ext.asyncio import AsyncSession
from bot.admin.schemas import (
    BanUserDTO,
    BroadcastDTO,
    DriverDetailDTO,
    DriverListItemDTO,
    PromoteAdminDTO,
    RemoveDriverDTO,
    ReviewDriverDTO,
    UnbanUserDTO,
    UpdateDriverFieldDTO,
)
from bot.admin.service import (
    add_authorized_driver,
    approve_driver,
    ban_user,
    get_all_drivers,
    get_available_drivers_ranked,
    get_broadcast_target_telegram_ids,
    get_driver_application_detail,
    get_driver_by_id,
    get_pending_drivers,
    get_pending_requests,
    get_stats,
    promote_admin,
    reject_driver,
    remove_driver,
    search_user_by_identifier,
    unban_user,
    update_driver_field,
)
from bot.admin.states import BroadcastFSM, DriverEditFSM
from bot.core.constants.limits import MAX_BROADCAST_LENGTH
from bot.core.constants.enums import UserRole
from bot.core.constants.messages import (
    ErrorMessages,
    SuccessMessages,
    MSG_MANAGEMENT_PORTAL,
    MSG_NO_PERMISSION,
    MSG_NOTIFY_DRIVER_ASSIGNED,
    MSG_SOMETHING_WENT_WRONG,
    MSG_STATS,
    MSG_DRIVER_LIST_TITLE,
    MSG_DRIVER_DETAIL_TITLE,
    MSG_DRIVER_EDIT_PROMPT,
    MSG_DRIVER_EDIT_SUCCESS,
    MSG_DRIVER_EDIT_INPUT_PROMPT,
    MSG_DRIVER_REMOVE_CONFIRM,
    MSG_DRIVER_REMOVED,
    MSG_DRIVER_REMOVE_CANCELLED,
)
from bot.core.exceptions import PackitbotError, ValidationError
from bot.core.models.user import User
from bot.core.services.notification_service import notify_driver_approval_status, send_broadcast_message
from bot.core.utils.callback_data import AdminAssign, AdminDriverApproval, AdminDriverEdit, AdminDriverManage, AdminDriverRemove, AdminUserAction, PaginationNav
from bot.request.schemas import AssignDriverDTO
from bot.request.service import RequestService

logger = logging.getLogger(__name__)
admin_router = Router()



class AdminUserMgmtState(StatesGroup):
    waiting_for_user_identifier = State()
    waiting_for_ban_reason = State()


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
    session: AsyncSession | None = None,
) -> None:
    """Displays live delivery metrics and system statistics."""
    await state.clear()

    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        return

    try:
        stats = await get_stats(session)
        avg_dur_str = (
            f"{stats.avg_delivery_duration_minutes} mins"
            if stats.avg_delivery_duration_minutes is not None
            else "N/A"
        )
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
            avg_delivery_duration=avg_dur_str,
            total_users=stats.total_users,
            total_students=stats.total_students,
            total_drivers=stats.total_drivers,
            total_admins=stats.total_admins,
            approved_drivers=stats.approved_drivers,
            active_drivers=stats.active_drivers,
            pending_drivers=stats.pending_drivers,
            rejected_drivers=stats.rejected_drivers,
            suspended_drivers=stats.suspended_drivers,
            total_feedbacks=stats.total_feedbacks,
            avg_rating=stats.avg_rating if stats.avg_rating is not None else "N/A",
        )
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error("Error fetching stats: %s", e)
        await message.answer(MSG_SOMETHING_WENT_WRONG)


@admin_router.message(Command("verify"))
async def cmd_verify_drivers(
    message: Message,
    state: FSMContext,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Displays pending driver applications for review."""
    await state.clear()

    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        return

    drivers, total_pages = await get_pending_drivers(session, page=1)
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
    session: AsyncSession | None = None,
) -> None:
    """Lists PENDING delivery requests for driver assignment."""
    await state.clear()

    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        return

    requests, total_pages = await get_pending_requests(session, page=1)
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
    session: AsyncSession | None = None,
) -> None:
    """Handles pagination for pending requests list."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    page = int(callback.data.split(":")[1])
    requests, total_pages = await get_pending_requests(session, page=page)
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
    session: AsyncSession | None = None,
) -> None:
    """Displays available drivers ranked by average rating for selection."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    request_id = int(callback.data.split(":")[1])
    drivers = await get_available_drivers_ranked(session)
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
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
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
                    logger.error("Failed to notify driver %s: %s", driver_profile.user.telegram_id, notif_err)

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
            logger.error("Error assigning driver: %s", e)
            await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(F.data == "admin_pending_req_back")
async def handle_back_to_pending_requests(
    callback: CallbackQuery,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Navigates back to the pending requests list."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    requests, total_pages = await get_pending_requests(session, page=1)
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
    session: AsyncSession | None = None,
) -> None:
    """Displays driver application details and approval buttons."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    try:
        detail = await get_driver_application_detail(session, callback_data.driver_id)
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
        logger.error("Error fetching driver detail: %s", e)
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(AdminDriverApproval.filter(F.action == "approve"))
async def handle_approve_driver(
    callback: CallbackQuery,
    callback_data: AdminDriverApproval,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Handles driver approval action."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    try:
        dto = ReviewDriverDTO(
            driver_id=callback_data.driver_id,
            admin_telegram_id=user.telegram_id,
        )
        approved_driver = await approve_driver(session, dto)

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
        logger.error("Error approving driver: %s", e)
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(AdminDriverApproval.filter(F.action == "reject"))
async def handle_reject_driver(
    callback: CallbackQuery,
    callback_data: AdminDriverApproval,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Handles driver rejection action."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    try:
        dto = ReviewDriverDTO(
            driver_id=callback_data.driver_id,
            admin_telegram_id=user.telegram_id,
        )
        rejected_driver = await reject_driver(session, dto)

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
        logger.error("Error rejecting driver: %s", e)
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(F.data == "admin_pending_drivers_back")
async def handle_back_to_pending_list(
    callback: CallbackQuery,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Navigates back to the pending drivers list."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    drivers, total_pages = await get_pending_drivers(session, page=1)
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


@admin_router.message(Command(CMD_DRIVERS))
async def cmd_drivers(
    message: Message,
    state: FSMContext,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Lists all driver records for admin management."""
    await state.clear()

    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        return

    drivers, total_pages = await get_all_drivers(session, page=1)
    if not drivers:
        await message.answer("ℹ️ No driver records found.")
        return

    keyboard = drivers_list_keyboard(drivers, page=1, total_pages=total_pages)
    await message.answer(
        MSG_DRIVER_LIST_TITLE,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


@admin_router.callback_query(F.data.startswith("admin_drv_page:"))
async def handle_drivers_pagination(
    callback: CallbackQuery,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Handles pagination for the drivers list."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    page = int(callback.data.split(":")[1])
    drivers, total_pages = await get_all_drivers(session, page=page)
    if not drivers:
        await callback.message.edit_text("ℹ️ No driver records found.")
        return

    keyboard = drivers_list_keyboard(drivers, page=page, total_pages=total_pages)
    await callback.message.edit_text(
        MSG_DRIVER_LIST_TITLE,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    await callback.answer()


@admin_router.callback_query(AdminDriverManage.filter(F.action == "view"))
async def handle_view_driver_detail_manage(
    callback: CallbackQuery,
    callback_data: AdminDriverManage,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Displays driver record details for management."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    try:
        detail = await get_driver_by_id(session, callback_data.driver_id)
        text = MSG_DRIVER_DETAIL_TITLE.format(
            full_name=detail.full_name,
            phone_number=detail.phone_number,
            license_number=detail.license_number,
            vehicle_type=detail.vehicle_type.upper(),
            plate_number=detail.plate_number,
            status=detail.status.value.upper(),
            availability=detail.availability.upper(),
            rating_avg=f"{detail.rating_avg:.1f}",
            total_deliveries=detail.total_deliveries,
        )
        if detail.username:
            text += f"\n💬 **Telegram:** @{detail.username}"

        keyboard = driver_detail_keyboard(detail.driver_id)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()
    except PackitbotError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error("Error fetching driver detail: %s", e)
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(AdminDriverManage.filter(F.action == "edit"))
async def handle_driver_edit_menu(
    callback: CallbackQuery,
    callback_data: AdminDriverManage,
    user: User | None = None,
) -> None:
    """Shows the field selection menu for editing a driver record."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    keyboard = driver_edit_field_keyboard(callback_data.driver_id)
    await callback.message.edit_text(
        MSG_DRIVER_EDIT_PROMPT,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    await callback.answer()


@admin_router.callback_query(AdminDriverEdit.filter())
async def handle_driver_field_select(
    callback: CallbackQuery,
    callback_data: AdminDriverEdit,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Prompts admin to enter a new value for the selected driver field."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    field_labels = {
        "full_name": "Name",
        "phone_number": "Phone Number",
        "vehicle_type": "Vehicle Type",
        "plate_number": "Plate Number",
        "license_number": "License Number",
        "status": "Status",
    }
    field_label = field_labels.get(callback_data.field, callback_data.field)

    await state.update_data(
        driver_id=callback_data.driver_id,
        field=callback_data.field,
    )
    await state.set_state(DriverEditFSM.waiting_for_field_value)

    await callback.message.answer(
        MSG_DRIVER_EDIT_INPUT_PROMPT.format(
            field_label=field_label,
            current_value="Current value",
        ),
        parse_mode="Markdown",
    )
    await callback.answer()


@admin_router.message(DriverEditFSM.waiting_for_field_value)
async def handle_driver_field_input(
    message: Message,
    state: FSMContext,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Processes the new field value and updates the driver record."""
    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        await state.clear()
        return

    data = await state.get_data()
    driver_id = data.get("driver_id")
    field = data.get("field")
    await state.clear()

    if not driver_id or not field:
        await message.answer("❌ Session expired. Please try editing the driver again.")
        return

    new_value = message.text.strip() if message.text else ""
    if not new_value:
        await message.answer("❌ Value cannot be empty. Please try again.")
        return

    try:
        dto = UpdateDriverFieldDTO(
            driver_id=driver_id,
            field=field,
            value=new_value,
            admin_telegram_id=user.telegram_id,
        )
        updated_driver = await update_driver_field(session, dto)

        field_labels = {
            "full_name": "Name",
            "phone_number": "Phone Number",
            "vehicle_type": "Vehicle Type",
            "plate_number": "Plate Number",
            "license_number": "License Number",
            "status": "Status",
        }
        field_label = field_labels.get(field, field)

        await message.answer(
            MSG_DRIVER_EDIT_SUCCESS.format(
                field=field_label,
                value=new_value,
            ),
            parse_mode="Markdown",
        )
    except PackitbotError as e:
        await message.answer(f"❌ {e}")
    except Exception as e:
        logger.error("Error updating driver field: %s", e)
        await message.answer(MSG_SOMETHING_WENT_WRONG)


@admin_router.callback_query(AdminDriverManage.filter(F.action == "remove"))
async def handle_remove_driver_confirm(
    callback: CallbackQuery,
    callback_data: AdminDriverManage,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Shows removal confirmation for a driver record."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    try:
        detail = await get_driver_by_id(session, callback_data.driver_id)
        keyboard = driver_remove_confirm_keyboard(detail.driver_id)
        await callback.message.edit_text(
            MSG_DRIVER_REMOVE_CONFIRM.format(full_name=detail.full_name),
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        await callback.answer()
    except PackitbotError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error("Error preparing driver removal: %s", e)
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(AdminDriverRemove.filter(F.action == "confirm"))
async def handle_remove_driver_execute(
    callback: CallbackQuery,
    callback_data: AdminDriverRemove,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Executes driver record removal."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    try:
        detail = await get_driver_by_id(session, callback_data.driver_id)
        dto = RemoveDriverDTO(
            driver_id=callback_data.driver_id,
            admin_telegram_id=user.telegram_id,
        )
        await remove_driver(session, dto)

        await callback.message.edit_text(
            MSG_DRIVER_REMOVED.format(full_name=detail.full_name),
            parse_mode="Markdown",
        )
        await callback.answer("Driver record removed successfully!")
    except PackitbotError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error("Error removing driver: %s", e)
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(AdminDriverRemove.filter(F.action == "cancel"))
async def handle_remove_driver_cancel(
    callback: CallbackQuery,
    callback_data: AdminDriverRemove,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Cancels driver removal and returns to driver detail."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    try:
        detail = await get_driver_by_id(session, callback_data.driver_id)
        keyboard = driver_detail_keyboard(detail.driver_id)
        text = MSG_DRIVER_DETAIL_TITLE.format(
            full_name=detail.full_name,
            phone_number=detail.phone_number,
            license_number=detail.license_number,
            vehicle_type=detail.vehicle_type.upper(),
            plate_number=detail.plate_number,
            status=detail.status.value.upper(),
            availability=detail.availability.upper(),
            rating_avg=f"{detail.rating_avg:.1f}",
            total_deliveries=detail.total_deliveries,
        )
        if detail.username:
            text += f"\n💬 **Telegram:** @{detail.username}"

        await callback.message.edit_text(
            MSG_DRIVER_REMOVE_CANCELLED + "\n\n" + text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        await callback.answer("Removal cancelled.")
    except PackitbotError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error("Error cancelling driver removal: %s", e)
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(F.data.startswith("admin_driver_detail_back:"))
async def handle_driver_edit_back(
    callback: CallbackQuery,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Navigates back to driver detail from edit menu."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    try:
        driver_id = int(callback.data.split(":")[1])
        detail = await get_driver_by_id(session, driver_id)
        keyboard = driver_detail_keyboard(detail.driver_id)
        text = MSG_DRIVER_DETAIL_TITLE.format(
            full_name=detail.full_name,
            phone_number=detail.phone_number,
            license_number=detail.license_number,
            vehicle_type=detail.vehicle_type.upper(),
            plate_number=detail.plate_number,
            status=detail.status.value.upper(),
            availability=detail.availability.upper(),
            rating_avg=f"{detail.rating_avg:.1f}",
            total_deliveries=detail.total_deliveries,
        )
        if detail.username:
            text += f"\n💬 **Telegram:** @{detail.username}"

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()
    except PackitbotError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error("Error navigating back: %s", e)
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(F.data == "admin_drivers_back")
async def handle_drivers_back(
    callback: CallbackQuery,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Navigates back to the first page of the drivers list."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    drivers, total_pages = await get_all_drivers(session, page=1)
    if not drivers:
        await callback.message.edit_text("ℹ️ No driver records found.")
        return

    keyboard = drivers_list_keyboard(drivers, page=1, total_pages=total_pages)
    await callback.message.edit_text(
        MSG_DRIVER_LIST_TITLE,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    await callback.answer()


@admin_router.message(Command("users"))
async def cmd_user_management(
    message: Message,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Prompt admin to enter user ID, Telegram ID, or Username for management."""
    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        return

    await state.set_state(AdminUserMgmtState.waiting_for_user_identifier)
    await message.answer(
        "🔍 **User Management Search**\n\n"
        "Please enter the **User ID**, **Telegram ID**, or **@username** of the user you want to manage:",
        parse_mode="Markdown",
    )


@admin_router.message(AdminUserMgmtState.waiting_for_user_identifier)
async def process_user_search(
    message: Message,
    state: FSMContext,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Processes user search input and displays user profile with action buttons."""
    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        await state.clear()
        return

    identifier = message.text.strip()
    user_detail = await search_user_by_identifier(session, identifier)

    if not user_detail:
        await message.answer(
            f"❌ No user found matching `{identifier}`.\n"
            f"Please check the ID or username and try again with /users.",
            parse_mode="Markdown",
        )
        await state.clear()
        return

    await state.clear()
    status_icon = "🔴 BANNED" if user_detail.account_status == "banned" else "🟢 ACTIVE"
    role_str = (user_detail.role or "N/A").upper()

    text = (
        f"👤 **User Profile Details**\n\n"
        f"🆔 **DB ID:** {user_detail.user_id}\n"
        f"📱 **Telegram ID:** {user_detail.telegram_id}\n"
        f"👤 **Name:** {user_detail.full_name or 'N/A'}\n"
        f"💬 **Username:** @{user_detail.username if user_detail.username else 'N/A'}\n"
        f"📞 **Phone:** {user_detail.phone_number or 'N/A'}\n"
        f"🎭 **Role:** {role_str}\n"
        f"📌 **Status:** {status_icon}\n"
    )
    if user_detail.account_status == "banned":
        text += f"⚠️ **Ban Reason:** {user_detail.banned_reason or 'No reason provided'}\n"
        text += f"🕒 **Banned At:** {user_detail.banned_at or 'N/A'}\n"

    keyboard = user_action_keyboard(user_detail)
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@admin_router.callback_query(AdminUserAction.filter(F.action == "ban"))
async def handle_ban_user_init(
    callback: CallbackQuery,
    callback_data: AdminUserAction,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Prompts admin to enter a reason for banning the user."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    await state.update_data(target_user_id=callback_data.user_id)
    await state.set_state(AdminUserMgmtState.waiting_for_ban_reason)

    await callback.message.answer(
        f"⚠️ **Ban User #{callback_data.user_id}**\n\n"
        f"Please reply with the reason for banning this user (or type `skip` for no reason):",
        parse_mode="Markdown",
    )
    await callback.answer()


@admin_router.message(AdminUserMgmtState.waiting_for_ban_reason)
async def process_ban_reason(
    message: Message,
    state: FSMContext,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Executes user ban with recorded reason."""
    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        await state.clear()
        return

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    await state.clear()

    if not target_user_id:
        await message.answer("❌ Session expired. Please search for the user again with /users.")
        return

    reason_text = message.text.strip()
    reason = None if reason_text.lower() == "skip" else reason_text

    try:
        dto = BanUserDTO(
            target_user_id=target_user_id,
            admin_telegram_id=user.telegram_id,
            reason=reason,
        )
        updated_user = await ban_user(session, dto)
        await message.answer(
            f"🛑 **User #{updated_user.user_id} has been banned.**\n\n"
            f"👤 **Name:** {updated_user.full_name or 'N/A'}\n"
            f"📌 **Status:** BANNED\n"
            f"📝 **Reason:** {updated_user.banned_reason or 'None'}",
            parse_mode="Markdown",
        )
    except PackitbotError as e:
        await message.answer(f"❌ {e}")
    except Exception as e:
        logger.error("Error banning user: %s", e)
        await message.answer(MSG_SOMETHING_WENT_WRONG)


@admin_router.callback_query(AdminUserAction.filter(F.action == "unban"))
async def handle_unban_user(
    callback: CallbackQuery,
    callback_data: AdminUserAction,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Executes user unban action."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    try:
        dto = UnbanUserDTO(
            target_user_id=callback_data.user_id,
            admin_telegram_id=user.telegram_id,
        )
        updated_user = await unban_user(session, dto)
        await callback.message.edit_text(
            f"🟢 **User #{updated_user.user_id} has been unbanned.**\n\n"
            f"👤 **Name:** {updated_user.full_name or 'N/A'}\n"
            f"📌 **Status:** ACTIVE",
            parse_mode="Markdown",
        )
        await callback.answer("User unbanned successfully!")
    except PackitbotError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error("Error unbanning user: %s", e)
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


@admin_router.callback_query(AdminUserAction.filter(F.action == "promote"))
async def handle_promote_admin(
    callback: CallbackQuery,
    callback_data: AdminUserAction,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Executes admin promotion action."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    try:
        dto = PromoteAdminDTO(
            target_user_id=callback_data.user_id,
            admin_telegram_id=user.telegram_id,
        )
        updated_user = await promote_admin(session, dto)
        await callback.message.edit_text(
            f"⭐ **User #{updated_user.user_id} promoted to ADMIN!**\n\n"
            f"👤 **Name:** {updated_user.full_name or 'N/A'}\n"
            f"🎭 **Role:** ADMIN",
            parse_mode="Markdown",
        )
        await callback.answer("User promoted to Admin!")
    except PackitbotError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error("Error promoting user: %s", e)
        await callback.answer(MSG_SOMETHING_WENT_WRONG, show_alert=True)


# --- Broadcast Handlers ---


@admin_router.message(Command("broadcast"))
async def cmd_broadcast(
    message: Message,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Initiates the broadcast workflow by requesting audience selection."""
    await state.clear()

    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        return

    await state.set_state(BroadcastFSM.waiting_for_audience)
    await message.answer(
        "📢 **Admin Broadcast**\n\n"
        "Please select the target audience for your broadcast message:",
        reply_markup=broadcast_audience_keyboard(),
        parse_mode="Markdown",
    )


@admin_router.callback_query(BroadcastFSM.waiting_for_audience, F.data.startswith("broadcast_audience:"))
async def process_broadcast_audience(
    callback: CallbackQuery,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Handles audience selection and prompts for message content."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        return

    audience = callback.data.split(":")[1]
    await state.update_data(audience=audience)
    await state.set_state(BroadcastFSM.waiting_for_content)

    audience_name = "Students" if audience == "students" else ("Drivers" if audience == "drivers" else "All Users")
    await callback.message.edit_text(
        f"🎯 **Target Audience:** `{audience_name}`\n\n"
        "Please type and send the broadcast message text below.\n"
        f"*(Maximum {MAX_BROADCAST_LENGTH} characters)*",
        parse_mode="Markdown",
    )
    await callback.answer()


@admin_router.message(BroadcastFSM.waiting_for_content)
async def process_broadcast_content(
    message: Message,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Validates broadcast message content and shows mandatory preview with confirmation."""
    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        await state.clear()
        return

    content = message.text.strip() if message.text else ""
    if not content:
        await message.answer("❌ Message content cannot be empty. Please enter your broadcast text:")
        return

    if len(content) > MAX_BROADCAST_LENGTH:
        await message.answer(
            f"❌ Broadcast message is too long ({len(content)} characters). "
            f"Maximum allowed is {MAX_BROADCAST_LENGTH} characters. Please enter a shorter message:"
        )
        return

    await state.update_data(content=content)
    await state.set_state(BroadcastFSM.waiting_for_confirmation)

    data = await state.get_data()
    audience = data.get("audience", "all")
    audience_name = "Students" if audience == "students" else ("Drivers" if audience == "drivers" else "All Users")

    await message.answer(
        "🔍 **Broadcast Preview & Confirmation**\n\n"
        f"🎯 **Audience:** `{audience_name}`\n\n"
        "📝 **Message Preview:**\n"
        "----------------------------------------\n"
        f"{content}\n"
        "----------------------------------------\n\n"
        "⚠️ Please review carefully before bulk dispatching.",
        reply_markup=broadcast_confirm_keyboard(),
        parse_mode="Markdown",
    )


@admin_router.callback_query(BroadcastFSM.waiting_for_confirmation, F.data == "broadcast_confirm:send")
async def execute_broadcast(
    callback: CallbackQuery,
    state: FSMContext,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Executes bulk dispatching of broadcast message via notification_service."""
    if not _is_admin(user):
        await callback.answer(ErrorMessages.ADMIN_ACCESS_REQUIRED, show_alert=True)
        await state.clear()
        return

    data = await state.get_data()
    audience = data.get("audience")
    content = data.get("content")

    if not audience or not content:
        await callback.message.edit_text("❌ Broadcast session data missing or expired.")
        await state.clear()
        return

    broadcast_dto = BroadcastDTO(
        audience=audience,
        message_text=content,
        admin_telegram_id=user.telegram_id,
    )

    await callback.message.edit_text("⏳ Dispatching broadcast messages... Please wait.")

    target_telegram_ids = await get_broadcast_target_telegram_ids(session, broadcast_dto.audience)
    total_targets = len(target_telegram_ids)
    success_count = 0

    for tid in target_telegram_ids:
        sent = await send_broadcast_message(
            bot=callback.bot,
            telegram_id=tid,
            text=broadcast_dto.message_text,
        )
        if sent:
            success_count += 1

    await callback.message.edit_text(
        f"✅ **Broadcast Completed!**\n\n"
        f"🎯 **Target Audience:** `{broadcast_dto.audience.capitalize()}`\n"
        f"📊 **Success Rate:** `{success_count} / {total_targets}` delivered",
        parse_mode="Markdown",
    )
    await state.clear()
    await callback.answer("Broadcast sent successfully!")


@admin_router.callback_query(F.data == "broadcast_cancel")
async def cancel_broadcast(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Cancels current broadcast process."""
    await state.clear()
    await callback.message.edit_text("❌ Broadcast operation cancelled.")
    await callback.answer("Broadcast cancelled")


@admin_router.message(Command("add_driver"))
async def cmd_add_driver(
    message: Message,
    state: FSMContext,
    user: User | None = None,
    session=None,
) -> None:
    """Add a Telegram user to the pre-approved authorized driver list.

    Triggered by ``/add_driver <telegram_id>``.  Only admins may use this
    command.  The target Telegram ID is added to the ``AuthorizedDriver``
    table so that the user (once they have the DRIVER role) can run
    ``/register_driver`` to begin the driver registration flow.

    Args:
        message: The incoming :class:`Message` containing the command.
        state:   The FSM context (cleared at the start).
        user:    The authenticated :class:`User` (injected by AuthMiddleware).
        session: Optional injected SQLAlchemy ``AsyncSession``.
    """
    await state.clear()

    if not _is_admin(user):
        await message.answer(MSG_NO_PERMISSION)
        return

    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
        await message.answer(
            "📋 **Usage:**\n"
            "• `/add_driver <telegram_id>` — Add user to authorized driver list",
            parse_mode="Markdown",
        )
        return

    target_tg_id = int(parts[1])

    try:
        added = await add_authorized_driver(target_tg_id, user.telegram_id, session)
        if added:
            await message.answer(
                f"✅ Telegram user {target_tg_id} has been added to the authorized driver list."
            )
        else:
            await message.answer(
                f"ℹ️ Telegram user {target_tg_id} is already in the authorized driver list."
            )
    except ValidationError as e:
        await message.answer(f"❌ {e}")
    except Exception as e:
        logger.error("Error adding authorized driver: %s", e)
        await message.answer(MSG_SOMETHING_WENT_WRONG)