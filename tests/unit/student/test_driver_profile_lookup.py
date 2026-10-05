"""Regression tests for the DriverProfile wrong-FK lookup (maintenance item #3).

``DeliveryRequest.driver_id`` is a ForeignKey to ``users.id`` — NOT to
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

from bot.core.models.driver_profile import DriverProfile
from bot.student.handlers.feedback import _recalculate_driver_rating


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
async def test_recalculate_resolves_profile_via_user_id_not_profile_pk() -> None:
    """The assigned driver's users.id must be matched against DriverProfile.user_id."""
    session = _make_session()
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
async def test_recalculate_is_a_noop_when_driver_has_no_profile() -> None:
    """A missing profile must not crash and must not run the aggregate query."""
    session = _make_session()

    with patch("bot.student.handlers.feedback.DriverRepository") as repo_cls:
        repo_cls.return_value.get_by_user_id = AsyncMock(return_value=None)

        await _recalculate_driver_rating(session, 999)

    session.execute.assert_not_awaited()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_restores_availability_of_the_correct_driver() -> None:
    """Cancelling a request must mark the ASSIGNED driver available again.

    Regression: the handler used ``session.get(DriverProfile, updated_req.driver_id)``.
    With driver_id being a users.id, that either missed the profile (availability never
    restored, driver stuck BUSY forever) or hit an unrelated driver's profile row.
    """
    from bot.core.constants.enums import DriverAvailability
    from bot.core.models.delivery_request import DeliveryRequest
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
