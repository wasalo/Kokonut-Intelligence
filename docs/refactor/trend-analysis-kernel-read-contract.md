# Trend analysis Kernel read contract

**Status:** First saved-estimate read implemented; capability remains prepared.
**Updated:** 24 October 2026

## Route and authorization

`GET /operator/api/trends/{location_id}/estimates` requires the exact OIDC
operator grant `trend_analysis:read` for the selected location. The Gateway
validates the operator/location UUIDs and bounded page (`limit` 1–50,
`offset` 0–10,000), then opens one repeatable-read, read-only transaction,
applies bounded statement and lock timeouts, establishes database-signed
tenant context, and runs the location-qualified query. Responses are `no-store`
and vary by cookie.

## Returned projection

The query selects the latest stored `trend_estimate` row per metric for the
authorized location. It returns only the metric key, period, point count,
slope/intercept, fit/error measures, direction/confidence, confidence bounds,
time unit, and save time. Results are ordered by save time and metric key, with
bounded pagination. Non-finite stored floating-point values are returned as
`null` so they cannot break JSON responses or appear as numeric measurements.
Database IDs, `computed_by`, metadata, raw observations, model parameters,
forecast values, and accuracy records are not selected.

The console appears only for the exact location grant, checks response scope
and page correlation, suppresses stale requests, renders fixed fields using
text nodes, and labels stored outputs advisory. It does not run a trend model
or certify calculations.

## Boundaries and remaining work

This slice does not implement model execution, smoothing/decomposition,
change-point or forecast-result reads, accuracy verification, geostatistics,
or populated numerical parity. Current application runtime database grants
remain broad; signed tenant context is not least-privilege ACL/RLS. Live OIDC
and browser behavior, scope configuration, populated fixtures, audience
review, database isolation, and `MAN-CAP-008` remain open.

## Verification and rollback

Focused route, paging, tenant-context, non-finite-value, console-contract, and
JavaScript checks use fakes. No migration, seed, candidate/legacy database,
provider, or external service is used. Rollback reverts the Gateway reader,
route registration/policy, and console panel, then regenerates
`runtime-sql-inventory.json`; no persistent data was written.
