import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base

from bot.core.db.base_class import Base as BotBase
from bot.core.exceptions import NotFoundError
from bot.core.repositories.base_repository import BaseRepository


class DummyModel(BotBase):
    __tablename__ = "dummy_model"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    value = Column(String(50), nullable=True)


@pytest.mark.asyncio
async def test_create_and_get():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(BotBase.metadata.create_all)
    session = AsyncSession(engine)
    repo = BaseRepository(session, DummyModel)
    entity = await repo.create(name="test", value="hello")
    assert entity.id is not None
    fetched = await repo.get_by_id(entity.id)
    assert fetched.name == "test"
    assert fetched.value == "hello"
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_update():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(BotBase.metadata.create_all)
    session = AsyncSession(engine)
    repo = BaseRepository(session, DummyModel)
    entity = await repo.create(name="original")
    updated = await repo.update(entity.id, value="updated")
    assert updated.value == "updated"
    assert updated.name == "original"
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_update_not_found():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(BotBase.metadata.create_all)
    session = AsyncSession(engine)
    repo = BaseRepository(session, DummyModel)
    with pytest.raises(NotFoundError):
        await repo.update(999, value="x")
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_delete():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(BotBase.metadata.create_all)
    session = AsyncSession(engine)
    repo = BaseRepository(session, DummyModel)
    entity = await repo.create(name="to_delete")
    result = await repo.delete(entity.id)
    assert result is True
    assert await repo.get_by_id(entity.id) is None
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_delete_not_found():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(BotBase.metadata.create_all)
    session = AsyncSession(engine)
    repo = BaseRepository(session, DummyModel)
    with pytest.raises(NotFoundError):
        await repo.delete(999)
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_list():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(BotBase.metadata.create_all)
    session = AsyncSession(engine)
    repo = BaseRepository(session, DummyModel)
    await repo.create(name="a")
    await repo.create(name="b")
    results = await repo.list()
    assert len(results) == 2
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_repository_never_commits(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(BotBase.metadata.create_all)
    session = AsyncSession(engine)
    repo = BaseRepository(session, DummyModel)
    commits = []
    original_commit = session.commit
    async def fake_commit():
        commits.append("commit")
        return await original_commit()
    monkeypatch.setattr(session, "commit", fake_commit)
    await repo.create(name="no_commit")
    assert len(commits) == 0
    await session.close()
    await engine.dispose()
