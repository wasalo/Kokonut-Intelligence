# Durable MQTT outcomes and operator recovery

Migration `372_mqtt_delivery_records.sql` adds private mqtt_delivery evidence
and mqtt_delivery_action operator history. Evidence includes topic and the
original signed payload (at most 10 KiB); it remains off-chain in the private
database, with no gateway route or public export added. Do not log, publish, or
return raw payloads through recovery lists. Apply retention/encryption and
database-access policy appropriate to the existing private sensor evidence.

## Processing and acknowledgement

In opt-in QoS 1 mode, process_delivery identifies a delivery by SHA-256 of its
topic plus original payload bytes and serializes matching deliveries under a
database row lock. Outcomes are pending, accepted, rejected, failed,
dead_letter, or disposed. Duplicate source readings count as accepted. Accepted,
rejected, dead-letter, and disposed receipts suppress further automatic
processing of the identical delivery. Normal rejects are now durably recorded
before acknowledgement.

Processing exceptions record the exception type (not SQL or raw error text),
increment attempt_count, and commit failed/dead-letter evidence. Attempts below
five leave the delivery unacknowledged and fail the subscriber callback for
broker redelivery. The fifth failure commits dead_letter before allowing ACK.
Failure to store the outcome or send ACK still propagates; a later redelivery
can observe the committed terminal receipt. Database-outage/lock failures that
prevent receipt persistence do not consume a recorded processing attempt.

The source/outbox transaction commits before the separate receipt transaction.
They are not one atomic transaction. A crash between them can redeliver and use
the existing reading duplicate key before recording accepted. The row lock is
held during source processing and is released transactionally on connection
loss; no separate lease worker or background replay dispatcher is introduced.
Five-second lock waits bound lock acquisition, not SQL execution or processing.
Long database operations can still block MQTT network-loop progress.

## Explicit recovery commands

```sh
python3 -m services.ingestion.mqtt_delivery_cli --list
python3 -m services.ingestion.mqtt_delivery_cli --replay DELIVERY_UUID --actor OPERATOR --reason "Corrected upstream problem"
python3 -m services.ingestion.mqtt_delivery_cli --dispose DELIVERY_UUID --actor OPERATOR --reason "Reviewed invalid evidence"
```

Lists show identifiers, states, attempt counts, exception types, and times only.
Replay/disposal require a nonempty actor and reason, recording an action row.
Only failed, rejected, or dead-letter receipts support those actions. Replay
uses the retained signed payload without broker publication, rechecks the
current device/topic/HMAC/validation policy, and starts a new reviewed retry
budget. It does not edit evidence, preregister a device, or bypass validation.
Replay returns nonzero unless accepted. Disposal marks the receipt terminal
without writing a sensor reading. Operator access is local CLI/database access;
no API authorization policy or financial write authority is added.

## Rollout and remaining gates

At the time this recovery slice was written, migrations 371 and 372 were still
pending. They have since been applied through the checksummed runner to the
active local Kernel candidate, which is now at migration 379. The legacy stack
and production are separate and were not migrated by this update. The
[subscriber image](mqtt-overlay.md#updated-subscriber-build) is a historical
local build and has not been rebuilt from the current checkout or deployed. No
broker start, ingestion, operator replay/disposal, or runtime MQTT recovery check
occurred during this source slice.

Pending acceptance: rejection persistence before ACK; five failure attempts;
dead-letter redelivery; source commit then receipt failure; duplicate readings;
concurrent delivery/replay/disposal; rollback/lock timeout; oversized evidence;
private-list output; action history; replay under changed device authorization;
and broker persistence/crash recovery. Timestamp canonicalization and existing
duplicate keys need explicit parity checks. Storage-outage restart behavior,
operator alerting and retention remain unresolved; subscription readiness is
implemented in [source](mqtt-readiness.md) but still awaits runtime checks. The
processing budget is not a bound on every possible infrastructure restart.
Static lint, provider/dependency gates, and diff checks passed.

## Rollback

Stop ingestion before changing delivery mode or image. Retain additive tables,
private evidence, operator actions, and broker session state. Reverting source
does not erase or automatically replay acknowledged dead letters; recover them
explicitly through a reviewed command. Never edit an applied migration or reset
recorded attempts as an automatic workaround for a failure.
