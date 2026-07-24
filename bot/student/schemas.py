from dataclasses import dataclass

from bot.core.constants.enums import UserRole


@dataclass
class RegisterStudentDTO:
    telegram_id: int
    full_name: str
    matric_number: str
    hall_of_residence: str
    phone_number: str