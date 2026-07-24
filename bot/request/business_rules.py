from bot.core.constants.enums import (
    DriverAvailability,
    DriverStatus,
    RequestStatus,
)
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.driver_profile import DriverProfile


def can_student_cancel(request: DeliveryRequest, actor_id: int) -> bool:
    if request.student_id != actor_id:
        return False
    return request.status in {
        RequestStatus.PENDING,
        RequestStatus.ASSIGNED,
        RequestStatus.ACCEPTED,
    }


def can_edit_request(request: DeliveryRequest) -> bool:
    return request.status == RequestStatus.PENDING


def can_assign_driver(driver: DriverProfile) -> bool:
    return (
        driver.status == DriverStatus.APPROVED
        and driver.availability == DriverAvailability.AVAILABLE
    )


def can_rate_delivery(request: DeliveryRequest, existing_feedback) -> bool:
    return request.status == RequestStatus.DELIVERED and existing_feedback is None