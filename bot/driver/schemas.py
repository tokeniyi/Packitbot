"""Data Transfer Objects (DTOs) for the driver module.

These lightweight, validated-only-at-consumption dataclasses carry data
between the aiogram handlers (``bot/driver/handler.py``) and the service
layer (``bot/driver/service.py``). They are *not* ORM models — persistence
is handled by ``bot.core.models.driver_profile`` and ``bot.core.models.user``.

DTOs
----
- ``RegisterDriverDTO``    -> Captures all fields collected during the driver registration FSM.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RegisterDriverDTO:
    """DTO carrying driver registration data collected via the FSM.

    Attributes:
        telegram_id:    Unique Telegram user identifier of the registering driver.
        username:       Optional Telegram username (may be ``None`` for some accounts).
        full_name:      Driver's full legal name as entered and validated.
        phone_number:   Driver's contact phone number (locale-specific format).
        vehicle_type:   Type of vehicle used for deliveries (e.g. "sedan", "suv").
        plate_number:   Vehicle registration plate number.
        license_number: Driver's license number for verification.

    Used by:
        ``bot/driver/handler.py`` -> ``process_submit_registration`` (constructs the DTO)
        ``bot/driver/service.py`` -> ``register_driver`` (consumes and validates the DTO).
    """

    telegram_id: int
    full_name: str
    phone_number: str
    vehicle_type: str
    plate_number: str
    license_number: str
    username: Optional[str] = None
