# Yield monitoring Kernel read contract

## Scope

The first CAP-002 Kernel slice exposes a read-only OIDC Gateway summary at:

```text
GET /operator/api/yield-monitoring/{location_id}/summary
```

It returns counts and aggregates from `harvest_yield_observation` where the
requested location matches and lifecycle status is `verified` or `published`.
The projection includes totals grouped by the stored yield unit, crop-and-unit
aggregates, and at most ten recent harvest summaries. It does not combine
numeric yields across different units. It deliberately omits draft/submitted
observations, source identifiers, actor fields, free-text metadata, and
evidence references.

## Authorization and data access

- The route requires the exact OIDC operator grant `yield_monitoring:read` for
  the path's location. Other methods and path suffixes do not match this route
  policy; unknown paths remain protected.
- The service validates both UUIDs before opening PostgreSQL.
- One read-only transaction installs database-verified signed tenant context
  before any yield query. Every query also has an explicit location predicate.
- The transaction uses bounded statement/lock timeouts and always rolls back
  and closes its connection.
- Responses are private and use `Cache-Control: no-store` and `Vary: Cookie`.
- No migration, new runtime dependency, Directus operation, or analytics
  provider is required. Existing CLI and legacy analytics behavior is unchanged.

## Verification boundary

The focused checks cover exact route policy, identifier preflight, signed
context ordering, location and lifecycle predicates, bounded/sanitized output,
transaction cleanup, and the authenticated HTTP response. They use synthetic
data and do not establish populated legacy output parity, browser/provider
acceptance, RLS/least-privilege database grants, or MAN-CAP-002 acceptance.

The CAP-002 named acceptance still requires frozen fixtures for yield,
irrigation, crop simulation, and nutrient outputs. This endpoint only starts
the tenant-aware Kernel path for the yield-summary surface.

## Operator console

The operator console exposes the summary only when the signed session carries
the exact `yield_monitoring:read` grant for a syntactically valid location.
Requests are same-origin, use `Cache-Control`-compatible `no-store` fetches,
and discard stale responses after a location change. The console also verifies
that the response `location_id` matches the currently selected grant. Fixed
aggregate, crop, and ten most recent harvest fields render through text nodes;
numeric yield totals remain separated by their recorded unit. The panel is
read-only and does not expose source identifiers, actor fields, evidence, or
metadata. These source/DOM contracts are not live browser or populated-data
acceptance ([evidence](builds/2026-10-23-recovery/cap-002-yield-monitoring-console.json)).

## Rollback

To roll back only the console, remove its panel, exact-scope bootstrap, event
bindings, and focused contract test; the existing read-only Gateway route stays
available. To roll back the full Kernel read slice as well, remove the Gateway
route and its `yield_monitoring:read` policy entry. Neither path needs schema or
data rollback, and the legacy yield CLI and analytics module remain available.
