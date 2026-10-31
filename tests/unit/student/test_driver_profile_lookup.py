"""
Regression tests for the DriverProfile wrong-FK lookup (maintenance item #3).

``DeliveryRequest.driver_id`` is a ForeignKey to ``users.id`` -- NOT to
``DriverProfile.id``. The cancellation and feedback-rating paths used to pass that
value to ``session.get(DriverProfile, ...)``, which looks up the *profile* primary
key. When the two keys differ (the normal case, since the two tables have
independent autoincrement sequences) the lookup silently returned ``None`` or, worse,
a different driver's profile.

These tests assert the profile is resolved through ``DriverRepository.get_by_user_id``
(``WHERE user_id = :users_id``) and that ``session.get`` is never used for it.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.student.handlers.feedback import _recalculate_driver_rating
from bot.student.handlers.requests import show_request_detail


def _make_session(avg: float = 4.5, delivered: int = 2) -> MagicMock:
    """Session whose two ``execute`` calls return the rating aggregate, then the delivered count.

    ``_recalculate_driver_rating`` issues the rating aggregate first and the
    ``DELIVERED`` count second. ``Result.one()`` and ``Result.scalar_one()`` are
    *sync* methods on the result object.
    """
    session = MagicMock()
    rating_result = MagicMock()
    rating_result.one.return_value = (avg, 99)  # feedback-row count is not used
    delivered_result = MagicMock()
    delivered_result.scalar_one.return_value = delivered
    session.execute = AsyncMock(side_effect=[rating_result, delivered_result])
    session.flush = AsyncMock()
    session.get = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_recalculate_driver_rating_resolves_profile_by_user_id():
    session = _make_session(avg=4.5, delivered=3)
    profile = MagicMock(rating_avg=0.0, total_deliveries=0)

    with patch("bot.student.handlers.feedback.DriverRepository") as repo_cls:
        repo_cls.return_value.get_by_user_id = AsyncMock(return_value=profile)
        await _recalculate_driver_rating(session, 42)

    repo_cls.return_value.get_by_user_id.assert_awaited_once_with(42)
    session.get.assert_not_called()
    assert profile.rating_avg == 4.5
    assert profile.total_deliveries == 3


@pytest.mark.asyncio
async def test_recalculate_resolves_profile_via_user_id_not_profile_pk():
    """The assigned driver's users.id must be matched against DriverProfile.user_id."""
    session = _make_session()
    from bot.core.models.driver_profile import DriverProfile
    profile = MagicMock(spec=DriverProfile)
    profile.rating_avg = None
    profile.total_deliveries = None

    with patch(
        "bot.student.handlers.feedback.DriverRepository"
    ) as repo_cls, patch.object(
        session, "get", wraps=session.get
    ) as session_get:
        repo_cls.return_value.get_by_user_id = AsyncMock(return_value=profile)

        await _recalculate_driver_rating(session, 4242)

    # Resolved through the users.id -> DriverProfile.user_id path.
    repo_cls.assert_called_once_with(session)
    repo_cls.return_value.get_by_user_id.assert_awaited_once_with(4242)

    # The bug: session.get(DriverProfile, users.id) must never be called.
    session_get.assert_not_called()

    # And both aggregate queries still filter DeliveryRequest by users.id.
    rating_stmt = session.execute.await_args_list[0][0][0]
    assert "driver_id" in str(rating_stmt)
    assert profile.rating_avg == 4.5
    assert profile.total_deliveries == 2
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_total_deliveries_counts_delivered_requests_not_feedback_rows():
    """``total_deliveries`` must count DELIVERED requests, not Feedback rows.

    Regression (maintenance P0 #3): the count used to be ``count(Feedback.id)``, so
    unrated deliveries were not counted and any extra feedback was double-counted.
    """
    from bot.core.constants.enums import RequestStatus

    session = _make_session(avg=3.0, delivered=7)
    profile = MagicMock(rating_avg=0.0, total_deliveries=0)

    with patch("bot.student.handlers.feedback.DriverRepository") as repo_cls:
        repo_cls.return_value.get_by_user_id = AsyncMock(return_value=profile)
        await _recalculate_driver_rating(session, 42)

    assert profile.total_deliveries == 7
    assert profile.rating_avg == 3.0

    delivered_stmt = session.execute.await_args_list[1][0][0]
    compiled = str(delivered_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "FROM delivery_requests" in compiled
    assert "feedback" not in compiled.lower()
    assert f"'{RequestStatus.DELIVERED.name}'" in compiled
    assert "driver_id = 42" in compiled


@pytest.mark.asyncio
async def test_recalculate_is_a_noop_when_driver_has_no_profile():
    """A missing profile must not crash and must not run the aggregate query."""
    session = _make_session()

    with patch("bot.student.handlers.feedback.DriverRepository") as repo_cls:
        repo_cls.return_value.get_by_user_id = AsyncMock(return_value=None)

        await _recalculate_driver_rating(session, 999)

    session.execute.assert_not_awaited()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_restores_availability_of_the_correct_driver():
    """Cancelling a request must mark the ASSIGNED driver available again.

    Regression: the handler used ``session.get(DriverProfile, updated_req.driver_id)``.
    With driver_id being a users.id, that either missed the profile (availability never
    restored, driver stuck BUSY forever) or hit an unrelated driver's profile row.
    """
    from bot.core.constants.enums import DriverAvailability
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.driver_profile import DriverProfile
    from bot.student.handlers.requests import confirm_cancel_request

    session = _make_session()
    profile = MagicMock(spec=DriverProfile)
    profile.availability = DriverAvailability.BUSY

    updated = MagicMock(spec=DeliveryRequest)
    updated.id = 7
    updated.driver_id = 4242

    callback = MagicMock()
    callback.data = "my_req_cancel_confirm:7"
    callback.answer = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.from_user.id = 555

    service = MagicMock()
    service.cancel_request = AsyncMock(return_value=(updated, None))

    with (
        patch("bot.student.handlers.requests.DriverRepository") as repo_cls,
        patch("bot.student.handlers.requests.RequestService") as svc_cls,
        patch("bot.student.handlers.requests.resolve_user_id", AsyncMock(return_value=555)),
        patch.object(session, "get", wraps=session.get) as session_get,
    ):
        repo_cls.return_value.get_by_user_id = AsyncMock(return_value=profile)
        svc_cls.return_value = service

        await confirm_cancel_request(callback, session=session)

    repo_cls.return_value.get_by_user_id.assert_awaited_once_with(4242)
    session_get.assert_not_called()
    assert profile.availability is DriverAvailability.AVAILABLE
    session.flush.assert_awaited_once()


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
