# Candidate Kernel process supervision

`services/core/runtime.py` supervises existing CLI processes rather than embedding
blocking worker loops in the ASGI event loop. It launches the API and, with
`--with-workers`, the enabled PostgreSQL scheduler and event worker. Vendor
feature switches and domain code remain unchanged. Workers do not run unless
that command flag is supplied; feature flags alone do not start processes.

The subsequent [standard overlay](standard-profile.md) adds `--workers-only`
for a separate worker container. Each supervisor lifetime now generates unique
scheduler/event identities instead of fixed names. Empty worker roles fail
startup. The running combined candidate predates this source change.

The candidate Dockerfile now uses this entry point. Its Compose app uses an init
process for orphan reaping and a 40-second shutdown grace period, exceeding the
supervisor's default 30-second budget. Child processes inherit the runtime
environment and write to container logs; secret values are not logged by the
supervisor. Commands use explicit argument arrays without a shell.

Each child gets a POSIX process group. SIGINT/SIGTERM triggers group termination,
a shared bounded wait, and forced termination of remaining descendants. Any
unexpected child exit, including exit code zero, fails the container and stops
its siblings. Compose's existing `unless-stopped` policy governs restarts; no
second internal retry loop is added. Partial-launch failures also clean up.

Lease recovery, handler delivery idempotency, retry ceilings, resource admission,
and dead-letter behavior remain in the existing workers. Interrupted work may
recover after its lease expires; this supervisor does not promise exactly-once
external effects. Do not run another dispatcher for the same job schedules.
The candidate has no numbered scheduler/handler seeds applied; schema SQL itself
registered five handlers. Pre-launch inspection found zero scheduled tasks,
five handlers, and zero platform events.
Inspect jobs and registered handlers before enabling workers on populated data.

This is Linux/POSIX supervision, not certified Windows support. Liveness remains
the gateway's `/health`; child existence does not prove worker progress or DB
readiness. Four focused tests cover graceful signal handling, process-group
escalation, an unexpected zero exit, and partial-launch cleanup; one POSIX
integration case verifies SIGTERM reaches both a child and grandchild process
([evidence](builds/2026-10-14-recovery/kernel-supervisor-unit-contract.json)).
Database-outage, lease-recovery, and workload-parity acceptance remain open. Lint,
dependency-boundary, and whitespace checks passed. The candidate
has now been rebuilt and started with this entry point. Logs show API, scheduler,
and event processes launched, scheduler startup completed, and API liveness 200.
This does not establish job execution or event-delivery parity.

Rollback: override the candidate app command with the previous gateway CLI
command, then recreate only the candidate app. Preserve its database volume.
No migrations or live task executions occurred while implementing supervision.
