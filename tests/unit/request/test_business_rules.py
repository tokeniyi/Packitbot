import pytest
from unittest.mock import MagicMock

from bot.core.constants.enums import (
    DriverAvailability,
    DriverStatus,
    RequestStatus,
)
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.user import User
from bot.request.business_rules import (
    can_assign_driver,
    can_edit_request,
    can_rate_delivery,
    can_student_cancel,
)


def _make_request(
    status: RequestStatus = RequestStatus.PENDING,
    student_id: int = 1,
    driver_id: int | None = None,
) -> DeliveryRequest:
    req = MagicMock(spec=DeliveryRequest)
    req.status = status
    req.student_id = student_id
    req.driver_id = driver_id
    req.feedback = None
    return req


def _make_driver(
    status: DriverStatus = DriverStatus.APPROVED,
    availability: DriverAvailability = DriverAvailability.AVAILABLE,
) -> DriverProfile:
    driver = MagicMock(spec=DriverProfile)
    driver.status = status
    driver.availability = availability
    return driver


class TestCanStudentCancel:
    def test_student_can_cancel_pending(self):
        req = _make_request(status=RequestStatus.PENDING, student_id=1)
        assert can_student_cancel(req, actor_id=1) is True

    def test_student_can_cancel_assigned(self):
        req = _make_request(status=RequestStatus.ASSIGNED, student_id=1)
        assert can_student_cancel(req, actor_id=1) is True

    def test_student_can_cancel_accepted(self):
        req = _make_request(status=RequestStatus.ACCEPTED, student_id=1)
        assert can_student_cancel(req, actor_id=1) is True

    def test_student_cannot_cancel_delivered(self):
        req = _make_request(status=RequestStatus.DELIVERED, student_id=1)
        assert can_student_cancel(req, actor_id=1) is False

    def test_student_cannot_cancel_en_route(self):
        req = _make_request(status=RequestStatus.EN_ROUTE_TO_PICKUP, student_id=1)
        assert can_student_cancel(req, actor_id=1) is False

    def test_student_cannot_cancel_in_transit(self):
        req = _make_request(status=RequestStatus.IN_TRANSIT, student_id=1)
        assert can_student_cancel(req, actor_id=1) is False

    def test_wrong_actor_cannot_cancel(self):
        req = _make_request(status=RequestStatus.PENDING, student_id=1)
        assert can_student_cancel(req, actor_id=999) is False


class TestCanEditRequest:
    def test_can_edit_pending(self):
        req = _make_request(status=RequestStatus.PENDING)
        assert can_edit_request(req) is True

    def test_cannot_edit_assigned(self):
        req = _make_request(status=RequestStatus.ASSIGNED)
        assert can_edit_request(req) is False

    def test_cannot_edit_accepted(self):
        req = _make_request(status=RequestStatus.ACCEPTED)
        assert can_edit_request(req) is False

    def test_cannot_edit_delivered(self):
        req = _make_request(status=RequestStatus.DELIVERED)
        assert can_edit_request(req) is False

    def test_cannot_edit_cancelled(self):
        req = _make_request(status=RequestStatus.CANCELLED)
        assert can_edit_request(req) is False


class TestCanAssignDriver:
    def test_can_assign_approved_available_driver(self):
        driver = _make_driver(
            status=DriverStatus.APPROVED,
            availability=DriverAvailability.AVAILABLE,
        )
        assert can_assign_driver(driver) is True

    def test_cannot_assign_pending_driver(self):
        driver = _make_driver(
            status=DriverStatus.PENDING_APPROVAL,
            availability=DriverAvailability.AVAILABLE,
        )
        assert can_assign_driver(driver) is False

    def test_cannot_assign_rejected_driver(self):
        driver = _make_driver(
            status=DriverStatus.REJECTED,
            availability=DriverAvailability.AVAILABLE,
        )
        assert can_assign_driver(driver) is False

    def test_cannot_assign_suspended_driver(self):
        driver = _make_driver(
            status=DriverStatus.SUSPENDED,
            availability=DriverAvailability.AVAILABLE,
        )
        assert can_assign_driver(driver) is False

    def test_cannot_assign_busy_driver(self):
        driver = _make_driver(
            status=DriverStatus.APPROVED,
            availability=DriverAvailability.BUSY,
        )
        assert can_assign_driver(driver) is False

    def test_cannot_assign_offline_driver(self):
        driver = _make_driver(
            status=DriverStatus.APPROVED,
            availability=DriverAvailability.OFFLINE,
        )
        assert can_assign_driver(driver) is False


class TestCanRateDelivery:
    def test_can_rate_delivered_with_no_feedback(self):
        req = _make_request(status=RequestStatus.DELIVERED)
        assert can_rate_delivery(req, existing_feedback=None) is True

    def test_cannot_rate_delivered_with_existing_feedback(self):
        req = _make_request(status=RequestStatus.DELIVERED)
        assert can_rate_delivery(req, existing_feedback=MagicMock()) is False

    def test_cannot_rate_pending(self):
        req = _make_request(status=RequestStatus.PENDING)
        assert can_rate_delivery(req, existing_feedback=None) is False

    def test_cannot_rate_accepted(self):
        req = _make_request(status=RequestStatus.ACCEPTED)
        assert can_rate_delivery(req, existing_feedback=None) is False

    def test_cannot_rate_cancelled(self):
        req = _make_request(status=RequestStatus.CANCELLED)
        assert can_rate_delivery(req, existing_feedback=None) is False