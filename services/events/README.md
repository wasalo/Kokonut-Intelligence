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
acknowledged. Freshness transitions publish `data_stale` in the same database
transaction as their check and alert-history record; configured webhook,
Directus, and email delivery then run asynchronously through this outbox. Provider
I/O never runs inside the freshness transaction. Event dispatch and outbox
delivery run independently; `--worker` remains a combined compatibility mode.
The Kernel supervisor starts separate child processes for both features.
`KOKONUT_FEATURE_NOTIFICATION_DELIVERY`
controls notification delivery and defaults to the event-bus feature setting,
preserving existing deployments while allowing delivery to be disabled or run
independently. Each CLI worker mode checks its own feature before opening a
database connection; combined `--worker` runs whichever loops are enabled.
By default, event handlers still use the shared runtime database identity to
enqueue intents. An opt-in path for `data_stale` and `threshold_breached` uses
a separate notification-enqueue login and a bounded source-event-validated
database function. Migration 417 grants that login no direct table access;
runtime-role provisioning also removes sequence access, grants only the bounded
function, and rejects other executable `SECURITY DEFINER` functions. The
function cannot send notifications or alter delivery attempts. Enable it
only after the migration and distinct login/DSN are provisioned; missing
credentials fail closed without a shared-DSN fallback. The outbox
uses stable `(source event, channel, destination)` identities and a bounded
retry budget, expiring leases, and operator-audited replay/disposal. Delivery is
at-least-once: an external send can succeed just before a worker loses its lease
or exits, so receivers that support `Idempotency-Key` should honor it.

Credentials and destination URLs are read from the worker environment at send
time and are not stored in the outbox. Directus enqueueing requires both the
Directus feature to be enabled and `DIRECTUS_ADMIN_TOKEN`; webhook enqueueing
requires `ALERT_WEBHOOK_URL`. An unconfigured channel is skipped, matching the
legacy optional-provider behavior.

SMTP sending uses the shared dependency-free `services.common.smtp` adapter.
`ALERT_SMTP_TLS_MODE` defaults to verified `starttls`; configure `implicit` for
SMTPS. `plain` must be explicitly selected for a trusted private relay and is
rejected when either authentication credential is set. The same transport
contract is used by the outbox, legacy anomaly CLI, and health-check script.

Set `KOKONUT_FEATURE_ISOLATED_NOTIFICATION_ENQUEUE=true` and provide
`KOKONUT_NOTIFICATION_ENQUEUE_DATABASE_URL` only after the runtime-role
bootstrap provisions the distinct `KOKONUT_NOTIFICATION_ENQUEUE_USER` and
encrypted password. The EventBus forwards this DSN only to its two registered
notification handlers. Migration 417 validates event ID/type and any supplied
location lineage, accepts only webhook, Directus, or email payloads for the
`primary` destination, bounds each payload to 16 KiB, and makes retries
idempotent. Notification sending and operator disposition remain separate.

When a `data_stale` or `threshold_breached` event payload includes a valid
`location_id`, its handler records that value in `notification_outbox` as
optional lineage. The value comes from the event payload and is not verified
against an authoritative source record; it does not grant tenant access or
establish signed worker context. Events without a location remain unassigned.

```bash
python3 -m services.events --event-worker --worker-id event-worker
python3 -m services.events --isolated-event-worker --worker-id event-kernel-worker
python3 -m services.events --notification-worker --worker-id notification-worker
python3 -m services.events --notification-process --batch-size 50
python3 -m services.events --notification-stats
python3 -m services.events --notification-list-dead-letter
python3 -m services.events --notification-replay-dead-letter \
  --notification-id UUID --notification-actor OPERATOR --reason "Endpoint restored"
python3 -m services.events --notification-dispose-dead-letter \
  --notification-id UUID --disposition resolved --notification-actor OPERATOR \
  --reason "Reviewed with provider"
```

Notification commands require migration `375_notification_outbox.sql` to be applied.
`--notification-stats` also reports oldest open age and the combined table/index
size of the outbox, attempt history, and operator audit. Its advisory defaults
are 256 MiB warning and 512 MiB critical; set
`KOKONUT_NOTIFICATION_OUTBOX_WARN_BYTES` and
`KOKONUT_NOTIFICATION_OUTBOX_CRITICAL_BYTES` to override them. The check is
read-only. No outbox retention/pruning operation is provided; see the
[retention and capacity policy](../../docs/refactor/notification-outbox-operations.md).

## Files

8 Python modules
