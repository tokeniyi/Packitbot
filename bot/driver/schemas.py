# bot/driver/schemas.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class RegisterDriverDTO:
    telegram_id: int
    full_name: str
    phone_number: str
    vehicle_type: str
    plate_number: str
    license_number: str
    username: Optional[str] = None
