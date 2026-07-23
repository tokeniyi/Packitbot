from datetime import date, datetime, timedelta

from bot.core.constants.enums import (
    AccountStatus,
    AdminActionType,
    CancelledBy,
    DriverAvailability,
    DriverStatus,
    LuggageSize,
    RequestStatus,
    VerificationStatus,
)

WAT_OFFSET = timedelta(hours=1)


def _utc_to_wat(utc_dt: datetime) -> datetime:
    if utc_dt.tzinfo is None:
        return utc_dt + WAT_OFFSET
    return utc_dt.astimezone(timedelta(hours=1))


def format_date_for_display(utc_date: date) -> str:
    return utc_date.strftime("%d %b %Y")


def format_datetime_for_display(utc_dt: datetime) -> str:
    return _utc_to_wat(utc_dt).strftime("%d %b %Y, %I:%M %p")


_STATUS_EMOJI = {
    RequestStatus.PENDING: "⏳",
    RequestStatus.ASSIGNED: "👤",
    RequestStatus.ACCEPTED: "✅",
    RequestStatus.REJECTED_BY_DRIVER: "❌",
    RequestStatus.EN_ROUTE_TO_PICKUP: "🚗",
    RequestStatus.PICKED_UP: "📦",
    RequestStatus.IN_TRANSIT: "🛣️",
    RequestStatus.DELIVERED: "🏁",
    RequestStatus.CANCELLED: "🚫",
    RequestStatus.FAILED: "⚠️",
}

_CANCELLED_BY_LABEL = {
    CancelledBy.STUDENT: "Cancelled by student",
    CancelledBy.ADMIN: "Cancelled by admin",
    CancelledBy.SYSTEM: "Cancelled by system",
}

_DRIVER_STATUS_LABEL = {
    DriverStatus.PENDING_APPROVAL: "Pending approval",
    DriverStatus.APPROVED: "Approved",
    DriverStatus.REJECTED: "Rejected",
    DriverStatus.SUSPENDED: "Suspended",
}

_DRIVER_AVAILABILITY_LABEL = {
    DriverAvailability.AVAILABLE: "Available",
    DriverAvailability.BUSY: "Busy",
    DriverAvailability.OFFLINE: "Offline",
}

_ACCOUNT_STATUS_LABEL = {
    AccountStatus.ACTIVE: "Active",
    AccountStatus.BANNED: "Banned",
}

_VERIFICATION_STATUS_LABEL = {
    VerificationStatus.UNVERIFIED: "Unverified",
    VerificationStatus.VERIFIED: "Verified",
}

_ADMIN_ACTION_TYPE_LABEL = {
    AdminActionType.APPROVE_DRIVER: "Approve driver",
    AdminActionType.REJECT_DRIVER: "Reject driver",
    AdminActionType.SUSPEND_DRIVER: "Suspend driver",
    AdminActionType.BAN_USER: "Ban user",
    AdminActionType.UNBAN_USER: "Unban user",
    AdminActionType.ASSIGN_REQUEST: "Assign request",
    AdminActionType.CANCEL_REQUEST: "Cancel request",
    AdminActionType.PROMOTE_ADMIN: "Promote admin",
    AdminActionType.BROADCAST: "Broadcast",
}


def format_status_label(status: RequestStatus) -> str:
    return f"{_STATUS_EMOJI.get(status, '')} {status.value.replace('_', ' ').title()}"


def format_cancelled_by_label(cancelled_by: CancelledBy | None) -> str | None:
    if cancelled_by is None:
        return None
    return _CANCELLED_BY_LABEL.get(cancelled_by, cancelled_by.value)


def format_driver_status(status: DriverStatus) -> str:
    return _DRIVER_STATUS_LABEL.get(status, status.value)


def format_driver_availability(availability: DriverAvailability) -> str:
    return _DRIVER_AVAILABILITY_LABEL.get(availability, availability.value)


def format_account_status(status: AccountStatus) -> str:
    return _ACCOUNT_STATUS_LABEL.get(status, status.value)


def format_verification_status(status: VerificationStatus) -> str:
    return _VERIFICATION_STATUS_LABEL.get(status, status.value)


def format_admin_action_type(action_type: AdminActionType) -> str:
    return _ADMIN_ACTION_TYPE_LABEL.get(action_type, action_type.value)


def format_luggage_size(size: LuggageSize) -> str:
    return size.value.title()


def format_request_summary(
    *,
    pickup_detail: str,
    dropoff_address: str,
    dropoff_landmark: str | None,
    hall_of_residence: str,
    recipient_name: str,
    recipient_phone: str,
    luggage_size: LuggageSize,
    luggage_count: int,
    preferred_date: date,
    preferred_time_window: str,
    special_instructions: str | None = None,
) -> str:
    lines = [
        f"<b>Pickup:</b> {pickup_detail} ({hall_of_residence})",
        f"<b>Dropoff:</b> {dropoff_address}" + (f" — {dropoff_landmark}" if dropoff_landmark else ""),
        f"<b>Recipient:</b> {recipient_name} ({recipient_phone})",
        f"<b>Luggage:</b> {format_luggage_size(luggage_size)} x{luggage_count}",
        f"<b>Date:</b> {format_date_for_display(preferred_date)}",
        f"<b>Time:</b> {preferred_time_window}",
    ]
    if special_instructions:
        lines.append(f"<b>Notes:</b> {special_instructions}")
    return "\n".join(lines)


def format_driver_name(full_name: str) -> str:
    return full_name.split(" ")[0]


def format_rating(rating_avg: float) -> str:
    return f"{rating_avg:.1f}"
