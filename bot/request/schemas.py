from dataclasses import dataclass
from datetime import date

from bot.core.constants.enums import LuggageSize, RequestStatus


@dataclass
class CreateRequestDTO:
    student_id: int
    pickup_detail: str
    dropoff_address: str
    dropoff_landmark: str | None
    recipient_name: str
    recipient_phone: str
    luggage_size: LuggageSize
    luggage_count: int
    special_instructions: str | None
    preferred_date: date
    preferred_time_window: str


@dataclass
class UpdateRequestDTO:
    request_id: int
    actor_id: int
    changed_fields: dict


@dataclass
class AssignDriverDTO:
    request_id: int
    driver_id: int
    admin_id: int


@dataclass
class TransitionDTO:
    request_id: int
    new_status: RequestStatus
    actor_id: int
    note: str | None = None