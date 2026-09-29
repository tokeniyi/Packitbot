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

- **7 P0 bugs.** Three break the product outright: `/add_driver` never authorizes
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

**#5 No ownership check on driver delivery callbacks** *(most severe)* — ✅ **FIXED 2026-09-29**
- `bot/driver/handler.py:567` (`process_driver_accept`), `:776` (`process_delivery_status_step`),
  `:927` (`process_driver_reject`); enabler at `bot/core/middlewares/rbac.py:171`
- `RBACMiddleware._extract_command` returns `""` for non-slash-command messages and
  rbac.py:171 gates only `if command:` — **callbacks are never role-checked**.
  The state machine blocks illegal *transitions*, never illegal *actors*.
- **Impact:** any Telegram user who guesses a sequential request ID can accept, advance,
  reject, or complete **any** delivery — and the two `send_message` calls at
  `driver/handler.py:660-672` hand them the student's name and phone number.
- **Fix applied:** added `can_driver_act_on_request(request, actor_id)` to
  `bot/request/business_rules.py` (pure predicate, matching the module's existing style)
  and enforced it **inside** `RequestService.transition_status`, so `process_driver_accept`
  and `process_delivery_status_step` are covered by construction and future callers cannot
  bypass it. `process_driver_reject` mutates through `RequestRepository` and does not call
  the service, so it carries an explicit guard in the handler.
  `TransitionDTO.require_assigned_driver` defaults to `True` (fail-closed); a caller with a
  different authorisation basis (e.g. an admin override) may pass `False`.
- **Verified empirically:** with the pre-fix code an attacker (`users.id=999`) accepting
  request #7 (`ASSIGNED -> ACCEPTED`, a *legal* transition) succeeded and wrote the change;
  with the fix the same call raises `PermissionDeniedError` with no write attempted, while
  the legitimate assigned driver (`users.id=3`) still succeeds.
- **Residual:** RBAC still never authorizes callbacks (#10). The service-level guard closes
  the exploit for the three mutation handlers; other callbacks remain unclassified.

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
| 2026-09-27 | `fix/assign-driver-wrong-fk` | P0 #2 — assignment writes the wrong FK | #5 | Open |
| 2026-09-28 | `fix/driver-profile-lookup-by-user-id` | P0 #3 — `DriverProfile` looked up by `users.id` | #6 | Open |
| 2026-09-29 | `fix/driver-callback-ownership-check` | P0 #5 — no ownership check on driver callbacks | #7 | Open; 34 pre-existing failures unchanged, +8 tests |

## 8. Run notes — 2026-09-29

**Corrections to this document (it was stale or wrong):**

1. **`docs/MAINTENANCE.md` does not exist on `main`.** It was introduced in the still-open
   PR #3 (`chore/maintenance-doc`) and was never merged. A run that trusts this document
   without checking will find no file at all. The copy on this branch is carried forward from
   PR #3; **PR #3 should be merged first** so subsequent runs have a single source of truth.
2. **`main` is not green.** A baseline `pytest` run on `main` at commit `2e31ff9` gives
   **34 failed, 367 passed**. The 34 failures are pre-existing and span
   `tests/unit/core/test_models.py` (8), `tests/unit/student/*` (8),
   `tests/unit/driver/test_service.py` (5), `tests/integration/db/test_alembic.py` (3),
   `tests/unit/admin/test_service.py` (2), `tests/unit/request/test_repository.py` (2),
   plus 6 singletons (`tests/integration/handlers/*` ×3, `tests/unit/admin/test_keyboards.py`,
   `tests/unit/core/test_middlewares.py`, `tests/unit/driver/test_keyboards.py`).
   The `test_models.py` failures are `sqlalchemy.exc` errors consistent with the broken
   model import in item 4 below.
   The section 5 claim of "342 tests, all passing" is **wrong**. Daily runs must diff their
   failure set against this baseline rather than assuming a red run means a regression.
3. **The 3.12 environment already exists** at `.venv` (Python 3.12.7, pytest 9.1.1) and is
   usable directly — `uv venv` is not needed on subsequent runs.
4. **Uncommitted model edits are sitting in the working tree** on this branch's base
   (`bot/core/models/*.py`, 9 files — adding `autoincrement=True` to primary keys). These are
   **not** part of any PR and were deliberately left uncommitted by this run.
   **One of them is broken:** `bot/core/models/student_profile.py:67` uses `Integer` without
   importing it, so `from bot.core.models.delivery_request import DeliveryRequest` raises
   `NameError` and the models cannot be imported at all in a clean checkout. Fix or revert
   these edits before relying on the model layer.

**Newly discovered problems:**

5. **Ownership must be enforced in the service, not the handler.** The backlog's suggested fix
   for #5 ("in each handler assert `req.driver_id == driver_user.id`") is insufficient:
   `process_driver_reject` calls `RequestRepository.update` directly, and the next caller
   added will do the same. The rule now lives in `RequestService.transition_status` with
   `TransitionDTO.require_assigned_driver=True` as the fail-closed default.
6. **The state machine masks the ownership hole.** A request in `ASSIGNED` cannot jump to
   `DELIVERED`, so a naive reproduction of #5 looks already-fixed. The exploit uses *legal*
   transitions (`ASSIGNED -> ACCEPTED`, then `ACCEPTED -> ... -> DELIVERED`). Any future
   regression test must use a legal transition or it will pass for the wrong reason.
7. **`PermissionDeniedError` is a subclass of `PackitbotError`**, so the driver handlers'
   existing `except PackitbotError` branch already renders it as a user-facing alert. No
   changes were needed in `main.py`'s global handler.

**Remaining backlog:** 6 × P0, 15 × P1, 12 × P2, 7 × P3 = **40 open items**.

**Next highest-value item:** P0 #4 (`MissingGreenlet` on "view request detail",
`bot/student/handlers/requests.py:668`) — still open, unblocked, and cheap to verify.
#6 and #7 remain; #7 (Alembic) is still the structural blocker but is a large task.
