"""Real-PostgreSQL tests for the SAVEPOINT in ``RequestService.create_request`` (P1 #14, backlog follow-up).

The SQLite tests in ``tests/unit/request/test_create_request_savepoint_real_db.py``
prove the SAVEPOINT behaviour for a ``NOT NULL`` violation. SQLite does not
enforce foreign keys by default, so this file covers the case that matters in
production: a ``student_id`` that points at no user, which PostgreSQL rejects
with a foreign-key ``IntegrityError`` on flush.

What they prove, against a real PostgreSQL database:
- the foreign-key violation inside ``create_request`` is translated to the
  domain ``ValidationError``;
- the session that raised it stays usable (no ``PendingRollbackError``);
- a second, independent session on another connection is unaffected and can
  write and read committed rows, so one failed request does not block others.

The tests need a real PostgreSQL server. They run only when ``DATABASE_URL``
points at PostgreSQL and the server is reachable; otherwise they are skipped,
so the suite still passes in environments without a database. CI provides
PostgreSQL through its service container.

Each test works in its own throwaway schema (created and dropped by the test),
so it never touches the tables used by the Alembic tests in the same database.
"""

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from bot.core.constants.enums import AccountStatus, LuggageSize, UserRole
from bot.core.db.base_class import Base
from bot.core.exceptions import ValidationError
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.status_log import RequestStatusLog
from bot.core.models.user import User
from bot.request.schemas import CreateRequestDTO
from bot.request.service import RequestService


STUDENT_ID = 1
MISSING_STUDENT_ID = 987654


def make_dto(**overrides) -> CreateRequestDTO:
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


_DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _is_postgres_url(url: str) -> bool:
    return url.startswith("postgresql")


pytestmark = pytest.mark.skipif(
    not _is_postgres_url(_DATABASE_URL),
    reason="DATABASE_URL does not point at PostgreSQL; these tests need a real server",
)


@pytest.fixture
async def schema_name():
    """A unique schema for one test, dropped afterwards."""
    name = f"savepoint_test_{uuid.uuid4().hex[:12]}"
    admin_engine = create_async_engine(_DATABASE_URL, poolclass=NullPool)
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{name}"'))
            await conn.commit()
    except Exception as exc:  # server not reachable or no privilege to create schemas
        await admin_engine.dispose()
        pytest.skip(f"PostgreSQL not usable for this test: {exc}")
    try:
        yield name
    finally:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))
            await conn.commit()
        await admin_engine.dispose()


@pytest.fixture
async def engine(schema_name):
    """Engine whose unqualified tables resolve to the test's own schema."""
    eng = create_async_engine(
        _DATABASE_URL,
        poolclass=NullPool,
        execution_options={"schema_translate_map": {None: schema_name}},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


async def _seed_student(session: AsyncSession) -> None:
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
    await session.commit()


async def _count(session: AsyncSession, model) -> int:
    result = await session.execute(select(func.count()).select_from(model))
    return result.scalar_one()


async def test_foreign_key_violation_is_translated_and_session_survives(engine):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await _seed_student(session)
        service = RequestService(session)

        await service.create_request(make_dto())
        await session.commit()

        # ``student_id`` references no user: PostgreSQL raises a foreign-key
        # IntegrityError on flush, inside the SAVEPOINT opened by create_request.
        with pytest.raises(ValidationError):
            await service.create_request(make_dto(student_id=MISSING_STUDENT_ID))

        # The session must still be usable: no PendingRollbackError, and the
        # earlier committed request is still there.
        assert await _count(session, DeliveryRequest) == 1

        await service.create_request(make_dto(recipient_name="Second Recipient"))
        await session.commit()
        assert await _count(session, DeliveryRequest) == 2
        assert await _count(session, RequestStatusLog) == 2


async def test_failed_create_leaves_no_rows_and_other_session_keeps_working(engine):
    failing = AsyncSession(engine, expire_on_commit=False)
    other = AsyncSession(engine, expire_on_commit=False)
    try:
        await _seed_student(failing)

        # Start the failing request in one session, on one connection.
        with pytest.raises(ValidationError):
            await RequestService(failing).create_request(
                make_dto(student_id=MISSING_STUDENT_ID)
            )
        await failing.rollback()

        # A second session on another connection can write and commit.
        await RequestService(other).create_request(make_dto())
        await other.commit()

        # Both sessions see exactly the committed state: one request, no
        # leftovers from the failed attempt.
        assert await _count(failing, DeliveryRequest) == 1
        assert await _count(failing, RequestStatusLog) == 1
        assert await _count(other, DeliveryRequest) == 1
    finally:
        await failing.close()
        await other.close()
