# Nutrient soil-test Kernel read contract

## Scope

The CAP-002 Gateway exposes a private, paginated read:

```text
GET /operator/api/nutrients/{location_id}/soil-tests?limit=25&offset=0
```

It returns location-owned soil-test measurements and nutrient application
recommendations for rows in `recorded` or `verified` lifecycle states. The
status remains explicit so clients do not present an unreviewed record as
verified. Recommendations are advisory; this endpoint does not prescribe,
approve, or apply inputs.

## Authorization and data access

- The route requires the exact `nutrient_budget:read` grant for the requested
  location. Other methods, suffixes, and unrecognized paths remain protected.
- Operator/location UUIDs and pagination are validated before connecting.
- A repeatable-read, read-only transaction installs signed tenant context before
  the count and page reads; both queries filter by the requested location and
  the same `recorded`/`verified` lifecycle set.
- Page size is capped at 50, offset at 10,000, statement timeout at five seconds,
  and lock timeout at two seconds. The connection is rolled back and closed on
  success and failure.
- Plot IDs are returned only when the referenced plot's farm belongs to the
  requested location. The projection omits notes, arbitrary metadata, and
  location names.
- Responses use `Cache-Control: no-store` and `Vary: Cookie`.
- No schema migration or provider dependency is required.

## Verification boundary

Focused tests cover exact route policy, pre-connection validation, signed
context ordering, location/status filters, cross-location plot-ID suppression,
bounded pagination, fields returned/omitted, connection cleanup, authenticated
HTTP behavior, and denial before data access when the grant is missing.

These checks do not establish populated-data parity, laboratory provenance,
recommendation validity, live ZITADEL/browser behavior, database RLS or
least-privilege boundaries, or MAN-CAP-002 acceptance.

## Rollback

This additive read can be rolled back by removing its route, exact authorization
policy, service module, and tests. No schema or data rollback is required; the
existing nutrient-budget CLI and balance route remain unchanged.
