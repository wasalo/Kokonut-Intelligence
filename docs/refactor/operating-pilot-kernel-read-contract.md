# CAP-037 Operating Pilot Kernel Read Contract

**Status:** Prepared (`P`), not MAN-CAP-037 accepted
**First slice:** Location-scoped operating-pilot summary
**Migration:** `schemas/postgres/461_location_scoped_operating_pilot_summary.sql`

## Route and authorization

`GET /operator/api/operating-pilot/{location_id}/summary` is an OIDC operator
route. It requires an exact `operating_pilot:read` grant for the requested
location. The Gateway validates both UUIDs, opens a read-only transaction,
sets signed tenant context on that connection, calls the bounded PostgreSQL
projection, rolls back the read transaction, and closes the connection.
Responses are `no-store`. A missing identity provider disables the route;
missing or stale tenant grants fail closed.

## Data boundary

Migration 461 exposes an aggregate projection only when an active
`operating_pilot_scope` row has `scope_type='adelphi'`, is active, and points
to an active `farm` whose `location_id` exactly matches the requested
location. This follows the legacy model: the Adelphi pilot scope ID is a farm
ID, while Gateway grants are location-scoped. The internal Kokonut
organization scope is never included in a farm/location response. Work items
are selected by their explicit `location_id`; capacity, demand, learning,
requests, and coaching records must use the same Adelphi farm-scope ID.
Competency summaries are limited to active roles in that pilot's governance
circle.

The response includes `as_of_date` and lifecycle counts for capacity profiles, demand signals,
location work items and claims, competency reviews, learning plans, resource
requests, and aggregate-only coaching sessions. It never returns personnel
identities, party IDs, descriptions, evidence, profile notes, resource request
text, coaching content, or private/limited coaching records. Capacity and
demand figures include only records whose period contains the database's
current date. Capacity hours include only submitted or approved profiles;
demand required-hours include only submitted or approved signals.

For person-linked capacity, work-claim, competency, learning, resource-request,
and aggregate-only coaching measures, the SQL projection counts distinct
participants internally and suppresses all associated counts/hours when the
group contains one or two people. Empty cohorts return zero; groups of at least
three return the aggregate plus `suppressed: false`. This is a baseline
disclosure control for authorized operator reads, not a substitute for
reviewing audience-specific privacy policy or temporal differencing risk.

The endpoint deliberately fails closed when the Adelphi pilot scope does not
map through an active farm row to the requested location. Legacy internal
organization scope IDs are not silently reinterpreted as farm or location
associations. Populated owner/tenant mapping still requires review before
rollout.

## Database boundary

The non-login `kokonut_operating_pilot_reader` role can select only the source
columns needed by this summary and has no identity-table access or mutation
privileges. `kokonut_runtime` is granted execution of the security-definer
function, which rechecks signed operator location context and the active exact
database grant on every call. This migration does not remove pre-existing
direct table grants from the legacy runtime or Directus roles; their direct
database boundary and forced RLS remain open gates. The disposable acceptance
uses clean test roles and proves this migration introduces no such table
grants; it does not represent the deployed role ACL state.

## Verification and rollback

The Gateway contract and exact route policy are covered by
`tests/test_gateway_operating_pilot_reads.py` and
`tests/test_operator_route_policy_inventory.py`. The disposable PostgreSQL 16
acceptance runner applies and replays migration 461, exercises active and
internal scopes, checks aggregate values and small-cohort suppression, verifies
tenant/grant denials, and inspects runtime, Directus, and reader privileges:
`scripts/check-operating-pilot-summary-disposable.py`.

Before migration rollout, disable the capability by removing the route/service
registration and route policy. If migration 461 is applied, retain its ordered
reader role and function; disable only the route. Do not edit or reverse an
applied migration.

## Remaining gates

This slice does not establish populated Adelphi scope mapping, item-level
capacity/work-claim/competency/learning/resource/coaching workflows, parity
with legacy reports, live OIDC/browser behavior, operator audience review,
production recovery, universal direct-database ACL/RLS, or MAN-CAP-037 owner
acceptance. Those gates remain open in `docs/refactor/batches.md`.
