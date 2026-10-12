# Isolated event-handler effect and concurrency checks

Updated: 11 October 2026. Batch 2 recovery evidence; this supports the later
Phase 7 workflow work but does not accept that phase or CAP-040.

## Metric handler

Restored the retained encrypted recovery checkpoint into a new PostgreSQL 16
container and isolated Compose project. The destination began with no user
relations, used the checkpoint's recorded database image, had an internal-only
network and no published ports, and restored 364 applied schema records. The
current event/cache/database source was mounted read-only into each operator
container. The new database was stopped after the check; its volume remains
available for review. Candidate API/database containers stayed healthy, and the
legacy stack remained stopped.

Inserted 16 uniquely marked synthetic `metric_computed` events, 16 analytics
cache rows for one synthetic location, and three sentinel cache rows for a
different synthetic location. Four separate operator containers ran the real
event CLI concurrently, each with a batch size of four. An in-flight database
read captured six completed and ten processing events across all four distinct
worker IDs. Each worker then reported four processed, zero failed and zero
skipped.

The allowlisted `services.cache.events.handle_metric_computed` handler invalidated
all 16 target cache entries. It left all three sentinel entries valid. PostgreSQL
recorded 16 successful handler receipts and logs, one attempt per event, with all
event leases released. This verifies concurrent claims across different events
and one real PostgreSQL-backed handler effect. It does not prove duplicate
same-event exclusion after lease expiry or exactly-once external effects.

The restored checkpoint contains one unrelated expired synthetic fixture event.
Its lease was moved forward only while the global worker ran, then restored to
the exact original timestamp. No other fields on that event changed. The new
probe data remains only in the separately named recovery volume.

## CRISP handler

On the same retained checkpoint volume, inserted 16 uniquely marked
`crisp_scored` events, 16 CRISP cache rows for a synthetic target location, and
three sentinel CRISP rows for a different synthetic location. Four separate
operator containers were launched concurrently with batch size four. Final
PostgreSQL ownership records show each of the four worker IDs completed four
events.

The allowlisted `services.cache.events.handle_crisp_scored` handler invalidated
all 16 target CRISP rows with reason `crisp_scored:crisp_scored`; it preserved
all three sentinel rows. PostgreSQL recorded 16 successful receipts and logs,
one attempt per event, and released all leases. The same generalized probe
helper also reverified the earlier metric-handler run successfully.

The CRISP in-flight observer query initially failed because `status` was
unqualified in a join. The helper now qualifies that column, and final worker
assignment is retained, but this CRISP run has no in-flight snapshot. The prior
metric run retains its own in-flight observation. Neither check exercises an
expired-lease takeover or a worker crash during a handler.

## Same-event active lease

A separate synthetic CRISP event exercised the same-row claim boundary. Worker
A claimed the event and entered the real cache handler while a temporary
PostgreSQL table lock held the cache write. The database showed one processing
delivery attempt owned by worker A. Worker B then ran the real event CLI; it
processed no event, and a second read still showed the event and delivery owned
by A with attempt count one. After releasing the lock, worker A completed the
event, wrote one successful receipt/log, invalidated its target cache row, and
preserved the sentinel row. This confirms an unexpired active lease excludes a
second claimant for the same event.

This does not test reclaim after the lease expires while the old handler is
still running, nor a process crash after a handler side effect and before the
receipt or event completion commits.

## Expired-lease takeover while the handler remains active

A fresh synthetic CRISP event was claimed by worker A. Its cache update was
held behind a temporary PostgreSQL `SHARE` lock; the first snapshot showed one
blocked cache update, a processing delivery, and worker A as lease owner. The
guarded fixture helper then expired only that event's lease. Worker B claimed
the same event while A's handler remained blocked. The second snapshot showed
worker B as owner, delivery attempt two, and two blocked cache updates, proving
both handler processes were still in flight.

After the lock was released, both handler calls succeeded. Worker A invalidated
zero rows because worker B had already invalidated the target; A then lost the
event completion race and its CLI reported one failed event. Worker B completed
the event. The final delivery row is successful at attempt two, PostgreSQL has
two successful handler logs, the target row is invalidated once, and the
sentinel remains valid. This confirms stale-lease takeover and duplicate
invocation for one idempotent cache effect. It does not establish safety for
non-idempotent or external side effects.

An initial attempt with the default 30-second handler timeout dead-lettered
before the second claim could be captured, leaving both cache rows unchanged.
For the successful isolated rehearsal, only the recovery fixture's handler
timeout was temporarily raised from 30 to 120 seconds; it was restored to 30
afterward. No application source setting or migration changed. [Machine
evidence](builds/2026-10-11-recovery/same-event-stale-lease-takeover.json).

## Handler timeout and retry

A separate synthetic CRISP event was held at its cache write by a temporary
PostgreSQL table lock. Worker A exceeded the handler's 30-second deadline. The
event returned to `pending` with `retry_count = 1`; its first delivery attempt
was recorded as a timeout. After releasing the lock, a new operator process
handled the same event successfully on attempt two. The event completed with
one timeout log and one success log. The real allowlisted cache handler
invalidated its one marked target row and preserved its sentinel row.

This demonstrates timeout-to-pending retry for one idempotent cache effect. The
temporary lock lasted longer than the handler deadline, so the planned second
worker did not run during the active lease; no expired-lease takeover was
tested. This also does not cover a process crash after an external side effect
or exactly-once delivery. [Machine evidence](builds/2026-10-11-recovery/same-event-timeout-retry.json).

## Reproduction artifacts

- Machine-readable counts, image/volume identities and source hashes:
  [evidence JSON](builds/2026-10-11-recovery/event-handler-concurrency.json)
- CRISP delivery and cache-effect evidence:
  [CRISP evidence JSON](builds/2026-10-11-recovery/crisp-handler-concurrency.json)
- Same-event active-lease exclusion evidence:
  [claim evidence JSON](builds/2026-10-11-recovery/same-event-claim-exclusion.json)
- Same-event handler-timeout and retry evidence:
  [retry evidence JSON](builds/2026-10-11-recovery/same-event-timeout-retry.json)
- Same-event stale-lease takeover evidence:
  [takeover evidence JSON](builds/2026-10-11-recovery/same-event-stale-lease-takeover.json)
- Guarded synthetic prepare/observe/verify helper:
  [recovery probe](../../scripts/fixtures/kernel-recovery-handler-concurrency.py)
- Guarded single-event exclusion helper:
  [same-event probe](../../scripts/fixtures/kernel-recovery-same-event-claim.py)
- Recovery source database and checkpoint scope:
  [preparation record](recovery-preparation.md)

The probe helper requires the explicit recovery Compose project marker, the
production-style private database settings, a new UUID run ID, and no unrelated
pending or expired event. It refuses a reused run ID. Keep the separate recovery
project and volume; do not point the worker at candidate, portability or legacy
databases.

## Stale-worker reporting correction

The takeover evidence above captured the pre-correction CLI output: worker A
reported one failure after worker B had reclaimed and completed the event. The
bus now returns a separate `lease_lost` statistic for that outcome and does not
attempt a retry/dead-letter update from the stale owner. Handler errors and
timeouts continue to increment `failed`. A one-shot CLI run exits successfully
when lease loss is its only outcome, and the persistent worker waits for its
poll interval when it has no processed or failed work.

The focused regression function exercised the `lease_lost` accounting and
verified that no stale-owner retry is attempted. It passed by direct invocation;
`py_compile` and `git diff --check` also passed. `pytest` is unavailable in the
host Python environment, so the standard runner did not execute. The historical
machine evidence was not edited; a live concurrent CLI rerun remains useful
confirmation. This change only clarifies worker reporting and polling behavior;
it does not strengthen handler idempotency or external side-effect guarantees.

## Process crash after a committed handler effect

A separate synthetic event exercised the crash window after the real
`handle_crisp_scored` child committed its cache invalidation but before the
parent updated `event_handler_delivery`. The parent was terminated with exit
code 86 at that boundary. The checkpoint showed a processing event and
processing delivery on attempt one, no handler log, one invalidated target
cache row and the valid sentinel. A guarded update expired only that event's
lease; the real event CLI reclaimed it, invoked the handler again, invalidated
zero additional rows and completed the event on delivery attempt two. The final
event lease was released, one success log was present, the target remained
invalid and the sentinel remained valid. [Machine evidence](builds/2026-10-11-recovery/event-crash-after-side-effect.json).

This demonstrates retry after a lost receipt for one idempotent database cache
effect. It is not exactly-once delivery: the handler ran twice. The lease was
expired by a guarded synthetic-only update instead of waiting for its full
duration. The unrelated seeded fixture event was deferred only during this
global-worker check and restored to its exact prior timestamp. The isolated
database is stopped with its volumes retained.

## Registered handler inventory and replay boundary

The effective migration state registers and the execution allowlist permits five
handler/event pairs:

| Event | Handler | Observed effect and replay boundary |
| --- | --- | --- |
| `metric_computed` | `services.cache.events.handle_metric_computed` | Scoped analytics cache invalidation. Concurrent delivery and crash/retry were exercised; duplicate invocation changes no additional rows. |
| `crisp_scored` | `services.cache.events.handle_crisp_scored` | Scoped CRISP cache invalidation. Concurrent delivery, same-event lease/retry and crash/retry were exercised; duplicate invocation changes no additional rows. |
| `sensor_reading` | `services.ingestion.anomaly_detector.handle_sensor_reading` | Resolves the exact source reading and reserves a per-reading/rule effect receipt before evaluating it. Alert, optional draft claim, ingestion log, durable notification intents, actuator approval record, and follow-up `sensor_alert` event share one transaction. A synthetic hard exit after handler commit but before EventBus receipt acknowledgement was recovered by a replacement worker on attempt two; all effects remained single-copy and critical actuator work remained `requires_approval`. External provider acceptance and recovery coverage for additional handlers/runtime conditions remain open. |
| `data_stale` | `services.events.handlers.handle_stale_data` | Delegates to the shared alert handler, which persists configured webhook/Directus delivery intent before the event receipt succeeds. Isolated fake-transport queue/recovery checks passed; real provider acceptance remains open. |
| `threshold_breached` | `services.events.handlers.handle_alert_notification` | Persists the same webhook/Directus notification intents as `data_stale`; isolated fake-transport queue/recovery checks passed, with real provider acceptance open. |

The original handler registrations in migration 116 were repaired by migration
297 for the sensor and stale-data module paths. The two cache handlers have
scoped database effects suitable for the existing at-least-once worker model.
The alert paths use additive migrations `375_notification_outbox.sql` and
`376_sensor_anomaly_delivery.sql` plus `services.events.notification_outbox`:
stable `(source event, channel, destination)` keys, durable attempt history,
expiring leases, bounded retry, dead-letter and operator audit/replay/disposal.
The dispatcher reads webhook, Directus and SMTP destinations from its runtime
environment, pauses channels whose providers are disabled, and sends stable
idempotency headers; external delivery remains at-least-once when a receiver
does not honor them. Sensor anomaly database effects and notification intents
now have a per-reading/rule receipt and passed an isolated hard exit followed
by actual EventBus lease reclaim and receipt recovery for one synthetic event.
The durable notification identity references the actual preallocated downstream
`sensor_alert` event ID.
Email uses a stable `Message-ID`, but SMTP receiver deduplication is not
guaranteed. Real provider acceptance remains open.
Noncritical actuator records may use status `pending` when configured without
approval; this handler only records work and does not publish MQTT commands.
Critical records use `requires_approval` and remain behind human approval. Any
refactor must retain that boundary.

No notification endpoint or actuator was contacted while implementing this
boundary. The candidate stack was left untouched and the legacy stack remained
stopped. Migrations 375 and 376 were applied only to isolated scratch databases;
no application database migration was applied. This closes the source
implementation and isolated fake-transport items, not real provider or CAP-040
acceptance.

## Isolated notification outbox check

Applied migration 375 twice to a fresh `notification_check` database in a new
Docker project with an internal-only network, no published ports and a retained
scratch volume. A read-only source mount excluded the repository's encrypted
dotenv file. The fake HTTP client had no network egress. It verified stable
enqueue identity, rejection of changed content under a reused identity, provider
pause without attempt consumption, a fake send followed by lease expiry/reclaim
with the same idempotency key, retry backoff then success, and operator-audited
replay/disposal. It also invoked the allowlisted handler twice with the same source
event id and confirmed one outbox row. The notification CLI help loaded and exposed
the added commands. All nine checks passed; six fake HTTP calls were recorded and
no real webhook or Directus endpoint was contacted. [Machine evidence](builds/2026-10-11-recovery/notification-outbox-check.json).

The scratch database is stopped with its volume retained. The candidate stack
remained healthy and the legacy stack remained stopped. The migration has not
been applied to either application database. This confirms queue/worker logic
against a fresh schema with fake transport; it does not certify a production
webhook receiver's idempotency behavior or the Directus installation's API.
Outbox/attempt/audit retention and capacity limits also remain to be selected;
no automatic pruning is implemented.

## Remaining gates

These checks cover two allowlisted cache handlers, timeout/retry, expired-lease
takeover and crash/retry after handler side effects for one idempotent cache
effect. The five registered handler contracts are inventoried, and event-driven
webhook/Directus sends now have a durable outbox implementation with isolated
fake-transport retry/crash/operator-action evidence. Sensor anomaly database
effects now have isolated hard-exit/replay evidence. Real provider contract
acceptance and recovery coverage beyond this one anomaly event remain open. Production
runtime-role least privilege, provider recovery, authenticated operator actions,
dashboard/report parity, and populated external-target lineage also remain open.
The stale-worker counter issue has a source-level correction, with live-CLI
confirmation still useful. Batch 2 and CAP-040 stay partial; no capability
acceptance count changes.

Rollback for these rehearsals is limited to stopping the named isolated database
and retaining its volume/checkpoint. No application migration, deployed service,
canonical farm record or external integration changed.


## Notification outbox capacity status recheck

The capacity follow-up passed in a separate fresh internal-only PostgreSQL
fixture. The ten-check rerun confirmed status counts, total/open row counts,
oldest-open age, combined relation bytes, and a forced critical state at
1/2-byte warning/critical thresholds. The stats query was read-only; all six
fake transport calls remained isolated and no external endpoint was contacted.
The scratch database is stopped with its volume retained. The report does not
measure volume free space or send external alerts, and no time-based pruning is
implemented. [Machine evidence](builds/2026-10-11-recovery/notification-outbox-capacity.json).
