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

The reads follow the installed source definitions in
`schemas/postgres/154_landscape_conservation.sql` and
`schemas/postgres/155_pollinator_health.sql`. They do not depend on the legacy
pollinator analytics module, whose SQL names do not match migration 155.

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

The focused synthetic Gateway, route-policy, console-contract, and JavaScript
syntax checks are recorded in
`builds/2026-10-23-recovery/cap-006-landscape-pollinator-kernel-read.json`.
No migration, candidate/legacy database, provider, or Raspberry Pi was used.
Rollback is limited to reverting these source, route-policy, console, inventory,
and documentation changes; no persistent data was written.

This is a prepared read path, not proof of output parity, deployment-role
least privilege, forced-RLS coverage, live ZITADEL behavior, browser acceptance,
or MAN-CAP-006 acceptance. A later reconciliation must align the old
`services/analytics/pollinator_health.py` against migration 155 before its
legacy write commands can be considered a parity source.
