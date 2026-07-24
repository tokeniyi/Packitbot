import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select

from bot.core.constants.enums import RequestStatus
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.feedback import Feedback
from bot.core.models.status_log import RequestStatusLog
from bot.request.repository import (
    FeedbackRepository,
    RequestRepository,
    StatusLogRepository,
)


def _make_request(
    id: int = 1,
    status: RequestStatus = RequestStatus.PENDING,
    student_id: int = 1,
    driver_id: int | None = None,
    created_at=None,
) -> DeliveryRequest:
    req = MagicMock(spec=DeliveryRequest)
    req.id = id
    req.status = status
    req.student_id = student_id
    req.driver_id = driver_id
    return req


async def test_request_repository_get_pending_returns_only_pending():
    session = AsyncMock()
    row = MagicMock()
    row.scalar_one_or_none.return_value = None

    req1 = _make_request(id=1, status=RequestStatus.PENDING)
    req2 = _make_request(id=2, status=RequestStatus.DELIVERED)
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [req1]
    session.execute.return_value = result_mock

    repo = RequestRepository(session)
    requests = await repo.get_pending(page=1)

    assert len(requests) == 1
    assert requests[0].id == 1


async def test_request_repository_get_active_for_driver_returns_one():
    session = AsyncMock()
    driver_req = _make_request(id=1, status=RequestStatus.ASSIGNED, driver_id=7)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = driver_req
    session.execute.return_value = result_mock

    repo = RequestRepository(session)
    result = await repo.get_active_for_driver(driver_id=7)

    assert result is not None
    assert result.id == 1
    assert result.driver_id == 7


async def test_request_repository_get_active_for_driver_returns_none():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock

    repo = RequestRepository(session)
    result = await repo.get_active_for_driver(driver_id=7)

    assert result is None


async def test_request_repository_get_history_for_student():
    session = AsyncMock()
    req = _make_request(id=1, student_id=42)
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [req]
    session.execute.return_value = result_mock

    repo = RequestRepository(session)
    requests = await repo.get_history_for_student(student_id=42)

    assert len(requests) == 1
    assert requests[0].student_id == 42


async def test_request_repository_get_dropoff_address_history():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.all.return_value = [("123 Lagos Street",), ("456 Abuja Road",)]
    session.execute.return_value = result_mock

    repo = RequestRepository(session)
    addresses = await repo.get_dropoff_address_history_for_student(student_id=42)

    assert len(addresses) == 2
    assert "123 Lagos Street" in addresses


async def test_status_log_repository_create():
    session = AsyncMock()
    repo = StatusLogRepository(session)

    log_entry = MagicMock(spec=RequestStatusLog)
    log_entry.request_id = 1
    session.add.return_value = None

    result = await repo.create(request_id=1, old_status=None, new_status=RequestStatus.ASSIGNED)
    assert result is not None
    session.add.assert_called_once()


async def test_feedback_repository_get_for_request_found():
    session = AsyncMock()
    feedback = MagicMock(spec=Feedback)
    feedback.id = 1
    feedback.request_id = 42
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = feedback
    session.execute.return_value = result_mock

    repo = FeedbackRepository(session)
    result = await repo.get_for_request(request_id=42)

    assert result is not None
    assert result.request_id == 42


async def test_feedback_repository_get_for_request_not_found():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock

    repo = FeedbackRepository(session)
    result = await repo.get_for_request(request_id=42)

    assert result is None


async def test_request_repository_get_pending_pagination():
    session = AsyncMock()
    req = _make_request(id=1, status=RequestStatus.PENDING)
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [req]
    session.execute.return_value = result_mock

    repo = RequestRepository(session)
    requests = await repo.get_pending(page=2)

    session.execute.assert_called_once()
    call_arg = session.execute.call_args[0][0]
    assert "OFFSET" in str(call_arg) or "LIMIT" in str(call_arg)


async def test_request_repository_list_returns_all():
    session = AsyncMock()
    req1 = _make_request(id=1, status=RequestStatus.PENDING)
    req2 = _make_request(id=2, status=RequestStatus.ASSIGNED)
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [req1, req2]
    session.execute.return_value = result_mock

    repo = RequestRepository(session)
    all_requests = await repo.list()

    assert len(all_requests) == 2