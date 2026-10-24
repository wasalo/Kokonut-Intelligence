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

## Remaining work

Other geostatistics outputs, numerical/populated fixture parity, live OIDC and
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
