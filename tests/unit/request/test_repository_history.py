import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.core.constants.enums import RequestStatus
from bot.core.models.delivery_request import DeliveryRequest
from bot.request.repository import RequestRepository


def _make_request(
    id: int = 1,
    status: RequestStatus = RequestStatus.PENDING,
    student_id: int = 1,
    driver_id: int | None = None,
    hall_of_residence: str = "Hall",
    created_at=None,
) -> MagicMock:
    req = MagicMock(spec=DeliveryRequest)
    req.id = id
    req.status = status
    req.student_id = student_id
    req.driver_id = driver_id
    req.hall_of_residence = hall_of_residence
    req.created_at = created_at
    return req


async def test_get_history_for_student_returns_page_with_total_count():
    session = AsyncMock()
    requests = [
        _make_request(id=1, student_id=42),
        _make_request(id=2, student_id=42),
        _make_request(id=3, student_id=42),
        _make_request(id=4, student_id=42),
        _make_request(id=5, student_id=42),
        _make_request(id=6, student_id=42),
    ]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = requests[:5]
    session.execute.return_value = result_mock

    count_result = MagicMock()
    count_result.scalar_one.return_value = 6
    session.execute.side_effect = [result_mock, count_result]

    repo = RequestRepository(session)
    page = await repo.get_history_for_student(student_id=42, page=1)

    assert len(page.items) == 5
    assert page.total == 6
    assert page.page == 1
    assert page.page_size == 5
    assert page.total_pages == 2
    assert page.has_next is True
    assert page.has_prev is False


async def test_get_history_for_student_page_two_returns_slice():
    session = AsyncMock()
    requests = [
        _make_request(id=i, student_id=42) for i in range(1, 8)
    ]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = requests[5:]
    session.execute.return_value = result_mock

    count_result = MagicMock()
    count_result.scalar_one.return_value = 7
    session.execute.side_effect = [result_mock, count_result]

    repo = RequestRepository(session)
    page = await repo.get_history_for_student(student_id=42, page=2)

    assert len(page.items) == 2
    assert page.total == 7
    assert page.page == 2
    assert page.total_pages == 2
    assert page.has_next is False
    assert page.has_prev is True
