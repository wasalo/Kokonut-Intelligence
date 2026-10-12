# Sensor anomaly idempotency and delivery

Status: implemented and exercised in a synthetic internal-only PostgreSQL
fixture. This closes the selected sensor anomaly crash/replay gate, not the
broader event-bus, provider, or Batch 2 acceptance gates.

## Event processing boundary

`services.ingestion.anomaly_detector.handle_sensor_reading` now requires the
stable `platform_event.id`. It resolves that event's exact
`source_table='sensor_reading'` / `source_id` and evaluates that one reading;
event delivery no longer rescans the sensor's recent hour of readings.

For every enabled alert rule, `sensor_anomaly_effect` reserves the
`(source_reading_id, alert_rule_id)` pair before evaluation and records
`no_match`, `cooldown`, or `alert_created`. A replay skips a rule with an
existing receipt. The receipt, alert, optional draft claim, ingestion log,
notification intents, actuator approval record, and follow-up `sensor_alert`
event share the handler's PostgreSQL transaction. The `EventBus.publish()`
event ID is allocated before enqueue and reused when publishing, so
`notification_outbox.source_event_id` points to the actual follow-up event. The
`EventBus.publish()` commit is the durable boundary; a crash immediately
afterward can cause a handler retry but does not recreate those effects.

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

The event handler records configured actuator work in `actuation_log` within
the same transaction. Critical alerts always use status `requires_approval`,
with `human_approval_required=true` and no approver. The anomaly handler does
not publish commands to MQTT or execute them; approval remains a separate human
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

Machine record: [sensor anomaly crash/retry](builds/2026-10-11-recovery/sensor-anomaly-crash-retry.json).

Migration 376 is additive. To roll back application behavior, disable the
`anomaly_detector` event registration or deploy the prior application image;
keep receipt and outbox data intact. Do not drop receipts or queued notices as a
rollback shortcut. Candidate and legacy application databases were not changed.

Remaining gates: external provider contract/acceptance, authenticated operator
approval/replay policies, receipt and notification retention ownership, and
recovery coverage for additional handlers and runtime conditions. CAP-047,
CAP-040 and Batch 2 remain partial.
