# Single-reading sensor entrypoint recovery

Updated: 10 October 2026. This is a scoped Batch 2 recovery result and a Phase 3/6
implementation signal. It does not accept the full sensor, analytics, or dMRV
capability.

## Exercised path

The normal API-style `services.ingestion.sensor_ingester.run_single` path was run
against the private recovery PostgreSQL and ClickHouse fixture. The operator used
the pinned recovery image with read-only mounts of the current
`sensor_ingester.py`, `sensor_projection.py`, and `clickhouse_outbox.py` modules.
No production or legacy container was started or changed.

For the retained 11 October synthetic slice, verification found:

- 2 canonical `sensor_reading` rows at stored four-decimal precision;
- 2 matching `sensor_reading` platform events;
- 2 distinct source UUIDs in `clickhouse_outbox`, both marked `succeeded`;
- 2 ClickHouse raw rows with matching average, minimum, maximum, sensor and
  location counts; and
- a v3 daily summary matching the two PostgreSQL source rows.

The retained machine-readable result is
[`sensor-e2e.json`](builds/2026-10-10-recovery/sensor-e2e.json). The repeatable
read-only verifier is `scripts/fixtures/kernel-recovery-sensor-e2e-verify.py`.
Ruff passed for that verifier and the touched producer modules.

## Visibility observation

The producer/outbox call reported two successful deliveries, but its first
post-delivery ClickHouse query did not see the rows within a five-second bounded
poll. A later read-only query found the two rows and the expected v3 aggregate.
The saved ClickHouse query log shows both inserts completed without exceptions in
`kokonut_analytics`; 44 immediate aggregate reads over five seconds used that same
database and reported no read rows. A later query found the sensor rows. The
effective settings show asynchronous inserts and query result caching disabled,
so those do not explain the delay. See the [sanitized query-log summary](builds/2026-10-10-recovery/sensor-e2e-clickhouse-visibility.json).
The root cause is still undetermined, so this result does not set or prove a
delivery-visibility latency guarantee. Reconciliation, restart behavior and
consumer consistency still need a deliberate acceptance rule.

## CSV and authenticated HTTP entrypoints — 10 October 2026

The isolated transport rehearsal exercised two valid CSV rows, one rejected
timestamp, an HTTP single reading, and a two-reading HTTP batch. A bad HTTP
signature returned 401; the authenticated single and batch returned success.
The route was invoked through the actual FastAPI ASGI app in-process because the
operator image does not include an HTTP test client. This covers body parsing,
middleware, route validation, HMAC, PostgreSQL writes, and responses, but not a
TCP listener, TLS, proxy, or network client.

The rehearsal exposed two HTTP path gaps. With postponed annotations, FastAPI
treated locally defined `Request` and Pydantic model types as query parameters
and returned 422 before authentication. Removing postponed annotation evaluation
made the route resolve those types at registration. The successful path also
publishes a durable `sensor_reading` platform event via the shared event-store
adapter in the same PostgreSQL transaction as the source row, health update, and
outbox enqueue.

Five new PostgreSQL source rows produced five `sensor_reading` events and five
distinct succeeded ClickHouse outbox rows. The new sensor's raw projection had
five rows with sum 150 and average 30; the location/day/type raw aggregate matched
`v_daily_sensor_summary_v3` for count, average, min/max, distinct sensor count,
and suspect count. The first read in this run saw all five rows immediately. This
does not explain or close the earlier five-second visibility delay. [Sanitized
evidence](builds/2026-10-10-recovery/sensor-csv-http.json).

The enabled `services.ingestion.anomaly_detector.handle_sensor_reading` handler
was not run; all five platform events remain pending. A random synthetic device
secret was removed and the device marked inactive after the run. Three unrelated
pending outbox rows were held only during targeted delivery and their previous
availability timestamps were restored. An earlier ASGI probe left two synthetic
CSV rows on a separate inactive device, so this fixture is not a clean baseline.

Ruff and `git diff --check` passed. No Python test suite or production image was
run. Legacy hash-keyed projection lineage, handler side effects/idempotency,
restart/concurrency, real network ingress, and dashboard/report parity remain
open; CAP-040 stays partially assessed.

Failed exploratory attempts also wrote synthetic rows to the isolated fixture.
The retained sensor has rows on 8, 9, 10 and 11 October; the fixture is not a clean
baseline for rerunning a write scenario. The saved verifier reads only 11 October
and does not modify data. Both fixture services were stopped after the transport
rehearsal; the handler check below later restarted only the database fixture.
Volumes and evidence remain available.

## Selected anomaly handler and acknowledgement recovery — 10 October 2026

After the CSV/HTTP write rehearsal, one pending synthetic low-moisture event was
processed through `services.ingestion.anomaly_detector.handle_sensor_reading` in
the isolated fixture. The first attempts exposed three existing runtime defects:
the device lookup compared text with a UUID parameter, rate-of-change evaluation
omitted its required current-value argument, and the emitted `sensor_alert` event
included a native UUID that JSON could not encode. These were corrected in the
handler; no migration was needed. Three failed attempts remain visible in durable
delivery and handler-log history before the successful fourth attempt.

The successful delivery created one warning alert for value 10 and no MRV claim.
SMTP, Directus, and actuator settings were explicitly blanked, so no external
notification or command was sent. The emitted `sensor_alert` platform event remains
pending. Four of the five sensor-reading events remain pending; no queue-wide
processor was invoked.

For acknowledgement recovery, the completed event alone was placed back in
`processing` with a new lease owner while its handler-delivery receipt remained
`success`. `_process_event` completed the event without invoking the handler again:
delivery attempt count stayed 4, handler logs stayed 4 (3 errors, 1 success), and
the alert count stayed 1. This controlled database-state simulation verifies the
durable-receipt skip path. It is not a killed-process test, concurrency test, or
proof of exactly-once behavior across arbitrary external side effects. [Sanitized
evidence](builds/2026-10-10-recovery/sensor-handler-recovery.json).

The earlier statement that all five events remained pending describes the state
immediately after transport checks; this later bounded handler rehearsal consumed
one. The real HTTP listener/proxy, additional handler types, concurrent delivery,
restarts, runtime-role policy and the rest of the recovery gates remain open. After
evidence capture, the fixture database was stopped; the analytics service remains
stopped and all volumes/checkpoints are retained.

## HTTP receiver over TCP — 10 October 2026

Created an encrypted PostgreSQL checkpoint before the listener writes at
`backups/recovery-fixture-pre-http-listener-20261011T024804Z`; its manifest records
`restore_rehearsed: false`. The actual Uvicorn receiver ran in a temporary operator
container. A second operator container sent requests over the fixture's internal
Docker network, with no host port published. This exercises the TCP/HTTP server and
route stack; it does not exercise a public ingress, TLS, or Caddy.

Observed responses: health 200; invalid HMAC 401; authenticated single 200;
authenticated two-reading batch 200 with two successes; repeat of the single
timestamp returned `duplicate`; signed URL/payload device mismatch returned 400.
A read-only PostgreSQL query found three distinct source rows (22.5, 23.5, 24.5),
three pending `sensor_reading` events and three pending ClickHouse outbox records.
At this capture point no ClickHouse worker or event handler had run yet. The
synthetic device was returned to inactive and its temporary credential removed.
Its health row remains online from the successful ingress.

The request assertions completed before a temporary probe tried to save its report
to an unmounted `/private/tmp` path. Uvicorn access logs and the independent SQL
query confirm the response codes and persisted counts. The runtime also emitted
Pydantic v2 deprecation warnings for `BaseModel.dict()`; they did not fail requests.
Evidence: [sensor-http-listener.json](builds/2026-10-10-recovery/sensor-http-listener.json).
The encrypted checkpoint and fixture volumes are retained; the listener and
database are stopped.

### Follow-up ClickHouse outbox delivery — 10 October 2026

Created a second encrypted PostgreSQL checkpoint before delivery at
`backups/recovery-fixture-pre-http-outbox-20261011T025910Z`; the encrypted dump
decrypted successfully to `/dev/null`, and restore remains unrehearsed. A private
operator container used the current service modules mounted read-only and invoked
the existing `clickhouse_outbox.deliver_batch` function. It claimed only the three
canonical UUID-keyed HTTP projections; all three succeeded on attempt one. The
preflight found no raw sink row at any target timestamp, and post-delivery reads
found exactly one row with exact numeric value parity at each timestamp. A
read-only source query confirmed the three rows were created after the exact
pre-listener checkpoint timestamp.

Three platform events for those source IDs remain pending, with zero handler
delivery or log records. No event handler ran. Three unrelated ready outbox rows
were temporarily deferred to scope the batch; their original availability times
were restored, and the three remain ready. A broad same-device event count included
older fixture work, so final event verification was narrowed to these three source
IDs. [Sanitized evidence](builds/2026-10-10-recovery/sensor-http-outbox-delivery.json).

The fixture database and analytics service were stopped afterward with volumes
retained. This confirms this synthetic delivery slice; it does not establish a
latency guarantee or public ingress behavior.

## Gates still open

- Reconcile remote or populated ClickHouse targets before promoting UUID-keyed
  producer output; the retained local legacy snapshot has no rows to remap.
- Expand handler effects/idempotency beyond the one sensor warning path; exercise
  device authorization under revocation, concurrent retries, restart/replay and
  outbox operator permissions.
- Exercise HTTP through TLS/proxy ingress and compare dashboard/report consumers;
  do not infer MQTT, CSV, or mobile parity from this internal HTTP listener.
- Compare all relevant dashboard/report queries and test recovery under a defined
  sink-visibility and duplicate-delivery policy; the listener rows now have a
  scoped successful outbox delivery.
- Do not infer MQTT/file/mobile parity from this single-reading workflow.

No migration or production cutover was made. Rollback for this rehearsal is to
stop the isolated fixture and retain or restore its scoped checkpoint; running
service images, legacy stores and canonical production data are unchanged.
