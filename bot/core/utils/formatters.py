"""Display formatting utilities for the Packitbot Telegram bot.

This module provides functions for formatting dates,
status labels, enum values, and request summaries
for user-facing messages.

Function Calls:
    - format_date_for_display(utc_date) -> str
    - format_datetime_for_display(utc_dt) -> str
    - format_status_label(status) -> str
    - format_cancelled_by_label(cancelled_by) -> str | None
    - format_driver_status(status) -> str
    - format_driver_availability(availability) -> str
    - format_account_status(status) -> str
    - format_verification_status(status) -> str
    - format_admin_action_type(action_type) -> str
    - format_luggage_size(size) -> str
    - format_request_summary(...) -> str
    - format_driver_name(full_name) -> str
    - format_rating(rating_avg) -> str

Cross-References:
    - Depends on: bot.core.constants.enums.*
    - Imported by: bot/student/handler.py, bot/student/handler_requests.py
"""

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
    """Convert a UTC datetime to West Africa Time (WAT).

    Args:
        utc_dt: The datetime in UTC.

    Returns:
        The datetime converted to WAT (UTC+1).
    """
    if utc_dt.tzinfo is None:
        return utc_dt + WAT_OFFSET
    return utc_dt.astimezone(timedelta(hours=1))


def format_date_for_display(utc_date: date) -> str:
    """Format a date for user-facing display.

    Args:
        utc_date: The date to format.

    Returns:
        A formatted date string like "06 Aug 2026".
    """
    return utc_date.strftime("%d %b %Y")


def format_datetime_for_display(utc_dt: datetime) -> str:
    """Format a datetime for user-facing display in WAT.

    Args:
        utc_dt: The datetime to format.

    Returns:
        A formatted datetime string like "06 Aug 2026, 03:30 PM".
    """
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
    """Format a RequestStatus enum with its emoji indicator.

    Args:
        status: The RequestStatus enum value.

    Returns:
        A formatted string like "⏳ Pending".
    """
    return f"{_STATUS_EMOJI.get(status, '')} {status.value.replace('_', ' ').title()}"


def format_cancelled_by_label(cancelled_by: CancelledBy | None) -> str | None:
    """Format a CancelledBy enum into a human-readable label.

    Args:
        cancelled_by: The CancelledBy enum value, or None.

    Returns:
        A human-readable label, or None if input is None.
    """
    if cancelled_by is None:
        return None
    return _CANCELLED_BY_LABEL.get(cancelled_by, cancelled_by.value)


def format_driver_status(status: DriverStatus) -> str:
    """Format a DriverStatus enum into a human-readable label.

    Args:
        status: The DriverStatus enum value.

    Returns:
        A human-readable label.
    """
    return _DRIVER_STATUS_LABEL.get(status, status.value)


def format_driver_availability(availability: DriverAvailability) -> str:
    """Format a DriverAvailability enum into a human-readable label.

    Args:
        availability: The DriverAvailability enum value.

    Returns:
        A human-readable label.
    """
    return _DRIVER_AVAILABILITY_LABEL.get(availability, availability.value)


def format_account_status(status: AccountStatus) -> str:
    """Format an AccountStatus enum into a human-readable label.

    Args:
        status: The AccountStatus enum value.

    Returns:
        A human-readable label.
    """
    return _ACCOUNT_STATUS_LABEL.get(status, status.value)


def format_verification_status(status: VerificationStatus) -> str:
    """Format a VerificationStatus enum into a human-readable label.

    Args:
        status: The VerificationStatus enum value.

    Returns:
        A human-readable label.
    """
    return _VERIFICATION_STATUS_LABEL.get(status, status.value)


def format_admin_action_type(action_type: AdminActionType) -> str:
    """Format an AdminActionType enum into a human-readable label.

    Args:
        action_type: The AdminActionType enum value.

    Returns:
        A human-readable label.
    """
    return _ADMIN_ACTION_TYPE_LABEL.get(action_type, action_type.value)


def format_luggage_size(size: LuggageSize) -> str:
    """Format a LuggageSize enum into a title-cased string.

    Args:
        size: The LuggageSize enum value.

    Returns:
        A title-cased string like "Small".
    """
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
    """Format a delivery request summary for display.

    Args:
        pickup_detail: The pickup location detail.
        dropoff_address: The delivery destination address.
        dropoff_landmark: Optional landmark near the destination.
        hall_of_residence: The student's hall of residence.
        recipient_name: The name of the package recipient.
        recipient_phone: The recipient's phone number.
        luggage_size: The size of the luggage.
        luggage_count: The number of luggage items.
        preferred_date: The preferred pickup date.
        preferred_time_window: The preferred delivery time window.
        special_instructions: Optional special instructions.

    Returns:
        A formatted multi-line summary string.
    """
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
    """Extract the first name from a full name.

    Args:
        full_name: The full name string.

    Returns:
        The first word of the full name.
    """
    return full_name.split(" ")[0]


def format_rating(rating_avg: float) -> str:
    """Format a floating-point rating to one decimal place.

    Args:
        rating_avg: The average rating value.

    Returns:
        A string representation rounded to one decimal.
    """
    return f"{rating_avg:.1f}"
