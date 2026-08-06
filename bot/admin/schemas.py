"""
Data Transfer Objects (DTOs) for the admin module.

This module defines the dataclasses used to pass structured data between the
admin handler layer and the admin service layer. DTOs enforce type safety and
make function contracts explicit without leaking ORM model internals.

Key exports:
    - ``ReviewDriverDTO``
    - ``BroadcastDTO``
    - ``DriverApplicationDetailDTO``
    - ``AvailableDriverDTO``
    - ``BanUserDTO``
    - ``UnbanUserDTO``
    - ``PromoteAdminDTO``
    - ``UserDetailDTO``
    - ``SystemStatsDTO``

Used by:
    - ``bot/admin/handler.py``: Constructs DTOs from callback/message data.
    - ``bot/admin/service.py``: Accepts DTOs as function parameters and
      returns populated DTOs to handlers.
"""

from dataclasses import dataclass
from typing import Optional

from bot.core.constants.enums import DriverStatus


@dataclass
class ReviewDriverDTO:
    """Request payload for reviewing (approving or rejecting) a driver application.

    Attributes:
        driver_id (int): The primary key of the ``DriverProfile`` being reviewed.
        admin_telegram_id (int): Telegram ID of the admin performing the action.
        rejection_reason (Optional[str]): Optional reason provided when rejecting.
            Defaults to ``None``.

    Used by:
        - ``bot/admin/service.py``: ``approve_driver``, ``reject_driver``
        - ``bot/admin/handler.py``: ``handle_approve_driver``, ``handle_reject_driver``
    """

    driver_id: int
    admin_telegram_id: int
    rejection_reason: Optional[str] = None


@dataclass
class BroadcastDTO:
    """Request payload for initiating an admin broadcast.

    Attributes:
        audience (str): Target audience identifier ("students", "drivers", or "all").
        message_text (str): The broadcast message body.
        admin_telegram_id (int): Telegram ID of the admin sending the broadcast.

    Used by:
        - ``bot/admin/service.py``: ``get_broadcast_target_telegram_ids``
        - ``bot/admin/handler.py``: ``execute_broadcast``
    """

    audience: str
    message_text: str
    admin_telegram_id: int


@dataclass
class DriverApplicationDetailDTO:
    """Detailed view of a driver's application for admin review.

    Attributes:
        driver_id (int): Primary key of the ``DriverProfile``.
        user_id (int): Primary key of the associated ``User``.
        telegram_id (int): Telegram ID of the driver applicant.
        full_name (str): Driver's full name.
        phone_number (str): Driver's contact phone number.
        vehicle_type (str): Type of vehicle (e.g., "sedan", "suv").
        plate_number (str): Vehicle registration plate number.
        license_number (str): Driver's license number.
        status (DriverStatus): Current approval status of the driver profile.
        username (Optional[str]): Telegram username of the driver.

    Used by:
        - ``bot/admin/service.py``: ``get_driver_application_detail``,
          ``approve_driver``, ``reject_driver``, ``get_pending_drivers``
        - ``bot/admin/handler.py``: ``handle_view_driver_detail``,
          ``handle_approve_driver``, ``handle_reject_driver``
        - ``bot/admin/keyboards.py``: ``pending_drivers_list_keyboard``
    """

    driver_id: int
    user_id: int
    telegram_id: int
    full_name: str
    phone_number: str
    vehicle_type: str
    plate_number: str
    license_number: str
    status: DriverStatus
    username: Optional[str] = None


@dataclass
class AvailableDriverDTO:
    """Summary of an approved, available driver for assignment selection.

    Attributes:
        driver_id (int): Primary key of the ``DriverProfile``.
        user_id (int): Primary key of the associated ``User``.
        telegram_id (int): Telegram ID of the driver.
        full_name (str): Driver's display name.
        phone_number (str): Driver's contact phone number.
        vehicle_type (str): Type of vehicle used for deliveries.
        rating_avg (float): Average rating from student feedback (0.0 if new).
        total_deliveries (int): Count of completed deliveries.
        username (Optional[str]): Telegram username of the driver.

    Used by:
        - ``bot/admin/service.py``: ``get_available_drivers_ranked``
        - ``bot/admin/handler.py``: ``handle_select_request_for_assignment``
        - ``bot/admin/keyboards.py``: ``available_drivers_keyboard``
    """

    driver_id: int
    user_id: int
    telegram_id: int
    full_name: str
    phone_number: str
    vehicle_type: str
    rating_avg: float
    total_deliveries: int
    username: Optional[str] = None


@dataclass
class BanUserDTO:
    """Request payload for banning a user.

    Attributes:
        target_user_id (int): Primary key of the ``User`` to ban.
        admin_telegram_id (int): Telegram ID of the admin performing the ban.
        reason (Optional[str]): Optional ban reason. Defaults to ``None``.

    Used by:
        - ``bot/admin/service.py``: ``ban_user``
        - ``bot/admin/handler.py``: ``process_ban_reason``
    """

    target_user_id: int
    admin_telegram_id: int
    reason: Optional[str] = None


@dataclass
class UnbanUserDTO:
    """Request payload for unbanning a user.

    Attributes:
        target_user_id (int): Primary key of the ``User`` to unban.
        admin_telegram_id (int): Telegram ID of the admin performing the unban.
        reason (Optional[str]): Optional note explaining the unban. Defaults to ``None``.

    Used by:
        - ``bot/admin/service.py``: ``unban_user``
        - ``bot/admin/handler.py``: ``handle_unban_user``
    """

    target_user_id: int
    admin_telegram_id: int
    reason: Optional[str] = None


@dataclass
class PromoteAdminDTO:
    """Request payload for promoting a user to admin role.

    Attributes:
        target_user_id (int): Primary key of the ``User`` to promote.
        admin_telegram_id (int): Telegram ID of the admin performing the promotion.

    Used by:
        - ``bot/admin/service.py``: ``promote_admin``
        - ``bot/admin/handler.py``: ``handle_promote_admin``
    """

    target_user_id: int
    admin_telegram_id: int


@dataclass
class UserDetailDTO:
    """Read-only snapshot of a user's profile for admin display and actions.

    Attributes:
        user_id (int): Primary key of the ``User``.
        telegram_id (int): Telegram ID of the user.
        full_name (Optional[str]): Display name of the user.
        username (Optional[str]): Telegram username.
        phone_number (Optional[str]): Contact phone number.
        role (Optional[str]): User role ("student", "driver", "admin").
        account_status (str): Current account status ("active", "banned").
        banned_reason (Optional[str]): Reason for the current ban, if any.
        banned_at (Optional[str]): ISO-formatted timestamp of the ban, if any.

    Used by:
        - ``bot/admin/service.py``: ``search_user_by_identifier``, ``ban_user``,
          ``unban_user``, ``promote_admin``
        - ``bot/admin/handler.py``: ``process_user_search``
        - ``bot/admin/keyboards.py``: ``user_action_keyboard``
    """

    user_id: int
    telegram_id: int
    full_name: Optional[str]
    username: Optional[str]
    phone_number: Optional[str]
    role: Optional[str]
    account_status: str
    banned_reason: Optional[str]
    banned_at: Optional[str]


@dataclass
class SystemStatsDTO:
    """Aggregated system-wide metrics returned by the stats command.

    Attributes:
        total_requests (int): Total number of delivery requests ever created.
        pending_requests (int): Requests currently in PENDING status.
        assigned_requests (int): Requests currently in ASSIGNED status.
        accepted_requests (int): Requests currently in ACCEPTED status.
        en_route_requests (int): Requests currently EN_ROUTE_TO_PICKUP.
        picked_up_requests (int): Requests currently PICKED_UP.
        in_transit_requests (int): Requests currently IN_TRANSIT.
        delivered_requests (int): Requests currently DELIVERED.
        cancelled_requests (int): Requests currently CANCELLED.
        failed_requests (int): Requests currently FAILED.
        rejected_by_driver_requests (int): Requests currently REJECTED_BY_DRIVER.
        total_users (int): Total registered users.
        total_students (int): Users with STUDENT role.
        total_drivers (int): Users with DRIVER role.
        total_admins (int): Users with ADMIN role.
        approved_drivers (int): Driver profiles with APPROVED status.
        active_drivers (int): Approved drivers whose availability is not OFFLINE.
        pending_drivers (int): Driver profiles with PENDING_APPROVAL status.
        rejected_drivers (int): Driver profiles with REJECTED status.
        suspended_drivers (int): Driver profiles with SUSPENDED status.
        total_feedbacks (int): Total feedback records submitted.
        avg_rating (float | None): Average rating across all feedback, or None if no feedback.
        avg_delivery_duration_minutes (float | None): Average minutes from ACCEPTED
            to DELIVERED, computed from status logs. ``None`` if no completed deliveries.

    Used by:
        - ``bot/admin/service.py``: ``get_stats``
        - ``bot/admin/handler.py``: ``cmd_stats``
    """

    total_requests: int
    pending_requests: int
    assigned_requests: int
    accepted_requests: int
    en_route_requests: int
    picked_up_requests: int
    in_transit_requests: int
    delivered_requests: int
    cancelled_requests: int
    failed_requests: int
    rejected_by_driver_requests: int
    total_users: int
    total_students: int
    total_drivers: int
    total_admins: int
    approved_drivers: int
    active_drivers: int = 0
    pending_drivers: int = 0
    rejected_drivers: int = 0
    suspended_drivers: int = 0
    total_feedbacks: int = 0
    avg_rating: float | None = None
    avg_delivery_duration_minutes: float | None = None
