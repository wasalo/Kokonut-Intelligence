# Governance tactical content mutation contract

## Scope

This contract completes the CAP-024 tactical content write path. It adds
location-scoped creation of tactical items and content-only edits to open items
and planned sessions. Lifecycle transitions remain in the separate tactical
action API; callers cannot set `status`, disposition, actor, or audit fields.

## Gateway API

- `POST /operator/api/governance/{location_id}/tactical-items`
  requires the exact `governance_tactical:create` location grant and creates an
  item with lifecycle state `open`.
- `PATCH /operator/api/governance/{location_id}/tactical-items/{item_id}`
  requires `governance_tactical:update`; only open items in the selected
  location can be edited.
- `PATCH /operator/api/governance/{location_id}/tactical-sessions/{session_id}`
  requires `governance_tactical:update`; only planned sessions in an active
  same-location circle can be edited.

Every request requires a UUID `request_id` and non-empty reason. Creates also
require a session and next action. Optional references (tension, work item,
decision, owner role/person, facilitator, recorder) must resolve within the
session's location or circle. Text and timestamps are bounded and validated;
timestamp inputs include a timezone. Unknown fields fail closed.

The Gateway establishes signed operator tenant context on the same database
connection as the security-definer mutation. The database rechecks the exact
grant and active person binding, location/circle/session state, and references.
The function owns a private append-only before/after event ledger and permits
only the content columns named above. Exact request retries return the original
result; reuse with changed content or actor binding fails. The console exposes
create/edit controls only with the matching grant and sends CSRF-protected,
no-store requests with a stable request ID for unchanged retries.

## Data and lifecycle boundaries

Tactical item creation always begins as `open`; edits do not change its state.
Item edits are restricted to next action, priority, due date, and linked
location/circle records. Session edits are restricted to type, title, schedule,
active same-circle facilitator/recorder roles, and agenda scope. Notes, outcome,
completion, cancellation, disposal, and reviewer identity are not editable
through these endpoints. Use the existing audited lifecycle/action paths for
state changes.

Runtime and Directus roles cannot write tactical content tables or read the
private content event ledger directly. The no-login function owner has only
column-scoped mutation privileges; its narrow `UPDATE(id)` reference grants
exist to support PostgreSQL row locks and do not grant content-column updates.

## Verification and rollout

Focused Gateway, route-policy, and console checks cover validation, grant/action
mapping, request identity, CSRF/no-store contracts, and edit gating. The
disposable PostgreSQL acceptance replays migrations 437–445 and exercises
tenant/grant denial, active binding, same-location references, lifecycle
boundaries, exact retries/collisions, immutable audit, forced direct-write
denial, and least-privilege ACLs. This evidence is code/database acceptance; it
does not claim populated-data parity, live OIDC/browser acceptance, universal
tenant RLS, or MAN-CAP-024 owner acceptance.

## Rollback

Before migration 445 is applied, remove/disable the three Gateway mutation
routes and console controls. If migration 445 is applied, roll back the app
surface while retaining its additive event ledger, function, and write guards;
do not edit or reverse an applied ordered migration. Re-enable UI/API only after
the route and database checks pass again.
