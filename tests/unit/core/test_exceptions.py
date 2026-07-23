from bot.core.exceptions import (
    DriverUnavailableError,
    InvalidStatusTransitionError,
    NotFoundError,
    PackitbotError,
    PermissionDeniedError,
    ValidationError,
)


def test_packitbot_error_is_base():
    err = PackitbotError("base")
    assert isinstance(err, Exception)
    assert str(err) == "base"


def test_validation_error_subclasses_packitbot():
    err = ValidationError("bad input")
    assert isinstance(err, PackitbotError)


def test_not_found_error_subclasses_packitbot():
    err = NotFoundError("missing")
    assert isinstance(err, PackitbotError)


def test_permission_denied_error_subclasses_packitbot():
    err = PermissionDeniedError("denied")
    assert isinstance(err, PackitbotError)


def test_invalid_status_transition_error_subclasses_packitbot():
    err = InvalidStatusTransitionError("bad transition")
    assert isinstance(err, PackitbotError)
    assert isinstance(err, ValueError) is False


def test_driver_unavailable_error_subclasses_packitbot():
    err = DriverUnavailableError("no drivers")
    assert isinstance(err, PackitbotError)


def test_each_exception_can_be_raised_and_caught_as_packitbot():
    exceptions = [
        ValidationError("v"),
        NotFoundError("n"),
        PermissionDeniedError("p"),
        InvalidStatusTransitionError("i"),
        DriverUnavailableError("d"),
    ]
    for exc in exceptions:
        try:
            raise exc
        except PackitbotError as caught:
            assert caught is exc
