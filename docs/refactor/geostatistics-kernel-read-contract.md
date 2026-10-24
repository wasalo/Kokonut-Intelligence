# Geostatistics Kernel read contract

**Status:** First saved spatial-autocorrelation read implemented; CAP-008 remains prepared.
**Updated:** 24 October 2026

## Route and authorization

`GET /operator/api/geostatistics/{location_id}/autocorrelation` requires the
exact OIDC `geostatistics:read` grant for the selected location. The Gateway
validates operator/location UUIDs and bounded pagination (`limit` 1–50,
`offset` 0–10,000), then opens a repeatable-read, read-only transaction with
statement and lock timeouts. It establishes signed tenant context before
querying and returns `no-store` responses that vary by cookie.

## Returned projection

The query selects the newest `spatial_autocorrelation` row for each
`property_key` and `metric` at the exact location. It returns the metric key,
Moran/Geary/join-count kind, statistic and expected values, p-value, z-score,
sample count, spatial-weight type, distance threshold, neighbor count, and
computation time. Non-finite numeric values become `null`. Database IDs,
interpretive text, metadata, and point coordinates are omitted. Results are
bounded and paginated with deterministic ordering.

The hidden-by-default console appears only for a matching `geostatistics:read`
location grant. It validates location/page correlation and fixed enum/numeric
shapes, suppresses stale responses, renders text only, and labels saved
statistics advisory. This is a read of persisted output; it does not recompute
or independently validate statistical methods or model assumptions.

## Spatial cross-validation route

`GET /operator/api/geostatistics/{location_id}/cross-validation` uses the same
exact grant and signed transaction boundary. It returns a bounded page of
saved spatial-block, leave-one-out, and k-fold summaries with property key,
strategy, fold count, optional block size, mean error, mean squared error,
root mean squared error, mean absolute error, R-squared, and computation time.
Ordering includes a private row-ID tie-breaker for stable offset pagination.
Fold-level JSON, model identifiers, SOC model references, metadata, and
free-text notes are not selected. Non-finite numeric fields become `null`.
The console renders the fixed projection as text and labels it advisory.

## Fitted variogram route

`GET /operator/api/geostatistics/{location_id}/variogram-models` uses the same
exact grant and signed, read-only transaction. It returns a bounded page of
stored fit summaries: property, one of the schema-defined spherical,
exponential, Gaussian, or Matérn model types, sill/range/nugget/partial sill,
lag distance/tolerance, bandwidth, pair count, R-squared, and fit time. A
private row-ID tie-breaker stabilizes page ordering. Model identifiers,
metadata, and raw observations are not selected; non-finite numbers become
`null`. Values are shown as stored and are not independently validated or
treated as recommendations.

## Sensor-network design route

`GET /operator/api/geostatistics/{location_id}/sensor-network-designs` uses
the same exact grant and signed, read-only transaction. Its bounded projection
contains property, optimal spacing and coverage radius, recommended and
current sensor counts, coverage-gap percentage, confidence, and computation
time. Notes, variogram-model references, IDs, and metadata are omitted.
Non-finite numeric values become `null`. The console labels the estimates
advisory; this endpoint neither places devices nor applies a field plan.

## Kriging summary route

`GET /operator/api/geostatistics/{location_id}/kriging-summaries` applies the
same grant and signed, read-only transaction. It selects a bounded page of
location-owned prediction runs first, then aggregates only those runs' point
rows. The response contains property, method, grid resolution, stored and
actual result-point counts, mean prediction/variance/standard deviation, min,
max, and run time. It does not return per-point predictions, geometries,
model IDs, thresholds, or metadata; non-finite numbers become `null`. The
aggregation is bounded by the run page, with the transaction statement
timeout retained. The console labels the saved output advisory.

## Geostatistical realization summary route

`GET /operator/api/geostatistics/{location_id}/realization-summaries` uses the
same exact grant and signed, read-only transaction. It selects a bounded page
of location-owned simulation runs before aggregating their child points. The
response contains property, realization number, method, grid resolution,
stored and actual result-point counts, mean and population standard deviation,
minimum, maximum, and run time. It omits simulated point values, geometries,
seeds, IDs, variogram-model references, and metadata; non-finite values become
`null`. Results are advisory and do not validate simulation assumptions or
drive a lifecycle transition.

## Remaining work

Other geostatistics outputs such as kriging predictions/points and simulations,
plus fold-level diagnostics, numerical/populated fixture parity, live OIDC and
browser behavior, least-privilege ACL/RLS, audience review, and `MAN-CAP-008`
remain open. The autocorrelation producer can persist a narrative
interpretation, but this read deliberately omits it pending governed semantic
review.

## Verification and rollback

Focused Gateway, route-policy, and console checks use fake connections and
synthetic rows. No migration, seed, candidate/legacy database, provider, or
external service is used. Rollback reverts the reader, route/policy, and console
panel, then regenerates `runtime-sql-inventory.json`; no persistent data was
written.
