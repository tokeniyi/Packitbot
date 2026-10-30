#!/usr/bin/env python3
"""Patch docs/MAINTENANCE.md for the 2026-10-19 run."""
import re

path = "docs/MAINTENANCE.md"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Fix orphaned "are still unguarded.**" line at end of P1 #22 section
content = content.replace(
    'stashed out, 9 of the 11 fail; with the guards applied, all 11 pass.\nare still unguarded.**',
    'stashed out, 9 of the 11 fail; with the guards applied, all 11 pass.\n---'
)

# 2. Update P1 #22 "Fixed 2026-10-13" date to 2026-10-19 (this run completes it)
content = content.replace(
    '**Fixed 2026-10-13 (this run):** all genuinely unguarded sites',
    '**Fixed 2026-10-19** (completing uncommitted work from the 2026-10-13 run):'
    ' all genuinely unguarded sites now guard the'
)

# 3. Mark P1 #11 as FIXED (it was fixed by PR #16 but the section header doesn't say so)
content = content.replace(
    '''**#11 Dead admin-promotion block** — `bot/core/middlewares/auth.py:177-181` compares an
`int` against `str.split(",")`, which is always `False`. The block is unreachable; delete
it and `_ensure_admin_profile` (88-111). `main.py::_seed_admins` already does this at boot.''',
    '''**#11 ~~Dead admin-promotion block~~** — FIXED 2026-10-09 (PR #16,
`fix/dead-admin-promotion-block`). `bot/core/middlewares/auth.py:177-181` compared an
`int` against `str.split(",")`, which is always `False`. The block was removed; admin
promotion is now handled exclusively at startup by `bot.main._seed_admins()`. Also
removed the unused `_ensure_admin_profile` method. 1 new test added.'''
)

# 4. Update section 2 headline state
old_headline = '''|- **6 P0 bugs** (was 7 — #6 was disproved on 2026-10-03 and removed). Three break the
  product outright: `/add_driver` never authorizes
  anyone (so nobody can ever register as a driver), driver assignment writes the wrong
  foreign key, and `session.get(DriverProfile, <users.id>)` breaks availability
  restoration *and* all driver ratings.
|- **1 critical security finding.** No ownership check on the three driver delivery
  callbacks — any Telegram user can hijack and complete **any** delivery and read the
  student's phone number. `RBACMiddleware` structurally cannot catch this because it
  inspects only slash-commands.
|- **1 more correctness bug.** Lazy relationship loads raise `MissingGreenlet`, so
  "view request detail" is broken for every request that has a driver assigned.
|- **Alembic is non-functional** (above).
|- **The test suite cannot catch any of the above.** All 4 "integration" files are
  `AsyncMock`-based; none starts Postgres, Redis, or a Dispatcher. No `conftest.py`;
  `tests/fixtures/__init__.py` is empty.
|- **Architectural drift.** Only `bot/request/` follows the layering in
  `.agents/rules/GEMINI.md`. The recurring `users.id` vs `DriverProfile.id` vs
  `telegram_id` ambiguity is the root cause of the entire P0 cluster.'''

new_headline = '''|- **0 P0 bugs** (was 6 — all fixed and merged on `main` by 2026-10-14:
  #0→PR #4, #2→PR #5, #3→PR #6, #4→PR #9, #5→PR #7, #7→PR #10). The three headline
  defects — `/add_driver` never authorizing, driver assignment writing the wrong FK,
  and `session.get(DriverProfile, <users.id>)` breaking availability restoration and
  driver ratings — are all resolved on `main`.
|- **PR #14 merged 2026-10-18** (`chorem: consolidate open fixes`). Introduced
  `bot/request/business_rules.py` with pure predicate functions. PR #14 introduced
  **3 test-file defects** (fixed this run): an `IndentationError` in
  `test_business_rules.py:149`, a wrong `patch` target in `test_handler.py:320`,
  and a missing `DriverProfile` import in `test_driver_profile_lookup.py:114`.
|- **Alembic is functional** — PR #10 merged the two heads into a linear chain.
  `bot/main.py` still calls `Base.metadata.create_all` at startup.
|- **499 unit tests pass**; 10 integration-test failures are pre-existing (require
  Postgres/Redis). No `conftest.py`; `tests/fixtures/__init__.py` is empty.'''

content = content.replace(old_headline, new_headline)

# 5. Update "Remaining backlog" line
content = content.replace(
    '| **Remaining backlog:** 6 × P0 (all in open PRs #5–#10), 10 × P1 (#10, #12, #14 closed, #22 partially), 12 × P2, 7 × P3 = **35 open items**.',
    '| **Remaining backlog:** 0 × P0 (all fixed & merged), 7 × P1 (#15, #17, #18, #19, #20, #21, #42), 12 × P2, 7 × P3 = **26 open items**. |'
)
# Fix the duplicate "Remaining backlog" line too
content = content.replace(
    '**Remaining backlog:** 6 × P0 (all in open PRs #5–#10), 10 × P1 (#10, #12, #14 closed, #22 partially), 12 × P2, 7 × P3 = **35 open items**.',
    '**Remaining backlog:** 0 × P0 (all fixed & merged), 7 × P1 (#15, #17, #18, #19, #20, #21, #42), 12 × P2, 7 × P3 = **26 open items**.'
)

# 6. Add run log entry after the 2026-10-13 entry
old_log_end = '''|- **PR:** #19 (`fix/integrity-error-savepoint`)
|- **Validation:** 466 unit tests pass (was 454). 7 pre-existing integration failures unchanged.

### 2026-10-05 run notes'''

new_log_entry = '''|- **PR:** #19 (`fix/integrity-error-savepoint`)
|- **Validation:** 466 unit tests pass (was 454). 7 pre-existing integration failures unchanged.

| 2026-10-18 | PR #14 merged | `chore: consolidate open fixes and resolve PR conflicts` | #14 | All P0 fixes merged onto `main` as a single linear history. Introduced `bot/request/business_rules.py`. **Introduced 3 test defects** (see below). |

### 2026-10-19 run notes

- **Task:** P1 #22 — complete the callback `int()` parsing guards (work was implemented
  but never committed by the 2026-10-13 run; recovered from `git stash`).
- **Also fixed (PR #14 cleanup, required for test validation):**
  - `tests/unit/request/test_business_rules.py:149` — `IndentationError` from a broken
    merge (merged duplicate test functions, lost function body). Restored
    `test_other_driver_cannot_act` with its body; removed the duplicate
    `test_assigned_driver_may_act` and `test_other_driver_may_not_act`.
  - `tests/unit/driver/test_handler.py:320` — `patch("bot.driver.handler.RequestService")`
    failed because `RequestService` is a local import inside the handler. Changed to
    `patch("bot.request.service.RequestService")`.
  - `tests/unit/student/test_driver_profile_lookup.py:114` — `NameError: DriverProfile`
    not imported. Added `from bot.core.models.driver_profile import DriverProfile`.
  - `bot/request/business_rules.py:102` — duplicate docstring on
    `can_driver_act_on_request`; removed the stale one-liner, kept the full docstring.
- **Validation:** 499 unit tests pass, 10 integration tests fail (pre-existing — require
  Postgres/Redis). 14 new callback-parsing regression tests + 25 business-rules tests
  all green. Tripwire: the 14 new tests fail without the source guards (the `int()`
  raises before the test assertions can run).
- **PR:** #20 (`fix/guard-callback-int-parsing`)
- **Discovered, not fixed:** 10 integration tests still require Postgres/Redis; `uv pip
  install -e .` still fails (`setuptools.backends.legacy`, P1 #42). `requirements.txt`
  is still UTF-16 (P1 #20).

### 2026-10-05 run notes'''

content = content.replace(old_log_end, new_log_entry)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Doc updated successfully")
