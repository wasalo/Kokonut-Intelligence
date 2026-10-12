# HTTP sensor transaction correction

`services/ingestion/http_sensor_receiver.py` now propagates projection enqueue
errors when supplied the reading transaction. Reading insertion, device health
update, and PostgreSQL outbox enqueue must all succeed before that transaction
commits. ClickHouse delivery remains deferred and optional. The explicit
no-transaction demo path retains its warning-only direct projection behavior.

Range lookup now uses `get_sensor_type_ranges(..., strict=True)` so a failed SQL
query cannot silently substitute defaults and continue in an aborted transaction.
Reading cursors close on every path, remaining transactions roll back, and the
database connection closes even if cleanup fails. Device-secret lookup cursors
also close explicitly. Existing exact-body HMAC checks and URL/payload device
matching remain in place.

Batch requests validate all device IDs before processing any readings. A later
mismatched device no longer causes a request-wide rejection after earlier rows
have already committed. Valid batches still commit each reading independently:
they are not an atomic batch, and per-reading processing failures remain in the
returned results. Existing unknown-device/validation/processing errors still
use the existing response contract. No new public gateway route is added.

## Acceptance still pending

Static lint and diff checks passed. No tests, HTTP requests, ingestion writes,
services, or migrations were run for this slice. The running candidate image
predates this change. Rebuild before adoption.

Validate atomic enqueue failure rollback, strict range-query failure, rejection
cleanup, duplicate behavior, successful commit, commit uncertainty, connection
cleanup failure, batch preflight, exact-body HMAC, disabled ClickHouse, and HTTP
versus MQTT parity. Timestamp normalization, replay/idempotency rules, bounded
request sizes, device status policy, and shared ingestion domain extraction
remain further work before certifying equivalent transports.

Ingestion logging uses a separate transaction after the source commit. A logging
failure can therefore report an error after the reading is committed; clients
must preserve the original timestamp when retrying. This correction does not
claim atomic logging or exactly-once delivery. The standalone receiver is not
yet integrated into the Kernel gateway/profile and still requires a deliberate
ingress and authorization review before public deployment.

Rollback keeps source/outbox data and device records intact. Reverting this
correction reintroduces the swallowed-enqueue gap; keep ingestion stopped until
a validated replacement is selected. Do not delete outbox evidence or edit
applied migrations as a rollback workaround.

## Retryable HTTP outcomes

The subsequent retry correction distinguishes timestamp/payload rejection from
storage and cleanup failures. Single-reading processing failures now return 503
with `Retry-After: 30`; malformed timestamps and existing semantic rejections
remain 400, and signature failures remain 401. Credential database lookup
failure returns 503 rather than misrepresenting the device as unauthorized.
Connection creation is inside the processing error boundary, and cleanup
failure is converted to a retryable outcome by the route wrapper.

Batch responses retain per-item results and partial-commit behavior. They add
`retryable` (failed item count) and `retry_after_seconds` (30 or zero); failed
processing items carry `retryable: true`. Clients should retry only those items
with their original signed evidence and timestamps, using bounded retries and
backoff. The server does not automatically replay or impose a durable HTTP
retry budget. A 503 may follow a committed write when audit logging or cleanup
fails; duplicate handling on a stable timestamp remains necessary.

This changes the error contract for storage failures and requires client
acceptance before rollout. Legacy missing-timestamp requests still cannot
promise stable retries. UTC mode requires a stable timezone-bearing timestamp;
it remains opt-in. No internal exception details are added to HTTP responses.
Pending checks include connection/credential failure, enqueue failure, cleanup
failure after commit, retry headers, malformed timestamp rejection, mixed batch
results, and clients preserving timestamps across retries.

## Internal TCP listener rehearsal — 10 October 2026

The actual receiver was run in a temporary operator container and exercised by a
second container on the recovery fixture's internal Docker network. No host port,
TLS termination, or reverse proxy was involved. Health/authentication, one signed
single reading, a signed two-reading batch, duplicate timestamp response, and
signed URL/payload mismatch were checked. The run produced three source rows, three
pending platform events and three pending outbox rows. The temporary device secret
was removed afterward. [Sanitized evidence](builds/2026-10-10-recovery/sensor-http-listener.json).

The probe's assertions completed, but its final JSON report write targeted a host
temporary path that was not mounted into the client container. Uvicorn access logs
and a separate read-only PostgreSQL query confirmed response codes and row counts.
The runtime emitted Pydantic v2 deprecation warnings for `.dict()`; they did not
affect the requests. TLS/proxy behavior, storage failure/retry paths, concurrency,
ClickHouse delivery, and broader transport parity remain unverified.

## Route and event-path rehearsal — 10 October 2026

Runtime ASGI execution found that postponed annotations hid the receiver's local
Pydantic models and `Request` class from FastAPI, producing 422 query-parameter
errors before endpoint authentication. The module now evaluates route annotations
when the nested endpoint functions are registered. Authenticated HTTP reads also
publish `sensor_reading` through the shared event-store adapter using the same
source connection, before commit, so the canonical reading, device health,
ClickHouse outbox, and platform event share the transaction boundary.

In the isolated fixture, an invalid signature returned 401, an authenticated
single request and two-item batch succeeded, and three HTTP rows created three
events and outbox records. Together with two CSV rows, five raw ClickHouse rows
and the v3 location/day/type aggregate matched. Events remain pending; event
handler effects were not exercised. ASGI was invoked in-process because the
operator image lacks `httpx`; TCP/TLS/proxy behavior remains open. Ruff passed;
no Python test suite ran. [Evidence](builds/2026-10-10-recovery/sensor-csv-http.json).
