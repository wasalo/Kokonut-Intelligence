# Transactional scheduler activation

`services/scheduler/activation.py:enable_schedule` validates definitions and
updates enabled state within the caller's transaction. The CLI uses shared
connection, JSON, and error helpers so exceptions roll back and produce a
nonzero exit. Output lists the names newly enabled, after commit.

The transaction takes an exclusive scheduled_task table lock before reading
definitions. It blocks definition writes and scheduler row-locking claims while
the audit and updates complete. Ordinary reads can continue. Lock waits have a
five-second timeout; contention causes failure and rollback, not partial
activation. The scope is deliberately conservative for infrequent operator
activation. No network calls or job execution occur while this lock is held.

## Commands and checks

- `--enable NAME` enables only that task. A disabled same-window task with
  prerequisites requires the graph command. An already-enabled task is an
  idempotent no-op, not a fresh certification of its graph.
- `--enable-graph NAME` explicitly enables the target and its transitive
  prerequisites atomically. Only that closure is audited; unrelated definitions
  are not activation blockers. Missing prerequisites remain audit failures.
- Both use the graph audit for cycles, module policy, argument types, cron,
  dependency modes, and disabled same-window cadence/timestamp alignment.
- Graphs containing same-window tasks must use that mode throughout and must
  be disabled before review. Running/retrying tasks selected for activation
  require reconciliation. No SQL module allowlist has been expanded.

The graph command changes more than one enabled state by explicit operator
request. Review every prerequisite before invoking it. Migration 371 is needed
before using the updated enable path; it has not been applied locally. Neither
activation command was invoked in this slice.

## Limits and pending acceptance

Activation does not certify credentials, optional dependencies, domain
idempotency, acquisition outcomes, or exclusive ownership relative to Prefect.
Legacy dependencies retain their prior last-completed semantics. An overdue
reviewed timestamp can become immediately eligible; backlog and first-run
selection remain operator responsibilities. SQL writes outside this command
can still enable or alter definitions afterward. Cross-dispatcher ownership
must be reconciled before invoking activation.

Pending runtime checks: atomic graph enable and rollback, audit rejection without
state changes, missing task, already-enabled no-op, prerequisite closure,
contention timeout, concurrent definition mutation/worker claims, clean CLI
errors, and in-flight/unaligned graph rejection. Static lint and provider and
dependency checks passed; no runtime tests or database changes were performed.

## Rollback

Revert the activation helper and CLI wiring if necessary; no persisted state
was changed during implementation. After actual activation, disable affected
tasks and reconcile durable runs before restoring prior enabled states or a
previous dispatcher. Never use an older worker against enabled same-window
tasks: it would ignore the new dependency contract.
