"""
Database session factory for the Packit bot.

This module initializes the asynchronous SQLAlchemy engine and session factory
used across the project for all database transactions. The engine is created
once at import time using the ``database_url`` from the application settings.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from bot.core.config import get_settings

# ---------------------------------------------------------------------------
# Settings & Engine Initialization
# ---------------------------------------------------------------------------

# Load application settings (reads from environment / .env).
# This is executed once when the module is first imported.
settings = get_settings()

# Create the async SQLAlchemy engine.
#
# - ``settings.database_url``: The async-capable database DSN (e.g.
#   ``postgresql+asyncpg://user:pass@host/db``).
# - ``echo=True``: Log all generated SQL statements to stdout. Useful during
#   development; may be disabled in production.
engine = create_async_engine(settings.database_url, echo=True)

# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------

# ``async_sessionmaker`` creates a factory for ``AsyncSession`` instances.
#
# Key parameters:
# - ``expire_on_commit=False``: Prevent SQLAlchemy from automatically expiring
#   object attributes after a commit. This avoids extra lazy-load queries when
#   accessing relationship attributes immediately after a transaction commits.
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ---------------------------------------------------------------------------
# Cross-References & Usage
# ---------------------------------------------------------------------------
#
# This module is imported by the following files (and many others) to obtain
# an ``AsyncSession`` for database operations:
#
#   - ``bot/admin/handler.py``
#   - ``bot/admin/service.py``
#   - ``bot/driver/handler.py``
#   - ``bot/request/service.py``
#   - ``bot/request/repository.py``
#   - ``bot/driver/service.py``
#   - ``bot/driver/repository.py``
#   - ``bot/student/repository.py``
#
# Dependencies:
#   - ``bot/core/config.py``: Provides ``get_settings()`` which yields the
#     ``database_url`` consumed by ``create_async_engine``.
#   - ``sqlalchemy.ext.asyncio``: Provides the async engine, session maker,
#     and ``AsyncSession`` base class.
