"""
Request Business Rules Module
==============================

Pure predicate functions that enforce domain-level permissions and
eligibility constraints for delivery request operations.

These functions are intentionally side-effect free so they can be called
from both service-layer methods and handler-level guards. They do not
perform database access; instead they inspect already-fetched model
instances.

**Key Dependencies:**
- *Uses:* ``bot.core.constants.enums``, ``bot.core.models.delivery_request``, ``bot.core.models.driver_profile``
- *Used by:* ``bot/request/service.py``, ``tests/unit/request/test_business_rules.py``
"""
from typing import Any

from bot.core.constants.enums import (
    DriverAvailability,
    DriverStatus,
    RequestStatus,
)
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.driver_profile import DriverProfile


def can_student_cancel(request: DeliveryRequest, actor_id: int) -> bool:
    """Check whether the student who owns the request may cancel it.

    A student may cancel only their own requests, and only while the
    request is in PENDING, ASSIGNED, or ACCEPTED status.

    **Calls / Depends on:** ``RequestStatus`` enum values.

    **Called by:** ``bot/request/service.py::RequestService.cancel_request``,
    ``tests/unit/request/test_business_rules.py``.

    Args:
        request: The ``DeliveryRequest`` instance under evaluation.
        actor_id: The Telegram user ID of the user attempting cancellation.

    Returns:
        ``True`` if the actor is the request owner and the request is in a
        cancellable status; ``False`` otherwise.
    """
    if request.student_id != actor_id:
        return False
    return request.status in {
        RequestStatus.PENDING,
        RequestStatus.ASSIGNED,
        RequestStatus.ACCEPTED,
    }


def can_edit_request(request: DeliveryRequest, actor_id: int) -> bool:
    """Check whether the request owner may edit request details.

    Editing is only permitted while the request is still in PENDING
    status. Once a driver has been assigned, the logistics are locked.

    **Calls / Depends on:** ``RequestStatus`` enum values.

    **Called by:** ``bot/request/service.py::RequestService.update_request``,
    ``tests/unit/request/test_business_rules.py``.

    Args:
        request: The ``DeliveryRequest`` instance under evaluation.
        actor_id: The Telegram user ID of the user attempting to edit.

    Returns:
        ``True`` if the actor is the request owner and the request is PENDING;
        ``False`` otherwise.
    """
    return request.student_id == actor_id and request.status == RequestStatus.PENDING


def can_assign_driver(driver: DriverProfile) -> bool:
    """Check whether a driver is eligible to be assigned to a request.

    A driver must be both ``APPROVED`` (by an admin) and ``AVAILABLE``
    (not currently on another active delivery) to receive new assignments.

    **Calls / Depends on:** ``DriverStatus`` and ``DriverAvailability`` enum values.

    **Called by:** ``bot/request/service.py::RequestService.assign_driver``,
    ``tests/unit/request/test_business_rules.py``.

    Args:
        driver: The ``DriverProfile`` instance being evaluated.

    Returns:
        ``True`` if the driver is approved and available; ``False`` otherwise.
    """
    return (
        driver.status == DriverStatus.APPROVED
        and driver.availability == DriverAvailability.AVAILABLE
    )


def can_rate_delivery(request: DeliveryRequest, existing_feedback: Any = None) -> bool:
    """Check whether a delivered request is eligible to receive feedback.

    Feedback is allowed only once the request has reached ``DELIVERED``
    status and no feedback record has yet been attached. ``existing_feedback``
    may be provided directly to avoid lazy-loading the relationship.

    **Calls / Depends on:** ``RequestStatus`` enum values.

    **Called by:** ``bot/request/service.py::RequestService.submit_feedback``,
    ``tests/unit/request/test_business_rules.py``.

    Args:
        request: The ``DeliveryRequest`` instance under evaluation.
        existing_feedback: Optional pre-fetched feedback object. If ``None``,
            the function falls back to ``request.feedback`` (lazy attribute).

    Returns:
        ``True`` if the request is delivered and has no existing feedback;
        ``False`` otherwise.
    """
    # Accept an explicit feedback object to keep this function pure and
    # avoid implicit ORM lazy-loading inside business logic.
    feedback = existing_feedback or getattr(request, "feedback", None)
    return request.status == RequestStatus.DELIVERED and feedback is None
