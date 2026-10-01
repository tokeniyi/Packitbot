# Packitbot — Maintenance & Development Backlog

> **This document is the source of truth for automated daily development runs.**
> It is updated on every task branch. Daily runs must re-read it *and* the code
> before choosing work — never trust a previous run's analysis.

- **Repository:** `tokeniyi/Packitbot`
- **Description:** Async Telegram logistics and delivery management bot (aiogram 3.x, SQLAlchemy 2.0)
- **Default branch:** `main` (protected — never pushed to directly)
- **Scale:** 130 Python files, ~14.7k LOC application code
- **Review baseline:** commit `2e31ff9`
- **Last reviewed:** 2026-09-26

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

- **6 P0 open** (was 7 — #6 was retracted as unfounded on 2026-10-01).
  Four are already in open PRs and awaiting review:
  - #0 `users.id` autoincrement on SQLite — PR #8
  - #1 `/add_driver` compares `users.id` against `telegram_id` — PR #4
  - #2 driver assignment writes `DriverProfile.id` into a `users.id` FK — PR #5
  - #3 `session.get(DriverProfile, <users.id>)` on cancel/feedback — PR #6
  - #5 no ownership check on driver callbacks — PR #7
  **These five PRs are all unmerged and have sat open for 1–5 days. Merging
  them is the single highest-value action available; they block 5 of the 6
  remaining P0 items.**
- **#4 `MissingGreenlet` on request detail — FIXED 2026-10-01 (PR #9).**
  The only open P0 with no PR, and the only one fixed to date.
- **#7 Alembic chain unusable — now the sole un-PR'd P0.** Highest-risk
  remaining item: it blocks #28 (unique index) and all future schema work.
- **1 critical security finding still open** — no ownership check on the three
  driver delivery callbacks. `RBACMiddleware` structurally cannot catch this
  because it inspects only slash-commands. Fix is in flight as PR #7.
- **Alembic is non-functional** (above).
- **The test suite cannot catch most of the above.** All 4 "integration" files
  are `AsyncMock`-based; none starts Postgres, Redis, or a Dispatcher. No
  `conftest.py`; `tests/fixtures/__init__.py` is empty.
- **Known baseline: 34 tests fail on `main` (372 pass) as of 2026-10-01.**
  These are pre-existing and unrelated to any single task — stale mock
  expectations (`AsyncMock` used where a real `Result` is needed), and
  `tests/integration/db/` requiring a live Postgres. **Establish this baseline
  before changing anything**, or you cannot prove a fix helped.
- **Real-database tests are possible and cheap.** `aiosqlite` is already a
  dependency and `Base.metadata.create_all` works. A file-backed SQLite engine
  (`poolclass=NullPool`) reproduces ORM-level bugs like #4 with no server.
  Prefer this over `AsyncMock` for anything touching ORM semantics.
- **Architectural drift.** Only `bot/request/` follows the layering in
  `.agents/rules/GEMINI.md`. The recurring `users.id` vs `DriverProfile.id` vs
  `telegram_id` ambiguity is the root cause of the P0 cluster.

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

**#4 `MissingGreenlet` on "view request detail"** — **FIXED 2026-10-01, PR #9**
- `bot/student/handlers/requests.py:668` (load) and `:141-147` (lazy access)
- `req.driver` / `req.driver.driver_profile` lazy-load outside an awaited context →
  `MissingGreenlet` (a subclass of `InvalidRequestError`, **not** `PackitbotError`),
  so it bypasses the global handler and shows a generic error.
- **Fix applied:** added `RequestRepository.get_by_id_with_driver()`
  (`bot/request/repository.py:60-95`) using
  `selectinload(DeliveryRequest.driver).selectinload(User.driver_profile)`;
  `show_request_detail` now calls it instead of `get_by_id`.
  A plain `get_by_id` was left untouched because other callers depend on its
  current shape.
- **Regression tests:** `tests/unit/request/test_request_detail_eager_load.py`
  (5 tests, real SQLite). Verified they genuinely catch the bug: with the
  method present but the `selectinload` removed, 2 fail with `MissingGreenlet`.
- *Still to check:* `driver/handler.py:637` (`driver = req.driver`) already
  eager-loads via `selectinload` at :625-632, so that site is safe.

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

**#6 Student registration NOT NULL violation — RETRACTED 2026-10-01, NOT A BUG**
*Originally listed as a P0. Empirically disproved. Do not "fix" it.*
- `bot/student/service.py:78` passes `verification_status=None` to a
  `nullable=False` column carrying `default=VerificationStatus.UNVERIFIED`.
- The original claim was "a Python-side `default` applies only when the
  attribute is **not supplied**, so passing `None` sends SQL `NULL` and every
  new student raises `IntegrityError`". That is **incorrect for SQLAlchemy 2.0**
  declarative models. Verified against a real SQLite database:
  - DDL emitted: `verification_status VARCHAR(10) NOT NULL`
  - explicit `verification_status=None` → **committed**, stored `'UNVERIFIED'`
  - argument omitted entirely → **committed**, stored `'UNVERIFIED'`
  - no `IntegrityError` in either case
- A non-`Optional` `Mapped[T]` column receives its default even when explicitly
  set to `None`; the "not supplied" rule is a Python-side-`default` nuance that
  does not apply to a plain column `default=`.
- **Left as-is.** Deleting the argument is a harmless readability cleanup only
  (folded into P3 #42).
- **Lesson:** this item sat in P0 for 5 days on reasoning alone, with no test
  and no 3.12 environment. It was never verified. Verify before fixing.

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

**#42 Drop the redundant `verification_status=None` argument** — `bot/student/service.py:78`.
Cosmetic only (the retracted #6 proved it is harmless), but it reads as a bug and
invites a future "fix". Removing it costs nothing.

**#43 Repair the 34 pre-existing test failures** — mostly stale mock
expectations. Representative: `tests/unit/request/test_repository.py:51,66` mock
`scalar_one_or_none()` but the code calls `.scalars().first()`; the
`TestRegisterDriver` group and the `test_*_round_trip` group fail for the same
reason. **Do this before any further work** — while the suite is red you cannot
prove a new fix did not break something else. Compare the FAILED list before and
after, never just the pass count.

**#44 Move `docs/MAINTENANCE.md` onto `main`** — the doc has lived only on
`chore/maintenance-doc` (PR #3, open since 2026-09-26). A source-of-truth
document that is branch-resident silently disappears on every fresh checkout:
`read_file docs/MAINTENANCE.md` fails on `main` today, and the run had to use
`git show origin/chore/maintenance-doc:docs/MAINTENANCE.md`. Note this PR does
carry the doc, so merging it resolves both #44 and PR #3 at once.

---

## 5. Testing

- 377 tests across 30 files under `tests/` (372 pass, 34 fail — see #43).
- **Baseline on `main` at commit `2e31ff9`: 34 failed / 367 passed.** Re-verify
  with `.venv/Scripts/python.exe -m pytest -q` before and after any change and
  `diff` the FAILED lists — equal counts can hide a swapped failure.
- **All 4 "integration" files are `AsyncMock`-based** — none starts Postgres,
  Redis, or a Dispatcher. They cannot reproduce any P0.
- No `conftest.py`; `tests/fixtures/__init__.py` is empty.
- **What does work:** real SQLite via `aiosqlite` (already a dependency).
  `tests/unit/core/test_models.py` and the new
  `tests/unit/request/test_request_detail_eager_load.py` both use it. A
  file-backed engine with `poolclass=NullPool` is the pattern — an in-memory
  `:memory:` DB with `NullPool` gives each connection its own empty schema.
- **Coverage gaps:** the entire DB persistence layer, all middleware (auth, RBAC,
  throttling, session), every service→repository interaction, and the FSM's real
  enforcement.
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
| 2026-09-26 | `fix/add-driver-admin-id-column` | P0 #1 `/add_driver` admin lookup | #4 | Open |
| 2026-09-27 | `fix/assign-driver-wrong-fk` | P0 #2 driver assignment FK | #5 | Open |
| 2026-09-28 | `fix/driver-profile-lookup-by-user-id` | P0 #3 `DriverProfile` lookup | #6 | Open |
| 2026-09-29 | `fix/driver-callback-ownership-check` | P0 #5 callback ownership | #7 | Open |
| 2026-09-30 | `fix/user-pk-sqlite-autoincrement` | P0 #0 `users.id` autoincrement | #8 | Open |
| 2026-10-01 | `fix/request-detail-missing-greenlet` | **P0 #4 `MissingGreenlet` on request detail** | #9 | **Fixed.** 5 real-DB regression tests added. 34 failed / 372 passed vs baseline 34 failed / 367 passed — FAILED set identical. Also **retracted P0 #6 as unfounded** and added #42–#44. |

**Remaining backlog:** 5 × P0 (all in open PRs except #7), 15 × P1, 12 × P2,
10 × P3 = **42 open items** (1 fixed, 1 retracted).

**Recommended next actions, in order:**
1. **Merge PRs #3–#9.** Five P0 fixes plus this doc are sitting unmerged.
2. **#7 (Alembic)** — the last un-PR'd P0, and it gates #28.
3. **#43 (repair the 34 failures)** — do this before more feature work.
4. **#5 security fix (PR #7)** is the highest-severity item in the whole backlog.
