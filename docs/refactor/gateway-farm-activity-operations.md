# Gateway farm-activity operations contract

**Status:** Gateway routes and a separate operator-console panel are implemented
in source; migration 404 and database acceptance are limited to a fresh
disposable PostgreSQL 16 database. Six focused console contract and inline
JavaScript syntax checks pass. The local candidate has not been migrated or
rebuilt for this slice; browser and live authenticated Gateway acceptance
remain open.

## Boundary

The Gateway provides operational reads and governed writes for
non-Field-Collector rows in `farm_activity`. Directus stays optional. Native
Field Collector submissions remain on the consent-aware capture, sync, and
review APIs; these routes neither read nor mutate them. Every request uses the
authenticated OIDC operator session, location-qualified tenant context, and an
explicit `farm_activity` resource/action grant before querying or writing.

The implementation is not a claim of parity for other Directus collections,
fields, relationships, hooks, or schedules. A historical non-Field-Collector
row with no attributable operator lifecycle event cannot be independently
verified or published through this path. It fails closed until an owner-approved
reconciliation records trustworthy history.

## HTTP surface

All routes are under `/operator/api/farm-activity-records` and require an
enabled OIDC operator session. Responses carry `Cache-Control: no-store` and
`Vary: Cookie`.

| Method and path | Scope | Contract |
| --- | --- | --- |
| `GET /operator/api/farm-activity-records?location_id=<uuid>&limit=50` | `farm_activity:read` | Bounded summaries, limit 1–100; excludes Field Collector rows. |
| `GET /operator/api/farm-activity-records/{id}?location_id=<uuid>` | `farm_activity:read_detail` | One location-scoped record plus bounded operator audit history. |
| `GET /operator/api/farm-activity-records/published?location_id=<uuid>&limit=50` | `farm_activity:read_published` | Analyst-safe verified/published summaries only. |
| `GET /operator/api/farm-activity-records/published/{id}?location_id=<uuid>` | `farm_activity:read_published_detail` | Analyst-safe detail and bounded audit history. |
| `POST /operator/api/farm-activity-records?location_id=<uuid>` | `farm_activity:create_draft` and `farm_activity:read_detail` | Body is `{ "content": { ... } }`; creates an attributed `draft` with Gateway lineage. |
| `PATCH /operator/api/farm-activity-records/{id}/draft?location_id=<uuid>` | `farm_activity:edit_draft` and `farm_activity:read_detail` | Body is `{ "content": { ... }, "reason": "..." }`; content edit and audit event commit atomically. |
| `POST /operator/api/farm-activity-records/{id}/{action}?location_id=<uuid>` | Action-specific grant | `submit`, `verify`, `reject`, `request-rework`, `publish`, or `close-exception`; body may contain only a reason. |

Content is allowlisted to plot/crop-cycle, activity type/date, description,
labor hours/cost, materials, evidence URLs, and notes. Callers cannot set
status, source identity, verification fields, audit rows, or arbitrary columns.
Database guards verify plot/crop location, valid lifecycle transitions, current
tenant grants, and separation of submitter, verifier, reviewer, and publisher.
Reject, rework, and exception-close require a bounded reason.

The operator console includes a separate panel for these records. It selects
the ordinary or published-only API from the operator's location grants, shows
detail and decision history only with a corresponding detail grant, and renders
draft/lifecycle controls only for matching grants and record state. Mutations
use same-origin credentials, `no-store`, and the console CSRF token. The
create/edit forms expose all Gateway-editable content fields, including
location-checked plot/crop-cycle IDs, bounded materials JSON, and evidence URLs.
The Field Collector intake and consent workflow remains a separate panel.

## Audit and database boundary

Migration 404 adds `farm_activity_operator_event`, a separate append-only ledger
for the Gateway workflow; it does not overload the Field Collector native-form
event table. A no-login/no-membership function-owner role writes audit events
through narrow trigger functions. `kokonut_runtime` has `SELECT` only, and the
optional Directus runtime has no ledger access. The migration applies
transactionally and records checksums through the ordered migration runner.

The candidate rollout procedure must use a fresh encrypted checkpoint and
restore rehearsal, then apply migration 404 with the ordered runner, rebuild
only the candidate app, and verify migration status, health, protected-route
behavior, and a human-reviewed test record. Rollback before migration is an app
deployment rollback. After applying the additive schema, roll back the app
while leaving the schema in place; do not edit or reverse the checksummed
migration. Correct defects with a forward migration. No rollout is authorized
or recorded here.

## Verification evidence

Thirteen focused HTTP, service, and OIDC route-policy tests pass. Five focused
console contract and inline JavaScript syntax checks pass, and Ruff passes for
the console test. Python compilation passes for the API/migration slice. The
disposable migration check passes 11 cases on a
fresh PostgreSQL 16 container with no mounted volumes, using a random host port
bound to `127.0.0.1`. Its tenant setter is a synthetic fixture function; signed
tenant-context cryptography is covered by separate checks. The runtime SQL
inventory is refreshed. Candidate and legacy databases were not touched
([evidence](builds/2026-10-16-recovery/gateway-farm-activity-operations-disposable.json)).

These checks establish source and disposable-database behavior only. They do
not establish configured OIDC, browser/runtime interaction, live authenticated
Gateway behavior, candidate rollout, populated legacy-row reconciliation,
wider Directus parity, RLS readiness, or MAN-CAP-001 acceptance ([console
evidence](builds/2026-10-16-recovery/operator-console-farm-activity-contract.json)).
