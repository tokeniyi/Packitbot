# Automation Progress

Cumulative log for scheduled daily review runs. Newest run first.
Backlog source of truth: `docs/MAINTENANCE.md` (section 4). This file tracks what each run did.

---

## Run 2026-10-31 05:47 WAT (Africa/Lagos)

**Branch:** `claude/daily-review-2026-10-31` (cut from `main` at `90525e4`; no open `claude/daily-review` PR existed to continue)
**PR:** opened against `main` at the end of this run (link in PR list)

### Starting state
- Open PRs on `tokeniyi/packitbot`: only #26 (`fix/driver-callback-error-message`), which is not a `claude/daily-review` branch and was not touched. PR #25 (the 2026-10-30 run) is merged.
- Standing issue #24 `Dev workflow requests`: no comments at all, so no owner requests this run.
- No `CLAUDE.md`. Conventions: `pytest` with asyncio auto mode (`pyproject.toml`), Python 3.12. No linter configured.

### Test environment (unblocked)
- `pypi.org` now resolves. A Python 3.12 venv installed `requirements.txt` cleanly.
- The alembic tests (`tests/integration/db/test_alembic.py`) need PostgreSQL at `localhost:5432` with user `user` / password `pass` and database `packitbot_test` (the defaults in `tests/conftest.py`). This sandbox has PostgreSQL 16 installed; it was started locally and the role and database were created. This is sandbox setup only, not a repo change.
- Baseline on `main` before this run: **11 failed, 488 passed** (without Postgres, 3 alembic tests fail with connection refused).

### Done this run
- **Test harness fixes (no production behaviour change):**
  - `tests/integration/handlers/test_request_flow.py` and `test_request_lifecycle.py`: `AsyncMock` sessions had no usable `begin_nested()`; added a `_make_session()` helper whose `begin_nested()` is an async context manager. Lifecycle test also stubs `get_by_id_for_update`.
  - `test_request_lifecycle.py::test_create_then_assign_then_transition_to_delivered`: the transition was issued by the admin (actor 3) instead of the assigned driver (users.id 7). The service correctly refused it under the P0 #5 guard; the test now uses the driver.
  - `test_request_flow.py::test_confirm_cancel_restores_driver_availability`: patched a service instance the handler never uses; now patches `RequestService.cancel_request` and `DriverRepository.get_by_user_id` on the classes.
  - `test_driver_registration_flow.py`: two tests omitted the injected `session`, so the handlers returned early; now pass `session`.
  - `tests/unit/driver/test_handler.py`: reject-routing test patched `bot.driver.handler.RequestService`, which is a local import; now patches `bot.request.service.RequestService`.
  - `tests/integration/db/test_alembic.py`: the autogenerate test left a real `*_test_rev.py` file in `alembic/versions/`, which broke `tests/unit/core/test_migrations.py` and later alembic runs. It now deletes files it created in a `finally`.
- **P0 #3 remainder (code fix):** `bot/student/handlers/feedback.py` `_recalculate_driver_rating` now sets `total_deliveries` from a count of `DeliveryRequest` rows with `status == DELIVERED` and `driver_id == users.id`. `rating_avg` still averages `Feedback.rating`. Updated `tests/unit/student/test_driver_profile_lookup.py` (two-query mock) and added `test_total_deliveries_counts_delivered_requests_not_feedback_rows`.
- **P0 #5 regression tests:** `tests/unit/driver/test_handler.py::TestDriverCallbackOwnershipGuard` (accept, reject, status step). Each drives the real `RequestService`, with a non-assigned driver, and asserts: refused with "is not the driver assigned", no commit, no message edit, status unchanged. Mutation check: with the service guard disabled, the accept and status tests fail. The reject test still passes when that guard is disabled, because `reject_assignment` does not go through `transition_status` (see Outstanding item 2).
- **Dependencies (patch level only):** `iniconfig` 2.3.0→2.3.1, `MarkupSafe` 3.0.3→3.0.4, `python-dotenv` 1.2.2→1.2.4, `pytest-asyncio` 1.4.0→1.4.1. `aiohttp` 3.14.3→3.14.5 was attempted and reverted: it requires `yarl>=1.25.1`, a transitive minor bump.
- **Files touched:** `bot/student/handlers/feedback.py`; `tests/integration/db/test_alembic.py`; `tests/integration/handlers/test_driver_registration_flow.py`; `tests/integration/handlers/test_request_flow.py`; `tests/integration/handlers/test_request_lifecycle.py`; `tests/unit/driver/test_handler.py`; `tests/unit/student/test_driver_profile_lookup.py`; `requirements.txt`; `docs/MAINTENANCE.md` (P0 #3 status and run-log row); `docs/AUTOMATION_PROGRESS.md` (this entry).

### Owner requests received this run
- None (standing issue #24 has no comments).

### Plan validation
- Not a multi-stage task this run.

### Verification
- `pytest` (full suite) on the branch with PostgreSQL 16 running and a freshly created `packitbot_test` database: **503 passed, 0 failed** (baseline on `main`: 11 failed, 488 passed).
- Targeted re-runs of the touched modules passed.
- Known caveat: the alembic tests are order-dependent on the state of `packitbot_test` (`alembic_version`). A leftover revision row breaks `downgrade base`. Recreate the database before a run if alembic tests fail with "Can't locate revision".
- No linter is configured, so none was run.

### Multi-run task status
- P0 backlog: #1 fixed; #2 fixed, regression tests already present (`test_assign_driver_rejects_driver_profile_id`, `test_assign_driver_persists_users_id`); #3 fixed (this run completes `total_deliveries`); #4 fixed, repo-level eager-load test present; #5 service enforcement + handler-level tests for accept/reject/status (this run); #6 disproved; #7 open (Alembic); #8 and #9 fixed earlier.

### Outstanding (for next run, in suggested order)
1. **Handler-level eager-load test for P0 #4:** `bot/student/handlers/requests.py:669` calls `repo.get_by_id_with_driver`. The repo test (`tests/unit/request/test_request_detail_eager_load.py`) covers the repository only. Add a test that `show_request_detail` uses that method (patch it and assert it is awaited with the request id).
2. **Reject path ownership:** `reject_assignment` does not go through `transition_status`, so the `require_assigned_driver` guard does not cover it. The new handler test still refuses an unassigned driver, so some other check in `reject_assignment` applies. Confirm which one with a service-level test. Then decide whether `reject_assignment` should enforce the actor rule explicitly.
3. **P1 #13 (double pagination on the student request list):** untouched. Start in `bot/student/handlers/requests.py` list handler; add a test that a page is fetched once.
4. **P0 #7 (Alembic):** still open per `docs/MAINTENANCE.md`. Re-check the revision chain with a clean `packitbot_test` database.
5. **Test isolation for alembic:** consider resetting the schema at the start of `tests/integration/db/test_alembic.py`. Deliberately not done in this run, because `DROP SCHEMA` against a developer's `DATABASE_URL` would be destructive. Needs an owner decision on a dedicated test database.
6. **Minor dependency updates not applied:** `aiohttp` 3.14.5 (needs `yarl` 1.25.1), `aiogram` 3.31.0, `alembic` 1.20.1, `pydantic` 2.14.2, `pydantic-core` 2.50.2, `pydantic-settings` 2.16.2, `SQLAlchemy` 2.1.6, `pytest` 9.2.0, `pluggy` 1.7.0, `Pygments` 2.21.0, `packaging` 26.3, `asyncpg` 0.32.0, `redis` 8.1.0, `Mako` 1.4.3, `typing-inspection` 0.4.4, `annotated-types` 0.8.0, `idna` 3.20, `greenlet` 3.5.6, `frozenlist`/`propcache`/`yarl` (see aiohttp), `certifi` 2026.10.23. Each needs the full suite run before it is applied; `SQLAlchemy` 2.1 is the one most likely to need code changes.
7. **Major upgrade available (not applied):** `multidict` 6.7.1 → 7.2.1.

### Found but not changed, and why
- **Open PR #26** (`fix/driver-callback-error-message`) is not part of this workflow. It was not touched.
- **Stray root files** `PENDING` (empty), `pr16_review.md`, `pr17_review.md`, and the `.agents/` and `.hermes/` directories. Left in place: deleting files is outside this run's categories and the owner should decide.
- **`.env.example`, `Dockerfile`, `docker-compose.yml`** were not reviewed for secrets (out of scope under the hard rules).
- **Attribution:** the stored task prompt names session `session_01VLAbn74n9b7QhQiKpdAp5k` for commit trailers; the session attribution guidance names `session_01VLAbn6rftGvyyxhwFRiznK`. This run used the session attribution guidance, as previous runs did. The owner should confirm which one to use.

### Major dependency upgrades available
- `multidict` 6.7.1 → 7.2.1 (major, not applied).

---

## Run 2026-10-30 05:40 WAT (Africa/Lagos)

**Branch:** `claude/daily-review-2026-10-30`
**PR:** opened against `main` at the end of this run (link in PR list)

### Starting state
- No open PRs on `tokeniyi/Packitbot` at start. PR #23 (the 2026-10-29 run) is merged into `main` (`53965c8`), so the 2026-10-29 branch has no open work. This run starts `claude/daily-review-2026-10-30` from `origin/main`.
- No `CLAUDE.md` in the repo. Conventions from `README.md`, `docs/MAINTENANCE.md` and `pyproject.toml`: `pytest` (asyncio auto mode), Python `>=3.12,<3.13`, no linter configured.
- No owner comments to act on. The standing issue "Dev workflow requests" did not exist; this run created it as issue #24, with a short explanation of how to use it.

### Test environment check (still blocked)
- `curl https://pypi.org/simple/six/` and `pip download six` both fail with `Could not resolve host` / `NameResolutionError`. `files.pythonhosted.org` also fails to resolve. The agent proxy status endpoint reports it enabled with no recent relay failures, so the block is DNS for these hosts, not TLS or proxy configuration.
- Installed Python: 3.13.18 as `python3`. No `aiogram`, `sqlalchemy` or `pytest` dependencies are installed, so the project's dependencies cannot be installed in this sandbox.
- Consequence: the suite cannot be run, so **no code was changed this run**. Per the run rules, a behaviour change needs a passing suite. This run is documentation and tracking only. It is the fifth consecutive run blocked by the same condition (2026-10-26 through 2026-10-30).

### Done this run
- Created the standing issue `Dev workflow requests` (#24).
- Confirmed that `main` (`53965c8`) already contains the 2026-10-29 progress entry and its Outstanding list, so the list below carries forward unchanged.
- **Files touched:** `docs/AUTOMATION_PROGRESS.md` (this entry), `docs/MAINTENANCE.md` (run-log row for 2026-10-30).

### Owner requests received this run
- None. The standing issue was created this run, so there were no comments to act on.

### Multi-run task status
- P0 backlog: unchanged from the 2026-10-29 run. #1 fixed; #2 handler fix present, regression test unconfirmed; #3 partly fixed (`total_deliveries` still counts Feedback rows); #4 fixed (test unconfirmed); #5 service-layer enforcement present, handler assertions and tests open; #6 disproved; #7 open (Alembic); #8 and #9 fixed earlier.

### Outstanding (for next run, in suggested order)
1. **Get the test environment working first.** Check `curl -sS -m 20 https://pypi.org/simple/six/`. If DNS still fails, the owner needs to allow `pypi.org` and `files.pythonhosted.org` for this session, or pre-install the dependencies in the environment. Until then, keep runs to docs and code reading. Check `tests/conftest.py` for fixtures before writing tests.
2. **P0 #3 remainder:** in `bot/student/handlers/feedback.py` `_recalculate_driver_rating`, change `total_deliveries` to count `DeliveryRequest` rows with `status == RequestStatus.DELIVERED` and `driver_id == driver_user_id`, not `Feedback` rows. Keep `rating_avg` on `Feedback`. Add a test in `tests/unit/student/test_driver_profile_lookup.py`.
3. **P0 #5 tests:** add a test per driver callback (`process_driver_accept` `bot/driver/handler.py:592`, `process_delivery_status_step` `:805`, `process_driver_reject` `:960`) showing that a user who is not `req.driver_id` is refused. Confirm the service raises `PermissionDeniedError` and that the handler reports it instead of crashing. Start with `tests/unit/driver/test_handler.py`.
4. **P0 #2:** add the regression test that a driver assignment persists `driver_profile.user_id`. `RequestService.assign_driver` checks `dto.driver_id != driver_profile.user_id` at `bot/request/service.py:227`. Follow `tests/unit/admin/test_service.py`.
5. **P0 #4:** confirm that `tests/unit/request/test_request_detail_eager_load.py` covers the handler's use of `get_by_id_with_driver`, and add that test if it does not.
6. **P1 #13 (double pagination on the student request list)** remains the next untouched item, once tests can run.

### Found but not changed, and why
- Stray files at the repo root: `PENDING` (empty), `pr16_review.md` and `pr17_review.md`. They look like leftovers from earlier review runs. Not removed: deleting files is outside the run's categories and the owner should decide.
- `.agents/` and `.hermes/` directories at the root were not reviewed. Out of scope for this run.
- `.env.example`, `Dockerfile` and `docker-compose.yml` were not reviewed for secrets. Out of scope under the run rules (secrets and deployment config).
- Attribution: the stored task prompt names a different session ID for commit trailers from the one in the session's attribution guidance. This run used the session's attribution guidance (`session_01VLAbn3EZQoBvnhTarrJKt2`), as previous runs did. The owner should confirm which one to use.

### Major dependency upgrades available
- None checked this run (no network access to PyPI, so resolution against the lock state was not possible).

---

## Run 2026-10-29 05:40 WAT (Africa/Lagos)

**Branch:** `claude/daily-review-2026-10-29`
**PR:** opened against `main` at the end of this run (link in PR list)

### Starting state
- No open PRs on `tokeniyi/Packitbot` at start. PR #22 (the 2026-10-28 run) is merged, so there was no open `claude/daily-review` work to continue. This run starts a new branch from `origin/main` (`105c044`).
- No `CLAUDE.md` in the repo. Conventions from `README.md`, `docs/MAINTENANCE.md` and `pyproject.toml`: `pytest` (asyncio auto mode), Python `>=3.12,<3.13`, no linter configured.
- No owner comments to act on (no open PRs).

### Test environment check (still blocked)
- `pypi.org`, `files.pythonhosted.org` and `registry.npmjs.org` do not resolve in the sandbox (`Could not resolve host`), including when routed through `HTTPS_PROXY`. Nothing is in the uv cache, so an offline install of `requirements.txt` also fails.
- Only Python 3.12.3 (`/usr/bin/python3.12`) and 3.13 exist, with no project dependencies (no `aiogram`, `sqlalchemy`, `pytest-asyncio`, etc.).
- Consequence: the suite cannot be run, so **no code was changed this run**. Per the run rules, a behaviour change needs a passing suite. This run is documentation only.

### Done this run
- **Re-verified outstanding items by reading code** (no execution):
  - P0 #3 remainder: `bot/student/handlers/feedback.py` `_recalculate_driver_rating` (lines ~28-46) still computes `total_deliveries = count(Feedback.id)`. Still open. The profile lookup already uses `DriverRepository.get_by_user_id`.
  - P0 #3 cancellation path: `bot/student/handlers/requests.py:1012-1017` already uses `get_by_user_id`. Done.
  - P0 #5: `bot/driver/handler.py:765` filters on `DeliveryRequest.driver_id == driver_user.id`. Service-layer guard unchanged. Handler-level assertions for `process_driver_accept` (line 592), `process_delivery_status_step` (805) and `process_driver_reject` (960) are still not verified or tested.
  - Existing test files that the next run should look at first: `tests/unit/student/test_driver_profile_lookup.py` (P0 #3), `tests/unit/request/test_request_detail_eager_load.py` (P0 #4), `tests/unit/driver/test_handler.py` (P0 #5).
- **Files touched:** `docs/AUTOMATION_PROGRESS.md` (this entry), `docs/MAINTENANCE.md` (run-log row for 2026-10-29).

### Owner requests received this run
- None.

### Multi-run task status
- P0 backlog: #1 fixed; #2 handler fix present, regression test unconfirmed; #3 partly fixed (`total_deliveries` still counts Feedback rows); #4 fixed (test unconfirmed); #5 service-layer enforcement present, handler assertions and tests open; #6 disproved; #7 open (Alembic); #8 and #9 fixed earlier.

### Outstanding (for next run, in suggested order)
1. **Get the test environment working first.** Check `curl -sS -m 20 https://pypi.org/simple/six/`. If DNS still fails, record it again and keep the run to docs and code reading. Check `tests/conftest.py` for fixtures before writing tests.
2. **P0 #3 remainder:** in `bot/student/handlers/feedback.py` `_recalculate_driver_rating`, change `total_deliveries` to count `DeliveryRequest` rows with `status == RequestStatus.DELIVERED` and `driver_id == driver_user_id`, not `Feedback` rows. Keep `rating_avg` on `Feedback`. Add a test in `tests/unit/student/test_driver_profile_lookup.py`.
3. **P0 #5 tests:** add a test per driver callback (`process_driver_accept` `bot/driver/handler.py:592`, `process_delivery_status_step` `:805`, `process_driver_reject` `:960`) showing that a user who is not `req.driver_id` is refused. Confirm the service raises `PermissionDeniedError` and that the handler reports it instead of crashing. Start with `tests/unit/driver/test_handler.py`.
4. **P0 #2:** add the regression test that a driver assignment persists `driver_profile.user_id`. `RequestService.assign_driver` checks `dto.driver_id != driver_profile.user_id` at `bot/request/service.py:227`, so the test can target that guard. Follow `tests/unit/admin/test_service.py`.
5. **P0 #4:** confirm that `tests/unit/request/test_request_detail_eager_load.py` covers the handler's use of `get_by_id_with_driver` and, if it does not, add that test.
6. **P1 #13 (double pagination on the student request list)** remains the next untouched item, once tests can run.

### Found but not changed, and why
- Stray files at the repo root: `PENDING` (empty), `pr16_review.md` and `pr17_review.md`. They look like leftovers from earlier review runs. Not removed: deleting files is outside the run's categories and the owner should decide.
- `.agents/` and `.hermes/` directories at the root were not reviewed. Out of scope for this run.
- `.env.example`, `Dockerfile` and `docker-compose.yml` were not reviewed for secrets. Out of scope under the run rules (secrets and deployment config).
- Attribution conflict: the stored task prompt names session `session_01BhvGjTBnhBeh2ZstJXiYE8` for commit trailers, but the session's attribution guidance names `session_01VLAbn6U2cxdRHHScNrVuK2`. This run used the attribution guidance given in the session, as the previous runs did. The owner should confirm which one to use.

### Major dependency upgrades available
- None checked this run (no network access to PyPI, so resolution against the lock state was not possible).

---

## Run 2026-10-28 05:40 WAT (Africa/Lagos)

**Branch:** `claude/daily-review-2026-10-28`
**PR:** opened against `main` at the end of this run (link in PR list)

### Starting state
- No open PRs on `tokeniyi/Packitbot`. PR #21 (the 2026-10-27 run) is merged. Its branch `claude/daily-review-2026-10-27` still exists on the remote but has no open PR, so this run starts a new branch.
- No `CLAUDE.md` in the repo. Conventions from `README.md`, `docs/MAINTENANCE.md` and `pyproject.toml`: `pytest` (asyncio auto mode), Python `>=3.12,<3.13`, no linter configured.
- No owner comments to act on (no open PRs).

### Test environment check (still blocked)
- A Python 3.12.3 venv can be created with `uv`, but PyPI is unreachable: `pypi.org` does not resolve in the sandbox and the proxy does not route it. `aiogram`, `sqlalchemy`, `pytest-asyncio` and the other dependencies are not installed. Only `pytest` and `pydantic` exist, under system Python 3.13.
- Consequence: the suite cannot be run, so **no code was changed this run**. Per the run rules, a behaviour change needs a passing suite. This run is documentation only.

### Done this run
- **Re-verified outstanding P0 items against current code** (the code had moved on from the backlog text):
  - P0 #3: cancellation availability restore and feedback rating recalculation now resolve through `DriverRepository.get_by_user_id`. `total_deliveries` still counts `Feedback` rows, so that part is still open.
  - P0 #4: fixed. `RequestRepository.get_by_id_with_driver` uses `selectinload` on both hops.
  - P0 #5: largely fixed at the service layer. `require_assigned_driver` defaults to `True` and `transition_status` / `reject_assignment` enforce it. Still open: explicit handler-level assertion, and regression tests for the three callbacks.
- **Files touched:** `docs/MAINTENANCE.md` (status text for P0 #3, #4, #5 and a run-log row), `docs/AUTOMATION_PROGRESS.md` (this entry).

### Owner requests received this run
- None.

### Multi-run task status
- P0 backlog: #1 fixed; #2 handler fix present, regression test still unconfirmed; #3 partly fixed (`total_deliveries` open); #4 fixed (test unconfirmed); #5 service-layer enforcement present, handler assertion and tests open; #6 disproved; #7 open (Alembic); #8 and #9 fixed earlier.

### Outstanding (for next run, in suggested order)
1. **Get the test environment working first.** Check whether PyPI is reachable (`pip download six`). If it is not, record it again and limit the run to docs and reading code. Check `tests/conftest.py` (108 lines, now present; the backlog said it was missing) so the next run knows what fixtures exist.
2. **P0 #3 remainder:** `bot/student/handlers/feedback.py` `_recalculate_driver_rating` (~line 42) should count `DeliveryRequest` rows with `status == DELIVERED` for `total_deliveries`, not `Feedback` rows. Add a unit test in `tests/unit/student`.
3. **P0 #5 tests:** add a test per driver callback (`process_driver_accept` in `bot/driver/handler.py` ~592, `process_delivery_status_step` ~776, `process_driver_reject` ~960) showing that a user who is not `req.driver_id` is refused. Confirm the service raises `PermissionDeniedError` and that the handler reports it to the user instead of crashing.
4. **P0 #2:** add the regression test that a driver assignment persists `driver_profile.user_id`. `RequestService.assign_driver` already checks `dto.driver_id == driver_profile.user_id` (`bot/request/service.py:227`), so the test can target that guard.
5. **P0 #4:** add a regression test that the request detail handler uses `get_by_id_with_driver`.
6. **P1 #13 (double pagination on the student request list)** remains the next untouched item, once tests can run.

### Found but not changed, and why
- `docs/MAINTENANCE.md` section 4 P0 headers and section 1.3 still describe older state in places. Section 1.3 says the Alembic chain has a single head, which was re-verified on 2026-10-26; that claim has not been re-checked since.
- `pyproject.toml` declares `setuptools.build_meta` (fine), but the MAINTENANCE doc mentions a different backend in the environment note. Not re-verified without a working install.
- Attribution: the commit trailer session ID in the stored task prompt (`session_01BhvGjTBnhBeh2ZstJXiYE8`) differs from the one in the session's attribution guidance (`session_01VLAbn4mmeXXRfBsKVyJ5Xn`). This run used the session's attribution guidance. The owner should confirm which one to use.
- `.env.example`, `Dockerfile`, `docker-compose.yml` not reviewed for secrets. Out of scope under the run rules.

### Major dependency upgrades available
- None checked this run (no network access to PyPI, so resolution against the lock state was not possible).

---

## Run 2026-10-27 05:39 WAT (Africa/Lagos)

**Branch:** `claude/daily-review-2026-10-27`
**PR:** opened against `main` at the end of this run (link in PR list)

### Starting state
- No open PRs on `tokeniyi/Packitbot`. Remote has only `main` (HEAD `f1ff944`). No `claude/daily-review-*` branches remained, so this is a fresh branch.
- `docs/AUTOMATION_PROGRESS.md` did not exist; created by this run.
- No `CLAUDE.md` in the repo. Conventions taken from `README.md`, `docs/MAINTENANCE.md` and `pyproject.toml`: `pytest` (asyncio auto mode), no linter configured, Python 3.12.
- No owner comments to act on (no open PRs).

### Done this run
- **Stale-status correction in `docs/MAINTENANCE.md`:**
  - P0 #1 (`/add_driver` admin lookup by `telegram_id`) is fixed on `main` by commit `dbf4ba8`. `bot/admin/service.py:1317` uses `User.id`, and `tests/unit/admin/test_service.py` covers it. Backlog header marked FIXED.
  - P0 #2 (driver assignment writes `DriverProfile.id` into `users.id`): the handler fix is present at `bot/admin/handler.py:337` (`driver_id=driver_profile.user_id`). Marked as handler-fixed, with a note to confirm a regression test and to check that `AvailableDriverDTO.driver_id` is never persisted.
  - Added a run-log row for 2026-10-27 to section 7.
- **Files touched:** `docs/MAINTENANCE.md`, `docs/AUTOMATION_PROGRESS.md` (new).

### Not done, and why
- **No code changes and no test run.** The sandbox could not install dependencies: PyPI requests through the agent proxy return `403 Forbidden` (policy denial, not retried per proxy guidance), so `pytest` cannot run. Per the run rules, no behavior change is committed without a passing suite. Work that needs code changes is recorded below as outstanding.
- Owner requests: none received (no PRs open).

### Owner requests received this run
- None.

### Multi-run task status
- P0 backlog (per MAINTENANCE.md, after this correction): #3, #4, #5, #7 open. #1 fixed, #2 handler-fixed pending a test, #6 disproved, #8 and #9 fixed earlier.
- P1: #10 and #14 fixed in prior runs (PRs #18, #19). #12 and #11 fixed. #22 partial. Others open as listed in MAINTENANCE.md.

### Outstanding (for next run, in suggested order)
1. **Confirm P0 #2 is closed:** add a regression test that a driver assignment persists `driver_profile.user_id` (not the profile PK), using the `tests/unit/admin` test style. Check `AvailableDriverDTO.driver_id` usages in `bot/admin/service.py` (lines ~193, 263, 316, 407, 496, 1017, 1074, 1201).
2. **P0 #3:** `bot/student/handlers/requests.py:1012` and `bot/student/handlers/feedback.py:28, 35, 189` re-query `DriverProfile` with a `users.id`. Fix via `DriverRepository(session).get_by_user_id(...)` and add a test. Separately, `total_deliveries` should count `DeliveryRequest` rows with status DELIVERED, not `Feedback` rows (`feedback.py:33-41`). Verify the current code before editing; the line numbers may have drifted.
3. **P0 #4:** `MissingGreenlet` on request detail. Add `selectinload` options at `bot/student/handlers/requests.py:668`. Verify first.
4. **P0 #5 (security, highest severity):** no ownership check on driver callbacks (`bot/driver/handler.py:567, 776, 927`). Fix by asserting `req.driver_id == driver_user.id` before mutating, and ideally enforce the actor rule inside `RequestService.transition_status`. Needs careful tests. Requires a working test run.
5. **Test environment:** the test suite cannot run in this sandbox because PyPI is blocked by the proxy. Next run should first check whether `pip install -r requirements.txt` works. If it does not, record it again and limit the run to documentation work.

### Found but not changed
- `.env.example`, `Dockerfile` and `docker-compose.yml` were not reviewed for secrets this run. Out of scope for the run's rules (secrets and deployment config are not to be touched).
- `docs/MAINTENANCE.md` section 1.3 still says `alembic.ini` has the placeholder URL and that `_init_db` bypasses Alembic. Not re-verified this run.
- Credential note: the stored task prompt names session `session_01BhvGjTBnhBeh2ZstJXiYE8` for commit trailers, but the session's attribution guidance names `session_01VLAbn6kMdgWgSvgdZ1cjhW`. This run used the attribution guidance given in the session. Owner should confirm which one to use.

### Major dependency upgrades available
- None checked this run (dependency resolution was not possible without network access to PyPI).
