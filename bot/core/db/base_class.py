"""
SQLAlchemy declarative base for the Packit bot.

This module defines the single ``Base`` class from which every ORM model in
the project inherits.  The shared ``Base.metadata`` object is used by Alembic
for migration generation and by ``Base.metadata.create_all`` (invoked in
``bot/main.py::_init_db``) to bootstrap the database schema.

Used by:
    - All model modules under ``bot/core/models/`` (e.g. ``user.py``,
      ``delivery_request.py``, ``feedback.py``).
    - ``bot/core/repositories/base_repository.py`` — as the type bound for the
      generic ``BaseRepository[T]``.
    - ``alembic/env.py`` — imported as ``Base`` to access ``Base.metadata``.
    - ``bot/main.py`` — imported as ``Base`` for ``Base.metadata.create_all``.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class for all ORM models.

    All mapped classes inherit from this class so that their table metadata
    is registered in a single ``MetaData`` instance (``Base.metadata``).
    This shared metadata is what Alembic and ``create_all`` use to
    introspect and create tables.

    Calls / Depends on:
        - ``sqlalchemy.orm.DeclarativeBase`` — supplies the default
          ``registry``, ``mapper_registry``, and ``metadata``.

    Called by:
        - ``alembic/env.py`` — accesses ``Base.metadata`` via
          ``target_metadata``.
        - ``bot/core/repositories/base_repository.py`` — uses ``Base`` as the
          type-bound for ``BaseRepository[T]``.
        - All model modules under ``bot/core/models/``.
    """

    pass
