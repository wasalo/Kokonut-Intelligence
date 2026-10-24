# CAP-006 landscape and pollinator Kernel read contract

Updated: 23 October 2026

## Routes and authorization

- `GET /operator/api/landscape/{location_id}/summary` requires the exact
  location grant `landscape_conservation:read`.
- `GET /operator/api/pollinators/{location_id}/summary` requires the exact
  location grant `pollinator_health:read`.
- Both routes are private, same-origin operator endpoints. Responses use
  `Cache-Control: no-store` and `Vary: Cookie`; invalid identifiers fail before
  opening a database connection.
- Each read uses a single repeatable-read, read-only PostgreSQL transaction,
  installs signed operator/location/resource/action context on that connection,
  and repeats the location predicate in every source query. The handler rolls
  back and closes the connection on success and failure.

## Source and lifecycle semantics

The reads follow the source definitions in
`schemas/postgres/154_landscape_conservation.sql` and
`schemas/postgres/155_pollinator_health.sql`. Migration 602 additively aligns
the existing pollinator analytics service with migration 155: it restores the
structured source/temperature and habitat fields used by its established
commands, adds pesticide application measurements and distinct numeric hive
strength scores, and introduces location-bound inspection history. Observations
may link to a hive only within the same location. No existing records are
rewritten by this migration.

Landscape inventories group habitat zones, wildlife corridors, and hedgerows
by their fixed type/condition/status dimensions and retain the source units
(hectares and metres). These records are descriptive and their lifecycle state
is returned. Buffer checks are limited to `verified`; biodiversity summaries
include only `verified` and `published` assessments and report means across the
selected records, not a latest-value or compliance determination.

Pollinator observations and pesticide-impact records include only `verified`
or `reviewed` rows. Pollinator habitats are descriptive inventories grouped by
type, condition, and source status. Active-hive summaries retain kg for honey
yield and counts for varroa observations; they are not a health certification.
The reference species catalog is network-wide and is not joined into a
location response.

The legacy analytics service now uses the canonical observation, habitat,
`pesticide_impact_log`, and `hive_record` tables. Its writes begin in the
`recorded` review state; the summary includes only verified/reviewed
observations and pesticide records. Hive inspections append a distinct record
and update the selected location-bound hive snapshot in one transaction. The
historic numeric colony-strength input is retained as a 0–10 score, separate
from the schema's categorical strength. Pesticide risk is an advisory
toxicity/mortality heuristic, not a safety or compliance determination. Detail
lists are bounded to 500 rows and report when more applications match.

These legacy analytics queries and CLI writes remain a repository-level
compatibility surface. They do not establish signed operator context or tenant
RLS. The Gateway is the scoped operator path; direct CLI/database use must stay
behind a trusted operator boundary until its runtime identity is narrowed.

Neither response includes names, geometry, plot IDs, species names, products,
active ingredients, hive identifiers, narratives, notes, assessor identities,
weather JSON, or arbitrary metadata. Fixed-schema groupings are small and have
an 8-second statement timeout. No client-supplied query or group dimensions
are accepted.

## Console behavior

The hidden-by-default console panel has independent subsections and selectors
for each grant. It does not reveal either section without its exact scope. Reads
are same-origin and no-store, validate response location and fixed categories,
discard stale responses, and render values through `textContent`.

## Verification and rollback

The focused Gateway, route-policy, console-contract, JavaScript syntax, and
pollinator service selection passes 35 tests; Ruff and Python compilation pass.
The disposable PostgreSQL 16 check applies migrations 155 and 602, replays 602,
and passes six grouped service/schema/location-link assertions. Evidence is in
`builds/2026-10-23-recovery/cap-006-pollinator-health-disposable.json` and the
earlier Gateway/console evidence remains in
`builds/2026-10-23-recovery/cap-006-landscape-pollinator-kernel-read.json`.
No candidate/legacy database, provider, or Raspberry Pi was used. If deployed,
rollback should revert the application only after stopping use of the new
fields; the additive migration and inspection history should be retained.

This is a prepared read path, not proof of output parity, deployment-role
least privilege, forced-RLS coverage, live ZITADEL behavior, browser acceptance,
populated output parity, or MAN-CAP-006 acceptance. Migration 602 has not been
applied to the candidate. The existing shared-identity CLI must not be treated
as a tenant-safe writer until the worker/runtime identity gates close.
