# Packitbot role-flow audit

Reviewed against main at c21ead0c7b968ff44e7fc595d281429736546ab6 on 25 November 2026. The review traced Telegram commands and keyboards through the dispatcher, role checks, FSM state, domain services, database writes, and outgoing notifications.

## Flow map

| Role | Paths reviewed |
| --- | --- |
| Student | Role selection, name/hall/phone registration, review and cancel, request creation and review, request history and details, pending-request edits, cancellation, profile edits, delivery rating |
| Admin | Portal and statistics, driver invitations, verification and pagination, assignment and eligibility, driver record edits and removal, user lookup and moderation, promotion, broadcast preview and send |
| Driver | Invitation and registration, registration cancellation and approval status, duty controls, assigned-delivery recovery, accept or decline, pickup and transit updates, delivery or failure, driver profile |
| Shared | Home and command menus, role gates, FSM isolation, update transactions, notification delivery, webhook and polling startup |

## Findings and changes

| ID | Priority | Finding on the reviewed commit | Change and regression coverage |
| --- | --- | --- | --- |
| 01 | High | The authorization middleware rejected real keyboard actions from the student wizards, admin assignment and broadcast. Menu text took a different authorization path from slash commands. | Match emitted callback prefixes and check menu text against the corresponding command permissions. The dispatcher suite drives the real role keyboards with registered users. |
| 02 | High | Two admin updates could assign the same driver to different requests. Assignment left the driver available, and the list admitted busy drivers. | Lock and refresh the driver profile, check account eligibility and active requests, then reserve the driver alongside the assignment and audit entry. A PostgreSQL test races two sessions holding stale profile objects. |
| 03 | High | Cancellation could validate against stale status. Cancellation, decline, and terminal transitions handled driver availability in different layers. | Lock cancellation in the request service and centralize driver release. Keep the reservation until the driver's final active assignment ends. PostgreSQL verifies assignment and cancellation, and the dispatcher verifies decline and completion. |
| 04 | High | Admin promotion omitted the profile required by the admin access check. An old student role-selection message could also restart onboarding for an existing account. | Create or repair the admin profile during promotion. Gate role selection and require the registration review state for edit and submit. The dispatcher promotes an existing student and exercises admin access after the student presses an old role button. |
| 05 | High | A stale verification button could reject an already approved driver. Moderation actions could leave a request without a driver able to advance it. | Lock review decisions and require a pending application. Record who approved the driver and when. Block access-changing actions during an active delivery. The dispatcher exercises stale review, and PostgreSQL exercises the removal guard. |
| 06 | High | A delivered request could fail to open in student history. Submitting its first rating could also trigger implicit async ORM loading. | Eager-load feedback for details and use the feedback query result directly during submission. Validate ownership and bind rating/skip buttons to the active form. The dispatcher opens the delivery, checks the rating button, and verifies the saved rating and driver average. |
| 07 | Medium | Edited dates could fail JSON serialization with Redis. Date shortcuts bypassed the configured booking window. Older edit buttons could affect a different request. | Store ISO dates, validate at selection and confirmation, and bind edits to the active request and field. The dispatcher rejects an expired date and mismatched confirmation, checks JSON serialization, and verifies the saved date. |
| 08 | Medium | Verification pagination opened the all-drivers view. Decline statistics counted a status the live decline path never wrote. | Give the verification queue its own route and count distinct declined requests from status logs. Pagination tests check the handler for each list. The dispatcher checks the statistic after decline. |
| 09 | Medium | /menu had no handler. Role command scopes duplicated entries. /duty, /active, and the assigned-deliveries button were disconnected. Assignment recovery depended on getting the notification. | Wire the menu, deduplicate commands, keep driver aliases, and recover assignments from the dashboard. Connect the driver profile button and record completed deliveries at delivery. Dispatcher tests check the command menu, dashboard recovery, and completed count. |
| 10 | Medium | /cancel could be treated as text in an admin form. Broadcasts parsed free text as Markdown, and the combined preview exceeded Telegram's limit for a maximum-length body. Duplicate updates could race within a chat. | Route cancellation before feature handlers, send plain-text previews and broadcasts, and serialize FSM updates with Redis event isolation. The dispatcher verifies cancellation and maximum-length preview and delivery. |
| 11 | Medium | A duplicate driver registration write left its session unusable. The onboarding cancel button was blocked before approval. | Validate profile fields before writing and wrap user/profile changes in a savepoint. Let an applicant clear the form. Duplicate-constraint tests and the dispatcher exercise these paths. |
| 12 | Medium | Webhook startup referenced missing settings and registered a fixed path. Restarting discarded queued Telegram updates. | Configure the listener port and webhook secret, use the configured URL path, and preserve queued updates. A startup test checks registration, listener creation, and cleanup. |

## Follow-up decisions

| Area | Observation | Decision needed |
| --- | --- | --- |
| Delivery operations | /orders is a pending assignment queue. There is no admin screen for tracking, reassigning, or resolving in-progress orders. | Define admin recovery for lost contact, failed pickups, and reporting. |
| Product scope | Older copy described a driver job marketplace, earnings, and delivery verification. The current bot supports admin assignment and driver status reporting. | Confirm whether fees, earnings, pickup proof, or recipient confirmation belong in the product. |
| Notification reliability | Telegram sends are best-effort. A delivery update can commit even if a notification fails. Student cancellation has no dedicated driver notification. | Decide which notifications need durable retries, delivery logs, or manual replay. |
| Legacy data | Older records may have overlapping assignments or completion totals that updated only after a rating. Assignment checks now account for existing open requests. | Reconcile production records using request and status logs if these cases exist. |
| Driver record policy | Removing a driver leaves the original invitation intact. License numbers lack a database uniqueness constraint. | Decide whether removal should revoke the invitation and how to resolve any older duplicate licenses before enforcing uniqueness. |
| Admin user search | A bare number can match two accounts across the internal and Telegram ID fields. Usernames can also be stale. | Choose an explicit ID format and how to synchronize identity updates from Telegram. |

## Verification

The existing [Tests workflow](../.github/workflows/tests.yml) runs the full pytest suite on pull requests with PostgreSQL and Redis services. The dispatcher cases replace the Telegram transport and use a real SQLite database and an in-memory FSM with event isolation. The date test checks JSON serialization. The PostgreSQL test exercises row locking in independent sessions. The webhook startup test replaces external network calls.
