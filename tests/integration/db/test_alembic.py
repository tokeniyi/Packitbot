import asyncio
import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def _run_alembic(*command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *command],
        cwd=".",
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "."},
    )


async def test_async_session_select_one():
    from bot.core.config import get_settings
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
    await engine.dispose()


def test_alembic_upgrade_and_downgrade():
    result = _run_alembic("downgrade", "base")
    assert result.returncode == 0, result.stdout + result.stderr

    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, result.stdout + result.stderr

    result = _run_alembic("downgrade", "base")
    assert result.returncode == 0, result.stdout + result.stderr

    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, result.stdout + result.stderr


def test_alembic_revision_autogenerate():
    _run_alembic("downgrade", "base")
    _run_alembic("upgrade", "head")

    result = _run_alembic("revision", "--autogenerate", "-m", "test_rev")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Generating" in result.stdout or "done" in result.stdout
