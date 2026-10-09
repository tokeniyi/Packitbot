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
    """Resolve the database URL used by both offline and online mode.

    ``alembic.ini`` intentionally ships with an empty ``sqlalchemy.url`` so
    that no DSN is ever committed to the repository. The real value comes
    from the application settings (``.env`` / ``DATABASE_URL``).

    Returns:
        The SQLAlchemy URL string to run migrations against.

    Raises:
        RuntimeError: If no URL can be resolved from the ini file or the
            application settings.
    """
    url = config.get_main_option("sqlalchemy.url", None)
    if url:
        return url

    try:
        from bot.core.config import get_settings

        url = get_settings().database_url
    except Exception as exc:  # pragma: no cover - depends on local env
            raise RuntimeError(
                "No database URL configured. Set DATABASE_URL in the environment "
                "or .env file, or set sqlalchemy.url in alembic.ini."
            ) from exc

    if not url:
        raise RuntimeError(
            "No database URL configured. Set DATABASE_URL in the environment "
            "or .env file, or set sqlalchemy.url in alembic.ini."
        )
    return url


def run_migrations_offline() -> None:
    """Emit SQL for the migrations without connecting to a database.

    Used by ``alembic upgrade head --sql`` to render a reviewable script.
    """
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
