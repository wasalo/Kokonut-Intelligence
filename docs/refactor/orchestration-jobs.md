# Shared orchestration jobs

## Implemented boundary

`services/core/jobs.py` defines sixteen immutable command specifications and
`run_job(job_id, location_id=..., driver_instance_id=...)`. It imports no orchestration SDK or domain
service. Commands use the current Python interpreter, fixed module names,
fixed arguments, and the existing operation timeouts. Location-scoped weather,
weather forecast, anomaly, climate, metrics, credit checks, remote sensing, and
sensor pulls validate their required UUID inputs before process creation.
Results retain the legacy status and
last 500 stdout characters. Nonzero exits and timeouts propagate to the owner.
Captured subprocess output still uses memory; this is not a bounded log store.

Legacy Prefect flows delegate their command bodies to these definitions.
Their names, decorators, retry counts, and retry delays are retained.
`pipelines.py` submits tasks for parallel ingestion, monitoring, and the
post-metrics dashboard/credit checks. Each task uses its operation's original
retry policy; pipeline retries remain unchanged. Parallel operations now appear
as tasks within the pipeline instead of child flow runs. Explicit standalone
and scheduled flow entry points remain available.

This follows Prefect's documented
[task submission API](https://docs.prefect.io/latest/tutorial/flows), replacing
the baseline calls to `.submit()` on ordinary flow objects. The current
Prefect 3 runtime, retry, dependency-order, and deployment-resolution contracts
are exercised against an isolated local test harness; this does not activate or
transfer schedule ownership.

## Authority and adoption

The catalog is not a schedule registry and creates no database rows.
`scheduler_allowed` reports the existing execution allowlist; it does not grant
permission. The credit adjustment JobSpec uses a dedicated read-only entrypoint;
the new weather-forecast module is allowlisted only for its one-location
command contract. Neither entry permits other interactive operations. Calling a known
operation explicitly does not expand database-driven scheduler authority. The
scheduler must continue validating its stored module paths independently.

The source-level dispatcher, cadence, cutover, and replay inventory is in the
[schedule ownership record](schedule-ownership-inventory.md). It distinguishes
these operation specifications from Prefect deployments, legacy cron examples,
historical scheduler seeds, and the long-running event worker.

`run_job` performs one attempt. It owns no leases, retry loops, run state, or
cron dispatcher. Adoption by the durable PostgreSQL scheduler requires an
explicit mapping of command arguments, dependencies, timeout, retry delay,
idempotency expectations, and overlap policy. Do not register a second owner
while Prefect deployments are active. The existing hourly, six-hourly, daily,
weekly, and manual deployment definitions have not changed.

Metrics still compute draft values; independent human verification is required.
Credit operations use `--check-adjustments`; this does not confirm retirements.
The scheduled anomaly JobSpec requires one location, and its Prefect adapter
fans out over active Kokonut Network locations. Scoped anomaly and baseline
checks keep their sensor/baseline reads and resulting alert records on that
location. An unscoped interactive CLI run retains the all-location behavior.
The hourly Prefect flow and full-ingestion composite no longer call the
source-less sensor operation. The hourly schedule now covers anomaly detection
and freshness only. Sensor ingestion has a disabled native JobSpec only for a
registered location-bound driver instance; CSV pulls are bounded and MQTT
remains event-driven. Five-day forecasts have a separate disabled native
JobSpec requiring one location; the repository has no dedicated Prefect or
cron forecast schedule. Neither operation is activated or tenant-authorized by
the JobSpec. The CLI rejects missing, incomplete, and conflicting
input modes instead of printing help and exiting successfully; its help and validation
paths also avoid loading SOPS/database configuration. Explicit CSV,
single-reading, list, and calibration operations retain their dispatch. The
shared `sensors` JobSpec rejects calls missing either its location or
driver-instance UUID before subprocess launch, so the Prefect wrapper cannot
report a successful no-op. HTTP and MQTT transports remain available. Recurring
sensor execution remains disabled pending real source, identity, tenant, and
schedule-owner review.

Remote sensing now delegates to the shared job catalog without changing its
internal durable job claims or retry state. It remains outside the scheduler
module allowlist. Its CLI prints a report and can exit zero when individual
provider jobs fail. Command-level success therefore does not certify provider
success. Reconcile `no_data`, skipped, retryable, and terminal outcomes before
changing that CLI exit policy or transferring schedule ownership.

`services/core/climate_jobs.py` owns sequential active-location fan-out with no
Prefect import. It closes the cursor and database connection even when reads
fail, converts UUIDs to strings, and closes the connection before commands run.
Each location has the original 600-second timeout. Nonzero command exits and
timeouts are collected, remaining locations run, and `ClimateRefreshFailed`
retains the aggregate report. Failed aggregates now raise instead of reporting
success, allowing the existing flow retry policy to operate. An empty location
set succeeds with zero work. Query failures and unexpected launcher errors
propagate immediately. The batch has no total timeout or persisted per-location
checkpoint; a flow retry repeats completed locations, so idempotency remains a
cutover gate. Climate CLI zero exits can still contain skipped provider results;
the fan-out reports process outcomes, not verified acquisition of every dataset.

## Acceptance status

1. **Source dispatcher contract passed:** focused checks cover fixed interpreter,
   module/argv, configured timeout argument, nonzero exit reporting, climate's required
   location, and rejection of source-less sensor dispatch before process launch
   (`tests/test_core_jobs_contract.py` and
   `tests/test_scheduled_command_contracts.py`). The subprocess is substituted;
   no provider or database is contacted.
2. **Prefect runtime contract passed:** the isolated runtime suite checks
   parallel task submission, JobSpec-derived retries, metrics-before-dependent
   work ordering, and task failure propagation. It runs against the local
   Prefect test harness and SQLite state, with all job handlers mocked
   (`tests/test_prefect_runtime_acceptance.py`).
3. **Flow/deployment resolution passed:** each checked-in deployment resolves
   to an importable Prefect flow with the same registered name, and the four
   scheduled deployment cron strings match their current declarations. The
   checks use the real Prefect 3.8.8 flow objects and YAML, without creating a
   deployment or schedule (`tests/test_prefect_runtime_acceptance.py`).
4. Check climate UUID conversion, cursor/connection cleanup on read failure,
   partial failure reports, timeouts, remaining-location continuation, and empty
   batches. Reconcile sensor input and climate/remote-sensing provider outcomes
   before migrating schedules. Check dependencies per image profile.
5. Rehearse restart, lease expiry, duplicate delivery, and rollback before
   transferring any dispatcher ownership to the PostgreSQL scheduler.

The dispatcher checks substitute subprocess execution. Prefect runtime checks
use an isolated local API and temporary SQLite database; every domain job is
mocked. No production Prefect server, provider, Kokonut database, schedule
activation, migration, or dispatcher cutover was exercised. These checks do
not close schedule ownership or runtime recovery gates.

## Rollback

No persisted state has changed. Restore the flow wrapper command bodies to
remove their dependency on the catalog. Keep the corrected Prefect task
submission path or deploy a separately validated previous workflow version;
restoring the baseline invalid flow submissions is not a working recovery.
When schedules are eventually migrated, disable the new owner before enabling
the previous owner and reconcile in-flight durable runs and idempotency keys.
