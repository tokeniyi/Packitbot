"""Regression tests for the request-detail ``MissingGreenlet`` bug (P0 #4).

The bug: ``show_request_detail`` loaded the request with a plain
``get_by_id`` and then ``_format_request_detail`` touched
``request.driver`` and ``request.driver.driver_profile``.  Both are lazy
relationships, so reading them after the statement completed triggered IO
outside an awaited greenlet context and raised ``MissingGreenlet``.

These tests run against a real SQLite database (not a mock), because the
failure mode only exists in genuine SQLAlchemy lazy-loading behaviour.
"""

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from bot.core.constants.enums import (
    AccountStatus,
    LuggageSize,
    RequestStatus,
    UserRole,
)
from bot.core.db.base_class import Base
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.user import User
from bot.request.repository import RequestRepository
from bot.student.handlers.requests import _format_request_detail

STUDENT_ID = 1
DRIVER_ID = 2


@pytest.fixture
async def session(tmp_path):
    """A real async session backed by a temporary on-disk SQLite database.

    A file is used rather than ``:memory:`` because an in-memory SQLite
    database is scoped to a single connection, so the ``create_all``
    connection and the test's connection would see different schemas.
    ``NullPool`` closes each connection eagerly, which avoids SQLAlchemy's
    "garbage collector is trying to clean up non-checked-in connection"
    SAWarning at interpreter shutdown.
    """
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", poolclass=NullPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    s = AsyncSession(engine, expire_on_commit=False)
    try:
        yield s
    finally:
        await s.close()
        await engine.dispose()


@pytest.fixture
async def assigned_request(session):
    """A PENDING-style request that has a driver assigned to it.

    ``users.id`` is supplied explicitly because SQLite does not honour
    ``BigInteger`` autoincrement (tracked separately in the backlog as P0 #0).
    """
    session.add(
        User(
            id=STUDENT_ID,
            telegram_id=111,
            username="student",
            full_name="John Doe",
            role=UserRole.STUDENT,
            account_status=AccountStatus.ACTIVE,
        )
    )
    session.add(
        User(
            id=DRIVER_ID,
            telegram_id=222,
            username="driver",
            full_name="Jane Doe",
            phone_number="08011112222",
            role=UserRole.DRIVER,
            account_status=AccountStatus.ACTIVE,
        )
    )
    session.add(
        DriverProfile(
            user_id=DRIVER_ID,
            license_number="LAG-001",
            vehicle_type="CAR",
            plate_number="ABC-123",
        )
    )
    req = DeliveryRequest(
        student_id=STUDENT_ID,
        driver_id=DRIVER_ID,
        pickup_detail="Main Gate",
        dropoff_address="Block B, Room 12",
        hall_of_residence="Esther Hall",
        recipient_name="John Doe",
        recipient_phone="08033334444",
        luggage_size=LuggageSize.SMALL,
        luggage_count=1,
        preferred_date=date(2026, 10, 5),
        preferred_time_window="10:00-12:00",
        status=RequestStatus.ASSIGNED,
    )
    session.add(req)
    await session.commit()
    return req


async def test_format_request_detail_raises_on_plain_get_by_id(session, assigned_request):
    """Documents the original defect.

    A plain ``get_by_id`` leaves the driver relationships unloaded, so
    ``_format_request_detail`` raises ``MissingGreenlet``.  This test pins
    the bug so a future regression in the repository layer is visible.
    """
    repo = RequestRepository(session)
    req = await repo.get_by_id(assigned_request.id)

    with pytest.raises(Exception) as exc_info:
        _format_request_detail(req)

    assert "greenlet" in str(exc_info.value).lower() or exc_info.value.__class__.__name__ in {
        "MissingGreenlet",
    }


async def test_get_by_id_with_driver_eagerly_loads_the_driver_chain(
    session, assigned_request
):
    """The fix: both relationship hops are populated before formatting."""
    repo = RequestRepository(session)
    req = await repo.get_by_id_with_driver(assigned_request.id)

    assert req is not None
    assert req.driver is not None
    assert req.driver.full_name == "Jane Doe"
    assert req.driver.driver_profile is not None
    assert req.driver.driver_profile.plate_number == "ABC-123"


async def test_format_request_detail_succeeds_with_eager_loading(
    session, assigned_request
):
    """End-to-end: the exact handler path no longer raises."""
    repo = RequestRepository(session)
    req = await repo.get_by_id_with_driver(assigned_request.id)

    text = _format_request_detail(req)

    assert f"#{assigned_request.id}" in text
    assert "Jane Doe (08011112222)" in text
    assert "ABC-123" in text


async def test_get_by_id_with_driver_returns_none_for_missing_request(session):
    repo = RequestRepository(session)
    assert await repo.get_by_id_with_driver(9999) is None


async def test_get_by_id_with_driver_handles_unassigned_request(session):
    """A request with no driver must render the 'not assigned' path."""
    session.add(
        User(
            id=STUDENT_ID,
            telegram_id=111,
            username="student",
            full_name="John Doe",
            role=UserRole.STUDENT,
            account_status=AccountStatus.ACTIVE,
        )
    )
    req = DeliveryRequest(
        student_id=STUDENT_ID,
        driver_id=None,
        pickup_detail="Main Gate",
        dropoff_address="Block B",
        hall_of_residence="Esther Hall",
        recipient_name="John Doe",
        recipient_phone="08033334444",
        luggage_size=LuggageSize.SMALL,
        luggage_count=1,
        preferred_date=date(2026, 10, 5),
        preferred_time_window="10:00-12:00",
        status=RequestStatus.PENDING,
    )
    session.add(req)
    await session.commit()

    repo = RequestRepository(session)
    loaded = await repo.get_by_id_with_driver(req.id)

    assert loaded is not None
    assert loaded.driver is None
    assert "Not assigned yet" in _format_request_detail(loaded)
