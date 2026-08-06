"""
Request State Machine Module
=============================

Declarative finite-state machine defining all legal status transitions
for delivery requests within the PackitBot domain.

The state machine enforces that a request can only move from one
``RequestStatus`` to another if that transition is explicitly listed in
``ALLOWED_TRANSITIONS``. Terminal states (DELIVERED, CANCELLED, FAILED)
have empty outgoing transition sets.

**Key Dependencies:**
- *Uses:* ``bot.core.constants.enums`` (``RequestStatus``)
- *Used by:* ``bot/request/service.py``, ``tests/unit/request/test_state_machine.py``
"""
from bot.core.constants.enums import RequestStatus

#: Directed graph of allowed ``(old_status -> new_status)`` transitions.
#:
#: Each key is a source ``RequestStatus``; its value is the set of
#: ``RequestStatus`` values it may legally transition to.
#:
#: Terminal states (DELIVERED, CANCELLED, FAILED) map to empty sets,
#: meaning no further transitions are permitted once reached.
ALLOWED_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.PENDING: {
        RequestStatus.ASSIGNED,
        RequestStatus.CANCELLED,
    },
    RequestStatus.ASSIGNED: {
        RequestStatus.ACCEPTED,
        RequestStatus.REJECTED_BY_DRIVER,
        RequestStatus.CANCELLED,
    },
    RequestStatus.ACCEPTED: {
        RequestStatus.EN_ROUTE_TO_PICKUP,
        RequestStatus.CANCELLED,
    },
    RequestStatus.REJECTED_BY_DRIVER: {
        RequestStatus.ASSIGNED,
        RequestStatus.CANCELLED,
    },
    RequestStatus.EN_ROUTE_TO_PICKUP: {
        RequestStatus.PICKED_UP,
        RequestStatus.CANCELLED,
    },
    RequestStatus.PICKED_UP: {
        RequestStatus.IN_TRANSIT,
        RequestStatus.CANCELLED,
    },
    RequestStatus.IN_TRANSIT: {
        RequestStatus.DELIVERED,
        RequestStatus.FAILED,
        RequestStatus.CANCELLED,
    },
    # Terminal states: no outgoing transitions permitted.
    RequestStatus.DELIVERED: set(),
    RequestStatus.CANCELLED: set(),
    RequestStatus.FAILED: set(),
}


def can_transition(old_status: RequestStatus, new_status: RequestStatus) -> bool:
    """Determine whether a status transition is permitted by the domain state machine.

    Looks up ``old_status`` in ``ALLOWED_TRANSITIONS`` and checks membership
    of ``new_status`` in the resulting set.

    **Calls / Depends on:** ``ALLOWED_TRANSITIONS`` (module-level constant).

    **Called by:** ``bot/request/service.py`` (all mutation methods),
    ``tests/unit/request/test_state_machine.py``.

    Args:
        old_status: The current ``RequestStatus`` of the delivery request.
        new_status: The desired target ``RequestStatus``.

    Returns:
        ``True`` if the transition is explicitly allowed; ``False`` otherwise
        (including when ``old_status`` is not found in the transition map).
    """
    allowed = ALLOWED_TRANSITIONS.get(old_status, set())
    return new_status in allowed
