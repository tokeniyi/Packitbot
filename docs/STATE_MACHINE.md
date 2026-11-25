# Delivery Request State Machine

This document describes the lifecycle of a `DeliveryRequest`. The authoritative
definition is the code in `bot/request/state_machine.py` (`ALLOWED_TRANSITIONS`
and `can_transition`). If this page and the code disagree, the code wins and
this page should be fixed. Tests that pin the graph are in
`tests/unit/request/test_state_machine.py`.

## Statuses

The statuses are the `RequestStatus` enum in `bot/core/constants/enums.py`.

| Status | Meaning | Terminal |
|---|---|---|
| `PENDING` | Created by a student and waiting for an admin to assign a driver. | No |
| `ASSIGNED` | An admin has assigned an approved, available driver. The driver has not yet accepted. | No |
| `ACCEPTED` | The assigned driver has accepted the job. | No |
| `REJECTED_BY_DRIVER` | Intended to record a driver rejection. See the note below: no production path writes it today. | No |
| `EN_ROUTE_TO_PICKUP` | The driver is heading to the pickup point. | No |
| `PICKED_UP` | The driver has collected the package. | No |
| `IN_TRANSIT` | The package is on its way to the recipient. | No |
| `DELIVERED` | The package was delivered. | Yes |
| `CANCELLED` | The request was cancelled by the student, an admin, or the system. | Yes |
| `FAILED` | The delivery attempt failed. | Yes |

## Allowed transitions

A transition is legal only if it is listed in `ALLOWED_TRANSITIONS`. Any other
move raises `InvalidStatusTransitionError` in `RequestService`.

| From | To |
|---|---|
| `PENDING` | `ASSIGNED`, `CANCELLED` |
| `ASSIGNED` | `ACCEPTED`, `REJECTED_BY_DRIVER`, `PENDING`, `CANCELLED` |
| `ACCEPTED` | `EN_ROUTE_TO_PICKUP`, `CANCELLED` |
| `REJECTED_BY_DRIVER` | `ASSIGNED`, `CANCELLED` |
| `EN_ROUTE_TO_PICKUP` | `PICKED_UP`, `CANCELLED` |
| `PICKED_UP` | `IN_TRANSIT`, `CANCELLED` |
| `IN_TRANSIT` | `DELIVERED`, `FAILED`, `CANCELLED` |
| `DELIVERED`, `CANCELLED`, `FAILED` | none |

The happy path is `PENDING → ASSIGNED → ACCEPTED → EN_ROUTE_TO_PICKUP → PICKED_UP → IN_TRANSIT → DELIVERED`.

## Who drives each transition

| Transition | Entry point |
|---|---|
| (new) `→ PENDING` | `RequestService.create_request`, called from the student request flow. |
| `PENDING → ASSIGNED` | `RequestService.assign_driver`, called from the admin driver-assignment flow. |
| `ASSIGNED → PENDING` | `RequestService.reject_assignment`, called when the assigned driver declines. The request returns to the admin queue. |
| `ASSIGNED → ACCEPTED` | Driver accept callback in `bot/driver/handler.py`. |
| `ACCEPTED → EN_ROUTE_TO_PICKUP → PICKED_UP → IN_TRANSIT → DELIVERED / FAILED` | Driver status callbacks in `bot/driver/handler.py` (`RequestService.transition_status`). |
| `* → CANCELLED` | The student handler calls `RequestService.cancel_request`. Students can cancel their own requests from `PENDING`, `ASSIGNED` or `ACCEPTED`. The state machine also defines transitions for future admin or system callers. |

The status-changing `RequestService` methods check `can_transition` first, write a
`RequestStatusLog` row, and run inside a SAVEPOINT (`session.begin_nested()`), so
a constraint violation rolls back only that step. Assignment locks the driver profile and sets it to `BUSY`. Decline, cancellation, delivery, and failure release the driver when no other active assignment remains.

## Notes for maintainers

**Why a driver's hand-back goes to `PENDING`, not `REJECTED_BY_DRIVER`.** The
state machine comment on `ASSIGNED` explains the choice. Admin pending-queue
queries (`admin/service.py::get_pending_requests` and
`request/repository.py::get_pending`) filter on `PENDING`. A request sitting in
`REJECTED_BY_DRIVER` would never come back to an admin.

**Decline reporting uses the status log.** The admin dashboard counts distinct
requests that have an `ASSIGNED → PENDING` hand-back or a legacy
`ASSIGNED → REJECTED_BY_DRIVER` event. A request can appear in this historical
statistic and in a current-status count.

**Terminal states have no outgoing edges.** Once a request is `DELIVERED`,
`CANCELLED` or `FAILED`, no code path can move it again. Re-opening a request
needs a new transition in the map, not a bypass.

**Adding a status or transition.** Update `ALLOWED_TRANSITIONS`, the table above,
the matching `can_transition` tests, and any status-to-message mappings in the
student and driver handlers. Keep `RequestStatus` values stable because they are
stored in the database.
