"""
Application-level exception hierarchy for the Packit bot.

Every custom exception inherits from :class:`PackitbotError`, enabling
callers to catch the full hierarchy with a single ``except`` clause while
still allowing fine-grained handling of specific error conditions.

Used by:
    - ``bot/core/repositories/base_repository.py`` — raises ``NotFoundError``.
    - ``bot/request/service.py`` — raises ``DriverUnavailableError``,
      ``InvalidStatusTransitionError``, ``NotFoundError``,
      ``PermissionDeniedError``, ``ValidationError``, ``PackitbotError``.
    - ``bot/admin/service.py`` — raises ``NotFoundError``, ``ValidationError``,
      ``PackitbotError``.
    - ``bot/driver/service.py`` — raises ``DuplicateResourceError``,
      ``PackitbotError``, ``ValidationError``.
    - ``bot/student/service.py`` — raises ``ValidationError``.
    - ``bot/core/middlewares/db_session.py`` — catches ``Exception`` (which
      includes ``PackitbotError`` subclasses).
    - ``bot/common/start.py`` — catches ``PackitbotError``.
    - ``bot/student/handler_requests.py``, ``bot/student/handler.py``,
      ``bot/driver/handler.py`` — catch specific subclasses in handlers.
    - Various tests throughout the project (e.g.
      ``tests/unit/core/test_exceptions.py``).
"""


class PackitbotError(Exception):
    """Base exception for all Packitbot errors.

    Every domain-specific exception in the project inherits from this class,
    allowing callers to broadly catch application errors with a single
    ``except PackitbotError`` clause.

    Raises:
        PackitbotError: Raised directly or via a subclass when a domain
            rule is violated (e.g. validation failure, not found,
            permission denied).
    """


class ValidationError(PackitbotError):
    """Raised when input validation fails.

    Typically raised by service-layer methods or business-rule predicates
    when user-supplied data (e.g. rating out of range, missing required
    field, invalid enum value) does not meet the expected constraints.

    Raises:
        ValidationError: When the provided input is syntactically or
            semantically invalid (e.g. rating not in 1–5, non-admin
            attempting an admin action).
    """


class NotFoundError(PackitbotError):
    """Raised when a requested entity does not exist.

    Usually raised after a database query returns ``None`` for an
    expected record (e.g. a request ID that no longer exists, or a
    user that has been deleted).

    Raises:
        NotFoundError: When a lookup by primary key or unique attribute
            yields no matching row.
    """


class PermissionDeniedError(PackitbotError):
    """Raised when an actor lacks permission for an action.

    Raised in service-layer guards and business-rule predicates when the
    authenticated user does not satisfy the role or ownership requirements
    for the requested operation (e.g. a student editing a request they do
    not own).

    Raises:
        PermissionDeniedError: When the current actor is unauthorized for
            the target resource or action.
    """


class InvalidStatusTransitionError(PackitbotError):
    """Raised when a state transition is not allowed.

    Raised by consumers of :func:`bot.request.state_machine.can_transition`
    — notably ``RequestService.transition_status`` and
    ``RequestService.assign_driver`` — when a requested
    ``RequestStatus`` change violates the finite-state-machine rules
    (e.g. moving directly from ``PENDING`` to ``DELIVERED``).

    Raises:
        InvalidStatusTransitionError: When the transition from the current
            status to the target status is not permitted by the state
            machine.
    """


class DriverUnavailableError(PackitbotError):
    """Raised when a driver is not available for assignment.

    Raised by ``RequestService.assign_driver`` when the target driver is
    either not yet approved by an admin or is not currently
    ``AVAILABLE`` (e.g. already ``BUSY`` or ``OFFLINE``).

    Raises:
        DriverUnavailableError: When a driver cannot be assigned because
            their approval status or availability precludes it.
    """


class DuplicateResourceError(PackitbotError):
    """Raised when a resource already exists.

    Typically raised as a translation of a database ``IntegrityError``
    caused by a unique-constraint violation (e.g. a driver attempting to
    register with a plate number that is already in use).

    Raises:
        DuplicateResourceError: When a unique constraint prevents
            inserting a duplicate record.
    """
