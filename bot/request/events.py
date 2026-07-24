from dataclasses import dataclass

from bot.core.constants.enums import CancelledBy, RequestStatus


@dataclass(frozen=True)
class RequestCreatedEvent:
    request_id: int
    student_id: int


@dataclass(frozen=True)
class RequestAssignedEvent:
    request_id: int
    driver_id: int
    admin_id: int


@dataclass(frozen=True)
class RequestStatusChangedEvent:
    request_id: int
    old_status: RequestStatus | None
    new_status: RequestStatus
    actor_id: int | None


@dataclass(frozen=True)
class RequestCancelledEvent:
    request_id: int
    cancelled_by: CancelledBy
    actor_id: int
    reason: str | None = None


@dataclass(frozen=True)
class FeedbackSubmittedEvent:
    feedback_id: int
    request_id: int
    student_id: int
    rating: int
