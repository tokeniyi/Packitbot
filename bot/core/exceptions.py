

class PackitbotError(Exception):
    """Base exception for all Packitbot errors."""


class ValidationError(PackitbotError):
    """Raised when input validation fails."""


class NotFoundError(PackitbotError):
    """Raised when a requested entity does not exist."""


class PermissionDeniedError(PackitbotError):
    """Raised when an actor lacks permission for an action."""


class InvalidStatusTransitionError(PackitbotError):
    """Raised when a state transition is not allowed."""


class DriverUnavailableError(PackitbotError):
    """Raised when a driver is not available for assignment."""
