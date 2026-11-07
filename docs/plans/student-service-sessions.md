# Plan: student service uses the injected session (P1 #18)

Status: planned and validated 2026-11-07. Implemented in the same run (single stage).

## Problem

`bot/student/service.py` functions take an optional `session`. When it is `None`
(or, for `get_profile` and `is_registered`, always) they open their own
`async_session()` and commit it independently. Inside a bot update, the
`DbSessionMiddleware` (`bot/core/middlewares/db_session.py`) has already opened a
per-update session and commits it at the end. A student write made through a
second connection therefore bypasses that transaction: it is not rolled back if
a later step of the same update fails, and it competes with the middleware
transaction for row locks. Driver and admin services take the session from the
middleware, so the student module is the outlier.

## Sites (verified by reading `bot/student/service.py`)

| Function | Fallback that opens its own session |
|---|---|
| `register_student` | `if session is not None` ... else `async with async_session()` |
| `get_profile` | always opens a session |
| `is_registered` | always opens a session |
| `resolve_user_id` | `if session` ... else `async with async_session()` |
| `get_student_profile_with_stats` | `if session` ... else `async with async_session()` |
| `update_student_hall` | `if session` ... else `async with async_session()` |
| `update_student_phone` | `if session` ... else `async with async_session()` |

## Callers (verified by grep over `bot/` and `tests/`)

- `register_student`: `bot/student/handlers/registration.py::submit_registration`
  (called with no session, so it is the one production caller that relied on
  the fallback). Re-exported by `bot/student/handler.py` (no call there).
- `resolve_user_id`: about 13 calls in `bot/student/handlers/requests.py` and
  `bot/student/handlers/feedback.py`; all already pass `session` positionally.
  Tests mock it with `AsyncMock`, so order does not affect them.
- `get_student_profile_with_stats`, `update_student_hall`, `update_student_phone`:
  `bot/student/handlers/profile.py`; all already pass `session=session`.
- `get_profile`, `is_registered`: no production callers; tests only.

## Decisions

1. Every function takes `session: AsyncSession` as its **first, required**
   parameter, as the backlog asks ("like `driver/` and `admin/`"). The fallback
   branches and the `async_session` import are removed from the service.
2. `submit_registration` declares `session: AsyncSession` so aiogram injects the
   middleware session (the same mechanism the driver and admin handlers use).
   `process_submit_registration` already does this.
3. `register_student` wraps its insert `flush()` in `session.begin_nested()`
   (SAVEPOINT, the pattern used for #14). Without it, a duplicate-Telegram-ID
   `IntegrityError` leaves the middleware session in a failed state. The handler
   catches the error and replies, so the middleware's commit would then raise.
   With the SAVEPOINT only the insert is rolled back, and the middleware commit
   is clean.
4. The `session` argument is not optional anywhere, so a missed caller fails
   loudly with `TypeError`, not silently with a second connection.

## Validation against the code

- Checked that aiogram passes middleware `data["session"]` to any handler whose
  signature names `session`: existing handlers in `profile.py`, `requests.py`
  and `driver/handler.py` rely on this.
- Checked that `bot/student/handler.py` is a re-export facade only; no logic
  changes there.
- Checked that no test calls `register_student` through the fallback except the
  two in `tests/unit/student/test_handler.py` and the two in
  `tests/unit/student/test_student_phase9.py`, which already pass `session=`.
- Checked that tests that patch `bot.student.service.async_session` (`is_registered`,
  `get_profile`) need rewriting to pass a session directly. Listed in the test plan.
- Checked the `begin_nested` change against the existing duplicate test: the
  mock `session.begin_nested` must be a `MagicMock` (async context manager), not
  the `AsyncMock` default, so the test is updated to set it.

## Test plan

- Update all callers and tests to the new signatures.
- New: `register_student` must not open `async_session` (patch it to raise, assert no call).
- New: duplicate path asserts the SAVEPOINT context is entered and exited with the exception.
- Full suite must stay green (baseline 557 after stage 2c tests).

## Outstanding

None for #18 once this run's change lands.
