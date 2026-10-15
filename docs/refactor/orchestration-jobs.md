# Shared orchestration jobs

## Implemented boundary

`services/core/jobs.py` defines fifteen immutable command specifications and
`run_job(job_id, location_id=...)`. It imports no orchestration SDK or domain
service. Commands use the current Python interpreter, fixed module names,
fixed arguments, and the existing operation timeouts. Weather and climate accept
a location override, validated as a UUID; climate requires it. Results retain the legacy status and
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
the baseline calls to `.submit()` on ordinary flow objects. Runtime acceptance
against the selected Prefect installation remains pending.

## Authority and adoption

The catalog is not a schedule registry and creates no database rows.
`scheduler_allowed` reports the existing execution allowlist; it does not grant
permission. Credit adjustment checks remain outside that allowlist. Calling a
known operation explicitly does not expand database-driven scheduler authority.
The scheduler must continue validating its stored module paths independently.

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
Sensor scheduling remains rejected because there is no recurring source
contract. The CLI now rejects missing, incomplete, and conflicting input modes
instead of printing help and exiting successfully; its help and validation
paths also avoid loading SOPS/database configuration. Explicit CSV,
single-reading, list, and calibration operations retain their dispatch. The
shared `sensors` JobSpec fails before subprocess launch, so the Prefect wrapper
cannot report a successful no-op. This closes false-success reporting only; a
source/input contract is still required before hourly sensor scheduling can be
ported.

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

## Acceptance gates still pending

1. Contract checks for fixed argv, interpreter, timeouts, nonzero exits, and
   weather/climate UUID validation, with subprocess execution substituted.
2. Prefect runtime checks for parallel submission, task retry settings,
   metrics-before-dependent-work ordering, and failure propagation.
3. Confirm standalone flow names and deployment schedules resolve unchanged.
4. Check climate UUID conversion, cursor/connection cleanup on read failure,
   partial failure reports, timeouts, remaining-location continuation, and empty
   batches. Reconcile sensor input and climate/remote-sensing provider outcomes
   before migrating schedules. Check dependencies per image profile.
5. Rehearse restart, lease expiry, duplicate delivery, and rollback before
   transferring any dispatcher ownership to the PostgreSQL scheduler.

No runtime tests, migrations, deployment activation, or dispatcher cutover were
performed in this slice. Static lint and provider boundary checks are separate
from these acceptance gates.

## Rollback

No persisted state has changed. Restore the flow wrapper command bodies to
remove their dependency on the catalog. Keep the corrected Prefect task
submission path or deploy a separately validated previous workflow version;
restoring the baseline invalid flow submissions is not a working recovery.
When schedules are eventually migrated, disable the new owner before enabling
the previous owner and reconcile in-flight durable runs and idempotency keys.
