import re
from datetime import date, datetime, timedelta

from bot.core.constants.enums import LuggageSize
from bot.core.constants.halls import CU_HALLS
from bot.core.constants.limits import (
    MAX_LUGGAGE_COUNT,
    MIN_LUGGAGE_COUNT,
    PAGE_SIZE,
    RATING_MAX,
    RATING_MIN,
)
PHONE_REGEX = re.compile(r"^(?:234|0)([7-9]\d{9})$")
# FIXED: Supports 21AB1234, 21/1234, 21/AB1234, etc.
MATRIC_REGEX = re.compile(r"^\d{2}/?[A-Za-z0-9]{4,6}$")
PLATE_REGEX = re.compile(r"^[A-Z]{3}-\d{3}[A-Z]{2}$")
NAME_REGEX = re.compile(r"^[A-Za-z][A-Za-z\-']+(?:\s[A-Za-z][A-Za-z\-']+)+$")
TIME_WINDOW_SLOTS = [
    "6am-9am",
    "7am-10am",
    "8am-11am",
    "9am-12pm",
    "10am-1pm",
    "11am-2pm",
    "12pm-3pm",
    "1pm-4pm",
    "2pm-5pm",
    "3pm-6pm",
    "4pm-7pm",
    "5pm-8pm",
    "6pm-9pm",
    "7pm-10pm",
]


class ValidationError(Exception):
    pass


def validate_phone(raw: str) -> str:
    # Strip spaces, hyphens, and leading plus signs for clean matching
    cleaned = re.sub(r"[\s\-\+]", "", raw.strip())
    if not PHONE_REGEX.match(cleaned):
        raise ValidationError("Enter a valid Nigerian phone number, e.g. 08012345678")
    if cleaned.startswith("234"):
        return "+" + cleaned
    if cleaned.startswith("0"):
        return "+234" + cleaned[1:]
    raise ValidationError("Enter a valid Nigerian phone number, e.g. 08012345678")

def validate_matric(raw: str) -> str:
    value = raw.strip().upper()
    if not MATRIC_REGEX.match(value):
        raise ValidationError("Enter a valid matriculation number (e.g. 21AB1234 or 12/3456).")
    return value


def validate_full_name(raw: str) -> str:
    value = raw.strip()
    if not NAME_REGEX.match(value):
        raise ValidationError("Enter your full name (first and last name, letters and hyphens only).")
    return value


def validate_hall(raw: str) -> str:
    value = raw.strip()
    if value not in CU_HALLS:
        raise ValidationError("Select a valid hall of residence from the list.")
    return value


def validate_pickup_detail(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValidationError("Pickup detail cannot be empty.")
    if len(value) > 255:
        raise ValidationError("Pickup detail is too long (max 255 characters).")
    return value


def validate_dropoff_address(raw: str) -> str:
    value = raw.strip()
    if len(value) < 10:
        raise ValidationError("Dropoff address must be at least 10 characters.")
    if len(value) > 255:
        raise ValidationError("Dropoff address is too long (max 255 characters).")
    return value


def validate_luggage_size(raw: str) -> LuggageSize:
    try:
        return LuggageSize(raw.strip().lower())
    except ValueError:
        raise ValidationError("Choose a valid luggage size: small, medium, or large.")


def validate_luggage_count(raw: str) -> int:
    try:
        count = int(raw.strip())
    except ValueError:
        raise ValidationError("Enter a valid number for luggage count.")
    if count < MIN_LUGGAGE_COUNT:
        raise ValidationError(f"Luggage count must be at least {MIN_LUGGAGE_COUNT}.")
    if count > MAX_LUGGAGE_COUNT:
        raise ValidationError(f"Luggage count cannot exceed {MAX_LUGGAGE_COUNT}.")
    return count


def validate_preferred_date(raw: str, max_lead_days: int = 7) -> date:
    try:
        parsed = date.fromisoformat(raw.strip())
    except ValueError:
        raise ValidationError("Enter a valid date (YYYY-MM-DD).")
    today = date.today()
    if parsed < today:
        raise ValidationError("Preferred date cannot be in the past.")
    if parsed > today + timedelta(days=max_lead_days):
        raise ValidationError(f"Preferred date cannot be more than {max_lead_days} days ahead.")
    return parsed


def validate_time_window(raw: str) -> str:
    value = raw.strip().lower()
    if value not in TIME_WINDOW_SLOTS:
        raise ValidationError("Select a valid time window from the options provided.")
    return value


def validate_special_instructions(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    if len(value) > 500:
        raise ValidationError("Special instructions are too long (max 500 characters).")
    return value


def validate_plate_number(raw: str) -> str:
    value = raw.strip().upper()
    if not PLATE_REGEX.match(value):
        raise ValidationError("Enter a valid plate number (e.g. ABC-123DE).")
    return value


def validate_license_number(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValidationError("License number cannot be empty.")
    if len(value) > 50:
        raise ValidationError("License number is too long (max 50 characters).")
    return value


_VEHICLE_TYPES = {"sedan", "suv", "bus", "bike", "van"}


def validate_vehicle_type(raw: str) -> str:
    value = raw.strip().lower()
    if value not in _VEHICLE_TYPES:
        raise ValidationError("Choose a valid vehicle type: sedan, suv, bus, bike, or van.")
    return value


def validate_rating(raw: str) -> int:
    try:
        rating = int(raw.strip())
    except ValueError:
        raise ValidationError("Enter a valid rating.")
    if rating < RATING_MIN:
        raise ValidationError(f"Rating must be at least {RATING_MIN}.")
    if rating > RATING_MAX:
        raise ValidationError(f"Rating cannot exceed {RATING_MAX}.")
    return rating


def validate_cancellation_reason(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValidationError("Cancellation reason cannot be empty.")
    if len(value) > 255:
        raise ValidationError("Cancellation reason is too long (max 255 characters).")
    return value


def validate_recipient_name(raw: str) -> str:
    value = raw.strip()
    if not NAME_REGEX.match(value):
        raise ValidationError("Enter the recipient's name (first and last name, letters and hyphens only).")
    return value
