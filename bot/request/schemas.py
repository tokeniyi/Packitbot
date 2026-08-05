from dataclasses import dataclass
from datetime import date
from typing import Any

from bot.core.constants.enums import CancelledBy, LuggageSize, RequestStatus


@dataclass(frozen=True)
class CreateRequestDTO:
    student_id: int
    pickup_detail: str
    dropoff_address: str
    dropoff_landmark: str | None
    hall_of_residence: str
    recipient_name: str
    recipient_phone: str
    luggage_size: LuggageSize
    luggage_count: int
    special_instructions: str | None
    preferred_date: date
    preferred_time_window: str


@dataclass(frozen=True)
class UpdateRequestDTO:
    request_id: int
    actor_id: int
    changed_fields: dict[str, Any]


@dataclass(frozen=True)
class AssignDriverDTO:
    request_id: int
    driver_id: int
    admin_id: int


@dataclass(frozen=True)
class TransitionDTO:
    request_id: int
    new_status: RequestStatus
    actor_id: int
    note: str | None = None


@dataclass(frozen=True)
class CancelRequestDTO:
    request_id: int
    actor_id: int
    cancelled_by: CancelledBy
    cancellation_reason: str | None = None


@dataclass(frozen=True)
class CreateFeedbackDTO:
    request_id: int
    student_id: int
    rating: int
    comment: str | None = None