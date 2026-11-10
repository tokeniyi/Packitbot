"""Regression guard: admin handlers must receive the middleware session.

``DbSessionMiddleware`` injects ``session`` into every handler. A ``None``
default would let a handler run without a session and silently open its own
connection outside the middleware transaction (backlog #18 follow-up).
"""

import inspect

import bot.admin.handler as admin_handler
from sqlalchemy.ext.asyncio import AsyncSession


def _handlers_with_session():
    found = []
    for name, obj in vars(admin_handler).items():
        if not inspect.iscoroutinefunction(obj) or obj.__module__ != admin_handler.__name__:
            continue
        params = inspect.signature(obj).parameters
        if "session" in params:
            found.append((name, params["session"]))
    return found


def test_every_admin_handler_session_parameter_is_required():
    handlers = _handlers_with_session()
    # 25 handlers take a session as of this run; a drop means one was lost.
    assert len(handlers) >= 25
    for name, param in handlers:
        assert param.default is inspect.Parameter.empty, f"{name} has a session default"


def test_session_annotation_is_async_session():
    for name, param in _handlers_with_session():
        assert param.annotation is AsyncSession, f"{name} session annotation is {param.annotation!r}"


def test_admin_handler_does_not_open_its_own_session():
    assert not hasattr(admin_handler, "async_session")
