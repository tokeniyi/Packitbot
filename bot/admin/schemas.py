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
    pending_drivers: int
    rejected_drivers: int
    suspended_drivers: int
    total_feedbacks: int
    avg_rating: float | None

