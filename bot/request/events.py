"""
Request Domain Events Module
=============================

Immutable dataclass definitions for all domain events emitted during the
delivery request lifecycle.

Events are produced by ``RequestService`` after each state-changing
operation and consumed by notification/messaging handlers to update
students, drivers, and admins via the Telegram bot interface.

Because these dataclasses are ``frozen=True``, they are safe to share
across async boundaries and can be used as hashable keys if needed.

**Key Dependencies:**
- *Uses:* ``bot.core.constants.enums`` (``CancelledBy``, ``RequestStatus``)
- *Used by:* ``bot/request/service.py``, ``tests/unit/request/test_events.py``
"""
from dataclasses import dataclass

from bot.core.constants.enums import CancelledBy, RequestStatus


@dataclass(frozen=True)
class RequestCreatedEvent:
    """Emitted when a student successfully creates a new delivery request.

    **Calls / Depends on:** ``RequestStatus`` (none directly, but structurally related).

    **Called by:** ``bot/request/service.py::RequestService.create_request``.

    Attributes:
        request_id: Primary key of the newly created ``DeliveryRequest``.
        student_id: Telegram user ID of the student who created the request.
    """
    request_id: int
    student_id: int


@dataclass(frozen=True)
class RequestAssignedEvent:
    """Emitted when an admin assigns a driver to a pending request.

    Signals the driver that they have a new delivery to accept or reject,
    and notifies the student that their request has been picked up.

    **Calls / Depends on:** None.

    **Called by:** ``bot/request/service.py::RequestService.assign_driver``.

    Attributes:
        request_id: Primary key of the ``DeliveryRequest``.
        driver_id: Telegram user ID of the assigned driver.
        admin_id: Telegram user ID of the admin who performed the assignment.
    """
    request_id: int
    driver_id: int
    admin_id: int


@dataclass(frozen=True)
class RequestStatusChangedEvent:
    """Emitted when a request transitions to a new status.

    Covers transitions driven by drivers (accept, reject, en-route,
    picked-up, in-transit, delivered, failed) as well as cancellations
    when emitted through the generic transition path.

    **Calls / Depends on:** ``RequestStatus`` enum.

    **Called by:** ``bot/request/service.py::RequestService.transition_status``.

    Attributes:
        request_id: Primary key of the ``DeliveryRequest``.
        old_status: The previous ``RequestStatus`` (``None`` if unknown).
        new_status: The new ``RequestStatus`` after the transition.
        actor_id: Telegram user ID of the user who triggered the change
            (driver or admin); ``None`` for system-initiated changes.
    """
    request_id: int
    old_status: RequestStatus | None
    new_status: RequestStatus
    actor_id: int | None


@dataclass(frozen=True)
class RequestCancelledEvent:
    """Emitted when a request is cancelled by a student, driver, or admin.

    **Calls / Depends on:** ``CancelledBy`` enum.

    **Called by:** ``bot/request/service.py::RequestService.cancel_request``.

    Attributes:
        request_id: Primary key of the ``DeliveryRequest``.
        cancelled_by: The role that initiated the cancellation.
        actor_id: Telegram user ID of the user who cancelled.
        reason: Optional free-text explanation for the cancellation.
    """
    request_id: int
    cancelled_by: CancelledBy
    actor_id: int
    reason: str | None = None


@dataclass(frozen=True)
class FeedbackSubmittedEvent:
    """Emitted when a student submits feedback for a delivered request.

    Triggers downstream processes such as driver rating aggregation and
    admin reporting.

    **Calls / Depends on:** None.

    **Called by:** ``bot/request/service.py::RequestService.submit_feedback``.

    Attributes:
        feedback_id: Primary key of the newly created ``Feedback`` record.
        request_id: Primary key of the associated ``DeliveryRequest``.
        student_id: Telegram user ID of the student who submitted feedback.
        rating: Integer score from 1 (worst) to 5 (best).
    """
    feedback_id: int
    request_id: int
    student_id: int
    rating: int
