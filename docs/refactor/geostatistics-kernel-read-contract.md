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
For spatial-block rows only, it additionally projects at most ten per-fold
aggregate diagnostics when the saved array is valid, under 16 KiB, contains
exactly the declared fold count, and every fold has at least five held-out
samples. Each diagnostic contains only sequence number, train/test counts, and
aggregate error metrics. Block identifiers, coordinates, individual actual
or predicted values, failure details, model identifiers, SOC model references,
metadata, and free-text notes are never selected. Leave-one-out and other
strategies return no per-fold diagnostics because their stored details can
contain point-level values. Invalid, small-sample, oversized, or non-finite
data fails closed or becomes `null`. The console renders the fixed projection
as text and labels it advisory.

The legacy `SpatialCrossValidator.cross_validate_from_db` runner also requires
an explicitly selected variogram model to match the requested location and
property before it reads source points. A mismatch returns a generic not-found
result without disclosing whether the model exists elsewhere. Soil and remote-
sensing source reads retain their exact location predicates. This source-level
scope check does not replace a least-privilege database role or RLS policy.

The leave-one-out calculation keeps each prediction paired with the held-out
observation that produced it. If a fold fails, aggregate error and R-squared
metrics use only the remaining successful pairs; later folds are never
compared to an earlier observation by array position.

The database runner accepts only `soil_carbon`, `soil_moisture`, `soil_ph`,
and `ndvi`. Each soil property maps to an explicit source column; unsupported
keys fail before the database is opened. This avoids silently treating an
unknown soil property as organic carbon. Variogram fitting, spatial
autocorrelation, kriging, simulation, and cross-validation use the same fixed
query helper and location predicate. Explicit variogram IDs used by kriging
and simulation must also match the requested location and property, with a
generic mismatch response.

The legacy variogram producer now calls GSTools' nonlinear robust
`fit_variogram` optimizer for valid empirical bins; returned sill, range,
nugget, partial sill, and R-squared are fitted values rather than starting
estimates. Invalid or non-finite bins are excluded. Synthetic known-model
fixtures cover spherical, exponential, Gaussian, and Matérn fits. Matérn
smoothness is held at GSTools' default because the current schema does not
persist that parameter, so smoothness is not yet configurable.

Empirical bins use the configured fixed `lag_distance` width. A pair must fall
within `lag_tolerance` of its bin center; tolerance cannot exceed half the bin
width. `bandwidth` caps the maximum pair separation, while the existing
half-of-maximum-observed-distance cap is retained. Pair counts, mean lag, and
Matheron semivariance use the same selected pairs; empty bins are omitted. This
path is omnidirectional, so the application applies its documented distance
cap directly rather than relying on GSTools' directional-only bandwidth
filter. The pairwise distance calculation uses SciPy's condensed vectors;
SciPy is declared explicitly in the analytics requirement group and was
already a transitive GSTools dependency.

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
seeds, point UUIDs, variogram-model references, and metadata; non-finite values
become `null`. The summary includes `realization_id` only as a request handle
for the optional point-detail route; the console does not display it. Results
are advisory and do not validate simulation assumptions or drive a lifecycle
transition.

## Saved realization point read

`GET /operator/api/geostatistics/{location_id}/realizations/{realization_id}/points`
requires the same exact `geostatistics:read` grant and signed tenant context.
The handler uses a repeatable-read, read-only transaction with statement and
lock timeouts. It selects the parent realization by both UUID and requested
location, then repeats the location predicate on the child-point count and page
queries. A missing or foreign-location realization returns the same not-found
response after authorization, without revealing its existence.

The page is ordered deterministically by latitude, longitude, and a private
point-ID tie breaker. `limit` is bounded from 1 to 50 and `offset` from 0 to
10,000. The response includes fixed run metadata and point sequence, longitude,
latitude, and finite simulated value fields. It omits point UUIDs, seed,
variogram-model ID, metadata, and raw geometry objects. The realization UUID is
used only as an opaque request handle and is not rendered in the console. The
console loads a page only after the operator selects “View points,” validates
location/run/page correlation and numeric bounds, suppresses stale responses,
and renders advisory values through text nodes; it does not change simulation
state or lifecycle.

Thirty-nine focused Gateway, route-policy, and console-contract tests cover
tenant-context ordering, location qualification, deterministic bounded pages,
non-finite value handling, not-found behavior, no-store responses, exact route
policy, and text-only console rendering. Ruff, Python compilation, inline
JavaScript syntax, runtime SQL inventory, and capability-matrix checks pass.
The tests use mocked connections; no migration or database was used.

## Kriging neighborhood and persisted geometry contract

Ordinary, simple, and indicator kriging now honor `max_neighbors` and
`search_radius` in their direct methods and database pipeline. For each grid
point, the solver selects observations at or inside the configured radius,
orders them by Euclidean distance, breaks equal-distance ties by source order,
and limits the solve to the configured maximum. Cells with no observations in
range have null prediction/variance/standard-deviation fields and a zero
neighbor count. The CLI exposes `--max-neighbors` and `--search-radius`; invalid
values fail before PostgreSQL opens. GSTools supports replacing conditioning
positions and values through `set_condition` ([API documentation](https://geostat-framework.readthedocs.io/projects/gstools/en/stable/api/gstools.krige.Krige.html)).

The database pipeline computes a local meter grid around the mean source
latitude/longitude using the repository's existing equirectangular conversion.
Before insertion into the schema's `geometry(4326)` column, persistence applies
the inverse conversion back to longitude/latitude. Missing or invalid origin
metadata fails closed before opening a connection. Non-finite/unestimated cells
are not inserted. The 5,000-row persistence cap uses deterministic evenly spaced
sampling; the run's `n_points` still records the full prediction grid size.
These choices prevent projected meter values from being mislabeled as WGS84 and
make capped saves repeatable. The numerical projection remains a local
approximation; populated geographic parity and domain review remain open.

The complete 104-test geostatistics selection covers neighbor limits, radius
exclusion, all three methods, database/CLI forwarding and preflight, WGS84
persistence, and skipping unresolved cells. These are synthetic tests; no
candidate/legacy database or provider was used.

## Bounded conditional field simulation

The legacy `sequential_gaussian_simulation` function and `simulate` CLI entry
now use GSTools `CondSRF` conditioned through ordinary kriging. The seeded
random stream makes repeated runs reproducible and preserves the legacy result
fields (`realizations`, `grid_points`, E-type, and percentiles). The change
removes the custom dense grid-covariance matrix and Cholesky factorization; it
also changes numerical behavior, so populated-output parity and scientific
review remain required before capability acceptance. GSTools documents
conditioned ensembles through `CondSRF` and repeatable seeds ([conditioned
realization example](https://geostat-framework.readthedocs.io/projects/gstools/en/v1.6.0/examples/06_conditioned_fields/00_condition_ensemble.html)).

Validate coordinates, observations, model family, positive structured
variance/range, nugget, seed, resolution, and realization count before the
simulation engine runs. Reject unknown model names rather than substituting an
exponential model. Resource bounds are 100,000 grid points, 1,000
realizations, and 1,000,000 aggregate numeric values across the returned grid,
realizations, and summary arrays. Calculate the grid size before allocating its
axes, then check the aggregate output budget before allocating realization
arrays. The DB pipeline rejects
malformed/non-finite source rows before generation and only adds location and
coordinate metadata to successful output.

The local simulation grid uses meters relative to the mean input latitude and
longitude. Persistence requires this origin, inverse-transforms positions to
WGS84 before inserting `geometry(4326)`, rejects invalid and near-polar origins
before opening PostgreSQL, drops non-finite/out-of-range cells, and samples
the point cap deterministically. The projection remains a local equirectangular
approximation; geographic parity remains part of scientific review.

The 129-test geostatistics module now covers seeded reproducibility, the
GSTools conditional-field path without dense Cholesky, resource bounds,
invalid/degenerate models, DB source preflight, CLI settings, and WGS84
persistence. These checks use synthetic data and mocks; no migration or
database was used.

## Remaining work

Other geostatistics outputs such as per-point kriging predictions/points,
numerical/populated fixture parity, live OIDC and browser
behavior, least-privilege ACL/RLS, audience review, and `MAN-CAP-008` remain
open. Source property selection and explicit model scope now share one contract
across all five legacy database runners; this source-level validation is not a
replacement for database privileges or RLS. Fold aggregates are a bounded presentation of saved values, not a
recomputation or scientific validation. The autocorrelation producer can persist a narrative
interpretation, but this read deliberately omits it pending governed semantic
review.

## Verification and rollback

Focused Gateway, route-policy, and console checks use fake connections and
synthetic rows. No migration, seed, candidate/legacy database, provider, or
external service is used. Rollback reverts the reader, route/policy, and console
panel, then regenerates `runtime-sql-inventory.json`; no persistent data was
written. The 73-test source-pipeline selection additionally checks the shared
property map, rejection before connection, and kriging/simulation model scope;
rollback for that source work is a code revert and SQL-inventory regeneration.
The 78-test geostatistics selection also checks optimizer recovery against
deterministic synthetic model curves and uses no database connection.
