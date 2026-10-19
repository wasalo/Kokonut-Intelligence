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

## Source-level state-machine checks — 19 October 2026

Eleven focused mocked checks cover accepted and rejected terminal outcomes,
duplicate suppression, exception-class-only retry records, the fifth-attempt
dead-letter transition, reviewed replay with a fresh attempt budget, paired
actor/reason validation, and the payload size bound. The checks found and fixed
a malformed replay case where a reason without an actor was silently treated
as ordinary processing. Related MQTT/IoT redaction and transport contract
checks pass 59 tests total. These use fake connections and do not verify SQL
behavior, PostgreSQL concurrency, broker acknowledgement, or reconnect/replay
after a process crash ([evidence](builds/2026-10-19-recovery/mqtt-delivery-state-machine.json)).

## Disposable PostgreSQL 16 and Mosquitto acceptance — 19 October 2026

The migration-372 schema and delivery function were exercised against a fresh
PostgreSQL 16 container with no volume and a loopback-only host binding. Twelve
assertions passed: accepted/rejected receipt persistence, terminal duplicate
suppression, five persisted failures and the dead-letter transition, replay
action history with a fresh attempt budget, operator disposal and terminal CLI
output, concurrent identical-delivery serialization, single-winner concurrent
operator replay/disposal, source/receipt recovery after a child exits at the
commit gap, row-lock timeout recovery, the database payload-size constraint,
and private operator-list redaction. The fresh database container was removed
afterward. A second phase exercised the real Paho subscriber callback against a
disposable Mosquitto broker: a subscriber child exited after its failed receipt
committed but before ACK, a replacement process using the same persistent client
ID received the message with MQTT `DUP=1`, advanced the receipt to accepted on
attempt two, committed one synthetic source effect, and ACKed only after receipt
processing returned. A third connection proved the broker did not redeliver after
that ACK. Both containers had no volumes and were bound to loopback; both were
removed afterward. Candidate, legacy, providers, and production broker were
untouched ([checker](../../scripts/check-mqtt-delivery-disposable.py);
[evidence](builds/2026-10-19-recovery/mqtt-delivery-postgresql-mosquitto.json)).

One synthetic child exits after its source insert commits and before the receipt
transaction commits; redelivery recognizes the existing source key without
duplicating the effect. The separate broker run exercises a real subscriber
process crash after a retryable receipt and before ACK, persistent-session
redelivery, and post-ACK suppression. The Mosquitto test listener used anonymous
plaintext only on loopback. Neither test exercises actual sensor/outbox lineage,
production TLS/ACL/device HMAC, broker restart/persistent-storage recovery, or
replay after device-authorization changes.

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
pending. They have since been applied through the checksummed runner to the local
Kernel candidate; later candidate schema state is recorded in the subsequent
rollout evidence. The legacy stack and production were not migrated by that
update. The
[subscriber image](mqtt-overlay.md#updated-subscriber-build) is a historical
local build and has not been rebuilt from the current checkout or deployed. A
separate disposable Mosquitto/Paho acceptance now exercises broker delivery and
subscriber process recovery; it does not deploy or contact the configured Kernel
broker, real sensor, or production service.

Pending acceptance: production sensor/outbox parity at the source/receipt
crash boundary and reading-key parity; replay after device authorization
changes; production TLS/ACL/device-HMAC identity; and broker restart with its
persistent storage. Timestamp canonicalization and existing duplicate keys need
explicit parity checks. Storage-outage restart behavior, operator alerting, and
dynamic retention remain unresolved;
subscription readiness is implemented in [source](mqtt-readiness.md) but still
awaits runtime checks. The processing budget is not a bound on every possible
infrastructure restart. Static lint, provider/dependency gates, and diff checks
passed.

## Rollback

Stop ingestion before changing delivery mode or image. Retain additive tables,
private evidence, operator actions, and broker session state. Reverting source
does not erase or automatically replay acknowledged dead letters; recover them
explicitly through a reviewed command. Never edit an applied migration or reset
recorded attempts as an automatic workaround for a failure.
