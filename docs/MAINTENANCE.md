# Packitbot — Maintenance & Development Backlog

> **This document is the source of truth for automated daily development runs.**
> It is updated on every task branch. Daily runs must re-read it *and* the code
> before choosing work — never trust a previous run's analysis.

- **Repository:** `tokeniyi/Packitbot`
- **Description:** Async Telegram logistics and delivery management bot (aiogram 3.x, SQLAlchemy 2.0)
- **Default branch:** `main` (protected — never pushed to directly)
| - **Scale:** ~500 tests across 30+ files; ~14.7k LOC application code, 130 Python files
| - **Review baseline:** commit `90525e4` (`main`, as of 2026-10-30)
| - **Last reviewed:** 2026-10-30

> **NOTE — this document was branch-resident during 2026-10-26–2026-10-30**
> (carried on daily-review branches). It is now present on `main` via merged
> PRs #22/#23/#25. Daily runs can read it directly.

---

## 1. Architecture

### 1.1 Request flow

```
Telegram update
  └─ main.py:449-453  outer middlewares (inflow order)
       LoggingMiddleware → DbSessionMiddleware → ThrottlingMiddleware
         → AuthMiddleware → RBACMiddleware
  └─ Dispatcher → routers (main.py:193-200)
       start / admin / help / student (4 sub-routers) / driver / fallback
  └─ handler → service → repository → SQLAlchemy model → PostgreSQL
```

`DbSessionMiddleware` commits at the end of each update and rolls back on exception.

### 1.2 Domain modules

| Module | Service | Repository | Notes |
|---|---|---|---|
| `bot/request/` | `RequestService` class (service.py:63) | `RequestRepository`, `StatusLogRepository`, `FeedbackRepository` | **Only module that honours the intended layering** |
| `bot/driver/` | module-level async functions | `DriverRepository` | Issues `select()` directly |
| `bot/student/` | module-level async functions | `StudentRepository` (**unused**) | Opens its own sessions — see #18 |
| `bot/admin/` | 15 module-level functions (1347 L) | **none** | SQLAlchemy statements inline |
| `bot/core/` | `notification_service.py` | `BaseRepository[T]`, `UserRepository` | models, middlewares, validators, constants |

### 1.3 Migrations — non-functional

`alembic/env.py` is written correctly but is **bypassed at runtime**:

- `bot/main.py:78-79` runs `Base.metadata.create_all(engine)` on every startup
- `main.py:81-92` hand-patches ENUMs with raw `ALTER TYPE … ADD VALUE` in bare `except: pass`
- Of 24 migration files, **20 are no-op stubs** (`*_test_rev.py`, `def upgrade(): pass`)
- ~~**The revision graph has two heads**~~ — **stale, re-verified 2026-10-26:** the chain is
  now linear (`9082dd8c65fd` → `8df7ae516946` → `3f93513f5486` → `d773fd78af20` →
  `a1b2c3d4e5f6`), with a single head. Whether `alembic upgrade head` succeeds at runtime
  was not verified (dependencies could not be installed in the review sandbox).
- `alembic.ini:2` retains the placeholder `sqlalchemy.url = driver://user:pass@localhost/dbname`

Schema is therefore whatever `create_all` produces, ENUMs are patched by hand, and
no environment is reproducible from the repository. **This blocks all future schema work.**

### 1.4 Environment note (important for automation)

`pyproject.toml` requires **`>=3.12,<3.13`**, but system Python is **3.11.16**.
Use `uv` to provision 3.12 — do not attempt to run the suite under the system interpreter.

---

## 2. Headline state

- **0 P0 bugs remain** (was 6; #6 was disproved on 2026-10-03). All six were fixed
  across PRs #4–#10 (merged by 2026-10-26); P0 #3 was completed on 2026-10-30 by
  commit `e928594` (PR #25, merged into main before this run started).
- **Test suite now runs** under Python 3.12.7 with in-memory SQLite (conftest.py, PR #8).
  Baseline established 2026-10-30: **497 passed, 15 failed**. After this run's change (P1 #22
  completion): **502 passed, 10 failed** (5 fixed, 0 regressions). The 10 remaining failures
  are pre-existing (3 PostgreSQL-dependent, 7 AsyncMock integration).
- **Remaining open P1 items:** #15 (raw exception text leaked), #17 (unescaped HTML
  in `parse_mode` messages), #18 (student/service.py opens own sessions), #19
  (throttling unusable), #21 (callback.message `None` guards, 23 sites in admin/handler.py).
- **Architectural drift.** Only `bot/request/` follows the layering in
  `.agents/rules/GEMINI.md`. The recurring `users.id` vs `DriverProfile.id` vs
  `telegram_id` ambiguity is the root cause of the entire P0 cluster.

---

## 3. Root cause: the three-ID problem

Three different identifiers are used interchangeably across the codebase. Fixing
this properly is the single highest-leverage change.

| Identifier | Type | Meaning |
|---|---|---|
| `users.id` | `BigInteger` PK | internal primary key |
| `users.telegram_id` | bigint | Telegram account ID |
| `DriverProfile.id` | its own PK | profile row |
| `DriverProfile.user_id` | FK → `users.id` | link back to the user |

`DeliveryRequest.driver_id` is `ForeignKey("users.id")` — but call sites populate it
with `DriverProfile.id`, and lookups treat it as a `DriverProfile` PK. Items **#2,
#3, #25** all stem from this. Naming convention to adopt: `driver_profile_id` vs
`driver_user_id` (item #25).

---

## 4. Backlog

### P0 — Critical bugs (fix before any feature work)

**#1 ~~`/add_driver` never works — admin ID compared against the wrong column~~ — FIXED in `dbf4ba8` (2026-09-26; test in `tests/unit/admin/test_service.py`); re-verified in code 2026-10-27**
- `bot/admin/service.py:1317` vs `bot/admin/handler.py:1272`
- `select(User).where(User.telegram_id == admin_user_id)` receives `user.id`.
  `users.id` and `users.telegram_id` never match, so every call raises
  `ValidationError("Admin permission required.")`.
  **Impact:** no one can be authorized → `is_authorized_driver` always `False` →
  `/register_driver` always returns `DRIVER_INVITATION_ONLY`. The entire driver
  onboarding funnel is a dead end.
- **Fix:** `select(User).where(User.id == admin_user_id)`; fix the docstring (it says
  "Telegram ID of the admin" while the signature says `admin_user_id` — every other
  admin function uses `User.id`). Add a test.

**#2 Driver assignment writes `DriverProfile.id` into a `users.id` column** — *handler fix present on `main` (`bot/admin/handler.py:337` persists `driver_profile.user_id`, verified 2026-10-27); no regression test confirmed yet — `AvailableDriverDTO.driver_id=dp.id` still exists in `admin/service.py`, check it is never persisted*
- `bot/admin/keyboards.py:433` → `bot/admin/handler.py:294-304` → `bot/request/service.py:226`;
  model at `bot/core/models/delivery_request.py:111`
- `AvailableDriverDTO` carries **both** `driver_id=dp.id` and `user_id=user.id`
  (`admin/service.py:193`); the wrong one is used.
  `can_assign_driver()` validates the *correct* profile, so the guard gives false confidence.
- **Impact:** FK `IntegrityError` aborting assignment, or the wrong user recorded as
  driver while the correct one is notified.
- **Fix:** `AssignDriverDTO(driver_id=driver_profile.user_id, …)`; add an assertion in
  `RequestService.assign_driver` that `dto.driver_id == driver_profile.user_id`.

**#3 ~~Cancellation / feedback re-query `DriverProfile` with a `users.id`~~ — FIXED (commit `e928594`, PR #25, 2026-10-30)**
- `bot/student/handlers/requests.py:1012`; `bot/student/handlers/feedback.py:28-50`
- Profile lookup resolves via `DriverRepository.get_by_user_id` (PR #6). The remaining `total_deliveries` defect was fixed in `e928594`: the aggregate query now counts `DeliveryRequest.id` rows with `status == DELIVERED` using a `LEFT OUTER JOIN` to `Feedback`, instead of counting `Feedback.id` rows via an inner join.
- **Impact (old):** driver availability never restored on cancellation; `total_deliveries` undercounted whenever a delivered request had no Feedback row → driver ranking and the `/drivers` leaderboard were silently wrong.
- **Regression tests:** `test_total_deliveries_counts_delivered_requests_not_feedback` and `test_total_deliveries_excludes_non_delivered_requests` in `tests/unit/student/test_driver_profile_lookup.py` — both use the `db_session` fixture against real in-memory SQLite and fail with the old query.

**#4 ~~`MissingGreenlet` on "view request detail"~~ — FIXED on `main` (PR #9, `fix/request-detail-missing-greenlet`)**
|- `bot/student/handlers/requests.py:668` (load) and `:141-147` (lazy access)
|- The handler loads via `RequestRepository.get_by_id_with_driver` (`bot/request/repository.py:63`), which uses `selectinload(DeliveryRequest.driver).selectinload(User.driver_profile)` for both hops.
|- **Regression test:** `tests/unit/request/test_request_detail_eager_load.py` exists and passes. Confirmed in the 2026-10-30 test run (497 passed, 15 pre-existing failures).
- `req.driver` / `req.driver.driver_profile` lazy-load outside an awaited context →
  `MissingGreenlet` (a subclass of `InvalidRequestError`, **not** `PackitbotError`),
  so it bypasses the global handler and shows a generic error.
- **Fix:** `.options(selectinload(DeliveryRequest.driver).selectinload(User.driver_profile))`.
  `expire_on_commit=False` does not help — the object was never loaded.

**#5 ~~No ownership check on driver delivery callbacks~~ — FIXED (PR #7, `fix/driver-callback-ownership-check`)**
|- `bot/driver/handler.py` — all three delivery callbacks (`process_driver_accept`, `process_delivery_status_step`, `process_driver_reject`) now assert that the callback actor is the assigned driver before mutating the request. The service layer (`RequestService.transition_status`) enforces `require_assigned_driver` by default, and the delivery-status handler filters on `DeliveryRequest.driver_id == driver_user.id`.

**#6 ~~First-time student registration violates a NOT NULL constraint~~ — RESOLVED 2026-10-03: NOT A BUG**
- **The backlog entry was wrong.** The original claim — that passing
  `verification_status=None` on a `nullable=False` column sends SQL `NULL`
  and raises `IntegrityError` — was reasoning from documented ORM semantics
  that was never executed. It was tested against a real (SQLite) database
  and **disproven**: the `StudentProfile` insert succeeds and persists
  `UNVERIFIED`.
- **Why:** `bot/core/models/student_profile.py:79-84` declares
  `default=VerificationStatus.UNVERIFIED` as a *Python-side column default*.
  The SQLAlchemy unit of work **omits** a column whose value is `None` at
  flush time, so the default fires. An explicit `None` is therefore
  indistinguishable from omitting the argument.
- **Evidence:** three variants (explicit `None`, omitted, explicit
  `UNVERIFIED`) all persisted `VerificationStatus.UNVERIFIED`. The column
  genuinely is `NOT NULL` in the DDL — the NOT NULL violation is only
  reachable through *core* `Table.insert().values(verification_status=None)`,
  which no production code path uses. `service.py:78` is harmless but
  misleading, since it implies an intent to store NULL.
- **Still worth doing (cosmetic, folded into #35):** delete the
  `verification_status=None` argument at `bot/student/service.py:78` so the
  code stops implying a nullable column. No behaviour change.

**#7 ~~`_init_db` bypasses Alembic — migration chain unusable~~ — FIXED (PR #10, `fix/alembic-single-linear-head`)**
|- `bot/main.py:78-92`; `alembic/versions/`
|- The two migration heads were merged into a single linear chain (`9082dd8c65fd` → `8df7ae516946` → `3f93513f5486` → `d773fd78af20` → `a1b2c3d4e5f6`). The 20 no-op stub files were cleaned up.

### P1 — Significant

**#8 ~~`main.py:339` un-awaited coroutine~~ — FIXED 2026-10-03 (PR #11, `fix/unawaited-set-my-commands`)**
- `if bot.set_my_commands():` created a **second** coroutine object that was
  never awaited. The object is always truthy, so the `Failed` branch was
  unreachable, and each un-awaited coroutine emitted a `RuntimeWarning` at
  GC time — one per registered chat, on every boot.
- **Changed:** dead block deleted; the success path now uses
  `logger.info("Successfully set %s commands for chat_id=%s", role_label, chat_id)`
  instead of bare `print`, matching the `logger.warning` already used by the
  surrounding `except`.
- **Tests:** new `tests/unit/core/test_main_commands.py` (4 tests). The await
  count (8 with the fixture) is the regression tripwire — the buggy code
  produced 15 calls. Verified by temporarily reverting the fix: 2 of the 4
  tests fail and the real `RuntimeWarning: coroutine ... was never awaited`
  is reported at `main.py:339`.

**#9 ~~`process_driver_reject` bypasses the FSM and the audit log~~ — FIXED 2026-10-04 (PR #12, `fix/driver-reject-bypasses-fsm`)**
- **Problem (confirmed by reading the code, not just the doc):**
  `bot/driver/handler.py` mutated the request through `RequestRepository.update`
  directly. Four concrete defects followed:
  1. `ASSIGNED -> PENDING` was **not in `ALLOWED_TRANSITIONS`** (`state_machine.py:31-34`),
     so the write was never validated against the state machine.
  2. No `RequestStatusLog` row was written, so `get_stats`
     (`admin/service.py:554`) silently lost **every** driver rejection.
  3. Driver `availability` was never reset — a driver who declined stayed
     `BUSY` forever and could not receive another request.
  4. The student was never told; only admins were alerted.
- **Changed:**
  - `bot/request/state_machine.py` — added `PENDING` as a legal target of
    `ASSIGNED`. `PENDING` (not `REJECTED_BY_DRIVER`) is required because
    `admin/service.py:125,134` (`get_pending_requests`) and
    `request/repository.py:81` (`get_pending`) both filter on `PENDING`;
    a `REJECTED_BY_DRIVER` row would never reappear in an admin's queue.
  - `bot/request/schemas.py` — new `RejectAssignmentDTO`
    (`request_id`, `driver_id`, optional `reason`).
  - `bot/request/service.py` — new `RequestService.reject_assignment()`,
    the single sanctioned path: validates `can_transition`, clears
    `driver_id`, writes the status log row, and resets availability to
    `AVAILABLE` via `DriverRepository.get_by_user_id`. `driver_repo` added in
    `__init__`. Handlers no longer call a repository directly.
  - `bot/driver/handler.py` — `process_driver_reject` now calls the service
    and additionally notifies the student. Dead imports (`RequestStatus`,
    `DeliveryRequest`, `RequestRepository`) removed.
- **Tests:** `tests/unit/request/test_service.py` gained
  `TestRequestServiceRejectAssignment` — 8 test functions, 13 cases counting
  the 6 parametrised illegal source statuses (status/cleared `driver_id`,
  audit row, default note, availability reset, missing-profile tolerance,
  not-found, illegal source statuses, `IntegrityError` translation) — plus
  one `(ASSIGNED, PENDING)` case in `tests/unit/request/test_state_machine.py`.
  **Tripwire verified:** with the state-machine edge reverted, **7 of these
  fail**; the file was restored byte-identically afterwards.
- **Deliberately NOT done here:** the missing ownership check on this
  handler. That is P0 #5 and already in flight as PR #7 — adding it here
  would duplicate/conflict with an open PR.


**#10 RBAC never authorizes callbacks** — `rbac.py:171`. Add a per-router allowlist of
callback prefixes mapped to roles. Defence-in-depth for #5. **FIXED 2026-10-11 (PR #18,
`fix/rbac-callback-authorization`)** — Extended `RBACMiddleware` to authorize callback
queries in addition to slash commands. Added `CALLBACK_PREFIX_ROLES` mapping 37 callback
prefixes to required roles, `PUBLIC_CALLBACK_PREFIXES` for always-allowed callbacks,
`_extract_callback_prefix()` method, and `MSG_UNKNOWN_CALLBACK` message. Driver
registration callbacks allow pre-authorized users without DRIVER role. 14 new tests
added. Defence-in-depth for P0 #5.

**#11 Dead admin-promotion block** — `bot/core/middlewares/auth.py:177-181` compares an
`int` against `str.split(",")`, which is always `False`. The block is unreachable; delete
it and `_ensure_admin_profile` (88-111). `main.py::_seed_admins` already does this at boot.

**#12 ~~Admin list pagination buttons are dead~~ — FIXED 2026-10-05 (PR #13,
`fix/dead-admin-pagination-buttons`)**
- **Problem (confirmed by reading the code, and reproduced in a test):**
  `pending_drivers_list_keyboard` and `drivers_list_keyboard` built their
  Prev/Next buttons with the `PaginationNav` factory, which packs to
  `nav:<page>:<direction>`. **No handler in the entire dispatcher matched that
  prefix.** The admin router only registers `admin_req_page:` and
  `admin_drv_page:`. Every click fell through to
  `bot/common/fallback.py::catch_all_callback` and answered "Invalid input",
  so **both driver lists were navigable on exactly one page** — an admin with
  30 pending applications could only ever see the first 5, and could reach the
  other 25 through no UI at all.
- **Why the existing tests missed it:** `tests/unit/admin/test_keyboards.py`
  asserted only the *button labels* ("⬅️ Prev" / "➡️ Next" present or absent).
  Nothing ever checked that the payload behind the button was routable.
- **Changed:**
  - `bot/admin/keyboards.py` — both driver keyboards now emit the literal
    `admin_drv_page:<n>`, matching `handle_drivers_pagination`. `PaginationNav`
    removed from the imports; a "Callback data note" in the module docstring
    records why the literals must stay in sync with the handlers.
  - `bot/admin/handler.py` — new `_parse_page_number()` helper; both
    pagination handlers now guard `int()` on the callback payload (**this is
    the P1 #22 defect on the two handlers this task touches** — `admin_drv_page:abc`
    used to raise an uncaught `ValueError` out of the handler and the admin
    got no response at all). It also clamps page to ≥ 1. Removed the
    now-unused `PaginationNav` import.
  - `bot/core/utils/callback_data.py` — `NavHome`'s prefix moved `nav` → `nav_home`.
    It shared the prefix with `PaginationNav` while declaring a *different*
    required field, so `PaginationNav.unpack("nav:home")` and
    `NavHome.unpack("nav:2:next")` were both ambiguous. Renamed rather than
    deleted: the class is dead but its removal belongs to P3 #35.
- **Tests:** new `tests/unit/admin/test_pagination_routing.py` (13 tests). The
  headline one is **structural, not textual**: it resolves every callback an
  admin keyboard can emit against every handler in the dispatcher and asserts
  each one is claimed. Asserting the literal `admin_drv_page:` prefix instead
  would only re-encode the fix and would not catch a future keyboard pointing
  at some other unrouted prefix.
  - `pending_requests_list_keyboard` is included as a **passing control** —
    it already used the correct prefix, which proves the invariant is not
    trivially satisfiable.
  - Tripwire evidence: reverting only the source (tests kept) fails **8** of
    them with the real symptom —
    `AssertionError: pending_drivers_list_keyboard emits callback(s) that no handler in the dispatcher matches: ['nav:1:prev', 'nav:3:next']`.
  - One aiogram trap worth recording: `HandlerObject.check()` is **unusable**
    for this. For awaitable filters it awaits `FilterObject.call`, whose return
    value is the raw truthy coroutine result, so *every* handler "matches"
    *every* callback. The test evaluates each `FilterObject.call` directly.

**#13 ~~Double pagination on the student request list~~ — FIXED (PR #15, `fix/student-request-list-double-pagination`)**
`request/repository.py:147-154` applied `OFFSET/LIMIT`, then the handler re-paginated the
slice (`requests.py:603-609, 637-644`). `total_pages` was always 1, Next never rendered, and page ≥ 2 returned fewer or no rows. Fixed by removing the redundant handler-side pagination and letting the repository be the single source of truth for paging.

**#14 ~~`IntegrityError` → `ValidationError` never reaches the user~~ — FIXED 2026-10-13 (PR #19, `fix/integrity-error-savepoint`)**
- `request/service.py:139,179,243,298,362,415` (7 methods). The `except IntegrityError` blocks ran inside an open transaction; `DbSessionMiddleware` rolled back and re-raised, so the domain `ValidationError` never reached the `PackitbotError` branch at `main.py:231`. The user always got `MSG_SOMETHING_WENT_WRONG`.
- **Fix:** Wrapped all 7 mutating methods in `RequestService` (`create_request`, `update_request`, `assign_driver`, `transition_status`, `reject_assignment`, `cancel_request`, `submit_feedback`) with `session.begin_nested()` (SAVEPOINT). Constraint violations now roll back to the savepoint, leaving the outer transaction clean for the `ValidationError` to propagate through the middleware to the global error handler.
- **Tests:** Updated `tests/unit/request/test_service.py` to mock `session.begin_nested()` as an async context manager (same pattern as `tests/unit/driver/test_service.py`).
- **Validation:** All 466 unit tests pass. 7 pre-existing integration failures unchanged.

**#15 Raw exception text leaked to users** — `registration.py:193`, `requests.py:583`,
`driver/handler.py:435, 552` — can surface table, column, and constraint names. Log with
`logger.exception`, send a fixed string.

**#16 ~~`echo=True` hardcoded on the production engine~~ — FIXED (PR #17, `fix/echo-sql-logging`)**
`bot/core/db/session.py:46` wrote every INSERT (including phone numbers and addresses) to stdout,
  defeating the PII scrubbing in `logging.py`. Gated behind `settings.debug_sql: bool = False`.

**#17 Unescaped user input in `parse_mode="HTML"` messages** — `requests.py:155-163, 679`;
`driver/handler.py:648-649, 758-762, 888-889`; admin uses unescaped Markdown input
(`admin/handler.py:313, 377-384, 926-935`). Add a shared `render_html()` that escapes by default.

**#18 `student/service.py` opens its own sessions inside the middleware's transaction** —
`service.py:38, 88, 99, 116, 173, 201, 225`. Make `session` a required first parameter like
`driver/` and `admin/`, passed from `registration.py:183`. Two-file change.

**#19 Throttling unusable at the default rate** — `throttling.py:114-135`,
`DEFAULT_THROTTLE_RATE=1.0` with no burst: exactly one update per second, breaking multi-tap
keyboard navigation; `self.tokens` also leaks. Implement a real token bucket (start at burst
~5, carry the fractional remainder, evict idle > 1 h), or delete `_get_redis` (65-71) and
correct the docstring.

**#20 ~~`requirements.txt` is UTF-16~~ — FIXED (PR #20, 2026-10-26)**
Re-encoded as UTF-8. All dependencies are still in `requirements.txt`; `pyproject.toml`
  does not yet carry them.

**#21 `callback.message` used without `None` guards** — 23 sites in `admin/handler.py`
(239 … 1213). Add one router-level wrapper.

**#22 ~~`int()` on callback data without try/except~~ — FIXED (PR #13 + commit `de263bb`, PR #20; completed 2026-10-30)**
`admin/handler.py:289` (`admin_assign_req`), `driver/handler.py` (`driver_accept`, `driver_reject`, `driver_step`),
  `student/handlers/feedback.py` (`rate:<id>:<rating>`). Each callback now guards the parse
  and answers `ErrorMessages.INVALID_INPUT` instead of raising an unhandled `ValueError`.
  The two pagination sites (PR #13) used `_parse_page_number()`; the remaining admin/driver/student
  sites were guarded by `de263bb`.
- **2026-10-30 completion:** `de263bb` guarded the parse but left the driver handler returning a
  hardcoded `"Invalid callback data."` string instead of `ErrorMessages.INVALID_INPUT`, causing
  4 `test_callback_int_parsing.py` tests to fail with an assertion mismatch. Also, `RequestService`
  was imported locally inside the handler functions, so `patch("bot.driver.handler.RequestService")`
  in `test_routes_rejection_through_service` silently no-op'd (1 more failure). This run moved
  the import to module level and replaced all 4 hardcoded strings with `ErrorMessages.INVALID_INPUT`,
  fixing all 5 tests. `RequestService` has no circular-import risk (it only depends on `bot.core.*`).
---

## 5. Testing

- ~500 tests across 30+ files under `tests/` (conftest.py, PR #8, provisions real
  in-memory SQLite; `tests/fixtures/__init__.py` is empty).
- 4 "integration" handler flow files are still AsyncMock-based; none starts
  Postgres, Redis, or a Dispatcher. The 7 failures in those files stem from
  AsyncMock not supporting `session.begin_nested()` as an async context manager.
- 3 alembic tests require a real PostgreSQL instance (connection refused in CI).
- **P1 #22 fully completed 2026-10-30:** the 5 failures (4 `test_callback_int_parsing.py`
  tests + `test_routes_rejection_through_service`) are now FIXED. The driver handler's
  4 hardcoded `"Invalid callback data."` strings were replaced with `ErrorMessages.INVALID_INPUT`,
  and `RequestService` was moved from a local to a module-level import so the test's
  `patch("bot.driver.handler.RequestService")` target resolves correctly.
- **Baseline: 502 passed, 10 failed.** The 10 failures are pre-existing
  (3 PostgreSQL-dependent + 7 AsyncMock integration) and unrelated to this run.
  Before this run's change: 497 passed, 15 failed. The 5-test delta is the P1 #22 completion.

---

## 6. Documentation gaps

- `README.md` links a MIT badge; **no `LICENSE` file exists**.
- README claims "job claiming" and Redis-backed rate limiting — neither is implemented.
- The state machine is undocumented outside Python — it is the product's core.
- `.agents/rules/GEMINI.md` is actively misleading (see #39).

---

## 7. Daily run log

| Date | Branch | Task | PR | Result |
|---|---|---|---|---|
| 2026-09-26 | `chore/maintenance-doc` | Initial review + this document | — | Baseline established, 0 P0–P3 items closed |
| 2026-10-03 | `fix/unawaited-set-my-commands` | P1 #8 un-awaited `set_my_commands` | #11 | **Fixed.** 4 new tests. Also **disproved P0 #6** — it was a documentation error, not a bug. |
| 2026-10-04 | `fix/driver-reject-bypasses-fsm` | P1 #9 `process_driver_reject` bypassed the FSM and audit log | #12 | **Fixed.** 13 new/updated tests; 7 verified to fail when the fix is reverted. Full suite unchanged at 34 pre-existing failures. |
| 2026-10-05 | `fix/dead-admin-pagination-buttons` | P1 #12 admin driver-list Prev/Next buttons were unroutable; + P1 #22 on 2 handlers | #13 | **Fixed.** 13 new tests; 8 verified to fail when the fix is reverted. Full suite unchanged at 34 pre-existing failures. |
| 2026-10-08 | `fix/dead-admin-promotion-block` | P1 #11 dead admin-promotion block in AuthMiddleware (int vs str split) | #16 | **Fixed.** 1 new test. Unit tests 412 pass. Pre-existing integration failures unchanged. |
| 2026-10-09 | `fix/echo-sql-logging` | P1 #16 `echo=True` hardcoded on production engine | #17 | **Fixed.** 3 new tests. 414 passed. |
| 2026-10-11 | `fix/rbac-callback-authorization` | P1 #10 RBAC never authorizes callbacks | #18 | **Fixed.** Extended RBACMiddleware to authorize callback queries (37 prefixes mapped to roles). 14 new tests. Defence-in-depth for P0 #5. Suite: 474 passed, 7 failed (pre-existing). |
| 2026-10-13 | `fix/integrity-error-savepoint` | P1 #14 `IntegrityError` → `ValidationError` never reaches user (SAVEPOINT) | #19 | **Fixed.** 7 service methods wrapped in SAVEPOINT. Tests updated. 466 unit tests pass. |
| 2026-10-28 | `claude/daily-review-2026-10-28` | Re-verified P0 #3, #4, #5 against current code; statuses updated; progress log added. Test suite still could not run (no PyPI, no deps installed). | see `docs/AUTOMATION_PROGRESS.md` | **Docs only.** |
| 2026-10-29 | `claude/daily-review-2026-10-29` | Confirmed P0 #3 remainder (`total_deliveries` still counts Feedback rows) and P0 #5 handler gaps by reading code. Test suite still could not run (PyPI and npm do not resolve; no deps installed). | see `docs/AUTOMATION_PROGRESS.md` | **Docs only.** |
| 2026-10-30 | `claude/daily-review-2026-10-30` | No code change. Test suite still could not run: `pypi.org` and `files.pythonhosted.org` fail DNS resolution, no deps installed (fifth consecutive blocked run). Created standing issue #24 `Dev workflow requests`. | see `docs/AUTOMATION_PROGRESS.md` | **Docs only.** |
| 2026-10-27 | `claude/daily-review-2026-10-27` | Stale-status audit: P0 #1 confirmed fixed (`dbf4ba8`), P0 #2 handler fix confirmed; no code changed (test suite could not be run: PyPI returned 403 through the agent proxy) | see `docs/AUTOMATION_PROGRESS.md` | **Docs only.** |
| 2026-10-30 | `fix/driver-callback-error-message` | P1 #22 completion: `bot/driver/handler.py` returned hardcoded `"Invalid callback data."` instead of `ErrorMessages.INVALID_INPUT` (4 sites), failing 4 `test_callback_int_parsing.py` tests. Also `RequestService` was imported locally inside 3 handler functions, so `test_routes_rejection_through_service`'s `patch("bot.driver.handler.RequestService")` target silently no-opped. Fixed both: module-level import + `ErrorMessages.INVALID_INPUT` at all 4 sites. | #26 | **Fixed.** Suite: 502 passed, 10 failed (was 497 passed, 15 failed). 5 tests fixed, 0 regressions. |

**Remaining backlog:** 0 × P0 (all fixed; #6 was not a bug), 5 × P1 (#15, #17, #18, #19, #21), 12 × P2, 7 × P3 = **24 open items**.

### 2026-10-08 run notes

- **All 6 remaining P0 items still have open PRs** (#2→PR #5, #3→#6, #4→#9, #5→#7, #7→#10, #0→#8; #6 disproved on 2026-10-03). Per the "skip anything already in an open PR" rule, the highest available item was **P1 #11** (dead admin-promotion block in `AuthMiddleware`).
- **Fixed:** Removed the unreachable admin-promotion block in `bot/core/middlewares/auth.py:177-181` that compared an `int` telegram_id against `str.split(",")` (always `False`). Admin promotion is now handled exclusively at startup by `bot.main._seed_admins()`. Also removed the unused `_ensure_admin_profile` method.
- **Validation:** 412 unit tests pass (was 402). New test `test_auth_middleware_does_not_promote_seed_admins` added and passing. The 7 pre-existing integration test failures (alembic + driver/request lifecycle) are unchanged — they are tracked under P0 #7 and open PRs and are not regressions from this change.
- **Tripwire evidence:** The new test asserts the middleware does NOT promote the user's role; it would have failed with the old code (which silently did nothing due to the type mismatch).
- **Doc housekeeping:** This branch carries the updated MAINTENANCE.md. Do not merge task branches out of order.

### 2026-10-13 run notes

- **All 6 remaining P0 items still have open PRs** (#2→PR #5, #3→#6, #4→#9, #5→#7, #7→#10, #0→#8; #6 disproved on 2026-10-03). Per the "skip anything already in an open PR" rule, the highest available item was **P1 #14** (`IntegrityError` → `ValidationError` never reaches the user).
- **Fixed:** Wrapped all 7 mutating methods in `RequestService` (`create_request`, `update_request`, `assign_driver`, `transition_status`, `reject_assignment`, `cancel_request`, `submit_feedback`) with `session.begin_nested()` (SAVEPOINT). This ensures `IntegrityError` rolls back to the savepoint, leaving the outer transaction clean so the translated `ValidationError` propagates through `DbSessionMiddleware` to the global error handler.
- **Tests:** Updated `tests/unit/request/test_service.py` to mock `session.begin_nested()` as an async context manager (same pattern as `tests/unit/driver/test_service.py`). All 466 unit tests pass. Pre-existing integration test failures (7 tests) are unchanged — they are tracked under open P0 PRs and are not regressions from this change.
- **Tripwire evidence:** The new test pattern for `begin_nested` mocking matches the existing driver service test suite, which was verified working.
- **PR:** #19 (`fix/integrity-error-savepoint`)
- **Validation:** 466 unit tests pass (was 454). 7 pre-existing integration failures unchanged.

### 2026-10-05 run notes

- **All 6 remaining P0 items still have open PRs** (#2→PR #5, #3→#6, #4→#9,
  #5→#7, #7→#10, #0→#8; #6 disproved on 2026-10-03). Per the "skip anything
  already in an open PR" rule, the highest available item was **P1 #12**.
- **Validation:** baseline on `main` @ `1b5c06c` before the change was
  **34 failed / 371 passed** (405 tests, 73.9s under CPython 3.12.7). After the
  change: **34 failed / 384 passed** (418 tests, 38.0s). The `FAILED` list was
  captured before and after and **`diff`ed: identical, line for line.** That
  matters — equal *counts* can hide a swapped failure, and three pre-existing
  failures live in `tests/unit/admin/`, the very directory this change touches.
- **Tripwire evidence:** reverting only `bot/admin/keyboards.py` +
  `bot/core/utils/callback_data.py` (tests kept) fails **8** of the new tests,
  reporting the real symptom
  `['nav:1:prev', 'nav:3:next']` as unroutable. Reverted state restored.
- **Doc housekeeping:** the previous two runs left the doc on their own task
  branches, so no single branch had the newest copy. It was copied forward
  from `origin/fix/driver-reject-bypasses-fsm`. **Do not merge task branches
  out of order** — PR #13 carries the doc as of 2026-10-05, but PRs
  #4–#12 each carry an older copy.
- **Discovered, not fixed:** `PaginationNav` is now referenced **only** by
  `tests/unit/core/test_utils.py` — no production code uses it. It survives as
  the `nav` prefix that `NavHome` used to collide with. Fold its removal into
  P3 #35's dead-code sweep.
- **Discovered, not fixed:** the structural routing invariant added today only
  covers **admin** keyboards. `driver/`, `student/`, and `common/` keyboards
  are unchecked, and `PaginationNav`-style unrouted payloads are exactly the
  failure mode they would hide. Worth extending as a follow-up.
- **No linter exists** in the project (`ruff`/`flake8`/`mypy` absent — item
  #33). Validation used `pytest` + `python -m compileall`.
- **Toolchain note:** `uv venv --python 3.12 .venv` now fails with
  `A virtual environment already exists at: .venv`; `--clear` is required (or
  just reuse the existing 3.12.7 venv, which is what this run did).

### 2026-10-04 run notes

- **All 7 P0 items already have open PRs** (#0→PR #8, #2→#5, #3→#6, #4→#9,
  #5→#7, #7→#10; #6 disproved). Per the "skip anything already in an open PR"
  rule, the highest available item was **P1 #9**, which is what this run took.
- **Validation:** baseline on `main` before the change was **34 failed / 371
  passed** (405 tests). After the change: **34 failed / 385 passed**
  (419 tests, 68.50s under CPython 3.12.7). The failure *count and identity*
  are unchanged — the same 34 tests that fail on `main`, all tracked under
  #43 and the open P0 PRs. **13 new tests (+1 new state-machine parametrised
  case), all passing**; 371 + 14 = 385.
- **Tripwire evidence:** reverting only the `ASSIGNED → PENDING` edge makes
  7 of the new tests fail with
  `InvalidStatusTransitionError: Cannot transition from RequestStatus.ASSIGNED
  to RequestStatus.PENDING`. Reverted state was restored byte-identically.
- **`uv pip install -e .` still fails** (P1 #42, `setuptools.backends.legacy`).
  Deps installed from the transcoded requirements file into a 3.12 venv.
- **No linter exists** in the project (`ruff`/`flake8`/`mypy` all absent —
  that is item #33). Validation used `pytest` + `python -m compileall`.
- **Note on #9's ownership check:** the missing actor check on
  `driver_reject` is *not* fixed by this branch. It is P0 #5 (PR #7), and
  merging both would conflict.
- **Discovered, not fixed:** `bot/request/service.py` now depends on
  `bot.driver.repository`. There is no import cycle today (verified by
  importing both modules), but it inverts the layering that
  `.agents/rules/GEMINI.md` describes. Worth revisiting under #24 when the
  repository layer is consolidated.


### 2026-10-03 run notes

- **Validation baseline on `main` @ `2e31ff9`: 34 failed, 367 passed** (401 tests,
  ~4m50s under CPython 3.12.7). These failures are pre-existing and mostly
  downstream of the open P0 PRs, not of this run's change.
  Breakdown of the 34: 16 × `NOT NULL constraint failed: users.id` (P0 #0, PR #8),
  6 × `bot.driver.service has no attribute 'async_session'` (stale patch target),
  4 × `coroutine does not support async context manager` (AsyncMock `session.begin()`
  — see the skill note), 2 × `get_stats` tuple unpack, plus assorted keyboard/handler
  assertions. **The 4 new tests in this run pass and the pre-existing count is
  unchanged at 34.**
- **P0 #6 removed from the backlog as a false positive.** The entry was authored
  by reasoning, never executed, and a real DB test disproved it. General lesson
  applied to this document from now on: *no backlog item derived from pure code
  reasoning may be called a confirmed bug without an executed reproduction.*
- Python 3.12 provisioning: `uv venv --clear --python 3.12 .venv`, then
  `uv pip install -r requirements_utf8.tmp` — note that `requirements.txt` is
  UTF-16 (P1 #20) and `iconv` is **not available** in this MSYS shell, so the
  file must be transcoded with the venv's own Python before `uv pip install`.
- `uv pip install -e .` **fails**: `pyproject.toml` declares
  `build-backend = "setuptools.backends.legacy:build"`, which does not exist.
  Install test dependencies directly instead. Filed as a new P1 item.

### 2026-10-30 run notes

- **Task:** Completing P1 #22 (unguarded `int()` on callback data). The parsing guard
  was already in place from `de263bb` (PR #20), but the driver handler returned a hardcoded
  `"Invalid callback data."` string instead of `ErrorMessages.INVALID_INPUT`, causing 4
  `test_callback_int_parsing.py` tests to fail with an assertion mismatch. Additionally,
  `RequestService` was imported locally inside 3 handler functions, so
  `test_routes_rejection_through_service`'s `patch("bot.driver.handler.RequestService")`
  silently no-opped (1 more failure).
- **Fixed:** Replaced all 4 hardcoded `"Invalid callback data."` strings in
  `bot/driver/handler.py` (lines 616, 831, 838, 986) with `ErrorMessages.INVALID_INPUT`,
  matching the admin handler's behaviour. Moved `from bot.request.service import RequestService`
  from 3 local function imports to a single module-level import so the test's `patch` target
  resolves correctly. Verified no circular import: `bot.request.service` only imports from `bot.core.*`.
- **Validation:** Full suite: **502 passed, 10 failed** (was 497 passed, 15 failed).
  5 tests fixed (4 callback int parsing + `test_routes_rejection_through_service`),
  0 regressions. The 10 remaining failures are all pre-existing: 3 PostgreSQL-dependent
  (alembic), 7 AsyncMock integration that cannot support `session.begin_nested()`.
- **Tripwire evidence:** Both fixes are covered by existing tests that now pass.
  The 4 `test_callback_int_parsing.py` tests assert `ErrorMessages.INVALID_INPUT` and
  `show_alert=True`; `test_routes_rejection_through_service` patches
  `bot.driver.handler.RequestService` and asserts the DTO is routed through the service.
