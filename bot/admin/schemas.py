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
