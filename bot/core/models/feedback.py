from __future__ import annotations
from typing import TYPE_CHECKING

# =============================================================================
# Cross-References (imports this file depends on):
#   - bot.core.db.base_class.Base: The declarative base class for all SQLAlchemy
#     ORM models in this project. Feedback inherits from Base to become a
#     mapped class tied to the "feedbacks" database table.
#   - bot.core.models.base.TimestampMixin: Provides created_at and updated_at
#     timestamp columns automatically managed by SQLAlchemy. Feedback inherits
#     from this mixin to track when feedback records are created and last
#     updated.
#   - bot.core.models.delivery_request.DeliveryRequest (TYPE_CHECKING): The
#     delivery request model. Used for type hints only; the relationship
#     "request" links a Feedback to its parent DeliveryRequest.
#   - bot.core.models.user.User (TYPE_CHECKING): The user model. Used for type
#     hints only; the relationship "student" links a Feedback to the User who
#     submitted it.
# =============================================================================
from sqlalchemy import ForeignKey, Integer, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.core.db.base_class import Base
from bot.core.models.base import TimestampMixin

if TYPE_CHECKING:
    from bot.core.models.delivery_request import DeliveryRequest
    from bot.core.models.user import User


# =============================================================================
# Code Logic:
#   The Feedback SQLAlchemy ORM model represents student ratings and comments
#   for completed delivery requests. It is stored in the "feedbacks" table.
#
#   Step-by-step explanation of the model structure:
#   1. The class inherits from Base (the declarative base) and TimestampMixin
#      (which adds created_at and updated_at columns automatically).
#   2. __tablename__ = "feedbacks" maps the class to the feedbacks table.
#   3. id: Primary key column, auto-incremented integer.
#   4. request_id: A foreign key referencing delivery_requests.id with CASCADE
#      delete behavior. It is unique (one feedback per request) and non-nullable.
#      An index is created on this column for fast lookups by request.
#   5. student_id: A BigInteger foreign key referencing users.id with CASCADE
#      delete behavior. It is non-nullable and indexed for fast lookups by
#      student. BigInteger is used because Telegram user IDs can exceed 32-bit
#      integer range.
#   6. rating: An integer column storing the student's rating (e.g., 1-5).
#      Non-nullable.
#   7. comment: An optional string column (max 500 chars) for the student's
#      written feedback. Nullable.
#   8. request: A one-to-one relationship to DeliveryRequest, with
#      back_populates="feedback" so that DeliveryRequest.feedback can access
#      this Feedback object. uselist=False indicates a single related object,
#      not a list.
#   9. student: A relationship to User (the student who submitted the feedback).
#      uselist=False indicates a single related User object.
# =============================================================================
class Feedback(Base, TimestampMixin):
    """Student feedback and rating for a completed delivery request."""

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
