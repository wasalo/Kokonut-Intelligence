# events

`services.events` — Event bus for reactive workflows.

## CLI Usage

```bash
python3 -m services.events
```
```bash
python3 -m services.events.cli --help
```

## Modules

- `bus` — Durable PostgreSQL-backed event bus.
- `cli` — CLI for the event bus.
- `notification_outbox` — PostgreSQL-backed alert delivery with leases, bounded retries and audited dead-letter operations.
- `fork_detector` — Fork detector — the chess "fork" tactic applied to cross-domain insight flow.
- `handlers` — Built-in event handlers for the event bus.
- `insight_transfer` — Cross-Domain Insight Transfer Engine — propagates insights across domains.

## Event retention cleanup

Deleting completed events is disabled by default. No event-retention schedule
or jurisdiction-specific period has been configured. Retention windows live in
approved `data_retention_policy` rows; there is no code or CLI default. New
policies remain drafts until an operator approves them. Record-level legal
holds are audited and event cleanup checks active holds. Keep
`KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP` disabled until the applicable policy
is configured and deployment acceptance is complete:

```bash
KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP=true \
  python3 -m services.events --cleanup --actor OPERATOR
```

Cleanup requires exactly one approved, active, auto-enforced global
`event_bus` / `platform_event` hard-delete policy with an accountable owner, derives its period from that
row, and rejects missing or ambiguous policy. It considers only completed or
dead-letter events, preserving pending dead letters, non-success handler
deliveries, and active legal holds. The operation records its actor and result.
No notification outbox, attempt-history, or operator-audit pruning operation
is provided. The feature flag is a default-off switch, not policy approval.

## Notification delivery

`data_stale` and `threshold_breached` handlers persist configured webhook and
Directus notifications to `notification_outbox` before their event delivery is
acknowledged. The event worker also claims and delivers notification rows. The
outbox uses stable `(source event, channel, destination)` identities, a bounded
retry budget, expiring leases, and operator-audited replay/disposal. Delivery is
at-least-once: an external send can succeed just before a worker loses its lease
or exits, so receivers that support `Idempotency-Key` should honor it.

Credentials and destination URLs are read from the worker environment at send
time and are not stored in the outbox. Directus enqueueing requires both the
Directus feature to be enabled and `DIRECTUS_ADMIN_TOKEN`; webhook enqueueing
requires `ALERT_WEBHOOK_URL`. An unconfigured channel is skipped, matching the
legacy optional-provider behavior.

```bash
python3 -m services.events --notification-process --batch-size 50
python3 -m services.events --notification-stats
python3 -m services.events --notification-list-dead-letter
python3 -m services.events --notification-replay-dead-letter \
  --notification-id UUID --notification-actor OPERATOR --reason "Endpoint restored"
python3 -m services.events --notification-dispose-dead-letter \
  --notification-id UUID --disposition resolved --notification-actor OPERATOR \
  --reason "Reviewed with provider"
```

These commands require migration `375_notification_outbox.sql` to be applied.
`--notification-stats` also reports oldest open age and the combined table/index
size of the outbox, attempt history, and operator audit. Its advisory defaults
are 256 MiB warning and 512 MiB critical; set
`KOKONUT_NOTIFICATION_OUTBOX_WARN_BYTES` and
`KOKONUT_NOTIFICATION_OUTBOX_CRITICAL_BYTES` to override them. The check is
read-only. No outbox retention/pruning operation is provided; see the
[retention and capacity policy](../../docs/refactor/notification-outbox-operations.md).

## Files

8 Python modules
