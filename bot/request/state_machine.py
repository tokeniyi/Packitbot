from bot.core.constants.enums import RequestStatus

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
    RequestStatus.DELIVERED: set(),
    RequestStatus.CANCELLED: set(),
    RequestStatus.FAILED: set(),
}


def can_transition(old_status: RequestStatus, new_status: RequestStatus) -> bool:
    """Check if transitioning from old_status to new_status is allowed by domain rules."""
    allowed = ALLOWED_TRANSITIONS.get(old_status, set())
    return new_status in allowed