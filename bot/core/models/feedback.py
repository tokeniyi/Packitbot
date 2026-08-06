"""
Feedback ORM model for the Packit bot.

Represents a student's rating and optional comment for a completed delivery
request.  Each ``DeliveryRequest`` can have at most one ``Feedback`` record
(enforced by a unique constraint on ``request_id``), creating a one-to-one
relationship between a request and its feedback.

Used by:
    - ``bot/request/service.py`` — ``RequestService.submit_feedback``
      creates feedback records.
    - ``bot/request/repository.py`` — ``FeedbackRepository`` wraps DB access.
    - ``bot/student/handler_requests.py`` — displays existing feedback and
      prompts for new feedback.
    - ``bot/admin/service.py`` — aggregates feedback for system stats
      (total feedback count, average rating).
    - ``alembic/env.py`` — registered for Alembic migrations.
    - ``tests/unit/core/test_models.py`` — model unit tests.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin

if TYPE_CHECKING:
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.user import User


class Feedback(Base, TimestampMixin):
    """Student feedback and rating for a completed delivery request.

    The ``request_id`` column has a unique constraint, enforcing a
    one-to-one relationship: a student can submit at most one feedback
    per delivery request.  Both ``request_id`` and ``student_id`` use
    ``ondelete="CASCADE"`` so that feedback is automatically removed if
    the underlying request or user is deleted.

    Attributes:
        id (int): Primary key.
        request_id (int): FK to ``delivery_requests.id``. Unique — one
            feedback per request. ``CASCADE`` on delete.
        student_id (int): FK to ``users.id`` of the rating student.
            ``CASCADE`` on delete.  ``BigInteger`` because Telegram user
            IDs can exceed the 32-bit integer range.
        rating (int): Numeric rating (e.g. 1–5 scale). Non-nullable.
        comment (str | None): Optional written feedback (max 500 chars).

    Relationships:
        request: The ``DeliveryRequest`` this feedback belongs to
            (one-to-one via ``uselist=False``).
        student: The ``User`` who submitted the feedback (one-to-one
            via ``uselist=False``).

    Calls / Depends on:
        - ``bot.core.db.base_class.Base`` — declarative base.
        - ``bot.core.models.base.TimestampMixin`` — audit timestamps.
        - ``bot.core.constants.enums`` — not directly; rating is a plain
          integer, not an enum column.

    Called by:
        - ``bot/request/service.py`` — ``RequestService.submit_feedback``
          creates and persists ``Feedback`` instances.
        - ``bot/request/repository.py`` — ``FeedbackRepository`` wraps the
          ORM for create and query operations.
        - ``alembic/env.py`` — table registration.
    """

    __tablename__ = "feedbacks"

    # Primary key for the feedback record.
    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign key to the delivery request being rated. CASCADE ensures that if
    # a delivery request is deleted, its feedback is also deleted. The unique
    # constraint enforces a one-to-one relationship between a request and its
    # feedback (a student can only submit one feedback per request).
    request_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_requests.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Foreign key to the student (User) who submitted the feedback. CASCADE
    # ensures that if a user is deleted, their feedback is also deleted.
    # BigInteger is used because Telegram user IDs can exceed 32-bit integer
    # range.
    student_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The numeric rating given by the student (e.g., 1-5 scale). Non-nullable.
    rating: Mapped[int] = mapped_column(Integer, nullable=False)

    # Optional written comment from the student, up to 500 characters.
    comment: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # One-to-one relationship to the DeliveryRequest this feedback is for.
    # back_populates="feedback" links to DeliveryRequest.feedback.
    # uselist=False means this is a scalar relationship (one Feedback per Request).
    request: Mapped[DeliveryRequest] = relationship(
        back_populates="feedback",
        uselist=False,
    )

    # Relationship to the User (student) who submitted this feedback.
    # uselist=False means a single User object, not a list.
    student: Mapped[User] = relationship(uselist=False)
