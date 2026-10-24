# Trend analysis Kernel read contract

**Status:** Saved trend reads and signed forecast generation implemented; capability remains prepared.
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

`GET /operator/api/trends/{location_id}/decomposition` uses the same exact
grant and signed-context transaction and reads only the newest saved
decomposition for the requested metric. The response includes the method,
period, saved summary statistics, source-point count, and the first 200
zero-based values of each trend, seasonal, and residual component. SQL bounds
each JSON array before returning it; malformed/non-array components become
empty arrays, and non-finite component or summary values become `null`. The
response marks whether any component was truncated. The console labels a
truncated result as partial and all saved decomposition output as advisory.
This read does not calculate or verify decomposition.

`GET /operator/api/trends/{location_id}/forecast` uses the exact
`trend_analysis:read` grant and signed-context transaction and selects the
newest saved `time_series_forecast` row for the requested metric and location,
regardless of its stored `active`/`superseded`/`expired` status. It returns at
most 100 forecast values and interval entries. Interval objects are reduced to
step, forecast, lower, and upper fields; the only other interval field exposed
is a finite confidence value. Non-finite or malformed numbers become `null`
and the response marks truncation. Model parameters, metadata, identifiers,
and accuracy rows are omitted. Status is displayed as stored.

`POST /operator/api/trends/{location_id}/forecast` requires a separate exact
`trend_analysis:compute` grant, authenticated operator session, and CSRF
protection. Its streamed JSON body is capped at 4 KiB. It validates a metric
key, a 1–100 step horizon, and one of the supported confidence levels (0.90,
0.95, 0.99) before connecting. In a single transaction it establishes signed
tenant context first, takes a per-location/metric advisory lock, and loads at
most the 365 newest verified values for an active metric definition at that
exact location. Draft/unverified values and other locations are excluded. It
calls the existing in-process ARIMA helper; this implementation is an advisory
approximation, not a verified scientific result. Forecast values and
confidence intervals must be finite and match the requested horizon before
persistence.

An active ARIMA forecast with the same digest of verified observation
identifiers and values, algorithm version, cadence, horizon, and confidence is
reused. Changed inputs supersede previous active ARIMA forecasts and insert
one new active ARIMA row atomically; other model types are not superseded. The
persisted model parameters contain only algorithm/config and an input digest;
the fixed `metadata` records advisory state and operator attribution. Cadence
comes from the metric definition's update frequency, or uses `observation`
when no supported frequency is configured. Failures roll back all writes. The
response is a fixed identifier/status summary; the console then reloads the
bounded read projection. It never verifies or publishes a forecast.

The console appears only for the exact location read grant, checks response
scope and page correlation, suppresses stale requests, renders fixed fields
using text nodes, and labels stored outputs advisory. Read controls do not run
a trend model or certify calculations. A selected estimate can load its saved
smoothing points, stored change-point detections, and seasonal-decomposition
preview; it can load saved forecast steps too. A separate generate button
appears only for locations with the exact compute grant and sends a
CSRF-protected, same-origin request.
Location changes and stale requests cannot render results into a different
location or metric. Stored change-point/forecast status is
informational only and no lifecycle actions are exposed.

## Boundaries and remaining work

This slice does not implement forecast-accuracy verification, geostatistics,
or populated numerical parity. Current application runtime database grants
remain broad; signed tenant context is not least-privilege ACL/RLS. Live OIDC
and browser behavior, scope configuration, populated fixtures, audience
review, database isolation, and `MAN-CAP-008` remain open.

## Verification and rollback

Focused route, paging, tenant-context, bounded-input, idempotency, atomic-write,
console-contract, and JavaScript checks use fakes. No migration, seed,
candidate/legacy database, provider, or external service is used. Rollback
reverts the Gateway reader/writer, route registration/policy, and console
panel, then regenerates `runtime-sql-inventory.json`; no persistent data was
written.
