"""Real-database check for P1 #18: student writes run on the injected session.

Uses the SQLite ``db_session`` fixture from ``tests/conftest.py`` (a genuine
``AsyncSession``), so the SQLAlchemy behaviour under test is real rather than
mocked: the savepoint, the flush, and the refresh.
"""

from sqlalchemy import select

from bot.core.models.student_profile import StudentProfile
from bot.core.models.user import User
from bot.student.service import get_profile, is_registered, register_student


async def test_register_then_update_on_the_same_session(db_session):
    profile = await register_student(
        db_session,
        telegram_id=555,
        username="johndoe",
        full_name="John Doe",
        hall="Esther Hall",
        phone="08023456789",
    )
    await db_session.commit()

    assert profile.hall_of_residence == "Esther Hall"
    assert await is_registered(db_session, telegram_id=555) is True

    updated = await register_student(
        db_session,
        telegram_id=555,
        username="johndoe",
        full_name="John Doe",
        hall="Dorcas Hall",
        phone="08023456789",
    )
    await db_session.commit()

    assert updated.hall_of_residence == "Dorcas Hall"
    users = (await db_session.execute(select(User).where(User.telegram_id == 555))).scalars().all()
    assert len(users) == 1
    stored = await get_profile(db_session, user_id=users[0].id)
    assert isinstance(stored, StudentProfile)
    assert stored.hall_of_residence == "Dorcas Hall"
