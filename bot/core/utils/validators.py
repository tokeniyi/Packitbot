"""Input validation utilities for the Packitbot Telegram bot.

This module provides reusable validation functions for
common input types such as phone numbers, names, dates,
luggage sizes, ratings, and more. Each function raises
a ValidationError with a descriptive message on failure.

Function Calls:
    - validate_phone(raw) -> str
    - validate_matric(raw) -> str
    - validate_full_name(raw) -> str
    - validate_hall(raw) -> str
    - validate_pickup_detail(raw) -> str
    - validate_dropoff_address(raw) -> str
    - validate_luggage_size(raw) -> LuggageSize
    - validate_luggage_count(raw) -> int
    - validate_preferred_date(raw, max_lead_days) -> date
    - validate_time_window(raw) -> str
    - validate_special_instructions(raw) -> str | None
    - validate_plate_number(raw) -> str
    - validate_license_number(raw) -> str
    - validate_vehicle_type(raw) -> str
    - validate_rating(raw) -> int
    - validate_cancellation_reason(raw) -> str
    - validate_recipient_name(raw) -> str

Cross-References:
    - Depends on: re, datetime, bot.core.constants.enums.LuggageSize,
        bot.core.constants.config.ALLOWED_PHONE_PREFIXES,
        bot.core.constants.halls.CU_HALLS, bot.core.constants.limits
    - Imported by: bot/student/service.py, bot/student/handler.py,
        bot/student/handler_requests.py, bot/core/utils/*.py
"""

import re
from datetime import date, datetime, timedelta

from bot.core.constants.enums import LuggageSize
from bot.core.constants.config import ALLOWED_PHONE_PREFIXES
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
    """Raised when input validation fails."""
    pass


def validate_phone(raw: str) -> str:
    """Validate and format a Nigerian phone number.

    Ensures the number is exactly 11 digits, starts with a
    valid network prefix, and returns it in international
    format (+234...).

    Args:
        raw: The raw phone number string from the user.

    Returns:
        The formatted international phone number.

    Raises:
        ValidationError: If the phone number is empty, not 11 digits,
            or has an invalid prefix.
    """
    if not raw:
        raise ValidationError("Phone number cannot be empty.")

    cleaned = raw.strip()

    # 1 & 2. Ensure strictly digits and exactly 11 characters
    if not cleaned.isdigit() or len(cleaned) != 11:
        raise ValidationError("Enter a valid 11-digit phone number, e.g., 08012345678")

    # 3. Check against allowed Nigerian prefixes
    if not cleaned.startswith(ALLOWED_PHONE_PREFIXES):
        raise ValidationError("Invalid phone network provider prefix.")

    # 4. Return formatted international number (+234...)
    return "+234" + cleaned[1:]


def validate_matric(raw: str) -> str:
    """Validate a Nigerian matriculation number.

    Supports formats like 21AB1234, 21/1234, 21/AB1234.

    Args:
        raw: The raw matric number string.

    Returns:
        The uppercased, stripped matric number.

    Raises:
        ValidationError: If the matric number does not match the expected pattern.
    """
    value = raw.strip().upper()
    if not MATRIC_REGEX.match(value):
        raise ValidationError("Enter a valid matriculation number (e.g. 21AB1234 or 12/3456).")
    return value


def validate_full_name(raw: str) -> str:
    """Validate a person's full name.

    Requires at least two words (first and last name)
    containing only letters, hyphens, and apostrophes.

    Args:
        raw: The raw full name string.

    Returns:
        The stripped full name.

    Raises:
        ValidationError: If the name does not match the expected pattern.
    """
    value = raw.strip()
    if not NAME_REGEX.match(value):
        raise ValidationError("Enter your full name (first and last name, letters and hyphens only).")
    return value


def validate_hall(raw: str) -> str:
    """Validate a hall of residence against the known list.

    Args:
        raw: The raw hall name string.

    Returns:
        The stripped hall name.

    Raises:
        ValidationError: If the hall is not in the CU_HALLS list.
    """
    value = raw.strip()
    if value not in CU_HALLS:
        raise ValidationError("Select a valid hall of residence from the list.")
    return value


def validate_pickup_detail(raw: str) -> str:
    """Validate a pickup detail string.

    Args:
        raw: The raw pickup detail string.

    Returns:
        The stripped pickup detail.

    Raises:
        ValidationError: If the pickup detail is empty or exceeds 255 characters.
    """
    value = raw.strip()
    if not value:
        raise ValidationError("Pickup detail cannot be empty.")
    if len(value) > 255:
        raise ValidationError("Pickup detail is too long (max 255 characters).")
    return value


def validate_dropoff_address(raw: str) -> str:
    """Validate a dropoff address string.

    Args:
        raw: The raw dropoff address string.

    Returns:
        The stripped dropoff address.

    Raises:
        ValidationError: If the address is shorter than 10 characters
            or exceeds 255 characters.
    """
    value = raw.strip()
    if len(value) < 10:
        raise ValidationError("Dropoff address must be at least 10 characters.")
    if len(value) > 255:
        raise ValidationError("Dropoff address is too long (max 255 characters).")
    return value


def validate_luggage_size(raw: str) -> LuggageSize:
    """Validate and convert a luggage size string to LuggageSize enum.

    Args:
        raw: The raw luggage size string.

    Returns:
        The corresponding LuggageSize enum member.

    Raises:
        ValidationError: If the size is not a valid LuggageSize value.
    """
    try:
        return LuggageSize(raw.strip().lower())
    except ValueError:
        raise ValidationError("Choose a valid luggage size: small, medium, or large.")


def validate_luggage_count(raw: str) -> int:
    """Validate a luggage count integer.

    Args:
        raw: The raw luggage count string.

    Returns:
        The validated integer count.

    Raises:
        ValidationError: If the count is not a valid integer or is
            outside the allowed range.
    """
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
    """Validate a preferred date string in YYYY-MM-DD format.

    Args:
        raw: The raw date string.
        max_lead_days: Maximum number of days in the future allowed.

    Returns:
        The parsed date object.

    Raises:
        ValidationError: If the date is invalid, in the past, or too far in the future.
    """
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
    """Validate a time window string against the allowed slots.

    Args:
        raw: The raw time window string.

    Returns:
        The stripped time window string.

    Raises:
        ValidationError: If the time window is not in TIME_WINDOW_SLOTS.
    """
    value = raw.strip().lower()
    if value not in TIME_WINDOW_SLOTS:
        raise ValidationError("Select a valid time window from the options provided.")
    return value


def validate_special_instructions(raw: str | None) -> str | None:
    """Validate special instructions text.

    Args:
        raw: The raw instructions string, or None.

    Returns:
        The stripped instructions string, or None if empty.

    Raises:
        ValidationError: If the instructions exceed 500 characters.
    """
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    if len(value) > 500:
        raise ValidationError("Special instructions are too long (max 500 characters).")
    return value


def validate_plate_number(raw: str) -> str:
    """Validate a vehicle plate number.

    Expected format: ABC-123DE (3 uppercase letters, dash, 3 digits, 2 uppercase letters).

    Args:
        raw: The raw plate number string.

    Returns:
        The uppercased, stripped plate number.

    Raises:
        ValidationError: If the plate number does not match the expected format.
    """
    value = raw.strip().upper()
    if not PLATE_REGEX.match(value):
        raise ValidationError("Enter a valid plate number (e.g. ABC-123DE).")
    return value


def validate_license_number(raw: str) -> str:
    """Validate a driver's license number.

    Args:
        raw: The raw license number string.

    Returns:
        The stripped license number.

    Raises:
        ValidationError: If the license number is empty or exceeds 50 characters.
    """
    value = raw.strip()
    if not value:
        raise ValidationError("License number cannot be empty.")
    if len(value) > 50:
        raise ValidationError("License number is too long (max 50 characters).")
    return value


_VEHICLE_TYPES = {"sedan", "suv", "bus", "bike", "van"}


def validate_vehicle_type(raw: str) -> str:
    """Validate a vehicle type string.

    Args:
        raw: The raw vehicle type string.

    Returns:
        The lowercased vehicle type.

    Raises:
        ValidationError: If the vehicle type is not one of the allowed values.
    """
    value = raw.strip().lower()
    if value not in _VEHICLE_TYPES:
        raise ValidationError("Choose a valid vehicle type: sedan, suv, bus, bike, or van.")
    return value


def validate_rating(raw: str) -> int:
    """Validate a rating integer.

    Args:
        raw: The raw rating string.

    Returns:
        The validated integer rating.

    Raises:
        ValidationError: If the rating is not a valid integer or is
            outside the allowed range.
    """
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
    """Validate a cancellation reason string.

    Args:
        raw: The raw cancellation reason string.

    Returns:
        The stripped cancellation reason.

    Raises:
        ValidationError: If the reason is empty or exceeds 255 characters.
    """
    value = raw.strip()
    if not value:
        raise ValidationError("Cancellation reason cannot be empty.")
    if len(value) > 255:
        raise ValidationError("Cancellation reason is too long (max 255 characters).")
    return value


def validate_recipient_name(raw: str) -> str:
    """Validate a recipient's full name.

    Requires at least two words (first and last name)
    containing only letters, hyphens, and apostrophes.

    Args:
        raw: The raw recipient name string.

    Returns:
        The stripped recipient name.

    Raises:
        ValidationError: If the name does not match the expected pattern.
    """
    value = raw.strip()
    if not NAME_REGEX.match(value):
        raise ValidationError("Enter the recipient's name (first and last name, letters and hyphens only).")
    return value
