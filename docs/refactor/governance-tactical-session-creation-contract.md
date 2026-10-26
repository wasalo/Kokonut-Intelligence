# CAP-024 tactical session creation contract

## Route

`POST /operator/api/governance/{location_id}/tactical-sessions`

The route requires an authenticated OIDC operator, CSRF token, signed tenant
context, and an active exact `governance_tactical:create` grant for the
requested location. It does not require a separate tactical read grant. The
console asks for an active circle UUID in that location; circle-name browsing
remains under the separate governance-role read surface.

## Request

```json
{
  "request_id": "UUID",
  "reason": "Why this session is being scheduled",
  "circle_id": "UUID",
  "session_type": "weekly_review",
  "title": "Weekly operations review",
  "scheduled_at": "2026-10-21T14:00:00Z",
  "facilitator_role_id": "UUID",
  "recorder_role_id": null,
  "agenda_scope": "Review field actions and follow-up"
}
```

`circle_id`, `session_type`, and `title` are required. The supported types are
`weekly_review`, `stakeholder_health`, `relationship_review`, `risk_triage`,
and `governance_followup`. The schedule must include a timezone. Role references
are optional but, when provided, must be active roles in the selected circle.
The circle itself must be active and location-owned by the requested location.

The request cannot set lifecycle status, notes, outcomes, actor identity, or
creation timestamps. PostgreSQL always creates the session as `planned` and
attributes it to the active person bound to the authenticated operator.

## Transaction and replay

The Gateway normalizes and validates the request before opening PostgreSQL. In
one transaction it sets signed operator context, then calls
`kokonut_security.create_governance_tactical_session`. The bounded
`SECURITY DEFINER` function rechecks context, exact grant, active person
binding, circle ownership/state, and optional role ownership/state. It creates
the planned session and appends a private immutable request/actor/reason event
atomically. A same-operator retry with the same request UUID and identical
location/content/reason returns the original result. Reusing the key with
different content is rejected.

Runtime and Directus roles cannot insert sessions directly and cannot inspect
the private creation ledger. A trigger also rejects direct session inserts by
non-owner roles if an inherited grant is introduced later. Directus remains
optional; this operation is owned by the Gateway.

## Acceptance and rollback

Migration 444 applies and replays in disposable PostgreSQL 16. Acceptance
covers exact signed scope, active binding, same-location active circle/role
checks, planned-only fields, exact retry and collision, immutable history,
runtime/Directus ACLs, and direct insert denial. Unit and console checks cover
preflight validation, transaction context, CSRF, no-store behavior, and
create-grant gating.

Before migration 444 is applied, application rollback is a route/service/console
revert. After application, keep the additive audit ledger, function, trigger,
and ACLs; do not edit or reverse the ordered migration. The legacy direct-write
CLI path will fail under the restricted runtime role after rollout, so an
application rollback must retain the Gateway create route or explicitly disable
session creation; do not restore direct runtime inserts.
