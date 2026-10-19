# Governance tactical action contract

**Status:** implemented against synthetic fixtures and disposable PostgreSQL;
not permission to change any real tactical item. Migration 441 is not applied
to the candidate or production.

## Scope and authority

Tactical items follow the existing lifecycle in migration 247:

- `open → in_progress` through `start`;
- `in_progress → disposed` through `dispose`;
- `open|in_progress → cancelled` through `cancel`.

Each operation requires a separate explicit, location-scoped operator grant:
`governance_tactical:start`, `:dispose`, or `:cancel`. The caller also needs
an active OIDC session, signed tenant context, and an active person binding.
Starting requires the bound person to match `owner_party_id` or a current,
active, non-recused assignment to `owner_role_id` in an active circle scoped to
the same location. Completed sessions may still have follow-up actions;
cancelled sessions and inactive circles cannot be changed. Disposal and
cancellation are separate delegated operator actions; each requires a reason.

Disposal also requires a schema-approved disposition type and a non-empty
outcome summary. The Gateway function sets `disposed_by_party_id` and
`disposed_at`. Cancellation has no actor fields on the original item schema,
so its actor and reason remain available in the new append-only action ledger.

Every request has a caller-generated UUID. Exact same-content retries from the
same active person binding replay the recorded result. Reusing the key with
different content or after the item changes conflicts. The item update and
the action ledger row commit in one database transaction. The ledger records
operator, human actor, location, item, action, previous/resulting state,
reason, optional disposition, and timestamp. It has an immutable trigger and
is unreadable to Gateway and Directus runtime roles.

## HTTP contract

- `POST /operator/api/governance/{location_id}/tactical-items/{item_id}/start`
  body: exactly `request_id`, `reason`.
- `POST /operator/api/governance/{location_id}/tactical-items/{item_id}/dispose`
  body: exactly `request_id`, `reason`, `disposition_type`,
  `disposition_summary`.
- `POST /operator/api/governance/{location_id}/tactical-items/{item_id}/cancel`
  body: exactly `request_id`, `reason`.

All routes require OIDC operator authentication, CSRF validation, no-store
responses, and their matching exact location grant. Unknown, cross-location,
or non-actionable items fail closed. The console displays controls only when
the caller has both tactical read access and the corresponding action grant.

## Database boundary and verification

Migration 441 removes direct INSERT/UPDATE/DELETE on tactical item rows from
PUBLIC, `kokonut_runtime`, and `kokonut_directus_runtime`; it gives the bounded
transition function only the column updates it needs. Directus does not receive
the private action ledger or execute the write function. This does not establish
RLS for other governance data or queries.

Focused mocked Gateway/route/console checks and a PostgreSQL 16 disposable
acceptance replay migrations 437–441, exercise start/dispose/cancel, ownership,
action grants, reasons, retry identity, immutable audit history, and runtime
ACLs. Candidate and legacy databases were not accessed. Candidate rollout
requires the least-privilege database runtime first; real OIDC grants, browser
acceptance, and populated-item parity remain open.
