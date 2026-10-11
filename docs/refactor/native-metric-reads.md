# Native public metric read execution

`GET /api/metrics/{location_id}` continues to use the owned analytics catalog's
`PUBLIC_METRIC_SUMMARY` query, its matching public location context, and the
canonical PostgreSQL `v_public_metric_summary` view. Route policy remains
explicitly public metric/read. No computation, verification, or lifecycle write
is performed.

The gateway now dispatches the synchronous catalog query through Starlette's
thread pool. The default PostgreSQL adapter uses a 3-second connection timeout,
read-only transaction, 5-second statement timeout, and 2-second lock timeout.
Cursor close, rollback, and connection close run on success or failure. Injected
factories retain their no-argument connection contract. Unknown catalog queries
and mismatched/non-public contexts are rejected before opening a connection.

UUID syntax is checked before the query: malformed identifiers now return 400
rather than becoming a database error and generic 500. Valid identifiers preserve
the existing response keys: location_id, computed, and total_computed. Missing or
excluded locations yield an empty computed array; no new existence disclosure is
introduced. Metric dictionaries retain their fields and ISO timestamp formatting.

`metric_value.value` is NUMERIC(15,4), which psycopg2 returns as Decimal. The
contract now acknowledges Decimal and the gateway uses FastAPI's JSON encoder
before constructing its response. Values are emitted as JSON numbers using that
encoder's integer/float convention. This is a presentation conversion, not an
exact-decimal financial export format; canonical values remain unchanged in
PostgreSQL. Precision-sensitive consumers need an explicit decimal contract.

The view requires an active location, active metric definition, verified metric
value, and verified/published farm registry record. It selects the latest verified
timestamp per metric/location and orders by metric key. Timestamp ties can yield
multiple values; this slice does not deduplicate or arbitrarily truncate existing
results. Field visibility and the view itself were not changed.

## Acceptance and rollback

Lint, provider boundaries, dependency groups, and diff checks passed. No tests,
metric computation, live metric request, or data creation ran. Populated-response
serialization, visibility, malformed-ID behavior, concurrent requests, timeout
cleanup, and response compatibility remain unvalidated at runtime. Thread-pool
queueing, cleanup, serialization, and connection behavior mean these are operation
timeouts, not a full request deadline or a certified resource budget.

Deployment/image evidence is recorded in [the portability runtime record](portability-runtime.md).
Other gateway analytics routes still need their own execution and capability review.
Rollback selects the previous application image; no schema/data rollback is needed
for these read-only changes. Preserve the public view and current route policy.
