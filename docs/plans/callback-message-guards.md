# Plan: guard callback handlers against unusable `callback.message` (P1 #21)

Status: stage 1 in progress (2026-11-03 run). Owner: automation.

## Problem

Handlers call `callback.message.edit_text(...)` or `callback.message.answer(...)` directly
(about 30 sites in `bot/admin/handler.py`, 9 in `bot/driver/handler.py`, plus the
student and common handlers). aiogram 3.31 types `CallbackQuery.message` as
`Message | InaccessibleMessage | None`.

## Validation against the code (2026-11-03)

Checked by reading the code and by running aiogram 3.31.0 in the project venv:

1. **The backlog's guard target is wrong.** A plain `if callback.message:` guard does
   not protect against the real failure. `bool(InaccessibleMessage(...))` is `True`.
   Telegram sends an `InaccessibleMessage` for a button on a message older than 48 hours.
   That object has `answer` but **no `edit_text`**, so an unguarded `edit_text` raises
   `AttributeError` and the user gets no feedback. The correct check is
   `isinstance(callback.message, Message)`.
2. **`callback.message is None` is rare** (inline-mode callbacks only). The bot has no
   inline-query handling, so the `None` case is mostly theoretical.
3. **The existing per-site guards are inconsistent.** `bot/student/handlers/*` use
   `if callback.message:` (about 30 sites, which does not catch `InaccessibleMessage`).
   `bot/admin/handler.py` and `bot/driver/handler.py` have no guard at all. `bot/common/start.py`
   checks `is None` only.
4. **Middleware placement works for nested routers.** The bot wires middlewares on
   `dp.update` (`bot/main.py` ~line 448). A middleware on `dp.callback_query.outer_middleware`
   runs for callbacks reaching any included router (`start`, `admin`, `help`, `student`,
   `driver`, `fallback`). Stage 1 validates this with a real `Dispatcher` in a test.
5. **Ordering.** The new guard must run after `RBACMiddleware` (update level), so an
   unauthorised user still gets the RBAC denial. It must run before any handler.
6. **No behaviour change for valid callbacks.** Callbacks whose message is a real
   `Message` pass through untouched.

## Options considered

- **A. One router-level outer middleware on callback queries (chosen).** Blocks any callback
  whose `message` is not a `Message`, answers it with an alert, and never calls the handler.
  One change covers every site, including the ones that do not guard today. Cost: a
  handler that legitimately needs no message would also be blocked. A grep found none in
  this bot (every callback comes from a bot message).
- **B. Per-site guards at about 40 call sites.** Bounded per site but repetitive, easy to
  miss on the next handler, and it still does not catch `InaccessibleMessage` unless each
  guard uses `isinstance`.
- **C. Replace `callback.message` with a helper that returns a `Message` or raises.** Cleaner
  typing, but it touches every handler body. Better as a later stage once A is in.

## Stages

**Stage 1 (this run): middleware + tests.**
- New module `bot/core/middlewares/callback_message.py` with
  `CallbackMessageGuardMiddleware(BaseMiddleware)`. For a `CallbackQuery` event whose
  `message` is not a `Message`, it calls `callback.answer(<expired text>, show_alert=True)`
  and returns `None` without calling the handler. Other events pass through.
- Register it in `bot/main.py` with `dp.callback_query.outer_middleware(...)`, after the
  existing `dp.update` middlewares.
- Tests: unit tests for the middleware (Message passes; `InaccessibleMessage` blocked;
  `None` blocked; non-callback events pass). Integration test with a real `Dispatcher`
  and a sub-router: an admin-style handler that calls `edit_text` is **not** invoked for an
  inaccessible message, and **is** invoked for a real message.
- Message text: reuse `ErrorMessages`-style constant, e.g. "This message is too old. Please
  start again from the menu." Added to `bot/core/constants/messages.py`.

**Stage 2 (next runs): remove redundant guards and tighten types.**
- Optional. Replace the `if callback.message:` guards in `bot/student/handlers/*` with a
  narrowed type once stage 1 is merged. Not needed for correctness.
- Decide whether `None` should still be answered silently in `start.py`.

**Stage 3 (later): helper for typed message access (option C)**, only if stage 2 shows
enough churn to justify it.

## Test strategy

- Fail-before/pass-after: the new integration test must fail when the middleware is not
  registered (handler is called and `edit_text` raises `AttributeError` on the fake
  inaccessible message).
- Full suite must stay green (524 passed after the dependency bumps in this run).

## Risks

- A callback with an `InaccessibleMessage` that previously got a silent no-op in
  `start.py` now gets an alert. This is intended.
- The middleware must not swallow errors from other middlewares; it only short-circuits
  on message type.
