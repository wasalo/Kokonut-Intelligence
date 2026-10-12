# MQTT source/projection transaction boundary

The subscriber's transactional `_insert_ch(..., conn=...)` path now propagates
enqueue failures. The source reading, device health update, and projection
outbox row must all reach the existing PostgreSQL commit before the success log
is attempted. The explicit no-connection demo/maintenance projection path
retains its previous best-effort warning behavior.

Every database-backed reading path now closes its cursor in finally and clears
any remaining transaction with rollback. This includes unknown devices, topic
identity mismatch, invalid HMAC, rejected validation, malformed timestamps,
database errors, duplicate readings, and successful commits. Rollback after a
successful commit cannot undo the already-committed source/outbox transaction.
If rollback fails, the connection is closed and the subscriber clears its cached
reference so the next message attempts a fresh connection.

`get_sensor_type_ranges(db, strict=False)` retains the legacy default for other
callers. MQTT uses `strict=True`, propagating query failures rather than hiding
an aborted transaction and continuing with built-in ranges. Successfully read
rows still supplement the existing default range catalog; a query failure now
rejects processing of this message.

## Unchanged contracts and limits

Device preregistration, identity binding, HMAC canonicalization, validation,
source schema, duplicate key, outbox event key, and human actuation boundaries
are preserved. ClickHouse-disabled operation still writes the durable outbox;
projection delivery remains deferred. Ingestion logging uses its existing
separate connection and is not an atomic part of the source/outbox commit.

The message callback still logs processing errors and continues. MQTT protocol
acknowledgement/QoS, persistent subscriber sessions, message replay, and manual
ack-after-commit are not changed here. These corrections establish the intended
database transaction path in source; they do not guarantee message redelivery
after a database failure. Runtime delivery/recovery certification remains open.

## Pending acceptance and rollout

Exercise successful atomic source/outbox insertion; enqueue failure after
source insert; range-query failure; rollback and fresh-connection recovery;
commit uncertainty; cursor cleanup on all rejection/error paths; duplicate
delivery; and delivery with ClickHouse disabled. Confirm success logging cannot
precede a committed source/outbox transaction. No tests were added or run, no
messages ingested, and no broker/subscriber started in this slice.

Static lint, provider boundary, dependency grouping, and diff checks passed.
The [updated MQTT image](mqtt-overlay.md#updated-subscriber-build) includes these
corrections; runtime failure-path validation remains pending before deployment.
Rollback restores the known failure-handling gap, so keep live subscriber
deployment disabled while selecting a validated replacement. No schemas,
device records, or persisted readings were changed by implementation.
