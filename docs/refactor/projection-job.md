# Explicit projection job and CLI outcomes

The shared job catalog now contains `projections`, invoking the existing outbox
CLI with `--run-once --limit 100`, a 300-second command timeout, and no catalog
retries. Outbox leases and per-row retry budgets remain the delivery authority.
No schedule is registered. The module remains outside the scheduler allowlist,
so disabled scheduler planning rejects it rather than granting new execution
authority. Selecting analytics overlays still does not drain projections.

The outbox CLI now requires exactly one action, bounds limits to 1–1000, uses
shared CLI error/JSON/connection helpers, and returns nonzero for failed batch
deliveries or unsuccessful dead-letter replay. Failed rows already committed
their outbox outcomes before that exit; the exit does not undo successful rows
or mean the entire batch failed. A disabled provider retains its existing zero
claim result, and pending claims/leases remain durable if the process terminates.

`DatabaseConnection.cursor()` now publicly delegates DB-API cursor creation so
legacy outbox functions can run under the shared context manager. Callers close
cursors; the shared adapter commits/rolls back and closes the connection. Existing
named-parameter execute() behavior is unchanged. Delivery functions' existing
explicit commits remain intact because claim and outcome state must survive
independent row failures.

Static lint and diff checks passed. No tests, commands, claims, schedules,
replays, schema initialization, image builds, or service changes were performed.
Pending acceptance includes raw-cursor compatibility, success/partial-failure
exit codes, provider-disabled behavior, client creation failure, lease recovery,
dead-letter replay, timeout interruption, and projection lineage. A successful
command exit alone does not certify analytical freshness or table parity.

Rollback restores the prior CLI/catalog while retaining outbox rows and leases.
Review consumers of changed nonzero exit codes and mandatory action selection
before adoption. Keep dispatch paused until ClickHouse schema and recovery gates
pass; never reset delivery attempts automatically to conceal a failing batch.
