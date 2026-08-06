"""
Request Data Transfer Objects (DTOs) Module
============================================

Frozen dataclass schemas used to validate and transport request-related
data between Telegram handlers and the service layer.

Each DTO acts as a typed contract: handlers construct these objects from
raw callback/message data, and ``RequestService`` methods consume them.
Using frozen dataclasses guarantees immutability and prevents accidental
mutation after validation.

**Key Dependencies:**
- *Uses:* ``bot.core.constants.enums`` (``CancelledBy``, ``LuggageSize``, ``RequestStatus``)
- *Used by:* ``bot/request/service.py``, ``bot/student/handler.py``, ``bot/student/handler_requests.py``, ``bot/admin/handler.py``, ``bot/driver/handler.py``, ``tests/unit/request/test_schemas.py``
"""
from dataclasses import dataclass
from datetime import date
from typing import Any

from bot.core.constants.enums import CancelledBy, LuggageSize, RequestStatus


@dataclass(frozen=True)
class CreateRequestDTO:
    """Schema for a new delivery request submitted by a student.

    **Calls / Depends on:** ``LuggageSize`` enum, ``date`` type.

    **Called by:** ``bot/student/handler.py`` (request creation flow),
    ``bot/request/service.py::RequestService.create_request``,
    ``tests/unit/request/test_schemas.py``.

    Attributes:
        student_id: Telegram user ID of the submitting student.
        pickup_detail: Free-text description of where the driver should pick up.
        dropoff_address: Destination street address.
        dropoff_landmark: Optional nearby landmark for the dropoff location.
        hall_of_residence: Student's hall of residence name.
        recipient_name: Name of the person receiving the delivery.
        recipient_phone: Contact phone number of the recipient.
        luggage_size: Categorical size of the luggage (from ``LuggageSize`` enum).
        luggage_count: Number of luggage items.
        special_instructions: Optional notes for the driver (e.g., "call on arrival").
        preferred_date: ISO date the student wants the delivery.
        preferred_time_window: Human-readable time window string (e.g., "2-4 PM").
    """
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
    """Schema for partial updates to an existing delivery request.

    Only ``PENDING`` requests may be edited; the service layer enforces
    this rule. ``changed_fields`` is a dict so only supplied keys are
    patched.

    **Calls / Depends on:** ``dict[str, Any]`` for ``changed_fields``.

    **Called by:** ``bot/student/handler.py`` (request edit flow),
    ``bot/request/service.py::RequestService.update_request``,
    ``tests/unit/request/test_schemas.py``.

    Attributes:
        request_id: Primary key of the ``DeliveryRequest`` to update.
        actor_id: Telegram user ID of the student requesting the edit.
        changed_fields: Mapping of model attribute names to new values.
    """
    request_id: int
    actor_id: int
    changed_fields: dict[str, Any]


@dataclass(frozen=True)
class AssignDriverDTO:
    """Schema for admin driver-assignment actions.

    **Calls / Depends on:** None.

    **Called by:** ``bot/admin/handler.py`` (driver assignment flow),
    ``bot/request/service.py::RequestService.assign_driver``,
    ``tests/unit/request/test_schemas.py``.

    Attributes:
        request_id: Primary key of the ``DeliveryRequest``.
        driver_id: Telegram user ID of the driver being assigned.
        admin_id: Telegram user ID of the admin performing the assignment.
    """
    request_id: int
    driver_id: int
    admin_id: int


@dataclass(frozen=True)
class TransitionDTO:
    """Schema for generic status-transition commands (primarily from drivers).

    Used by driver handlers to accept, reject, or progress a delivery.

    **Calls / Depends on:** ``RequestStatus`` enum.

    **Called by:** ``bot/driver/handler.py`` (driver action flows),
    ``bot/request/service.py::RequestService.transition_status``,
    ``tests/unit/request/test_schemas.py``.

    Attributes:
        request_id: Primary key of the ``DeliveryRequest``.
        new_status: Target ``RequestStatus`` to transition to.
        actor_id: Telegram user ID of the driver or admin triggering the transition.
        note: Optional free-text note explaining the transition reason.
    """
    request_id: int
    new_status: RequestStatus
    actor_id: int
    note: str | None = None


@dataclass(frozen=True)
class CancelRequestDTO:
    """Schema for request cancellation commands.

    May originate from students, drivers, or admins. The service layer
    enforces role-specific cancellation rules.

    **Calls / Depends on:** ``CancelledBy`` enum.

    **Called by:** ``bot/student/handler.py``, ``bot/admin/handler.py``,
    ``bot/driver/handler.py`` (cancellation flows),
    ``bot/request/service.py::RequestService.cancel_request``,
    ``tests/unit/request/test_schemas.py``.

    Attributes:
        request_id: Primary key of the ``DeliveryRequest``.
        actor_id: Telegram user ID of the user initiating cancellation.
        cancelled_by: The role of the cancelling user (``CancelledBy`` enum).
        cancellation_reason: Optional explanation for the cancellation.
    """
    request_id: int
    actor_id: int
    cancelled_by: CancelledBy
    cancellation_reason: str | None = None


@dataclass(frozen=True)
class CreateFeedbackDTO:
    """Schema for student feedback submission on a delivered request.

    **Calls / Depends on:** None.

    **Called by:** ``bot/student/handler.py`` (feedback flow),
    ``bot/request/service.py::RequestService.submit_feedback``,
    ``tests/unit/request/test_schemas.py``.

    Attributes:
        request_id: Primary key of the ``DeliveryRequest`` being rated.
        student_id: Telegram user ID of the student submitting feedback.
        rating: Integer score from 1 to 5.
        comment: Optional free-text comment accompanying the rating.
    """
    request_id: int
    student_id: int
    rating: int
    comment: str | None = None
