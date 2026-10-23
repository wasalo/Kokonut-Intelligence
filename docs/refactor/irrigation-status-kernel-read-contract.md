# Irrigation status Kernel read contract

## Scope

The CAP-002 irrigation slice exposes a private OIDC Gateway read:

```text
GET /operator/api/irrigation/{location_id}/status?limit=25&offset=0
```

It returns active irrigation zones, latest moisture status and target, the
earliest pending irrigation schedule, and the latest irrigation event. Pages
are capped at 50 zones. Moisture status follows the existing
`get_zone_status` thresholds (`no_data`, `below_trigger`, `below_target`,
`in_range`, `above_target`). The endpoint is advisory/read-only; it does not
approve schedules, trigger actuators, or modify sensor data.

## Authorization and data access

- The route requires the exact `precision_irrigation:read` grant for its
  location. Other methods, suffixes, and unrecognized paths remain protected.
- Operator and location UUIDs and pagination are validated before connecting.
- A repeatable-read, read-only transaction installs database-verified signed
  tenant context before the count and zone queries, keeping count and page on
  one snapshot.
- Both queries include the exact location predicate. The latest soil-moisture
  lookup also matches the sensor reading location to the zone location.
- The query uses bounded statement/lock timeouts. Connections are rolled back
  and closed on success and failure.
- Device/actuator identifiers, coordinates, geometry, arbitrary metadata,
  target notes, schedule reasons, and actor identities are not returned.
- Responses use `Cache-Control: no-store` and `Vary: Cookie`.
- No migration, provider, Directus, or additional runtime dependency is needed.

## Verification boundary

Focused tests cover exact route policy, pre-connection validation, signed
context ordering, repeatable-read controls, location scoping, sensor location
matching, pagination, moisture-status thresholds, bounded/sanitized output,
cleanup, and authenticated HTTP/grant denial. Synthetic/unit checks do not
establish populated legacy parity, live OIDC/browser acceptance, RLS or least-
privilege database grants, device actuation, or MAN-CAP-002 acceptance.

CAP-002 still needs crop simulation and nutrient outputs, plus frozen-fixture
and populated-data parity across yield, irrigation, simulation, and nutrients.

## Rollback

This is an additive read-only route. Remove its route registration and exact
`precision_irrigation:read` policy entry to roll back; no schema or data rollback
is required. Legacy precision-irrigation CLI behavior remains available.
