"""Handler-level regression tests for the student request list and detail views.

Covers two items from docs/AUTOMATION_PROGRESS.md Outstanding list:
- P1 #13: the list is paginated exactly once (the repository slices, the
  handler must not re-slice), so Next/Prev render from the true total.
- P0 #4: the detail handler loads the request through
  ``get_by_id_with_driver`` so the driver chain is eager-loaded.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.core.constants.enums import RequestStatus
from bot.core.constants.limits import PAGE_SIZE
from bot.core.utils.pagination import Page
from bot.student.handlers import requests as requests_handlers


def _req(id: int, status: RequestStatus = RequestStatus.PENDING, student_id: int = 7) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        status=status,
        student_id=student_id,
        hall_of_residence="Hall A",
        driver=None,
        feedback=None,
    )


def _callback(data: str, telegram_id: int = 111) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user = SimpleNamespace(id=telegram_id)
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    return cb


def _button_texts_and_data(markup) -> list[tuple[str, str]]:
    return [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row]


# ---------------------------------------------------------------------------
# P1 #13 - list pagination
# ---------------------------------------------------------------------------

async def test_page_callback_fetches_requested_page_exactly_once():
    """The handler asks the repository for the page once and does not re-slice it."""
    # PAGE_SIZE full pages plus one extra row -> 3 pages. Repository returns the page-2 slice.
    first_id = PAGE_SIZE + 1
    page_ids = list(range(first_id, first_id + PAGE_SIZE))
    total = 2 * PAGE_SIZE + 1
    repo = MagicMock()
    repo.get_history_for_student = AsyncMock(
        return_value=Page(items=[_req(i) for i in page_ids], total=total, page=2, page_size=PAGE_SIZE)
    )
    cb = _callback("my_reqs_page:2")

    with patch.object(requests_handlers, "RequestRepository", return_value=repo), \
         patch.object(requests_handlers, "resolve_user_id", AsyncMock(return_value=7)):
        await requests_handlers.my_requests_page_callback(cb, session=MagicMock())

    repo.get_history_for_student.assert_awaited_once_with(student_id=7, page=2)
    cb.message.edit_text.assert_awaited_once()
    markup = cb.message.edit_text.await_args.kwargs["reply_markup"]
    buttons = _button_texts_and_data(markup)

    # Every item on the page is rendered, none dropped by a second slice.
    detail_ids = [d for _, d in buttons if d.startswith("my_req_detail:")]
    assert detail_ids == [f"my_req_detail:{i}" for i in page_ids]

    # Navigation reflects the true total (3 pages), so both Prev and Next render.
    assert ("Page 2/3", "noop") in buttons
    assert ("⬅ Previous", "my_reqs_page:1") in buttons
    assert ("Next ➡️", "my_reqs_page:3") in buttons


async def test_first_page_of_multi_page_history_shows_next_not_prev():
    repo = MagicMock()
    repo.get_history_for_student = AsyncMock(
        return_value=Page(items=[_req(i) for i in range(1, PAGE_SIZE + 1)], total=PAGE_SIZE + 2, page=1, page_size=PAGE_SIZE)
    )
    cb = _callback("my_reqs_list")

    with patch.object(requests_handlers, "RequestRepository", return_value=repo), \
         patch.object(requests_handlers, "resolve_user_id", AsyncMock(return_value=7)):
        await requests_handlers.my_requests_page_callback(cb, session=MagicMock())

    repo.get_history_for_student.assert_awaited_once_with(student_id=7, page=1)
    buttons = _button_texts_and_data(cb.message.edit_text.await_args.kwargs["reply_markup"])
    assert ("Page 1/2", "noop") in buttons
    assert ("Next ➡️", "my_reqs_page:2") in buttons
    assert not any(text == "⬅ Previous" for text, _ in buttons)


async def test_bad_page_payload_falls_back_to_page_one():
    repo = MagicMock()
    repo.get_history_for_student = AsyncMock(
        return_value=Page(items=[_req(1)], total=1, page=1, page_size=PAGE_SIZE)
    )
    cb = _callback("my_reqs_page:not-a-number")

    with patch.object(requests_handlers, "RequestRepository", return_value=repo), \
         patch.object(requests_handlers, "resolve_user_id", AsyncMock(return_value=7)):
        await requests_handlers.my_requests_page_callback(cb, session=MagicMock())

    repo.get_history_for_student.assert_awaited_once_with(student_id=7, page=1)


# ---------------------------------------------------------------------------
# P0 #4 - detail handler uses the eager-loading repository method
# ---------------------------------------------------------------------------

async def test_detail_handler_uses_eager_loading_repository_method():
    repo = MagicMock()
    repo.get_by_id_with_driver = AsyncMock(return_value=_req(42, student_id=7))
    cb = _callback("my_req_detail:42")

    with patch.object(requests_handlers, "RequestRepository", return_value=repo), \
         patch.object(requests_handlers, "resolve_user_id", AsyncMock(return_value=7)), \
         patch.object(requests_handlers, "_format_request_detail", return_value="DETAIL"), \
         patch.object(requests_handlers, "request_detail_keyboard", return_value="KB"):
        await requests_handlers.show_request_detail(cb, session=MagicMock())

    repo.get_by_id_with_driver.assert_awaited_once_with(42)
    cb.message.edit_text.assert_awaited_once_with("DETAIL", parse_mode="HTML", reply_markup="KB")


async def test_detail_handler_refuses_request_owned_by_another_student():
    repo = MagicMock()
    repo.get_by_id_with_driver = AsyncMock(return_value=_req(42, student_id=999))
    cb = _callback("my_req_detail:42")

    with patch.object(requests_handlers, "RequestRepository", return_value=repo), \
         patch.object(requests_handlers, "resolve_user_id", AsyncMock(return_value=7)):
        await requests_handlers.show_request_detail(cb, session=MagicMock())

    cb.message.edit_text.assert_not_awaited()
    cb.message.answer.assert_awaited_once()
