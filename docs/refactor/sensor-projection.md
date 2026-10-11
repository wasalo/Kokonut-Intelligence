# Shared HTTP/MQTT sensor projection

`services/ingestion/sensor_projection.py` now owns the common projection column
order, row conversion, payload hash, and outbox identity used by HTTP and MQTT.
Both transport `_insert_ch` methods delegate to `project_sensor_reading` while
retaining their existing signatures for compatibility.

With a supplied PostgreSQL connection, the helper enqueues the existing
`sensor_reading:sensor_readings:READING_ID` event, identifies source and target
tables, and propagates every enqueue error. It never commits, rolls back, closes
the caller's connection, or starts delivery. The transport's source transaction
still owns reading, device health, and projection atomicity. ClickHouse remains
optional: enqueueing is canonical PostgreSQL state; disabled delivery can wait.

Without a connection, the helper performs the existing explicit direct-write
maintenance/demo operation. Transport wrappers retain warning-only handling for
that path. Production ingestion always supplies its source connection. No raw
ClickHouse SDK import or new credential requirement was introduced.

This extraction preserves the previous payload/hash conversions and does not
normalize additional fields, rewrite existing outbox rows, migrate CSV ingestion,
or change HMAC formats. Source writing and audit logging are still separate
transport implementations; complete domain-service extraction remains work.

Static lint and diff checks passed. No tests, projection delivery, source writes,
images, or services were run. Pending runtime acceptance includes exact payload
and event-key parity, wrapper compatibility, atomic enqueue failure rollback,
disabled-provider imports, direct demo behavior, duplicate handling, and
projection lineage. Rebuild receiver images before adopting this source.

Rollback restores the previous transport implementations while preserving all
outbox identities and database history. Keep the corrected enqueue failure
propagation when selecting a rollback image; do not restore a version that
silently commits after a failed projection enqueue.
