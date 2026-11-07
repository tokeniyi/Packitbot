# Plan: escape user-supplied values in legacy Markdown messages (P1 #17, stage 2)

Status: validated 2026-11-06 against `bot/admin/handler.py`, `bot/core/constants/messages.py`,
`bot/core/utils/formatters.py`, `bot/core/services/notification_service.py`.

## Problem
Admin handlers send messages with `parse_mode="Markdown"` (legacy Markdown, not V2) and
interpolate values that come from users or the database: names, phone numbers, plate and
licence numbers, Telegram usernames, ban reasons, admin-typed search text and edited field
values. Legacy Markdown fails on an unbalanced `_`, `*`, `` ` `` or `[`. Telegram then rejects
the message ("can't parse entities"), so the admin sees an error, or the text is mangled.
Telegram usernames may contain `_`, so `@some_name` is affected even for normal users.

## Approach
1. Add two helpers in `bot/core/utils/formatters.py`:
   - `escape_markdown(value)`: `None` becomes `""`. Prefix `\` before `_ * ` [` (the four
     characters legacy Markdown lets you escape). Also escape `\` itself is NOT needed for
     legacy Markdown, so it is left alone.
   - `markdown_code(value)`: for values placed inside `` `code` `` spans. Escapes are not
     honoured inside code entities, so backticks are replaced with an apostrophe.
2. Apply `escape_markdown` to every interpolated user/DB value in the admin Markdown sites.
3. Apply `markdown_code` to `` `{identifier}` `` (admin search text) and `` `{audience_name}` ``
   is a constant, so it stays as is.
4. Leave untouched, on purpose:
   - Broadcast body (`process_broadcast_content` preview, `execute_broadcast`,
     `notification_service.send_broadcast_message`). It is admin-authored text whose Markdown
     formatting the admin intends. Escaping would remove the formatting. If it fails to parse,
     the admin is shown the error at preview time.
   - Constant template text and enum `.value.upper()` strings (no user input).
   - Driver-side messages, which are already HTML (P1 #17 stage 1).

## Site list (bot/admin/handler.py, line numbers at 2026-11-06)
- 349: driver assignment notification: `updated_req.hall_of_residence`, `dropoff_address`.
- 414-422: driver application detail: `full_name`, `phone_number`, `plate_number`,
  `license_number`, `username`.
- 462-463: driver approved: `approved_driver.full_name`, `phone_number`.
- 503: driver rejected: `rejected_driver.full_name`.
- 611-623, 828-840, 877-889: `MSG_DRIVER_DETAIL_TITLE.format(...)` with `full_name`,
  `phone_number`, `license_number`, `plate_number`; plus `username`.
- 658-672 (`MSG_DRIVER_EDIT_INPUT_PROMPT`): `current_value` is a constant "Current value".
  No change.
- 752-756 (`MSG_DRIVER_EDIT_SUCCESS`): `value=new_value` is admin-typed. Escape.
- 962: `markdown_code(identifier)`.
- 975-985: `full_name`, `username`, `phone_number`, `banned_reason`.
- 1046-1049: `full_name`, `banned_reason`.
- 1078-1079: `full_name`.
- 1110-1111: `full_name`.

## Validation against code
- Confirmed that `MSG_DRIVER_DETAIL_TITLE` (messages.py:293) and `MSG_DRIVER_EDIT_SUCCESS`
  take their values through `.format(...)`, so escaping must happen at the call site, not in
  the template. Sites: 611, 828, 877 and the edit-success send.
- Confirmed that `MSG_NOTIFY_DRIVER_ASSIGNED` (messages.py:336) is constant text, so only the
  hall and dropoff values need escaping at line 349.
- Confirmed the broadcast path is admin-authored and is deliberately excluded.
- Legacy Markdown escape set: `_`, `*`, `` ` ``, `[`. Escaping `]`, `(`, `)` is unnecessary.
- Risk: a `\` typed by the user survives unchanged and is harmless in legacy Markdown.
- Risk: `None` values. The helper returns `""`, so the surrounding `or 'N/A'` fallbacks keep
  working when they are applied before escaping.

## Tests
- `tests/unit/core/test_markdown_escaping.py`: helper behaviour (escapes the four characters,
  leaves plain text alone, `None` to `""`, backticks removed for code spans).
- One regression test per representative admin site, checking the sent text contains the
  escaped form and the legacy-Markdown parse would not be broken (underscore usernames,
  asterisks in names).
- Fail-before check: stash `bot/admin/handler.py`, the new tests must fail.

## Stages
- Stage 2a (this run): helpers, all sites listed above, tests.
- Stage 2b (outstanding): the broadcast preview path, only if the owner wants it escaped.
  Needs an owner decision because it changes admin formatting.
- Stage 2c (outstanding): per-site tests for the remaining driver-side HTML sites (P1 #17
  coverage gap, listed in AUTOMATION_PROGRESS.md).
