# Scheduler And Events

The scheduler and event bus use PostgreSQL leases so multiple workers can cooperate without central in-memory coordination.

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
```

- Claiming atomically creates `task_run`, advances cadence, and sets a lease for `timeout_seconds + 60`.
- `FOR UPDATE SKIP LOCKED` prevents duplicate claims. Dependencies must have completed.
- Non-overlap is the default behavior unless `allow_overlap` is true; a running task blocks another claim.
- Failures and timeouts increment failure state and retry after `retry_delay_seconds` through `max_retries`.
- An expired lease marks the abandoned run failed and makes the task retryable. Resource starvation cancels the unstarted run and immediately releases it for retry.
- `--run-now` executes directly and does not use the scheduler claim/run bookkeeping; use it deliberately for operator diagnostics.

## Event Bus

```text
pending -> processing lease -> each enabled handler delivery
        -> completed
        -> pending retry -> dead_letter -> replay -> pending
                                      \-> resolved/discarded
```

```bash
python3 -m services.events --process
python3 -m services.events --stats
python3 -m services.events --list-handlers
python3 -m services.events --list-dead-letter
python3 -m services.events --replay-dead-letter --event-id UUID --actor OPERATOR
python3 -m services.events --dispose-dead-letter --event-id UUID \
  --disposition resolved --actor OPERATOR --reason "Fixed upstream"
```

- Delivery state is per `(event, handler)`. Successful handlers are skipped on retry; failed handlers are attempted again.
- Handler processes have enforced timeouts. Event leases are extended before each delivery and expired leases are reclaimable.
- After maximum retries, the event and a pending dead-letter record are retained.
- Replay resets event retry/lease state but preserves successful per-handler deliveries. Disposal records `resolved` or `discarded`, actor, reason, and time; it does not replay work.

Task/service owners fix deterministic failures. Operators decide replay versus documented disposal. Handlers must be idempotent because crashes can occur around external side effects and delivery recording. See [Platform Integrity](platform-integrity.md), [Gateway](gateway.md), and [Metric Verification](metric-verification.md).
