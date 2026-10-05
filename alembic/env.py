import asyncio
from logging.config import fileConfig
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from bot.core.db.base_class import Base
from bot.core.models import user
from bot.core.models import student_profile
from bot.core.models import driver_profile
from bot.core.models import admin_profile
from bot.core.models import authorized_driver
from bot.core.models import delivery_request
from bot.core.models import status_log
from bot.core.models import feedback
from bot.core.models import admin_action_log

target_metadata = Base.metadata


def _resolve_url() -> str:
    url = config.get_main_option("sqlalchemy.url", None)
    if url:
        return url
    try:
        from bot.core.config import get_settings
        url = get_settings().database_url
    except Exception as exc:
        raise RuntimeError(
            "No database URL configured. Set DATABASE_URL/.env or sqlalchemy.url in alembic.ini."
        ) from exc
    if not url:
        raise RuntimeError(
            "No database URL configured. Set DATABASE_URL/.env or sqlalchemy.url in alembic.ini."
        )
    return url


def run_migrations_offline() -> None:
    context.configure(url=_resolve_url(), target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(_resolve_url())
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
