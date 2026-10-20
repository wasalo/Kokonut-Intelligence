# Business planning Kernel edit contract

This contract defines location-scoped editing and version reads for the nine
business model canvas blocks. It complements the additive draft-create contract
and does not replace the legacy CLI or optional Directus workflows.

## Routes and grants

- `PATCH /operator/api/business-planning/{location_id}/canvases/{canvas_id}/blocks/{block_name}` requires an authenticated OIDC operator, CSRF protection, and the exact tenant-qualified `business_planning:update` grant for the location.
- `GET /operator/api/business-planning/{location_id}/canvases/{canvas_id}/versions` requires the exact tenant-qualified `business_planning:read` grant for the location.
- Both routes establish signed tenant context on the same connection used by their bounded database functions. They return `Cache-Control: no-store` and vary on the session cookie.
- A canvas must have matching `location_id`, `entity_type='location'`, and `entity_id` values. Organization canvases are outside these routes.

## Editing behavior

The PATCH route replaces one named block: `key_partners`, `key_activities`,
`key_resources`, `value_propositions`, `customer_relationships`, `channels`,
`customer_segments`, `revenue_streams`, or `cost_structure`. Array blocks require
JSON arrays; `cost_structure` requires a JSON object. One block is limited to
64 KiB. The request contains exactly `request_id`, `expected_version`,
`expected_updated_at`, `items`, and a required 1–500 character `change_reason`.

Only canvases in `draft` status are editable. An edit increments `version`
atomically and updates `updated_at` and `updated_by`; it does not alter lifecycle
status, submit, verify, publish, attest, or edit canvas metadata. Version and
timestamp must both match the caller's last read. A stale edit returns `409` and
the operator must reload before retrying. Exact request retries return the
original result; reusing a request ID with changed content returns `409`.

Migration 464 adds a private append-only Kernel request/history ledger and a
non-login function-owner role. It records the full prior canvas snapshot before
the block change in the same transaction. The version endpoint returns bounded
legacy `canvas_version` snapshots, Kernel prior snapshots, and the current
state, preferring the Kernel snapshot for a duplicate version number. Legacy
JSON is rebuilt from the allowlisted canvas name, description, fiscal year,
tags, and nine blocks; unrelated metadata and raw-import keys are not returned.
Actor identifiers are omitted, and a page is capped at five entries and 512
KiB.

## Compatibility and limits

Migration 464 grants the runtime role execution of two bounded functions but
does not grant direct access to the Kernel ledger. Directus cannot execute the
new functions. Existing runtime and Directus table writes are intentionally
preserved while their compatibility paths remain in use. Those legacy writers
can still bypass the Kernel version ledger; universal write isolation and full
legacy-versus-Kernel history reconciliation remain open.

The service also checks `updated_at` because legacy edits may not increment the
canvas version consistently. This guards supported update paths that refresh
the timestamp, but it does not substitute for removing unrestricted legacy
writers. The route must not be described as proving universal optimistic
concurrency across all direct database clients.

## Verification boundary

Mocked tests cover payload validation before connection, exact signed-context
scope, transaction cleanup, route policy, HTTP status and cache behavior,
history pagination, and response size limits. The disposable PostgreSQL 16
acceptance applies and replays migrations 457, 463, and 464 and checks exact
grants, stale writes, retry collisions, immutable history, lifecycle denial,
history output, and direct-table/function privileges. It does not touch the
candidate or legacy database, and migration 464 has not been rolled out there.

Populated reference-output parity, live OIDC/browser behavior, migration
rollout, broader ACL/RLS, legacy writer retirement, and MAN-CAP-065 owner review
remain open.
