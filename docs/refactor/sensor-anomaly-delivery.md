# Sensor anomaly idempotency and delivery

Status: the signed worker integration is implemented and passed eight
synthetic end-to-end PostgreSQL 16 checks. The separate crash/replay exercise
below passed against the earlier handler path; it does not yet establish live
process recovery for the new signed adapter. Broader event-bus, provider, and
Batch 2 acceptance gates remain open.

## Event processing boundary

`services.ingestion.anomaly_detector.handle_sensor_reading` requires the stable
`platform_event.id` and delegates to `services.ingestion.sensor_anomaly_worker`.
The adapter requires a dedicated worker DSN and opaque credential, establishes
signed `sensor_reading/process` context, and reads the exact event-linked source
row through bounded database functions. It never rescans recent sensor history
or directly reads/writes the protected tables.

For every enabled alert rule, `sensor_anomaly_effect` reserves the
`(source_reading_id, alert_rule_id)` pair before evaluation and records
`no_match`, `cooldown`, or `alert_created`. A replay skips a rule with an
existing receipt. The receipt, alert, audit row, optional draft claim,
notification intents, actuator approval record, and follow-up `sensor_alert`
event share one non-autocommit PostgreSQL transaction. Migration 414 publishes
canonical, source-derived event context through a bounded function, then
enqueues notification intents with matching payloads. The downstream
notification handler deduplicates the event-backed intent. The worker commits
once after all bounded effects succeed and rolls back on any error. The receipt
suppresses duplicate work after a retry.

The receipt intentionally has no foreign key to source events or readings so
event cleanup or later source archival cannot erase duplicate suppression.
There is no automatic receipt pruning. Auto-created claims use the source
reading's date. Migration 376 also allows `requires_approval` in
`actuation_log.status`, matching the existing critical-severity safety path.

## Notifications and actuators

Event-driven `sensor_alert` notifications are queued through
`services.events.notification_outbox`. Webhook and Directus payloads include
alert context; email stores only the subject/body. SMTP host, recipient, sender,
username and password are read from the delivery worker environment at send
time and are not written into outbox rows. Email includes an outbox-derived
`Message-ID` and `X-Kokonut-Idempotency-Key`; SMTP delivery remains at-least-once
because receiver-side deduplication is not guaranteed.

The worker checks actuator configuration through a signed boolean-only
function, then records configured work as an approval-required intent in the
same transaction. Critical alerts always use status `requires_approval`, with
`human_approval_required=true` and no approver. The anomaly worker does not
publish commands to MQTT or execute them; approval remains a separate human
action. Legacy CLI and baseline alert paths retain their existing notification
entry points.

SMTP configuration is optional and forwarded only to Kernel app/worker roles:

```dotenv
ALERT_SMTP_HOST=
ALERT_SMTP_PORT=587
ALERT_SMTP_USER=
ALERT_SMTP_PASSWORD=
ALERT_EMAIL_FROM=alerts@kokonut.network
ALERT_EMAIL_TO=
```

Email is enabled only when both `ALERT_SMTP_HOST` and `ALERT_EMAIL_TO` are set.
Directus still requires its feature flag and admin token. Provider settings are
read at delivery time, so disabled or removed providers remain unclaimed rather
than consuming retry attempts.

## Recovery evidence and rollback

The isolated check uses
[`docker-compose.kernel-recovery-sensor.yml`](../../docker-compose.kernel-recovery-sensor.yml)
and [`sensor-anomaly-recovery-check.py`](../../scripts/fixtures/sensor-anomaly-recovery-check.py).
It ran the real `EventBus.process_pending()` path in a child process and forced
exit code 86 after the handler transaction committed but before the delivery
receipt and source event could be acknowledged. The source event and handler
receipt remained `processing` at attempt one with no handler log. After the
fixture expired only that event's lease, a replacement worker reclaimed it and
finished attempt two; the event completed, the delivery receipt became
`success`, and one success log was recorded. The retry created no duplicate
alert, draft claim, per-rule receipt, notification intent, follow-up event,
ingestion log, or actuation record. The recovery worker reported one processed
source event, one skipped follow-up event, and no failures or lost leases.
SMTP formatting was tested with a fake transport; no provider or actuator was
contacted. The fixture's internal network disabled egress, published no ports,
and its volume was retained after stopping the database. It applied only the
schema set needed for this slice, not all repository migrations.

Machine record: [sensor anomaly crash/retry](builds/2026-10-11-recovery/sensor-anomaly-crash-retry.json). This is retained as evidence for the prior handler path, not the new migration-414 adapter.

The current signed adapter was exercised by
[`check-sensor-anomaly-worker-delivery-disposable.py`](../../scripts/check-sensor-anomaly-worker-delivery-disposable.py)
against isolated PostgreSQL 16 after EventBus migrations 116/165 and worker
migrations 405–414. Its eight checks cover migration replay, signed forced-RLS
operations, alert/claim/notification and approval-intent writes, notification
payload parity, retry suppression, direct-table denial, and a real EventBus
child-process crash followed by lease reclaim and attempt-two completion
without duplicate effects. Evidence:
[sensor-anomaly-worker-delivery-disposable.json](builds/2026-10-16-recovery/sensor-anomaly-worker-delivery-disposable.json).

Migration 376 is additive. To roll back application behavior, disable the
`anomaly_detector` event registration or deploy the prior application image;
keep receipt and outbox data intact. Do not drop receipts or queued notices as a
rollback shortcut. Candidate and legacy application databases were not changed.

Remaining gates: provision a real isolated worker login, secret, and active
location grant; roll migration 414 onto the candidate after a fresh checkpoint;
verify candidate recovery and external provider delivery; accept authenticated operator approval/replay policies; establish
dynamic receipt/notification retention policy; and expand recovery coverage
for other handlers and runtime conditions. No MAN-CAP status is implied by the
disposable implementation checks.
