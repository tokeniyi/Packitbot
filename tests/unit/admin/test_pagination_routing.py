"""Regression tests for dead admin pagination buttons (backlog P1 #12).

``pending_drivers_list_keyboard`` and ``drivers_list_keyboard`` rendered their
Prev/Next controls with the ``PaginationNav`` factory, which packs to
``nav:<page>:<direction>``.  No handler anywhere in the project matched that
prefix: the admin router only registers ``admin_req_page:`` and
``admin_drv_page:``.  Every click therefore fell through to
``bot/common/fallback.py::catch_all_callback`` and answered "Invalid input", so
the driver lists were navigable on exactly one page.

The invariant enforced here is structural, not textual: **every callback data
string an admin keyboard can emit must be claimed by at least one handler on
``admin_router``.**  Asserting the literal ``admin_drv_page:`` prefix instead
would just re-encode the fix and would not catch a future keyboard pointing at
another unrouted prefix.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import CallbackQuery, User

from bot.admin.keyboards import (
    drivers_list_keyboard,
    pending_drivers_list_keyboard,
    pending_requests_list_keyboard,
)
from bot.core.constants.enums import DriverStatus


def _callback_data(keyboard) -> list[str]:
    """Flatten a markup's buttons into the list of callback strings it emits."""
    return [
        btn.callback_data
        for row in keyboard.inline_keyboard
        for btn in row
        if btn.callback_data
    ]


async def _routed_handler_names(cq: CallbackQuery) -> set[str]:
    """Return names of handlers anywhere in the dispatcher that claim ``cq``.

    ``HandlerObject.check`` is unusable for this: for awaitable filters it
    awaits ``FilterObject.call``, whose return value is the raw (truthy)
    coroutine result rather than a boolean, so every handler "matches"
    everything.  Evaluating each ``FilterObject.call`` and requiring truthiness
    resolves filters the way aiogram's observer does.

    The whole dispatcher is scanned, not just ``admin_router``: an admin
    keyboard's Home button is served by ``start_router``, so restricting the
    scan to the admin router would report a false positive on ``home``.
    ``fallback_router`` is excluded because it matches everything by design —
    including it would make the invariant vacuous.
    """
    from bot.admin.handler import admin_router
    from bot.common.help import help_router
    from bot.common.start import start_router
    from bot.driver.handler import driver_router
    from bot.student.handlers import student_router

    claimed = set()
    for router in (start_router, admin_router, help_router, student_router, driver_router):
        for handler in router.callback_query.handlers:
            if not handler.filters:
                claimed.add(handler.callback.__name__)
                continue
            if all([await f.call(cq) for f in handler.filters]):
                claimed.add(handler.callback.__name__)
    return claimed


def _probe(data: str) -> CallbackQuery:
    return CallbackQuery(
        id="probe",
        from_user=User(id=1, is_bot=False, first_name="Probe"),
        chat_instance="probe",
        data=data,
    )


def _driver_item(driver_id: int):
    return MagicMock(
        driver_id=driver_id,
        full_name=f"Driver {driver_id}",
        vehicle_type="CAR",
        rating_avg=4.5,
        status=DriverStatus.APPROVED,
    )


# ---------------------------------------------------------------------------
# The invariant: no admin keyboard may emit an unrouted callback.
# ---------------------------------------------------------------------------

KEYBOARD_CASES = [
    pytest.param(
        "pending_drivers_list_keyboard",
        lambda: pending_drivers_list_keyboard(
            [_driver_item(1)], page=2, total_pages=5
        ),
        id="pending_drivers_list_keyboard",
    ),
    pytest.param(
        "drivers_list_keyboard",
        lambda: drivers_list_keyboard(
            [_driver_item(1)], page=2, total_pages=5
        ),
        id="drivers_list_keyboard",
    ),
    pytest.param(
        "pending_requests_list_keyboard",
        lambda: pending_requests_list_keyboard(
            [MagicMock(id=1, hall_of_residence="H1", dropoff_address="Somewhere")],
            page=2,
            total_pages=5,
        ),
        id="pending_requests_list_keyboard",
    ),
]


@pytest.mark.parametrize(
    "kb_name, build", KEYBOARD_CASES, ids=[c.values[0] for c in KEYBOARD_CASES]
)
@pytest.mark.asyncio
async def test_every_keyboard_callback_is_routed(kb_name, build):
    """Every callback an admin keyboard emits must reach a real handler.

    Before the fix the two driver keyboards emitted ``nav:<n>:prev`` /
    ``nav:<n>:next``, which nothing routed, so the assertion fails on exactly
    those two strings.
    """
    unrouted = []
    for data in _callback_data(build()):
        if not await _routed_handler_names(_probe(data)):
            unrouted.append(data)

    assert not unrouted, (
        f"{kb_name} emits callback(s) that no handler in the dispatcher "
        f"matches: {unrouted}. They fall through to catch_all_callback and "
        f"answer 'Invalid input'."
    )


# ---------------------------------------------------------------------------
# Targeted assertions: the two broken keyboards now use real pagination prefixes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("build", "prefix", "handler"),
    [
        (pending_drivers_list_keyboard, "admin_verify_page:", "handle_back_to_pending_list"),
        (drivers_list_keyboard, "admin_drv_page:", "handle_drivers_pagination"),
    ],
)
async def test_driver_pagination_stays_in_its_queue(build, prefix, handler):
    keyboard = build([_driver_item(1)], page=2, total_pages=5)
    nav = [value for value in _callback_data(keyboard) if value.startswith(prefix)]
    assert nav == [f"{prefix}1", f"{prefix}3"]
    for payload in nav:
        assert handler in await _routed_handler_names(_probe(payload))


@pytest.mark.parametrize(
    "build",
    [
        lambda: pending_drivers_list_keyboard([_driver_item(1)], page=2, total_pages=5),
        lambda: drivers_list_keyboard([_driver_item(1)], page=2, total_pages=5),
    ],
    ids=["pending_drivers_list_keyboard", "drivers_list_keyboard"],
)
def test_driver_pagination_no_longer_emits_bare_nav_prefix(build):
    """The unrouted ``nav:`` payload must be gone from both driver keyboards."""
    data = _callback_data(build())
    assert not [d for d in data if d.startswith("nav:")]


@pytest.mark.asyncio
async def test_previous_and_next_callbacks_each_reach_a_handler():
    """Both directions must route, not just the one that happens to be checked.

    Guards against a fix that only rewires the Next button.
    """
    kb = drivers_list_keyboard([_driver_item(1)], page=3, total_pages=6)
    prev = [d for d in _callback_data(kb) if d.endswith(":2")]
    nxt = [d for d in _callback_data(kb) if d.endswith(":4")]

    assert prev == ["admin_drv_page:2"]
    assert nxt == ["admin_drv_page:4"]
    assert await _routed_handler_names(_probe("admin_drv_page:2"))
    assert await _routed_handler_names(_probe("admin_drv_page:4"))


@pytest.mark.parametrize(
    "build",
    [
        lambda: pending_drivers_list_keyboard([_driver_item(1)], page=1, total_pages=1),
        lambda: drivers_list_keyboard([_driver_item(1)], page=1, total_pages=1),
    ],
    ids=["pending_drivers_list_keyboard", "drivers_list_keyboard"],
)
def test_single_page_still_renders_no_navigation(build):
    """The fix must not introduce navigation controls on a single page."""
    data = _callback_data(build())
    assert not [d for d in data if "page:" in d]


# ---------------------------------------------------------------------------
# Prefix collisions between CallbackData factories. The unused ``NavHome``
# factory (which shared the ``nav`` prefix with ``PaginationNav``) was removed
# in the P3 #35 dead-class sweep; this guard stops a new factory from reusing
# an existing prefix.
# ---------------------------------------------------------------------------


def test_callback_data_prefixes_are_unique():
    """Every CallbackData factory in the module must have its own prefix.

    Two factories sharing a prefix make ``unpack`` ambiguous (backlog P1 #12).
    """
    from bot.core.utils import callback_data as cb_module

    factories = [
        obj
        for obj in vars(cb_module).values()
        if isinstance(obj, type)
        and hasattr(obj, "__prefix__")
        and obj.__module__ == cb_module.__name__
    ]
    prefixes = [f.__prefix__ for f in factories]
    assert len(prefixes) == len(set(prefixes)), (
        f"duplicate CallbackData prefixes: {prefixes}"
    )


def test_pagination_nav_prefix_is_nav():
    """PaginationNav keeps its prefix — it is the audited, routed factory."""
    from bot.core.utils.callback_data import PaginationNav

    assert PaginationNav.__prefix__ == "nav"


# ---------------------------------------------------------------------------
# Int() without try/except on callback payload (backlog P1 #22, same handlers)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_page_number_does_not_raise_value_error():
    """A tampered ``admin_drv_page:abc`` must be answered, not crash the handler.

    The handler parses the page with a bare ``int()``; an unparsable value
    raises ``ValueError`` out of the handler and the user gets nothing at all.
    This test pins the required behaviour so the guard cannot be lost again.
    """
    from bot.admin.handler import admin_router
    from bot.core.constants.enums import UserRole
    from bot.core.models.user import User

    handler = next(
        h.callback
        for h in admin_router.callback_query.handlers
        if h.callback.__name__ == "handle_drivers_pagination"
    )

    callback = AsyncMock()
    callback.data = "admin_drv_page:abc"
    callback.message = AsyncMock()

    admin = User(role=UserRole.ADMIN)

    with patch(
        "bot.admin.handler.get_all_drivers", new=AsyncMock(return_value=([], 1))
    ) as svc:
        assert await handler(callback, user=admin, session=AsyncMock()) is None

    callback.answer.assert_awaited()
    svc.assert_not_awaited()
