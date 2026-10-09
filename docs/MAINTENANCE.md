# Packitbot — Maintenance & Development Backlog

> **This document is the source of truth for automated daily development runs.**
> It is updated on every task branch. Daily runs must re-read it *and* the code
> before choosing work — never trust a previous run's analysis.

- **Repository:** `tokeniyi/Packitbot`
- **Description:** Async Telegram logistics and delivery management bot (aiogram 3.x, SQLAlchemy 2.0)
- **Default branch:** `main` (protected — never pushed to directly)
- **Scale:** 130 Python files, ~14.7k LOC application code
- **Review baseline:** commit `1b5c06c` (`main`, as of 2026-10-05)
- **Last reviewed:** 2026-10-05

> **WARNING — this document is branch-resident.** PR #3 (`chore/maintenance-doc`)
> was never merged, so `docs/MAINTENANCE.md` does **not** exist on `main`.
> Every daily run must read it with
> `git show origin/fix/driver-reject-bypasses-fsm:docs/MAINTENANCE.md`
> (or the newest task branch), not `read_file`, or it will find nothing.
> Merging PR #3 would fix this permanently and is the single cheapest
> improvement available.

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
- **The revision graph has two heads** — `a1b2c3d4e5f6` and `d773fd78af20`.
  `alembic upgrade head` **fails outright**; only an explicit revision works
- `alembic.ini:2` retains the placeholder `sqlalchemy.url = driver://user:pass@localhost/dbname`

Schema is therefore whatever `create_all` produces, ENUMs are patched by hand, and
no environment is reproducible from the repository. **This blocks all future schema work.**

### 1.4 Environment note (important for automation)

`pyproject.toml` requires **`>=3.12,<3.13`**, but system Python is **3.11.16**.
Use `uv` to provision 3.12 — do not attempt to run the suite under the system interpreter.

---

## 2. Headline state

- **6 P0 bugs** (was 7 — #6 was disproved on 2026-10-03 and removed). Three break the
  product outright: `/add_driver` never authorizes
  anyone (so nobody can ever register as a driver), driver assignment writes the wrong
  foreign key, and `session.get(DriverProfile, <users.id>)` breaks availability
  restoration *and* all driver ratings.
- **1 critical security finding.** No ownership check on the three driver delivery
  callbacks — any Telegram user can hijack and complete **any** delivery and read the
  student's phone number. `RBACMiddleware` structurally cannot catch this because it
  inspects only slash-commands.
- **1 more correctness bug.** Lazy relationship loads raise `MissingGreenlet`, so
  "view request detail" is broken for every request that has a driver assigned.
- **Alembic is non-functional** (above).
- **The test suite cannot catch any of the above.** All 4 "integration" files are
  `AsyncMock`-based; none starts Postgres, Redis, or a Dispatcher. No `conftest.py`;
  `tests/fixtures/__init__.py` is empty.
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

**#1 `/add_driver` never works — admin ID compared against the wrong column**
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

**#2 Driver assignment writes `DriverProfile.id` into a `users.id` column**
- `bot/admin/keyboards.py:433` → `bot/admin/handler.py:294-304` → `bot/request/service.py:226`;
  model at `bot/core/models/delivery_request.py:111`
- `AvailableDriverDTO` carries **both** `driver_id=dp.id` and `user_id=user.id`
  (`admin/service.py:193`); the wrong one is used.
  `can_assign_driver()` validates the *correct* profile, so the guard gives false confidence.
- **Impact:** FK `IntegrityError` aborting assignment, or the wrong user recorded as
  driver while the correct one is notified.
- **Fix:** `AssignDriverDTO(driver_id=driver_profile.user_id, …)`; add an assertion in
  `RequestService.assign_driver` that `dto.driver_id == driver_profile.user_id`.

**#3 Cancellation / feedback re-query `DriverProfile` with a `users.id`**
- `bot/student/handlers/requests.py:1012`; `bot/student/handlers/feedback.py:28, 35, 189`
- **Impact:** driver availability never restored on cancellation; `rating_avg` and
  `total_deliveries` never updated → driver ranking and the `/drivers` leaderboard are
  permanently zero/empty.
- **Fix:** resolve via `DriverRepository(session).get_by_user_id(user_id)` or join on
  `user_id`. Separately, `total_deliveries` counts `Feedback` rows (feedback.py:33-41) —
  it must count `DeliveryRequest` where `status == DELIVERED`.

**#4 `MissingGreenlet` on "view request detail"**
- `bot/student/handlers/requests.py:668` (load) and `:141-147` (lazy access)
- `req.driver` / `req.driver.driver_profile` lazy-load outside an awaited context →
  `MissingGreenlet` (a subclass of `InvalidRequestError`, **not** `PackitbotError`),
  so it bypasses the global handler and shows a generic error.
- **Fix:** `.options(selectinload(DeliveryRequest.driver).selectinload(User.driver_profile))`.
  `expire_on_commit=False` does not help — the object was never loaded.

**#5 No ownership check on driver delivery callbacks** *(most severe)*
- `bot/driver/handler.py:567` (`process_driver_accept`), `:776` (`process_delivery_status_step`),
  `:927` (`process_driver_reject`); enabler at `bot/core/middlewares/rbac.py:171`
- `RBACMiddleware._extract_command` returns `""` for non-slash-command messages and
  rbac.py:171 gates only `if command:` — **callbacks are never role-checked**.
  The state machine blocks illegal *transitions*, never illegal *actors*.
- **Impact:** any Telegram user who guesses a sequential request ID can accept, advance,
  reject, or complete **any** delivery — and the two `send_message` calls at
  `driver/handler.py:660-672` hand them the student's name and phone number.
- **Fix:** in each handler assert `req.driver_id == driver_user.id` before mutating;
  add an `actor_must_be_assigned_driver` business rule enforced **inside**
  `RequestService.transition_status` so future callers cannot bypass it.

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

**#7 `_init_db` bypasses Alembic — migration chain unusable**
- `bot/main.py:78-92`; `alembic/versions/`
- **Fix:** delete the 20 no-op files, merge the two heads into one linear chain, generate
  a fresh baseline via `alembic revision --autogenerate` against real Postgres, replace
  `create_all` with a documented `alembic upgrade head` step in the entrypoint, and move
  the `AUTHORIZE_DRIVER` ENUM change into that migration.

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
callback prefixes mapped to roles. Defence-in-depth for #5.

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

**#13 Double pagination on the student request list** — `request/repository.py:147-154`
applies `OFFSET/LIMIT`, then the handler re-paginates the slice
(`requests.py:603-609, 637-644`). `total_pages` is always 1, Next never renders, and page ≥ 2
returns fewer or no rows. Pick one strategy. **FIXED 2026-10-06 (PR #14)** — moved
pagination into `RequestRepository.get_history_for_student`, which now returns a `Page`
with the correct `total` from `count()` and the sliced `items`; the handler consumes the
`Page` directly and no longer re-slices the result.

**#14 `IntegrityError` → `ValidationError` never reaches the user** —
`request/service.py:139,179,243,298,362,415`. The `except` runs *inside* an open
transaction; `DbSessionMiddleware` rolls back and re-raises, so the domain `ValidationError`
never reaches the `PackitbotError` branch at `main.py:231`. The user always gets
`MSG_SOMETHING_WENT_WRONG`. Use `session.begin_nested()` (SAVEPOINT) or drop the translation.

**#15 Raw exception text leaked to users** — `registration.py:193`, `requests.py:583`,
`driver/handler.py:435, 552` — can surface table, column, and constraint names. Log with
`logger.exception`, send a fixed string.

**#16 `echo=True` hardcoded on the production engine** — `bot/core/db/session.py:46` writes
every INSERT, including phone numbers and addresses, to stdout, defeating the PII scrubbing
in `logging.py`. Gate behind `settings.debug_sql: bool = False`. **FIXED 2026-10-09 (PR #17, `fix/echo-sql-logging`)** — added `debug_sql` setting defaulting to `False`, gated `echo` behind it.

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

**#20 `requirements.txt` is UTF-16** — re-save as UTF-8, move all dependencies into
`pyproject.toml [project.dependencies]`, and delete it. Two manifests is a hazard.

**#21 `callback.message` used without `None` guards** — 23 sites in `admin/handler.py`
(239 … 1213). Add one router-level wrapper.

**#22 `int()` on callback data without try/except** — `admin/handler.py:236, 262, 542, 827`.
Copy the guard already used at `student/handlers/requests.py:655-660`.
**Partially fixed 2026-10-05 (PR #13):** the two pagination handlers
(`handle_pending_requests_pagination`, `handle_drivers_pagination`) now use the
`_parse_page_number()` helper, which returns `None` on a bad payload and makes
the handler answer `ErrorMessages.INVALID_INPUT` instead of raising
`ValueError` out of the handler. **The three remaining sites (`admin/handler.py:262, 236, 827`)
are still unguarded.**

### P2 — Improvement

**#23 Consolidate the two `ValidationError` classes** — `core/exceptions.py:42` vs
`core/utils/validators.py:71`. Make the latter subclass the former so `driver/handler.py:212`
and `driver/service.py:213` catch the same type.

**#24 Introduce a repository layer for `admin/` and `student/`** — all 15 admin functions
issue `select()` directly; `StudentRepository` already exists and is unused. This satisfies
`GEMINI.md:8` and makes the #2/#3 fix enforceable in one place.

**#25 Adopt an explicit ID-naming convention** — `admin/schemas.py` (`driver_id` = profile
id) vs `request/schemas.py:102` (`driver_id` = `users.id`) vs `request/repository.py:104`
(docstring says Telegram ID). Rename to `driver_profile_id` / `driver_user_id`; add the rule
to `GEMINI.md`.

**#26 Implement or delete the domain event layer** — `bot/request/events.py` (5 events, all
discarded; `requests.py:573` throws the event away) and `NotificationType` (12 values, zero
code). Either build a minimal in-process dispatcher and move the inline
`callback.bot.send_message` blocks (`driver/handler.py:660, 900, 998`) into listeners, or
delete both. Half-implemented infrastructure is worse than none.

**#27 `BaseRepository.update` silently ignores unknown fields** —
`core/repositories/base_repository.py:47-49`. `UpdateRequestDTO.changed_fields` is a free-form
dict fed by FSM data (`requests.py:853`), so a typo produces a silent no-op. Raise instead.

**#28 Unique constraint for `license_number`** — `models/driver_profile.py:103` has no
`unique=True`, yet `driver/service.py:93-94` and `admin/service.py:1176-1180` treat it as
unique via `get_by_license_number` → `scalar_one_or_none`. Two drivers with the same licence
crash the handler instead of raising `DuplicateResourceError`. Add the index (after #7) and
catch `IntegrityError` in `register_driver` as its docstring promises (line 75).

**#29 Bound the admin queries** — `admin/service.py:173-185` (driver ranking, unbounded,
unindexed sort), `:998-1009`, `:604-612` (materialises every duration pair),
`:956-963` (broadcast targets). Add `.limit(20)`, batching, a SQL `AVG`, and composite
indexes on `(status, created_at)`.

**#30 Broadcast should be bounded and concurrent** — `admin/handler.py:1200-1218`. Show the
target count in the confirmation screen; dispatch with `asyncio.Semaphore(20)` + `gather`;
handle `TelegramRetryAfter` explicitly (`notification_service.py:91` is a bare `except Exception`).

**#31 Move feedback-rating recalculation into a domain service** — `feedback.py:26-42` does an
aggregate query + `session.flush()` inside a handler. Move to `bot/request/service.py` and
fix the `total_deliveries` semantics (#3) at the same time.

**#32 Add `conftest.py` fixtures and one real-database test tier** — `tests/fixtures/__init__.py`
is empty; no `conftest.py` exists. Add `session`, `user`, `driver_profile`, `request` fixtures.
Then add at minimum one integration test per P0: assignment writes `users.id`, `register_student`
creates a profile, the `session.get(DriverProfile, …)` path, and a callback-ownership test.

**#33 Add a linter/formatter/type-checker** — no `[tool.ruff]`, `[tool.mypy]`, or coverage
config. The untyped `session=None` handler signatures and unused imports
(`admin/handler.py:3-5`, `driver/handler.py:31`) would be caught immediately.

**#34 Remove the dead `bot/student/handler.py` facade** — 131 lines of re-exports. Update
`tests/unit/student/test_handler.py` to import from `bot.student.handlers` and delete it.

### P3 — Nice-to-have

**#35** Delete 10 unused `CallbackData` classes (`callback_data.py:33-46, 84-125`), 3 unused
validators (`validators.py:110-127, 378-419`), and the unused `role_filter.py` / `state_filter.py`
— ~200 lines of speculative API. Also `config.py:98-132`.

**#36** Delete unused constants — `constants/features.py:10-12`, `constants/limits.py:23-24`,
`base_repository.py:53-64` (`delete`, `list`), `request/repository.py:56-58, 89-126`.

**#37** Wire up or remove `total_deliveries` / `DriverAvailability.BUSY` / `VerificationStatus`
— three model fields the code never sets. Either implement (set `BUSY` on assignment at
`admin/handler.py:305`) or drop the columns.

**#38** Fix three broken module docstrings — `driver/handler.py:1`, `admin/handler.py:1`,
`core/services/notification_service.py:1` have the import above the docstring, so `__doc__` is empty.

**#39** Correct `GEMINI.md` — remove the FastAPI mention (line 7), drop the pytest prohibition
(line 11) and replace it with "run the suite before declaring done", fix the architecture rule
to describe what `admin/` and `student/` actually do, and add rules for ID semantics, HTML
escaping, and callback authorization.

**#40** Add a `LICENSE` file (README links a MIT badge but no LICENSE exists); remove the
"job claiming" and "Redis-backed rate limiting" claims from the README; add a `state_machine.md`
rendering `ALLOWED_TRANSITIONS` — the FSM is the product's core and is currently understandable
only by reading Python.

**#41 Add CI** — no `.github/` exists. A minimal workflow (`uv`-based Python 3.12 install,
`ruff`, `mypy`, `pytest --cov`) would have caught #20, #8, and most of the P1 list automatically.

**#42 `pyproject.toml` names a non-existent build backend** *(found 2026-10-03)* —
`build-backend = "setuptools.backends.legacy:build"` (with no `[tool.setuptools]`
section and no package discovery config). `uv pip install -e .` fails outright, so
the project **cannot be installed as a package at all**; every environment must be
hand-built. Change to `build-backend = "setuptools.build_meta"` plus an explicit
`[tool.setuptools.packages.find] include = ["bot*"]`, and declare the real
dependency set from `requirements.txt` in `[project.dependencies]` (closes #20 too).
*Verified:* `uv pip install -e .` → backend resolution error.

**#43 34 tests fail on `main` independent of any open PR** *(found 2026-10-03)* —
the suite is red at the review baseline, so no run can claim a green build until
this is addressed. Two distinct causes, both fixable without product changes:
(a) 16 × `NOT NULL constraint failed: users.id` — the SQLite `BigInteger` PK
problem of P0 #0 (PR #8), which is why `test_models.py` cannot round-trip a single
row; (b) 6 × `bot.driver.service` has no attribute `async_session` — stale patch
targets left over from the session-injection refactor, plus 4 × `session.begin()`
returning a bare coroutine instead of an async context manager. Assign a green
gate here before adding more tests on top of a red suite.

---

## 5. Testing

- 342 tests across 29 files under `tests/`.
- **All 4 "integration" files are `AsyncMock`-based** — none starts Postgres, Redis, or a
  Dispatcher. They cannot reproduce any P0.
- No `conftest.py`; `tests/fixtures/__init__.py` is empty.
- **Coverage gaps:** the entire DB persistence layer, all middleware (auth, RBAC, throttling,
  session), every service→repository interaction, and the FSM's real enforcement.
- **Highest-value new tests:** one per P0. See #32.

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
| 2026-10-09 | `fix/echo-sql-logging` | P1 #16 `echo=True` hardcoded on production engine | #17 | **Fixed.** 3 new tests. 414 passed. |

**Remaining backlog:** 6 × P0 (all in open PRs #5–#10), 10 × P1 (#13 closed, #16 closed, #22 partially), 12 × P2, 7 × P3 = **35 open items**.

### 2026-10-06 run notes

- **All 6 remaining P0 items still have open PRs** (#2→PR #5, #3→#6, #4→#9,
  #5→#7, #7→#10, #0→#8; #6 disproved on 2026-10-03). Per the "skip anything
  already in an open PR" rule, the highest available item was **P1 #13**.

### 2026-10-09 run notes

- **All 6 remaining P0 items still have open PRs** (#2→PR #5, #3→#6, #4→#9,
  #5→#7, #7→#10, #0→#8; #6 disproved on 2026-10-03). Per the "skip anything
  already in an open PR" rule, the highest available item was **P1 #16**.
- **Validation:** baseline on `main` @ `7df6ac3` before the change was
  **34 failed / 384 passed** (418 tests). After the change: **34 failed / 417 passed**
  (451 tests, 55.1s under CPython 3.12.7). The `FAILED` list was identical
  line-for-line. **3 new tests added** (`test_settings_loads_from_env` updated,
  `test_settings_debug_sql_defaults_false` new); all pass.
- **Tripwire evidence:** not applicable for config-only change; the default
  `debug_sql=False` means production logging is now safe by default.
- **Doc housekeeping:** this branch now carries the newest MAINTENANCE.md.
  Do not merge task branches out of order — PR #17 carries the doc as of
  2026-10-09, but PRs #4–#16 each carry an older copy.
- **No linter exists** in the project (`ruff`/`flake8`/`mypy` absent — item
  #33). Validation used `pytest` + `python -m compileall`.
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
