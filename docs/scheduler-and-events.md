# Scheduler And Events

The scheduler and event bus are PostgreSQL-backed durable dispatch systems. Leases, retry state, run history, handler delivery state, and dead-letter disposition survive worker restarts and allow multiple workers to cooperate without central in-memory coordination.

## Scheduler

```text
due task -> row lock/SKIP LOCKED -> running lease -> subprocess
         -> completed
         -> failed/timeout -> delayed retry -> exhausted until next cadence/operator action
dead worker -> lease expires -> failed run -> retry eligibility
```

```bash
python3 -m services.scheduler.worker --tick-interval 30
python3 -m services.scheduler.cli --status
python3 -m services.scheduler.cli --list-runs
python3 -m services.scheduler.cli --tick
python3 -m services.scheduler.cli --enable TASK_NAME
python3 -m services.scheduler.cli --disable TASK_NAME
python3 -m services.scheduler.cli --run-now TASK_NAME
python3 -m services.scheduler.cli --worker --tick-interval 30 --worker-id WORKER_ID
```

### Scheduler Records

| Table | Purpose |
|---|---|
| `scheduled_task` | Task module, cadence, priority, dependency, retry, overlap, enablement, and lease state |
| `task_run` | Per-attempt status, worker, timing, output, errors, and retry count |
| `task_resource` | Named concurrency resources and current capacity |

`scheduled_task` stores a unique name, allowlisted `module_path`, cron expression, priority (`critical`, `high`, `normal`, `low`), timeout, retry limit/delay, dependency IDs, enablement, cadence timestamps, last status, consecutive failures, structured JSON-array `command_args`, overlap policy, lease owner/expiry, and retry state. `task_run.status` is one of `running`, `completed`, `failed`, `timeout`, or `cancelled`.

Default resources are `db_connection` (5), `clickhouse_connection` (3), `network_api` (10), and `cpu_intensive` (2). The current engine gates critical tasks on the `db_connection` resource; non-critical tasks do not request a resource through the engine.

### Claim And Completion Guarantees

- A claim uses `FOR UPDATE SKIP LOCKED`, verifies enabled status, cadence/retry eligibility, completed dependencies, and overlap policy, then atomically creates a `task_run`, advances cadence, and sets a lease for `timeout_seconds + 60`.
- Non-overlap is the default. The partial unique index on running `task_run` rows prevents concurrent non-overlapping runs even under concurrency; `allow_overlap = TRUE` opts a task out.
- The worker validates the scheduled module against the execution allowlist and invokes it as `python -m MODULE ...` with structured arguments in a subprocess.
- Successful completion clears retry/failure state and the lease. Failed and timed-out runs update failure state and retry after `retry_delay_seconds` while the attempt is within `max_retries`; exhausted failures wait for the next cadence or operator action.
- A dead worker's expired lease marks its run failed, increments retry state when eligible, clears ownership, and makes the task retryable.
- Critical-task resource starvation cancels the unstarted run, clears the lease, and immediately makes the task retryable.
- Completion checks both the run worker and unexpired task lease. A stale worker raises `SchedulerLeaseLostError`, rolls back, and cannot update the task or publish a completion/failure event.
- Each valid completion publishes `task_completed` or `task_failed` to `platform_event` after the guarded state update.

`--run-now` validates the module and executes it directly with its configured arguments and timeout. It does not create scheduler claim/run bookkeeping or publish scheduler completion events, so use it deliberately for diagnostics.

`--status` reports enabled, disabled, running, and failing task counts, task cadence/status, and resource usage. `--list-runs` shows recent run history; use `--limit N` to change its default limit of 20. `--worker` runs the continuous tick loop and responds to SIGTERM/SIGINT.

Only one recurring-job owner should be active for a given job: worker cron, host cron, or the opt-in database scheduler. Duplicate dispatchers can duplicate ingestion and derived records.

## Event Bus

```text
pending -> processing lease -> each enabled handler delivery
        -> completed
        -> pending retry -> dead_letter -> replay -> pending
                                      \-> resolved/discarded
```

```bash
python3 -m services.events --process
python3 -m services.events --worker --batch-size 100 --poll-interval 2 --lease-seconds 300
python3 -m services.events --stats
python3 -m services.events --cleanup --days 30
python3 -m services.events --list-handlers
python3 -m services.events --list-dead-letter
python3 -m services.events --replay-dead-letter --event-id UUID --actor OPERATOR
python3 -m services.events --dispose-dead-letter --event-id UUID \
  --disposition resolved --actor OPERATOR --reason "Fixed upstream"
```

### Event Bus Records

| Table | Purpose |
|---|---|
| `platform_event` | Durable event queue, payload, priority, lease, retry, and processing state |
| `event_handler` | Enabled handler registration, module/function, order, timeout, and concurrency metadata |
| `event_handler_delivery` | Durable current status and attempt count for each `(event, handler)` pair |
| `event_handler_log` | Append-only per-attempt success/error/skip/timeout history |
| `event_dead_letter` | Operator disposition record for events that exceed retry limits |

`platform_event.priority` is `critical`, `high`, `normal`, or `low`; status is `pending`, `processing`, `completed`, `failed`, or `dead_letter`. Published events default to three retries unless `max_retries` is supplied. `event_handler_delivery` status is `pending`, `processing`, `success`, `error`, or `timeout`.

### Delivery Guarantees

- Claiming uses priority ordering, `FOR UPDATE SKIP LOCKED`, and a worker lease. Pending events and processing events with expired leases are claimable.
- The default event lease is 300 seconds. Before each handler, it is extended to at least the configured handler timeout plus 30 seconds. Expired leases are reclaimable by another worker.
- Enabled handlers for the event type run in `priority_order`. Each handler is resolved through the event-handler execution allowlist and invoked in an isolated child process.
- Handler timeouts terminate the child process. Handler errors and timeouts are recorded in both `event_handler_delivery` and the append-only `event_handler_log`.
- Delivery state is per `(event, handler)`. Successful handlers are skipped on event retry; failed and timed-out handlers are attempted again. A failed handler does not prevent later enabled handlers in the same delivery pass from being attempted.
- The event is completed only if all enabled handler deliveries succeed and the processing worker still owns the event lease. A lease-lost worker cannot report success.
- After the retry limit is reached, the event becomes `dead_letter` and one pending `event_dead_letter` record is retained. A partial unique index prevents multiple pending dead letters for the same event.
- `--cleanup --days N` deletes old completed and dead-letter platform events. The default retention window is 30 days; deleting an event cascades its delivery and attempt history.

### Dead-Letter Operations

- Replay requires an event UUID and non-empty actor. It resets event status to `pending`, retry count to zero, error and lease state, and marks the dead-letter row `replayed`. It intentionally preserves successful handler deliveries.
- Disposal requires `resolved` or `discarded`, an actor, and a non-empty reason. It records disposition, reason, actor, and time without replaying work.
- `--list-dead-letter` shows event type, failure count, last error, creation time, and disposition. `--stats` reports platform-event counts from the last 24 hours.

The default seeded handlers include anomaly detection for `sensor_reading`, data freshness for `data_stale`, metric cache invalidation for `metric_computed`, CRISP cache invalidation for `crisp_scored`, and alert notification for `threshold_breached`. Handler `max_concurrency` is stored as registration metadata; the current bus implementation enforces leases and per-handler delivery state but does not independently schedule a concurrency pool from that column.

Task/service owners fix deterministic failures. Operators decide replay versus documented disposal. Handlers and scheduled tasks must be idempotent because crashes can occur around external side effects and delivery recording. The event worker and scheduler worker are separate processes; deployment should start each only when its corresponding durable workload is enabled.

## References And Tests

- Scheduler schema: `schemas/postgres/117_task_scheduler.sql`
- Scheduler durability: `schemas/postgres/164_scheduler_durability.sql`
- Event schema: `schemas/postgres/116_event_bus.sql`
- Event durability: `schemas/postgres/165_event_bus_durability.sql`
- Scheduler engine/CLI: `services/scheduler/engine.py`, `services/scheduler/cli.py`, `services/scheduler/worker.py`
- Event bus/CLI: `services/events/bus.py`, `services/events/cli.py`
- Execution allowlist: `services/security/execution_allowlist.py`
- Focused tests: `tests/test_scheduler_durability.py` and `tests/test_event_bus_durability.py`
- Related operations: [Deployment](deployment.md), [Platform Integrity](platform-integrity.md), [Gateway](gateway.md), and [Metric Verification](metric-verification.md)
