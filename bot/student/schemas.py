"""Data transfer objects (DTOs) and schema definitions for student operations.

This module defines pydantic/dataclass schemas used for
validating and transferring student-related data between
the handler, service, and repository layers.
"""

from dataclasses import dataclass

from bot.core.constants.enums import UserRole


@dataclass
class RegisterStudentDTO:
    """Data transfer object for student registration payloads.

    Attributes:
        telegram_id: The unique Telegram user identifier.
        full_name: The student's full name.
        matric_number: The student's matriculation number.
        hall_of_residence: The student's hall of residence.
        phone_number: The student's contact phone number.
    """
    telegram_id: int
    full_name: str
    matric_number: str
    hall_of_residence: str
    phone_number: str