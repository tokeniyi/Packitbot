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


def _make_session() -> MagicMock:
    session = MagicMock()
    # session.execute() is awaited; Result.one() is a *sync* method on the result.
    result = MagicMock()
    result.one.return_value = (4.5, 2)
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    session.get = AsyncMock()
    return session


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

    # And the aggregate query still filters DeliveryRequest by users.id.
    stmt = session.execute.await_args[0][0]
    assert "driver_id" in str(stmt)
    assert profile.rating_avg == 4.5
    assert profile.total_deliveries == 2
    session.flush.assert_awaited_once()


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


@pytest.mark.asyncio
async def test_total_deliveries_counts_delivered_requests_not_feedback(db_session):
    """Regression for P0 #3 remainder.

    ``total_deliveries`` must count ``DeliveryRequest`` rows whose status is
    ``DELIVERED``, not ``Feedback`` rows.  With the old query (inner join on
    ``feedbacks``, ``count(Feedback.id)``) a driver who delivered 5 requests
    but whose students left feedback on only 3 would show
    ``total_deliveries == 3`` — an under-count that silently breaks the
    ``/drivers`` leaderboard and per-driver profile stats.

    The fix uses ``count(DeliveryRequest.id)`` with a ``LEFT OUTER JOIN`` to
    ``feedbacks`` and a ``status == DELIVERED`` filter, so all delivered
    requests are counted regardless of whether feedback exists.
    """
    from datetime import date

    from bot.core.constants.enums import LuggageSize, RequestStatus, UserRole
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.feedback import Feedback
    from bot.core.models.user import User
    from bot.core.models.driver_profile import DriverProfile

    # --- driver user + profile ---
    driver = User(telegram_id=100, username="drv", full_name="D", role=UserRole.DRIVER)
    db_session.add(driver)
    await db_session.flush()

    profile = DriverProfile(
        user_id=driver.id,
        vehicle_type="motorcycle",
        plate_number="ABC-001",
        license_number="LIC-001",
    )
    db_session.add(profile)
    await db_session.flush()

    # --- student user (needed as FK target) ---
    student = User(telegram_id=200, username="stu", full_name="S", role=UserRole.STUDENT)
    db_session.add(student)
    await db_session.flush()

    # --- 5 DELIVERED requests for this driver ---
    delivered_reqs = []
    for i in range(5):
        req = DeliveryRequest(
            student_id=student.id,
            driver_id=driver.id,
            pickup_detail=f"Pickup {i}",
            dropoff_address=f"Dropoff {i}",
            hall_of_residence="Hall A",
            recipient_name=f"Recipient {i}",
            recipient_phone="08012345678",
            luggage_size=LuggageSize.SMALL,
            luggage_count=1,
            preferred_date=date.today(),
            preferred_time_window="09:00-12:00",
            status=RequestStatus.DELIVERED,
        )
        db_session.add(req)
        delivered_reqs.append(req)
    await db_session.flush()

    # --- feedback for only 3 of the 5 (ratings 4, 5, 3) ---
    for req, rating in zip(delivered_reqs[:3], [4, 5, 3]):
        db_session.add(
            Feedback(request_id=req.id, student_id=student.id, rating=rating)
        )
    await db_session.flush()

    # --- exercise the function under real SQL ---
    await _recalculate_driver_rating(db_session, driver.id)

    # All 5 delivered requests counted, not just the 3 with feedback.
    assert profile.total_deliveries == 5, (
        "total_deliveries should count DELIVERED DeliveryRequest rows "
        "(5), not Feedback rows (3)"
    )
    # Average of the 3 ratings that exist: (4 + 5 + 3) / 3 = 4.0
    assert profile.rating_avg == 4.0


@pytest.mark.asyncio
async def test_total_deliveries_excludes_non_delivered_requests(db_session):
    """A request in a non-DELIVERED terminal state must not be counted.

    Even if a ``Feedback`` row exists for a ``CANCELLED`` request, the
    ``total_deliveries`` count must only include ``DELIVERED`` requests.
    """
    from datetime import date

    from bot.core.constants.enums import LuggageSize, RequestStatus, UserRole
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.feedback import Feedback
    from bot.core.models.user import User
    from bot.core.models.driver_profile import DriverProfile

    driver = User(telegram_id=101, username="drv2", full_name="D2", role=UserRole.DRIVER)
    db_session.add(driver)
    await db_session.flush()

    profile = DriverProfile(
        user_id=driver.id,
        vehicle_type="car",
        plate_number="ABC-002",
        license_number="LIC-002",
    )
    db_session.add(profile)
    await db_session.flush()

    student = User(telegram_id=201, username="stu2", full_name="S2", role=UserRole.STUDENT)
    db_session.add(student)
    await db_session.flush()

    # One DELIVERED request with feedback.
    delivered = DeliveryRequest(
        student_id=student.id,
        driver_id=driver.id,
        pickup_detail="p1",
        dropoff_address="d1",
        hall_of_residence="Hall B",
        recipient_name="R1",
        recipient_phone="08011112222",
        luggage_size=LuggageSize.MEDIUM,
        luggage_count=2,
        preferred_date=date.today(),
        preferred_time_window="10:00-14:00",
        status=RequestStatus.DELIVERED,
    )
    db_session.add(delivered)
    await db_session.flush()

    db_session.add(
        Feedback(request_id=delivered.id, student_id=student.id, rating=5)
    )

    # One CANCELLED request with its own feedback — must NOT count toward
    # total_deliveries.  With the old query (inner join, no status filter)
    # this row would inflate the count to 2; the fix's status == DELIVERED
    # filter ensures only delivered requests are counted.
    cancelled = DeliveryRequest(
        student_id=student.id,
        driver_id=driver.id,
        pickup_detail="p2",
        dropoff_address="d2",
        hall_of_residence="Hall B",
        recipient_name="R2",
        recipient_phone="08033334444",
        luggage_size=LuggageSize.SMALL,
        luggage_count=1,
        preferred_date=date.today(),
        preferred_time_window="10:00-14:00",
        status=RequestStatus.CANCELLED,
    )
    db_session.add(cancelled)
    await db_session.flush()
    db_session.add(
        Feedback(request_id=cancelled.id, student_id=student.id, rating=5)
    )
    await db_session.flush()

    await _recalculate_driver_rating(db_session, driver.id)

    assert profile.total_deliveries == 1, (
        "CANCELLED requests must not be counted in total_deliveries"
    )
    # rating_avg averages only DELIVERED requests' feedback = 5.0
    assert profile.rating_avg == 5.0
