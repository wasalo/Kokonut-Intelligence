# Batch 4 job schedule ownership and cutover inventory

**Reviewed:** 12 October 2026
**Status:** Source-level inventory and target ownership policy; no schedule was
registered, enabled, paused, or executed by this review.

## Ownership rule

The Kernel's minimal profile should use the durable PostgreSQL scheduler as the
default owner for recurring Kernel jobs. `services/core/jobs.py` is the shared
operation catalog; it is not itself a schedule registry. Prefect may remain an
optional workflow adapter for deployments that need its UI, but each recurring
job must have exactly one active dispatcher at a time. A cron entry, Prefect
deployment, `scheduled_task`, or operator trigger must not run the same work
concurrently without a reviewed idempotency and overlap contract.

The repository does not establish which Prefect schedules are currently active
in an external Prefect server. The checked-in deployment file is configuration,
not runtime evidence. The recovery record says the restored legacy database had
no `scheduled_task` or `task_run` rows; the local candidate scheduler has also
been observed with zero tasks. The historical seed
`schemas/seeds/050_scheduled_tasks.sql` inserts enabled rows, so it must not be
applied to a target until its ownership and duplication implications are
reviewed. The default `scripts/seed.sh` migration call uses `--schemas-only`,
which excludes seed data, and its curated seed list does not include seed 050.
This seed is not applied by normal bootstrap; do not add or manually apply it to
a Kernel target without first disabling its schedules and reviewing their
contracts. Reconcile live provider state immediately before any cutover.

A read-only status query inside the healthy local candidate app on 12 October
local time (13 October UTC) reported zero enabled, disabled, running, or failing
native scheduler tasks. The candidate project has no Prefect container. This
confirms the candidate has no registered native schedules; it says nothing
about a remote Prefect service or host process. A read-only Docker name filter
also found no running local container matching `prefect`. See the
[candidate scheduler snapshot](builds/2026-10-12-recovery/candidate-scheduler-owner-snapshot.json).

## Configured recurring flows

`config/prefect/deployment.yaml` declares four UTC schedules and one manual
deployment. The flow contents below come from
`services/flows/pipelines.py`; an external Prefect service's actual activation
state remains unknown.

| Declared owner | UTC schedule | Work declared by the flow | Cutover/replay notes |
| --- | --- | --- | --- |
| Prefect `scheduled-hourly` | `0 * * * *` | sensors, anomaly detection, freshness | Sensor's shared job currently has no input contract and its CLI no-argument path prints help. Do not transfer sensor scheduling until it accepts a defined source. |
| Prefect `scheduled-every-6h` | `0 */6 * * *` | weather, dashboard refresh, remote-sensing flow | Remote sensing has its own durable job claims and provider-level outcomes. Keep one outer trigger and let the internal worker own child attempts; inspect `no_data`, skipped, retryable, and terminal outcomes before replay. |
| Prefect `scheduled-daily` | `0 6 * * *` | market data, metrics, credit-adjustment check | Metrics create draft, unverified values. The old cron/seed cadence is every four hours, so reconcile the intended cadence and existing output before cutover. Credit adjustment is outside the scheduler module allowlist; retain manual/Prefect ownership until its safety and execution contract is reviewed. |
| Prefect `scheduled-weekly` | `0 3 * * 0` | climate-data flow | The flow fans out across active locations; each invocation of the climate CLI uses `--all` to select datasets and a required `--location-id`. Native planning currently describes one location per scheduled task, so cutover must preserve the fan-out without duplicate all-location runs. The flow docstring mentions ML retraining, but the flow body does not run it. |
| Prefect `full-pipeline` | Manual only | ingestion, monitoring, analytics, then remote sensing | Manual runs can overlap scheduled deployments. Require an operator to check current run state or route through a single guarded workflow before enabling native schedules. |

The deployment file does not declare schedules for EAS, RPC, Gnosis indexing,
NOI snapshots, or ClickHouse projections. The full pipeline includes EAS, RPC,
and Gnosis as manual ingestion tasks, but that does not create recurring
ownership for them.

## JobSpec ownership map

The source inventory below compares the 15 `JOBS` entries with Prefect flows,
the active and deprecated entries in `config/worker/crontab`, and the historical
database seed. “Declared” describes repository configuration only. “Target” is
the intended single-owner policy after the gates close; it does not assert that
a job is currently running.

| JobSpec | Current source declarations | Target owner and cutover/replay policy |
| --- | --- | --- |
| `weather` | Prefect every six hours; deprecated cron and seed also say every six hours | Native scheduler in the minimal profile after provider/checkpoint idempotency review. Do not auto-catch-up missed windows; reconcile the source watermark and duplicate keys first. |
| `sensors` | Prefect hourly; deprecated cron and seed say every five minutes | No transfer yet. Define the sensor input/source contract first; no-argument CLI success is not evidence of ingestion. Replay only by sensor identity and source timestamp after duplicate handling is verified. |
| `market_data` | Prefect daily at 06:00 UTC; deprecated cron and seed match | Native scheduler after source-period upsert and provider-failure behavior are verified. Reconcile the requested periods before replay; no blind backlog. |
| `eas` | Deprecated cron and seed every 15 minutes; EAS flow is included in the manual full ingestion pipeline | Native scheduler only after cursor/finality and duplicate-attestation handling are verified. Resume from the persisted indexed block; inspect reorg and duplicate behavior before replay. |
| `rpc` | Deprecated cron and seed every 30 minutes; RPC flow is included in the manual full ingestion pipeline | Native scheduler only after cursor, confirmation depth, and idempotent upsert behavior are verified. Resume from a reviewed checkpoint; do not replay irreversible external actions. |
| `gnosis` | Deprecated cron and seed every two hours; Gnosis flow is included in the manual full ingestion pipeline | Native scheduler after chain cursor and reorg recovery are verified. Replay from the canonical checkpoint after reconciling affected indexed rows. |
| `anomaly` | Prefect hourly; deprecated cron and seed hourly | Native scheduler after alert/claim/outbox writes are shown idempotent per source window. Retry the same window only; inspect emitted alerts and actuation approvals first. |
| `freshness` | Prefect hourly; deprecated cron and seed hourly | Native scheduler after its read/alert effects are classified. Recompute the missed interval only if any emitted notification can be deduplicated. |
| `metrics` | Prefect daily at 06:00 UTC; deprecated cron and seed every four hours | Native scheduler after reconciling cadence and duplicate output keys. Recompute creates drafts only; verification remains an independent human action. Do not promote computed output automatically. |
| `noi_snapshots` | Prepared daily native job; not registered in the candidate; no legacy cron/Prefect deployment | Native scheduler after owner approval, exact next-run selection, and reconciliation parity. Upsert by crop-cycle key; rerun reconciliation for the same source state rather than replaying every missed cadence. |
| `dashboards` | Prefect every six hours; deprecated cron and seed every six hours | Native scheduler after named-view and saved-card output parity. Refresh is rebuild-oriented; compare the affected time range and published-only filters before accepting a rerun. |
| `credit_adjustment` | Prefect daily check and manual full-pipeline path; no legacy cron/seed entry | Keep outside native scheduling until its domain effects and permissions are reviewed. The check command is not retirement confirmation; never auto-confirm a credit retirement. |
| `remote_sensing` | Prefect every six hours and manual full-pipeline path; internal durable fetch jobs | One reviewed outer trigger only. Prefer the internal durable job system as execution/retry owner; do not also create scheduler rows for the same provider jobs. Reconcile per-provider terminal and no-data states before replay. |
| `climate` | Prefect weekly; deprecated cron and seed weekly | `--all` selects all climate datasets for one required location; the Prefect flow fans out over active locations sequentially. Preserve that fan-out in native scheduling with one reviewed task per location or an explicitly allowlisted durable fan-out. Resume per location and avoid repeating completed locations without idempotency evidence. |
| `projections` | One-shot ClickHouse outbox command; not declared in Prefect, cron, or seed schedules | Keep under the durable outbox/projection delivery owner. Do not add periodic scheduler rows until the worker, module policy, sink checkpoint, and reconciliation behavior are explicitly defined. Replay from the durable outbox cursor, never from an untracked wall-clock window. |

## Work outside the 15-job catalog

| Work | Current source owner | Policy |
| --- | --- | --- |
| `scripts/health-alert.sh` | The only active entry in the worker crontab, every five minutes | Keep as a separate host/worker health timer until a provider-neutral health and alert contract replaces it. It is a shell/Docker-oriented check, not a `JobSpec`; do not silently add it to database scheduling. |
| `services.events --worker` | Long-running event worker in the worker overlay / Kernel supervisor | Keep event delivery under its durable lease, retry, and dead-letter loop. Do not also run the legacy seed's `services.events --process` every two minutes. |
| `services.events --cleanup` | Historical daily 04:00 UTC task in seed 050; no Prefect or crontab declaration | No recurring owner is established. The CLI and service cleanup path now fail closed unless `KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP=true` and an explicit `--days` value are supplied. The query does not yet evaluate event-level legal holds; keep it disabled until the retention schedule is approved and hold-aware eligibility is implemented. Add cleanup scheduling only with explicit eligible-row rules and audit evidence. |
| ML model retraining | Mentioned only in the weekly flow docstring in the checked-in body | No executable schedule or JobSpec exists. Treat as unscheduled until a concrete operation, artifact versioning, approval, and rollback contract exist. |

The deprecated crontab examples and seed cadences are historical configuration,
not a recovery schedule to reactivate automatically. In particular, sensor and
metrics cadence/input differences must be resolved before any transfer. The
historical seed's event-processing tasks also predate the current long-running
event worker and should not be used alongside it.

## Safe cutover sequence

1. Inventory active schedules and in-flight runs from every configured owner
   (Prefect, crontab, `scheduled_task`, and internal provider queues). Export
   definitions and record the current checkpoint and output counts.
2. Select the accountable operational owner and one dispatcher per job. Confirm
   required secrets, profile dependencies, source inputs, side effects,
   idempotency keys, overlap behavior, timeout, retry ceiling, and manual approval
   boundaries.
3. Resolve each row's open contract above. Set the initial `next_run_at`
   deliberately; never let an overdue schedule imply an automatic catch-up.
4. Disable the previous recurring owner, wait for or reconcile active runs, and
   then register the native definition disabled. Audit its graph and compare its
   arguments, cadence, timeout, retries, dependencies, and window to the reviewed
   export.
5. Enable one job at a time. Observe output lineage and error/retry state for an
   agreed window. Keep a reference query or legacy output for comparison where
   the operation produces derived data.
6. Roll back by disabling the new definition first, reconciling its durable run
   state and side effects, then restoring the prior owner from the export. Never
   enable both owners to “catch up.”

The scheduler's bounded retries and durable leases do not prove application
idempotency. A process retry is permitted only after the domain-side effects
are safe to repeat. Unknown outcomes require operator reconciliation, not
automatic replay.

## Acceptance to close the Batch 4 item

- Reconcile runtime provider state and identify an accountable schedule owner
  for each activated job.
- Resolve all input/cadence discrepancies and no-owner rows.
- Verify each operation's idempotency, dependency/window, bounded retry, and
  replay policy against a scoped fixture.
- Complete one-at-a-time cutover with a retained export, non-overlap evidence,
  output parity, and exercised rollback.

No external Prefect server was queried and no runtime job was run for this
inventory. See [job catalog](orchestration-jobs.md), [schedule planner](scheduler-job-planning.md),
[scheduler activation](scheduler-activation.md), [run windows](scheduler-run-windows.md),
and the [Batch 4 checklist](batches.md).
