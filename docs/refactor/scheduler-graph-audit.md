# Scheduler graph preactivation audit

`services/scheduler/graph.py:audit_graph` accepts stored task definitions and
returns `valid`, structured errors/warnings, and dependency order. It has no
database access or side effects. The scheduler command `--check-graph` reads the
definitions with shared connection/JSON/error helpers and exits nonzero when
configuration errors are present. It performs no schedule writes or execution.

```sh
python3 -m services.scheduler.cli --check-graph
```

This command requires scheduler schema migration 371. It has not been run
against the local candidate in this slice.

## Checks

- Duplicate task identifiers, missing prerequisites, and self-dependencies.
- Cycles and tasks downstream from cycles, using an iterative graph traversal.
- Existing module allowlist, module-specific operation/value/combination
  contracts, and cron fields that parse to nonempty sets using the scheduler's
  current parser. Runtime dispatch repeats command validation.
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
An empty graph can be valid without configured work. Argument contracts check
operation syntax, values, and required combinations, but they do not verify
credentials, tenant ownership, domain idempotency, or narrow database access.
Cron checking inherits the existing parser's permissive range handling; equal
cron strings are deliberately conservative and do not recognize equivalent
spellings. No backlog repair or external scheduler ownership validation is
performed. Dependency order is useful only when configuration errors are
absent.

The standalone audit snapshot can become stale after concurrent edits. The new
[transactional activation path](scheduler-activation.md) runs this audit under
definition locking before enabling tasks. Runtime validation and dispatcher
ownership reconciliation remain required before pipeline cutover.

Focused source tests cover invalid operations/values, malformed arrays, module
contract parity, graph-preflight errors, run-now denial before spawn, terminal
runtime rejection without retry, and generated job plans. The candidate graph
and current persisted rows have not been audited here; run `--check-graph`
before activation and reconcile rejected enabled rows with their operator.
Runtime database acceptance remains separate.

No migration, task definition, durable run, or enabled state was changed in this
code-only slice.
