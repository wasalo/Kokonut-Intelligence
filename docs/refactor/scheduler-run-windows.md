# Scheduler run windows

## Implemented contract

Migration `371_scheduler_run_windows.sql` adds `scheduled_task.dependency_mode`
(`last_completed` by default, or opt-in `same_window`), `run_window_at`, and
`task_run.scheduled_for`, plus an index on completed run windows. Previously
applied migrations are unchanged. Historical runs remain without a window;
their timestamps are not guessed or backfilled.

On a new claim the scheduler records the task's due `next_run_at` as its window.
Legacy tasks with no due timestamp use claim time. On retry the scheduler uses
the stored `run_window_at`, including resource deferral and lease recovery.
The cadence still advances on the initial claim. Claim locks, lease tokens,
ownership checks, retry limits, and subprocess execution remain in their
existing transaction paths.

For `same_window`, every dependency needs a completed `task_run` with exactly
the same `scheduled_for` UTC timestamp. Missing dependencies, historical runs
without a window, failed runs, and completions from other windows do not satisfy
the condition. A newer failed run does not erase an earlier successful outcome
for the required window. Tasks in this mode require an explicit `next_run_at`
for their first claim; a missing initial or retry window blocks dispatch.
Generated job plans select this mode but remain disabled and require a reviewed
initial timestamp before installation.

## Adoption limits

This is an exact timestamp contract, not an arbitrary DAG engine. Related tasks
need aligned cadence and initial timestamps. Different cadences, missed windows,
cycles, and manual catch-up require explicit operator policy. The existing
scheduler advances cadence from current time and does not replay every missed
occurrence. A prerequisite may therefore skip a timestamp still required by a
dependent task; that dependent remains blocked until reconciled. Do not activate
pipeline graphs until backlog and window coordination are implemented and
validated. The [preactivation graph audit](scheduler-graph-audit.md) reports
configuration problems; definitions are not yet validated at write time.

Historical completion metadata must be retained for blocked dependents and
pending retries. Do not introduce task_run retention that removes their matching
completions. Same-window semantics do not establish domain idempotency, verify
metrics, or grant authorization for a module.

## Migration and rollout

1. Export task definitions and review enabled tasks and in-flight leases.
2. Apply migration 371 using the checksummed migration runner before deploying
   the updated scheduler. The new worker requires these columns even for legacy
   tasks. This migration has not been applied to the local candidate.
3. Deploy with existing tasks in `last_completed`; do not change owners mid-run.
4. Rehearse a disabled aligned graph, including initial timestamps and failure,
   retry, lease recovery, and backlog policy, before opting into `same_window`.
5. Disable the former dispatcher and reconcile its in-flight runs before
   enabling the reviewed graph. No schedules were activated in this slice.

## Acceptance checks pending

Validate migration application and checksum preservation; old task defaults;
fresh and historical completion matching; missing prerequisites; retry window
preservation; resource deferral; expired leases; absent initial windows; and
two-worker claim behavior. Verify no early dependent dispatch when a prior
window succeeded. Check overdue/catch-up and cadence alignment explicitly.
Runtime tests and migration execution have not been performed; static lint and
provider/dependency gates are separate evidence.

## Rollback

Stop dispatch and reconcile running leases before reverting worker code.
Reset reviewed tasks to `last_completed` only if the old dependency behavior is
acceptable, or keep them disabled. Retain the additive columns and window
history; an older worker ignores them. Never edit migration 371 after application
or remove recorded run windows as part of a code rollback. An old worker does
not enforce `same_window`, so it must not run while such tasks remain enabled.
