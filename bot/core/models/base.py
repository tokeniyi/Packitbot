"""
Timestamp mixin for ORM models.

Provides ``created_at`` and ``updated_at`` columns shared by every domain
model so individual models do not need to declare their own audit timestamps.
Both columns are server-managed — the database (``func.now()``) is the source
of truth, which ensures consistency regardless of the application's clock.

Used by:
    - All model modules under ``bot/core/models/`` (``user.py``,
      ``delivery_request.py``, ``feedback.py``, ``driver_profile.py``,
      ``student_profile.py``, ``admin_profile.py``, ``status_log.py``,
      ``admin_action_log.py``).
"""

from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Mixin that adds server-managed ``created_at`` / ``updated_at`` columns.

    ``created_at`` is set automatically on ``INSERT`` via
    ``server_default=func.now()``.  ``updated_at`` is likewise set on
    ``INSERT`` and refreshed on every ``UPDATE`` via
    ``onupdate=func.now()``, so the application never needs to manually
    refresh these values.

    Attributes:
        created_at (Datetime): Timestamp of row insertion, set by the DB.
        updated_at (Datetime): Timestamp of the last row modification,
            set by the DB on insert and refreshed on update.

    Calls / Depends on:
        - ``sqlalchemy.func`` — provides the database-level ``now()``
          function used for default and on-update values.

    Called by:
        - ``bot/core/models/user.py``, ``delivery_request.py``,
          ``feedback.py``, ``driver_profile.py``, ``student_profile.py``,
          ``admin_profile.py``, ``status_log.py``, ``admin_action_log.py``.
    """

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
