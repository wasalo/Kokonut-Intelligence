# Projection client and completion failure boundaries

`clickhouse_outbox.deliver_batch` now records client-creation failures against
its already claimed batch using the existing fenced completion function.
Each claimed row becomes retryable or dead-letter according to its existing
attempt count. The returned batch has zero delivered and all rows failed,
causing the revised CLI to exit nonzero. Stored setup errors contain only the
exception type. No extra attempts, replay, or background dispatcher are added.

Client insertion and PostgreSQL completion now have separate error boundaries.
A transport insertion failure records an ordinary failed outcome. A database
completion error propagates immediately rather than being misclassified and
followed by another SQL update in a potentially aborted transaction. Completed
rows remain committed; unfinished rows retain leases and recover through the
existing expiry path. If recording setup failure itself fails partway through,
the same partial-completion/lease recovery boundary applies.

A successful insert with a lost completion fence now counts as failed rather
than disappearing from batch totals. The stale owner still cannot change the
row's durable state. Existing lease duration, token ownership, eight-attempt
budget, one-minute retry delay, and disabled-provider no-claim behavior remain.
Client closure still runs in finally and can itself produce a command failure.

ClickHouse insertion before uncertain PostgreSQL completion can lead to replayed
projection rows. This correction does not add target-side deduplication or claim
exactly-once effects. Audit analytical table semantics and source identity before
certifying crash/replay parity or enabling automatic dispatch.

Static lint and diff checks passed. No tests, claims, client connections,
projection writes, images, or containers were run. Pending acceptance includes
client unavailable/exception, failed setup-outcome persistence, insertion error,
successful insert plus database failure, lost fence, partial batches, expiry
recovery, close failure, and CLI exit codes. Rebuild before adoption.

Rollback retains committed outcomes, pending rows, leases, and projection data.
Pause dispatch while selecting a validated image; preserve source/outbox lineage
and reconcile duplicates explicitly. Never clear attempts or delete analytical
rows merely to make a retry appear successful.
