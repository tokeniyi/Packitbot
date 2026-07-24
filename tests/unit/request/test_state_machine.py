import pytest

from bot.core.constants.enums import RequestStatus
from bot.request.state_machine import ALLOWED_TRANSITIONS, can_transition


ALL_STATUSES = list(RequestStatus)


@pytest.mark.parametrize(
    "old_status,new_status",
    [
        (RequestStatus.PENDING, RequestStatus.ASSIGNED),
        (RequestStatus.PENDING, RequestStatus.CANCELLED),
        (RequestStatus.ASSIGNED, RequestStatus.ACCEPTED),
        (RequestStatus.ASSIGNED, RequestStatus.REJECTED_BY_DRIVER),
        (RequestStatus.ASSIGNED, RequestStatus.CANCELLED),
        (RequestStatus.ACCEPTED, RequestStatus.EN_ROUTE_TO_PICKUP),
        (RequestStatus.ACCEPTED, RequestStatus.CANCELLED),
        (RequestStatus.REJECTED_BY_DRIVER, RequestStatus.ASSIGNED),
        (RequestStatus.REJECTED_BY_DRIVER, RequestStatus.CANCELLED),
        (RequestStatus.EN_ROUTE_TO_PICKUP, RequestStatus.PICKED_UP),
        (RequestStatus.EN_ROUTE_TO_PICKUP, RequestStatus.CANCELLED),
        (RequestStatus.PICKED_UP, RequestStatus.IN_TRANSIT),
        (RequestStatus.PICKED_UP, RequestStatus.CANCELLED),
        (RequestStatus.IN_TRANSIT, RequestStatus.DELIVERED),
        (RequestStatus.IN_TRANSIT, RequestStatus.FAILED),
        (RequestStatus.IN_TRANSIT, RequestStatus.CANCELLED),
    ],
)
def test_can_transition_returns_true(old_status, new_status):
    assert can_transition(old_status, new_status) is True


@pytest.mark.parametrize(
    "old_status,new_status",
    [
        (RequestStatus.DELIVERED, RequestStatus.IN_TRANSIT),
        (RequestStatus.CANCELLED, RequestStatus.PENDING),
        (RequestStatus.FAILED, RequestStatus.DELIVERED),
        (RequestStatus.ASSIGNED, RequestStatus.IN_TRANSIT),
        (RequestStatus.REJECTED_BY_DRIVER, RequestStatus.PICKED_UP),
        (RequestStatus.PENDING, RequestStatus.IN_TRANSIT),
        (RequestStatus.ACCEPTED, RequestStatus.DELIVERED),
        (RequestStatus.EN_ROUTE_TO_PICKUP, RequestStatus.REJECTED_BY_DRIVER),
        (RequestStatus.PICKED_UP, RequestStatus.ASSIGNED),
        (RequestStatus.PENDING, RequestStatus.PICKED_UP),
    ],
)
def test_can_transition_returns_false(old_status, new_status):
    assert can_transition(old_status, new_status) is False


def test_terminal_statuses_have_no_outgoing_transitions():
    for terminal in (
        RequestStatus.DELIVERED,
        RequestStatus.CANCELLED,
        RequestStatus.FAILED,
    ):
        assert ALLOWED_TRANSITIONS[terminal] == set()


def test_all_allowed_transitions_are_exhaustive():
    for old_status, new_statuses in ALLOWED_TRANSITIONS.items():
        for new_status in new_statuses:
            assert can_transition(old_status, new_status) is True


def test_no_illegal_transitions_slipped_through():
    for old_status in ALL_STATUSES:
        for new_status in ALL_STATUSES:
            is_allowed = new_status in ALLOWED_TRANSITIONS.get(old_status, set())
            assert can_transition(old_status, new_status) == is_allowed