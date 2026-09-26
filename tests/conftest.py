"""Shared pytest fixtures for the Packitbot test suite.

The suite previously had **no** ``conftest.py``, which meant two problems:

1. ``bot.core.config.Settings`` is instantiated at import time and requires
   ``bot_token`` / ``database_url`` / ``redis_url``.  Without environment
   variables set, six test modules failed at *collection* with a pydantic
   ``ValidationError`` — a harness defect, not a product defect.
2. There was no way to test anything that actually touches SQL, so the whole
   persistence layer was untested (backlog item #32).

This module fixes both:

- Required settings are defaulted to harmless placeholders **before** the
  application package is imported, so collection never depends on a developer's
  local ``.env``.
- ``db_session`` provides a genuine ``AsyncSession`` against a temporary
  SQLite database, giving the suite its first real-database tier.

The SQLite override exists because the production dialect is PostgreSQL
(``postgresql+asyncpg``) and CI has no Postgres service.  Tests that rely on
Postgres-specific features must opt in explicitly rather than silently getting
a different behaviour than production.
"""

from __future__ import annotations

import os
from typing import AsyncIterator

# Populate the settings the application requires BEFORE ``bot`` is imported.
# ``.setdefault`` means a real environment (or ``.env``) always wins.
os.environ.setdefault("BOT_TOKEN", "0:test-token")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/packitbot_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ADMIN_IDS", "1")

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from bot.core.db.base_class import Base

# Register every model with ``Base.metadata`` so ``create_all`` builds the
# full schema.  Importing the package is enough; the F401 is deliberate.
import bot.core.models  # noqa: F401


@compiles(BigInteger, "sqlite")
def _biginteger_as_integer_on_sqlite(element, compiler, **kw):
    """Render ``BigInteger`` as ``INTEGER`` when compiling DDL for SQLite.

    Every primary key in this project is a ``BigInteger`` because Telegram IDs
    and user IDs are 64-bit.  SQLite only applies ``AUTOINCREMENT`` to columns
    declared exactly ``INTEGER PRIMARY KEY``, so a ``BIGINT`` primary key is
    never populated and every insert fails with
    ``NOT NULL constraint failed: users.id``.

    Emitting ``INTEGER`` for SQLite DDL restores autoincrement for the test
    tier **without** modifying the production models — the Postgres schema is
    untouched, and the models are not used with a real Postgres engine in
    tests.  This is scoped to SQLite only.
    """
    return "INTEGER"


@pytest_asyncio.fixture
async def async_engine():
    """A fresh in-memory SQLite engine for a single test.

    ``StaticPool`` keeps every connection pointed at the same in-memory
    database, otherwise each pooled connection would see an empty schema.
    """
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncIterator[AsyncSession]:
    """An ``AsyncSession`` bound to a throwaway database.

    Each test gets full control of the transaction: the schema is created for
    the test and dropped after it, so tests cannot leak state into one
    another.  The session is **not** auto-committed — the test decides, which
    makes rollback-based assertions straightforward.
    """
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    session = factory()

    try:
        yield session
    finally:
        await session.close()
