from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.student.handlers.feedback import _recalculate_driver_rating
from bot.student.handlers.requests import show_request_detail


@pytest.mark.asyncio
async def test_recalculate_driver_rating_resolves_profile_by_user_id():
    session = MagicMock()
    result = MagicMock()
    result.one.return_value = (4.5, 3)
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    session.get = AsyncMock()
    profile = MagicMock(rating_avg=0.0, total_deliveries=0)

    with patch("bot.student.handlers.feedback.DriverRepository") as repo_cls:
        repo_cls.return_value.get_by_user_id = AsyncMock(return_value=profile)
        await _recalculate_driver_rating(session, 42)

    repo_cls.return_value.get_by_user_id.assert_awaited_once_with(42)
    session.get.assert_not_called()
    assert profile.rating_avg == 4.5
    assert profile.total_deliveries == 3


@pytest.mark.asyncio
async def test_show_request_detail_uses_eager_driver_query():
    callback = MagicMock()
    callback.data = "my_req_detail:9"
    callback.from_user.id = 1001
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()

    request_obj = MagicMock()
    request_obj.student_id = 77
    request_obj.id = 9

    class FakeRepo:
        def __init__(self, session):
            pass

        async def get_by_id_with_driver(self, request_id):
            assert request_id == 9
            return request_obj

        async def get_by_id(self, request_id):
            raise AssertionError("show_request_detail should use get_by_id_with_driver")

    with (
        patch("bot.student.handlers.requests.RequestRepository", FakeRepo),
        patch("bot.student.handlers.requests.resolve_user_id", AsyncMock(return_value=77)),
        patch("bot.student.handlers.requests._format_request_detail", return_value="detail"),
        patch("bot.student.handlers.requests.request_detail_keyboard", return_value=MagicMock()),
    ):
        await show_request_detail(callback, session=MagicMock())

    callback.message.edit_text.assert_awaited_once()
