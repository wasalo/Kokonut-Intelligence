# Metric Verification

Metric computation and verification are intentionally separate duties.

```text
governed inputs -> calculator -> metric_value(verified=false)
                                 -> human review -> verified=true -> public eligibility
```

## Compute

```bash
python3 -m services.metrics --compute --metric value_flowed --location-id UUID
python3 -m services.metrics --compute --all --location-id UUID
./scripts/compute-metrics.sh
```

`compute_metric` always inserts a new unverified `metric_value`, including computation method, source UUIDs, definition version metadata, and computation time. Computation never carries verification forward from an older value.

`scripts/compute-metrics.sh` defaults to `KOKONUT_METRICS_EXECUTION=auto`. If the Compose `database` service is running and the host is otherwise local, it launches a one-shot `kokonut-worker` with the worker overlay so private database networking remains intact. Set `KOKONUT_METRICS_EXECUTION=host` to force host execution. A non-local `PG_HOST` also uses host execution.

## Review

```bash
python3 -m services.metrics --list
python3 -m services.metrics --verify-value UUID \
  --verified-by REVIEWER_UUID \
  --verification-notes "Reviewed evidence and source records"
```

The reviewer ID is mandatory. Verification updates only an existing unverified row and records reviewer, timestamp, and notes; missing or already verified IDs fail.

## Invariants And Recovery

- Calculators compute; independent humans verify. Agents cannot verify or publish.
- `v_public_metric_summary` reads only `verified = TRUE` values and requires an eligible farm registry record.
- A calculator error is reported per metric; successful metrics remain committed. Correct inputs or code and recompute, producing a new unverified row.
- Failure to publish the follow-up `metric_computed` event is logged and does not undo committed metric values. Recover event-driven work using [Scheduler and Events](scheduler-and-events.md).
- Do not edit a value into correctness or reuse reviewer identity. Recompute, compare provenance, and explicitly verify the correct row.

See [Platform Integrity](platform-integrity.md), [Migrations](migrations.md), and [Credit Lifecycle](credit-lifecycle.md).
