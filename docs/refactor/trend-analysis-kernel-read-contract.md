# Trend analysis Kernel read contract

**Status:** Saved estimate, smoothing, and change-point reads implemented; capability remains prepared.
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

`GET /operator/api/trends/{location_id}/smoothing` uses the same exact
`trend_analysis:read` grant and signed-context transaction. It requires the
`metric_key` selected from a returned estimate and returns at most 100 saved
points for that location and metric. The projection includes only timestamp,
smoothing method, original value, smoothed value, and save time; estimator
parameters and metadata are omitted. Non-finite values become `null` and the
points are ordered newest first.

`GET /operator/api/trends/{location_id}/change-points` uses the same exact
grant and signed-context transaction. It requires a metric key from the
authorized estimate list and returns up to 100 stored detections for that
location and metric. The projection includes the detector method, point index
and optional timestamp, magnitude, direction, confidence, segment count,
stored status, and detection time. It omits internal IDs, classification text,
metadata, and actor details. Non-finite numeric values become `null`. The
saved `detected`/`confirmed`/`dismissed` status is displayed as recorded; this
route does not confirm or dismiss a finding.

The console appears only for the exact location grant, checks response scope
and page correlation, suppresses stale requests, renders fixed fields using
text nodes, and labels stored outputs advisory. It does not run a trend model
or certify calculations. A selected estimate can load its saved smoothed
points and stored change-point detections; location changes and stale requests
cannot render results into a different location or metric. Change-point status
is informational only and no lifecycle actions are exposed.

## Boundaries and remaining work

This slice does not implement model execution, decomposition, forecast-result
reads, accuracy verification, geostatistics, or populated
numerical parity. Current application runtime database grants
remain broad; signed tenant context is not least-privilege ACL/RLS. Live OIDC
and browser behavior, scope configuration, populated fixtures, audience
review, database isolation, and `MAN-CAP-008` remain open.

## Verification and rollback

Focused route, paging, tenant-context, non-finite-value, console-contract, and
JavaScript checks use fakes. No migration, seed, candidate/legacy database,
provider, or external service is used. Rollback reverts the Gateway reader,
route registration/policy, and console panel, then regenerates
`runtime-sql-inventory.json`; no persistent data was written.
