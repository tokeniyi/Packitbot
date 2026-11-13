"""Real-database regression tests for the SAVEPOINT in ``RequestService.create_request`` (P1 #14).

The backlog fix wraps the mutating ``RequestService`` methods in
``session.begin_nested()`` so that a constraint violation rolls back only the
nested transaction. The unit tests for that fix mock ``begin_nested`` and so
cannot prove the behaviour. These tests run against a real (temporary) SQLite
database, where a ``NOT NULL`` violation is a genuine ``IntegrityError`` raised
on flush inside the SAVEPOINT.

What they prove:
- the violation is translated to the domain ``ValidationError``;
- the outer session is still usable afterwards (no ``PendingRollbackError``),
  which is what lets the global error handler reply to the user;
- the failed row is not persisted, while earlier successful work is kept.
"""

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import func, select

from bot.core.constants.enums import AccountStatus, LuggageSize, UserRole
from bot.core.db.base_class import Base
from bot.core.exceptions import ValidationError
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.status_log import RequestStatusLog
from bot.core.models.user import User
from bot.request.schemas import CreateRequestDTO
from bot.request.service import RequestService

STUDENT_ID = 1


@pytest.fixture
async def session(tmp_path):
    """A real async session on a temporary on-disk SQLite database.

    A file is used rather than ``:memory:`` for the same reason as the other
    real-session tests: the schema and the test must share one database.
    """
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'savepoint.db'}", poolclass=NullPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    s = AsyncSession(engine, expire_on_commit=False)
    s.add(
        User(
            id=STUDENT_ID,
            telegram_id=111,
            username="student",
            full_name="John Doe",
            role=UserRole.STUDENT,
            account_status=AccountStatus.ACTIVE,
        )
    )
    await s.flush()
    try:
        yield s
    finally:
        await s.close()
        await engine.dispose()


def _dto(**overrides) -> CreateRequestDTO:
    values = dict(
        student_id=STUDENT_ID,
        pickup_detail="Front desk, block A",
        dropoff_address="Room 12, block C",
        dropoff_landmark=None,
        hall_of_residence="Hall A",
        recipient_name="Jane Doe",
        recipient_phone="08000000000",
        luggage_size=LuggageSize.SMALL,
        luggage_count=1,
        special_instructions=None,
        preferred_date=date(2026, 12, 1),
        preferred_time_window="2-4 PM",
    )
    values.update(overrides)
    return CreateRequestDTO(**values)


async def _count(session: AsyncSession, model) -> int:
    result = await session.execute(select(func.count()).select_from(model))
    return result.scalar_one()


async def test_successful_create_persists_request_and_status_log(session):
    service = RequestService(session)

    request, _event = await service.create_request(_dto())
    await session.commit()

    assert await _count(session, DeliveryRequest) == 1
    assert await _count(session, RequestStatusLog) == 1
    assert request.id is not None


async def test_integrity_error_inside_savepoint_is_translated_and_session_survives(session):
    service = RequestService(session)

    # Keep one good request so we can prove the failure did not wipe prior work.
    await service.create_request(_dto())
    await session.commit()

    # ``pickup_detail`` is NOT NULL, so this raises IntegrityError on flush,
    # inside the SAVEPOINT opened by ``create_request``.
    with pytest.raises(ValidationError):
        await service.create_request(_dto(pickup_detail=None))

    # The outer session must still be usable: a further query must not raise
    # PendingRollbackError. Before the SAVEPOINT fix this line fails.
    assert await _count(session, DeliveryRequest) == 1

    # And a subsequent valid write on the same session must succeed.
    await service.create_request(_dto(recipient_name="Second Recipient"))
    await session.commit()
    assert await _count(session, DeliveryRequest) == 2
    assert await _count(session, RequestStatusLog) == 2
