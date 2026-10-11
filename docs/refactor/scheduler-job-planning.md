# Kernel job schedule planning

## Implemented

`services/scheduler/job_plan.py` maps shared job specifications to the existing
`scheduled_task` fields. `services.scheduler.cli --job-plan JOB` prints the
definition using the shared JSON/error helpers. The builder has no database
access and the command performs no job execution or schedule writes.

Example preparation commands (not activation):

```sh
python3 -m services.scheduler.cli --job-plan metrics --cadence daily
python3 -m services.scheduler.cli --job-plan weather --cadence every-6h
python3 -m services.scheduler.cli --job-plan climate --cadence weekly --location-id LOCATION_UUID
```

Cadences mirror the existing Prefect UTC schedules: hourly, every six hours,
daily at 06:00, and Sunday at 03:00. The timezone is review metadata; the
scheduled_task table has no timezone column and its parser uses UTC. Callers
select cadence explicitly; the default is daily. No inference is made that a
job belongs to a particular existing pipeline.

Every generated definition has `is_enabled=false`, `allow_overlap=false`,
normal priority, no dependencies, and opt-in `same_window` dependency mode.
That mode requires migration 371 and a reviewed initial `next_run_at`.
It carries the catalog's module, fixed
arguments, timeout, max retries, and retry delay. `activation_ready=false` and
review requirements are envelope metadata, not scheduled_task columns.
Weather and climate location identifiers are normalized UUIDs; climate requires
one location. Planning all active climate locations as one aggregate is not
supported because that wrapper is not an allowlisted scheduler module.

The builder validates the existing module allowlist. Remote sensing and credit
adjustment are rejected under that policy. Sensors are rejected because their
baseline no-argument command prints help without ingesting data. No permission
or module allowlist has changed.

## Remaining dependency and cutover work

These definitions represent independent operations. They are not a migration of
the Prefect pipeline graph. The scheduler currently checks dependencies using
`last_status='completed'`; that status can belong to an earlier cadence. It does
not establish that metrics completed for the current dashboard run window.
The new [run-window contract](scheduler-run-windows.md) adds opt-in exact
timestamp matching. Migration, aligned cadence, backlog policy, and runtime
validation remain prerequisites for scheduling coupled stages.

Before installing any plan, select one dispatcher, disable overlapping Prefect
deployments, reconcile in-flight work, check command/provider outcomes and
profile dependencies, and select a deliberate initial `next_run_at`. A null
next_run_at is immediately eligible when enabled. Do not blindly insert the
JSON envelope or enable tasks based only on cron validity. Existing retry values
are preserved for review; they do not prove retry safety for every domain job.

## Acceptance and rollback

Pending checks: field mapping for each permitted job, UTC cadence mapping,
disabled/non-overlap defaults, UUID validation, invalid jobs, module policy
rejections, sensor rejection, and clean CLI errors. Verify the resulting
definitions against the database schema and rehearse claim/retry/restart
behavior before activation. No runtime tests or database registration were
performed. Static lint and provider/dependency checks passed.

Rollback this preparation by removing the job-plan CLI option and builder.
No persisted scheduler state changed. Eventual activation must retain an export
of the prior definitions; disable the new owner and reconcile durable runs
before restoring the previous dispatcher.
