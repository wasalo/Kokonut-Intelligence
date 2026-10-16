# Notification outbox retention and capacity

Status: capacity reporting implemented; temporal retention remains an owner
decision. This policy is intentionally non-destructive until the platform's
data-retention and archive requirements are approved.

## Retention baseline

- Do not automatically delete notification rows, attempts, or operator audit
  records. The outbox's `(source_event_id, channel, destination_key)` identity
  also acts as the duplicate-suppression record.
- Never prune `pending`, `processing`, `retryable`, or undisposed
  `dead_letter` rows. They represent work or operator action that is still due.
- Retain terminal `succeeded`, `resolved`, and `discarded` rows, their attempt
  history, and their operator audit history until a deployment owner approves a
  retention interval and an archive that preserves the identity/audit evidence.
- There is no outbox pruning command. PostgreSQL backup and restore includes
  these tables as canonical operational state.
- The generic data-governance retention sweeper skips the outbox, attempt, and
  operator-audit tables in both preview and enforcement modes. A future
  retention operation must preserve the idempotency key and parent/child links,
  honor record-level legal holds, and use owner-approved policy windows.

This is a non-expiring default, not a claim that indefinite retention is suitable
for every jurisdiction or deployment. Before enabling automated retention,
define the applicable data-minimization and audit period, make a verified
archive, and retain an idempotency tombstone for every pruned event/channel/
destination identity. Pruning the queue row without that tombstone can allow a
replayed event to enqueue a duplicate notification.

## Capacity reporting

`python3 -m services.events --notification-stats` reports status counts, total
and open row counts, age of the oldest open item, and combined PostgreSQL table
and index bytes for the outbox, attempt history, and operator audit. It does not
include notification payloads in its output.

The default advisory thresholds are 256 MiB (`warning`) and 512 MiB (`critical`)
for those three relations combined. Override them with:

```dotenv
KOKONUT_NOTIFICATION_OUTBOX_WARN_BYTES=268435456
KOKONUT_NOTIFICATION_OUTBOX_CRITICAL_BYTES=536870912
```

Require `1 <= warning <= critical`. These levels report growth; they do not
block enqueue or delivery and do not delete data. Operators should schedule the
stats command or collect its JSON from the worker environment, alert on
`storage_state`, and also monitor PostgreSQL volume free space independently.
At `warning`, inspect delivery backlog and database growth. At `critical`, add
capacity or complete an approved archive/retention change before storage
exhaustion. Do not clear active queue rows to recover space.

The status command requires migration `375_notification_outbox.sql`. Migration
376 adds the optional `email` channel for event-driven sensor alerts. SMTP is
at-least-once; a stable `Message-ID` does not guarantee that a receiving mail
system deduplicates retries. The current implementation does not send a
separate external capacity alert; the JSON status is the operator integration
point.
