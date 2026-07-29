# bot/admin/schemas.py
from dataclasses import dataclass
from typing import Optional
from bot.core.constants.enums import DriverStatus


@dataclass
class ReviewDriverDTO:
    driver_id: int
    admin_telegram_id: int
    rejection_reason: Optional[str] = None


@dataclass
class BroadcastDTO:
    audience: str
    message_text: str
    admin_telegram_id: int



@dataclass
class DriverApplicationDetailDTO:
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
    target_user_id: int
    admin_telegram_id: int
    reason: Optional[str] = None


@dataclass
class UnbanUserDTO:
    target_user_id: int
    admin_telegram_id: int
    reason: Optional[str] = None


@dataclass
class PromoteAdminDTO:
    target_user_id: int
    admin_telegram_id: int


@dataclass
class UserDetailDTO:
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

