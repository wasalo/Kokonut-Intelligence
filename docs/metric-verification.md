# Metric Verification

Metric computation and verification are intentionally separate duties. The
metric engine creates draft values; an explicitly identified human reviewer
verifies individual values before public metric views expose them.

```text
governed inputs -> calculator -> metric_value(verified=false)
                                  -> human review -> verified=true
                                  -> public eligibility
```

## Metric Definitions

`metric_definition` is the governed semantic layer. Each definition includes:

- `metric_key`, display name, description, and formula.
- Source tables, inclusion rules, and exclusion rules.
- Unit, data type, owner, update frequency, active flag, and version.
- Validation tests, report usage, category, and deprecation policy when seeded
  by metric-governance data.

Definition changes to formula, source tables, inclusion/exclusion rules, unit,
or data type automatically create a `metric_version` record. The database
trigger also advances the definition version when the submitted version is not
higher than the previous version.

The current calculator registry contains 20 metrics:

- `crop_revenue`, `net_crop_revenue`, `direct_crop_cost`,
  `allocated_shared_cost`, `crop_noi`, `loss_rate_pct`, and
  `operating_margin_pct`.
- `baseline_revenue`, `baseline_asset_value`, `baseline_cash_flow`, and
  `baseline_cost`.
- `value_flowed`, `wallet_retention`, `digital_lego_usage`,
  `soil_carbon_delta`, `biodiversity_delta`, and `attestation_coverage`.
- `governed_lead_time_days`, `first_time_through_yield_pct`, and
  `rework_rate_pct`.

Only active definitions with registered calculators are computed by
`compute_all()`.

## Compute

```bash
python3 -m services.metrics --compute --metric value_flowed --location-id UUID
python3 -m services.metrics --compute --all --location-id UUID
python3 -m services.metrics --compute --all --location-id UUID \
  --period-start 2026-01-01 --period-end 2026-03-31
python3 -m services.metrics --compute --all-locations --json
```

`compute_metric()` runs the registered calculator, stores a new
`metric_value` row with `verified = FALSE`, and records the computation method,
source UUIDs, definition version metadata, value, unit, period, and computation
time. It never carries verification forward from an older value.

The source UUID array is retained for compatibility. The normalized
`metric_value_source` table and `v_metric_value_provenance` view are the
structured provenance model for newer consumers. The phase-3 validation
migration backfills normalized links from existing `source_record_ids`; it does
not remove the legacy column.

`compute_all()` commits each successful metric computation independently,
continues after per-metric errors, and returns computed results plus an error
list and counts. After the batch it publishes one `metric_computed` event for
cache and downstream processing. Failure to publish that event is logged and
does not undo committed metric values.

For `--all-locations`, the CLI iterates over locations, prints per-location
results, emits JSON when requested, and exits non-zero if any location reports
metric errors. A single metric or location is required for `--compute` unless
`--all-locations` is used.

## Compute Script

```bash
./scripts/compute-metrics.sh
```

The script computes all active registered metrics for all locations. Its
execution mode is controlled by `KOKONUT_METRICS_EXECUTION`:

- `auto` (default): use the Compose worker when the private `database` service
  is running and host execution is otherwise local.
- `host`: always run `python3 -m services.metrics` on the host.
- Any non-local `PG_HOST` also uses host execution.

The Compose path runs a one-shot `kokonut-worker` with the worker overlay and
removes it when complete. This is not a persistent metrics service. The script
uses `set -eo pipefail` and reports completion only after the command succeeds.

## Review

List definitions and their current metadata:

```bash
python3 -m services.metrics --list
python3 -m services.metrics --list --json
```

Verify one computed value:

```bash
python3 -m services.metrics --verify-value UUID \
  --verified-by REVIEWER_UUID \
  --verification-notes "Reviewed evidence and source records"
```

The reviewer ID is mandatory. Verification updates only an existing unverified
row and records `verified_by`, `verified_at`, and `verification_notes`.
Missing IDs and already verified IDs fail. The database constraint also
requires reviewer attribution and a timestamp whenever `verified = TRUE`.

Verification is an individual human decision. Computation does not verify a
value, and agents cannot verify or publish metric values.

## Lifecycle And Integrity

`metric_value` has no textual `status` column. Its `verified` boolean is mapped
into the lifecycle ledger as:

```text
draft -> verified
```

The verified state is terminal. Inserts and changes to `verified` are recorded
in `lifecycle_transition`, with optional actor context from the database
session settings `kokonut.actor_id` and `kokonut.actor_type`.

Draft computations are append-only and may be repeated. Verified values have a
semantic unique boundary across:

- Metric definition
- Location, including a normalized null location key
- Period start and end, including normalized null dates
- Computation method

This prevents two current verified values for the same semantic metric result
while allowing repeated draft calculations and historical verified values with
different periods or methods.

## Public Eligibility

The canonical public projection is `v_public_metric_summary`. It exposes only
the latest verified value for each active metric definition and location. A
location must also be active and have a `farm_registry_record` with status
`verified` or `published`.

The gateway exposes the read-only public path:

```http
GET /api/metrics/{location_id}
```

The endpoint reads `v_public_metric_summary`, returns metric key, display name,
unit, value, computation time, and a computed count, and never invokes the
metric engine or creates records. Public gateway access is an explicit route
policy; unknown routes remain protected.

Public metric summaries do not expose draft values, reviewer notes, source
record arrays, or normalized provenance links.

## Recovery And Boundaries

- If a calculator fails, correct the input or implementation and recompute;
  the new row remains unverified.
- If the follow-up `metric_computed` event fails, inspect the event bus and
  recover event-driven work using [Scheduler and Events](scheduler-and-events.md).
- Do not edit a value into correctness, reuse reviewer identity, or verify an
  older row merely because a newer computation exists.
- Compare computation method, period, definition version, source provenance,
  and metadata before verifying the correct row.
- Public eligibility is not evidence maturity. Public carbon claims and other
  governed claims may require additional evidence, external verification, or
  claim-specific gates.
- Metric verification does not authorize publication of unrelated governed
  records, credit issuance, attestations, or financial actions.

## Source References

- `services/metrics/engine.py`
- `services/metrics/cli.py`
- `services/metrics/calculators/`
- `scripts/compute-metrics.sh`
- `schemas/postgres/007_modeled_outputs.sql`
- `schemas/postgres/018_public_views.sql`
- `schemas/postgres/024_metric_governance_enforcement.sql`
- `schemas/postgres/162_platform_integrity.sql`
- `schemas/postgres/179_lifecycle_transition.sql`
- `schemas/postgres/187_state_model_triggers.sql`
- `schemas/postgres/309_relationship_entities.sql`
- `schemas/postgres/310_cardinality_temporal_integrity.sql`
- `schemas/postgres/313_phase2_backfill_phase3_reference_validation.sql`
- `services/gateway/router.py`

## Tests

```bash
python3 -m pytest tests/test_metrics.py -v
python3 -m pytest tests/test_flow_metrics.py -v
python3 -m pytest tests/test_gateway_public_metrics.py -v
python3 -m pytest tests/test_bpm_state_models.py tests/test_cardinality_constraints.py tests/test_evidence_lineage_integrity.py -v
python3 -m pytest tests/test_scheduler_durability.py -v
```

These tests cover calculator registration and output shape, governance fields,
draft-only computation, reviewer attribution, public-view filtering, flow
metrics, lifecycle instrumentation, semantic uniqueness, provenance
backfill, gateway read behavior, and scheduler integration.

See [Platform Integrity](platform-integrity.md), [Migrations](migrations.md),
[Evidence Maturity](evidence-maturity.md), and [Credit Lifecycle](credit-lifecycle.md)
for adjacent governance boundaries.
