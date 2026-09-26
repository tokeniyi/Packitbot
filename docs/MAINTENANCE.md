# Packitbot — Maintenance & Development Backlog

> **This document is the source of truth for automated daily development runs.**
> It is updated on every task branch. Daily runs must re-read it *and* the code
> before choosing work — never trust a previous run's analysis.

- **Repository:** `tokeniyi/Packitbot`
- **Description:** Async Telegram logistics and delivery management bot (aiogram 3.x, SQLAlchemy 2.0)
- **Default branch:** `main` (protected — never pushed to directly)
- **Scale:** 130 Python files, ~14.7k LOC application code
- **Review baseline:** commit `2e31ff9`
- **Last reviewed:** 2026-09-27

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

- **6 P0 bugs** (#1 now fixed). Two still break the product outright: driver
  assignment writes the wrong foreign key, and
  `session.get(DriverProfile, <users.id>)` breaks availability restoration
  *and* all driver ratings.
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
  ✅ **FIXED 2026-09-26** — branch `fix/add-driver-admin-id-column`, PR #4.
- `bot/admin/service.py:1317` vs `bot/admin/handler.py:1272`
- `select(User).where(User.telegram_id == admin_user_id)` received `user.id`.
  `users.id` and `users.telegram_id` never match, so every call raised
  `ValidationError("Admin permission required.")`.
  **Impact:** no one can be authorized → `is_authorized_driver` always `False` →
  `/register_driver` always returns `DRIVER_INVITATION_ONLY`. The entire driver
  onboarding funnel is a dead end.
- **Fix applied:** `select(User).where(User.id == admin_user_id)`, plus the
  docstring corrected to say the internal `users.id` (it previously claimed
  "Telegram ID of the admin"). Confirmed the convention: all 7 peer admin
  functions already use `User.id`; this was the sole outlier.
- **Verification:** 7 new tests. The real-database test reproduces the exact
  production failure (`ValidationError: Admin permission required.`) on the old
  code and passes on the new.

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

**#6 First-time student registration violates a NOT NULL constraint**
- `bot/student/service.py:78` — `verification_status=None` on a `nullable=False` column
- A Python-side `default` applies only when the attribute is **not supplied**; passing
  `None` explicitly sends SQL `NULL` → `IntegrityError`. This is the `else` branch of
  `register_student`, i.e. **every new student**.
- *(Reasoning from documented ORM semantics; not executed against a live DB — no 3.12 env.)*
- **Fix:** delete the argument so the column default applies. Add a regression test.

**#7 `_init_db` bypasses Alembic — migration chain unusable**
- `bot/main.py:78-92`; `alembic/versions/`
- **Fix:** delete the 20 no-op files, merge the two heads into one linear chain, generate
  a fresh baseline via `alembic revision --autogenerate` against real Postgres, replace
  `create_all` with a documented `alembic upgrade head` step in the entrypoint, and move
  the `AUTHORIZE_DRIVER` ENUM change into that migration.

### P1 — Significant

**#8 `main.py:339` un-awaited coroutine** — `if bot.set_my_commands():` creates a second
coroutine that is never awaited; always truthy, so the `Failed` branch is unreachable and
a `RuntimeWarning` is emitted per registered user at every boot. Delete the block.

**#9 `process_driver_reject` bypasses the FSM and the audit log**
- `bot/driver/handler.py:971-978` — `ASSIGNED → PENDING` is not in `ALLOWED_TRANSITIONS`
  (`state_machine.py:26-61`); no `RequestStatusLog` row is written (so `get_stats` at
  `admin/service.py:585-609` silently loses every rejection); driver `availability` is
  never reset to `AVAILABLE`; the student is never notified.
- **Fix:** add `PENDING` as a legal target of `ASSIGNED`, or add
  `RequestService.reject_assignment()`. Never call the repository from a handler.

**#10 RBAC never authorizes callbacks** — `rbac.py:171`. Add a per-router allowlist of
callback prefixes mapped to roles. Defence-in-depth for #5.

**#11 Dead admin-promotion block** — `bot/core/middlewares/auth.py:177-181` compares an
`int` against `str.split(",")`, which is always `False`. The block is unreachable; delete
it and `_ensure_admin_profile` (88-111). `main.py::_seed_admins` already does this at boot.

**#12 Admin list pagination buttons are dead** — `admin/keyboards.py:132,139,199,206` emit
`nav:…`; only `admin_req_page:` and `admin_drv_page:` handlers exist, so the ⬅️/➡️ buttons
on `pending_drivers_list_keyboard` and `drivers_list_keyboard` fall through to
`catch_all_callback` and show "Invalid input". Also rename `NavHome`'s prefix off `"nav"`
(`callback_data.py:123`) — it declares a different required field, a latent filter collision.

**#13 Double pagination on the student request list** — `request/repository.py:147-154`
applies `OFFSET/LIMIT`, then the handler re-paginates the slice
(`requests.py:609, 644`). `total_pages` is always 1, Next never renders, and page ≥ 2
returns fewer or no rows. Pick one strategy.

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
in `logging.py`. Gate behind `settings.debug_sql: bool = False`.

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

**#41** Add CI — no `.github/` exists. A minimal workflow (`uv`-based Python 3.12 install,
`ruff`, `mypy`, `pytest --cov`) would have caught #20, #8, and most of the P1 list automatically.

---

## 5. Testing

- 349 tests across 30 files under `tests/`.
- **`tests/conftest.py` now exists** (added 2026-09-27 with the #1 fix). It supplies
  a `db_session` fixture backed by in-memory SQLite — the suite's **first**
  real-database tier — and defaults the required settings so the suite can be
  collected without a hand-written `.env`. See §8.2.
- **All 4 "integration" files are still `AsyncMock`-based** — none starts Postgres,
  Redis, or a Dispatcher. They cannot reproduce any P0 (#42).
- `tests/fixtures/__init__.py` is still empty.
- **26 tests fail at baseline** (down from 34) for harness reasons, not product
  reasons — see §8.4 for the itemised list.
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
| 2026-09-26 | `chore/maintenance-doc` | Initial review + this document | #3 | Baseline established, 0 P0–P3 items closed |
| 2026-09-27 | `fix/add-driver-admin-id-column` | P0 **#1** `/add_driver` admin-column fix + first real-DB test tier (part of #32) | #4 | Fixed; suite 34→26 failures; 367→382 passing |

**Remaining backlog:** 6 × P0, 15 × P1, 11 × P2, 7 × P3 = **39 open items**.

---

## 8. Run notes — 2026-09-27 (`fix/add-driver-admin-id-column`)

### 8.1 What was verified vs. what was assumed

Item #1 was **confirmed in the code before changing anything**:
`bot/admin/handler.py:1272` calls `add_authorized_driver(..., admin_user_id=user.id)`,
while `bot/admin/service.py:1317` filtered on `User.telegram_id`. Seven peer admin
functions (`admin/service.py:370, 459, 673, 751, 829, 1134, 1255`) all use
`User.id`, so this was a clear outlier rather than a deliberate convention.

### 8.2 New infrastructure: `tests/conftest.py`

The suite had **no `conftest.py`**, which produced two real defects:

- **6 modules failed at *collection*** because `Settings` is instantiated at
  import time and requires `bot_token` / `database_url` / `redis_url`. The suite
  could not even be collected on a clean machine without a hand-written `.env`.
  `conftest.py` now `os.environ.setdefault`s placeholders *before* `bot` is
  imported, so a real environment always wins but collection never depends on it.
- **No way to test anything touching SQL.** Added a `db_session` fixture backed
  by in-memory SQLite (this is the start of item #32).

One non-obvious detail: every PK in this project is `BigInteger`, and SQLite only
applies `AUTOINCREMENT` to columns declared exactly `INTEGER PRIMARY KEY`. A
`BIGINT` PK is never populated, so every insert died with
`NOT NULL constraint failed: users.id`. `conftest.py` registers a
`@compiles(BigInteger, "sqlite")` hook that renders `INTEGER` for SQLite DDL
only. **Production models are untouched** and the Postgres schema is unaffected.

### 8.3 Effect of the new fixture, measured

Running the full suite before and after produced:

| | before | after |
|---|---|---|
| passed | 367 | **382** |
| failed | 34 | **26** |

The 26 remaining failures are a **strict subset** of the original 34 — this
change introduced **no new failures**. The 8 tests that flipped from fail to
pass are the ORM round-trip tests in `tests/unit/core/test_models.py`, which had
been failing for want of a real session.

### 8.4 Test-harness defects discovered (new backlog candidates)

These are **not** product bugs; they are broken tests. Listed here because they
inflate the failure count and hide real regressions.

- **#42 — `AsyncMock` is the wrong double for `AsyncSession` in several suites.**
  `tests/unit/student/*`, `tests/unit/driver/test_service.py` and
  `tests/integration/handlers/*` fail with
  `TypeError: 'coroutine' object does not support the asynchronous context
  manager protocol` on `async with session.begin()`. `AsyncMock` returns a
  coroutine from `begin()`, which is not an async CM. `AsyncMock(spec=AsyncSession)`
  does not fix this; these tests need the real `db_session` fixture.
  **These tests currently verify nothing** — they fail for harness reasons,
  not product reasons.
- **#43 — `TestGetStats` (`tests/unit/admin/test_service.py`) is stale.**
  Fails with `ValueError: not enough values to unpack (expected 11, got 0)`:
  the test feeds 22 scalar results, but `get_stats` now unpacks one row of 11
  aggregate columns. The test was never updated when `get_stats` was rewritten.
- **#44 — `TestRegisterDriver` / student-phase9 keyboard assertions are stale**
  against current callback and label constants.
- **#45 — `tests/integration/db/test_alembic.py` requires a live Postgres.**
  All 3 tests fail on `asyncpg.exceptions.InvalidPasswordError`. They cannot pass
  on a developer machine with no database, which is why the Alembic chain (#7) has
  never actually been exercised. **These must move behind a marker that is
  skipped when no `TEST_DATABASE_URL` is set.**

### 8.5 Packaging defect (blocks any `pip install -e .`)

`pyproject.toml:1-3` declares:

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends.legacy:build"
```

`setuptools.backends` **does not exist in any released setuptools** (checked up to
84.0.0), so `uv pip install -e .` fails outright — the project cannot be
installed in editable mode at all. The intended backend is
`setuptools.build_meta:__legacy__`. The suite only runs today because
`uv pip install -r requirements.txt` bypasses the build entirely.

**#46 — fix the build backend** to `setuptools.build_meta:__legacy__`, and move
dependencies from the UTF-16 `requirements.txt` (#20) into
`[project.dependencies]`, which is currently **empty** — the manifest declares a
package with no dependencies at all.

### 8.6 Environment note for future runs

- Provision 3.12 with `uv venv --python 3.12 .venv`, then
  `uv pip install -r requirements.txt pytest pytest-asyncio aiosqlite`.
  Do **not** rely on `uv pip install -e .` — it fails per §8.5.
- `requirements.txt` is UTF-16; `uv` reads it, most other tools will not.
- 26 pre-existing failures are the expected baseline as of this commit. Compare
  against it rather than expecting green.
