# Scheduler graph preactivation audit

`services/scheduler/graph.py:audit_graph` accepts stored task definitions and
returns `valid`, structured errors/warnings, and dependency order. It has no
database access or side effects. The scheduler command `--check-graph` reads the
definitions with shared connection/JSON/error helpers and exits nonzero when
configuration errors are present. It performs no schedule writes or execution.

```sh
python3 -m services.scheduler.cli --check-graph
```

This command requires migration 371. It has not been run against the candidate,
where that migration remains unapplied.

## Checks

- Duplicate task identifiers, missing prerequisites, and self-dependencies.
- Cycles and tasks downstream from cycles, using an iterative graph traversal.
- Existing module allowlist, string-array command arguments, and cron fields
  that parse to nonempty sets using the scheduler's current parser.
- Unknown dependency modes and warnings for legacy completion semantics.
- Disabled same-window definitions need timezone-aware initial timestamps on
  exact UTC cron boundaries, including zero seconds/microseconds.
- Their prerequisites must be disabled, use same-window mode, and have equal
  cron strings and initial timestamps. Running/retrying disabled tasks require
  reconciliation before preactivation review.

Enabled same-window tasks produce a live-graph warning; their current next-run
timestamps are not compared as if they were fresh definitions. Their successful
prerequisite may already have advanced to a later window. Audit that situation
against durable task_run history before modifying ownership or definitions.

## Scope and remaining gates

`valid=true` means no configuration errors were found in this snapshot. It is
not activation approval or capability certification. Warnings remain visible.
An empty graph can be valid without configured work. Command argument validation
checks types, not each module's semantic input contract or credentials. Cron
checking inherits the existing parser's permissive range handling; equal cron
strings are deliberately conservative and do not recognize equivalent spellings.
No backlog repair, domain idempotency, or scheduler ownership validation is
performed. Dependency order is useful only when configuration errors are absent.

The standalone audit snapshot can become stale after concurrent edits. The new
[transactional activation path](scheduler-activation.md) runs this audit under
definition locking before enabling tasks. Runtime validation and dispatcher
ownership reconciliation remain required before pipeline cutover.

Pending acceptance: missing/duplicate identifiers, cycles and their dependents,
valid aligned chains, timestamp normalization, off-cadence windows, mixed modes,
enabled prerequisites, unresolved retries, malformed arguments/cron, and clean
CLI nonzero exits. Runtime tests and live database audit were not performed.
Static lint, provider boundaries, requirement grouping, and diff checks passed.

Rollback removes the new audit command and pure audit module. No migrations,
task definitions, durable runs, or enabled states changed in this slice.
