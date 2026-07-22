# Prediction Calibration And Outside View

Kokonut records scalar forecasts in `prediction_ledger` while retaining each domain table as its source of truth. Forecasts are projections, not verified facts. The ledger records the source table and record, domain, metric, unit, location, optional crop/cycle/plot context, model and version, issuance time, target period, horizon, predicted value, interval, confidence, inputs, and input hash.

## Prediction Lifecycle

Prediction ledger and outcome records use the governed lifecycle:

```text
draft -> submitted -> verified -> published
draft -> rejected -> draft
```

Forecast execution writes `forecast_output` and its corresponding `prediction_ledger` row in one database transaction. The ledger row is initially `submitted`; computation and submission remain available even when later calibration fails.

The ledger uses a unique source record and source-point key for idempotency. Re-running a forecast does not create duplicate scalar ledger rows for the same source point.

## Outcome Workflow

1. Forecast execution writes `forecast_output` and a submitted ledger record atomically.
2. An actual outcome is linked through `prediction_outcome`.
3. Outcomes are drafts by default. Supplying a valid human UUID to `--verified-by` can create an already-verified outcome.
4. Automatically resolved outcomes are always created as drafts, even when their source records are verified or published.
5. A human verifies a draft or submitted outcome with `verify-outcome`.
6. Evaluation consumes only verified or published outcomes and requires matching prediction/outcome units.
7. Only one verified or published active outcome is allowed per prediction. The schema includes `supersedes_id` for lineage, but the current service does not implement an active-outcome replacement workflow.

Signed error is always `predicted - actual`; positive values mean overprediction. Evaluation records:

- signed error;
- absolute error;
- squared error;
- absolute percentage error, when the actual value is nonzero;
- interval coverage, when both interval bounds exist;
- Brier score for binary predictions with an actual outcome of `0` or `1`.

## Prediction Commands

```bash
python3 -m services.predictions record-forecast --output-id UUID
python3 -m services.predictions record-outcome \
  --prediction-id UUID \
  --source-table harvest_event \
  --source-id UUID \
  --actual-at 2027-03-31T00:00:00+00:00 \
  --actual-value 20 \
  --unit tonnes \
  --verified-by HUMAN_UUID
python3 -m services.predictions resolve-outcome --prediction-id UUID
python3 -m services.predictions verify-outcome --outcome-id UUID --verified-by HUMAN_UUID
python3 -m services.predictions evaluate --prediction-id UUID
python3 -m services.predictions calibrate \
  --model kokonut_forecast_engine \
  --version v2026.07 \
  --metric total_yield_tonnes
```

### Allowlisted Outcome Resolution

`resolve-outcome` does not search arbitrary tables. It supports governed resolvers for:

| Forecast metric | Actual source | Unit |
|---|---|---|
| `projected_revenue_usd` | verified/published `revenue_event` | `usd` |
| `total_yield_tonnes` | verified/published `harvest_event` | `tonnes` |
| `loss_adjusted_yield_tonnes` | verified/published `harvest_event` | `tonnes` |
| `projected_noi_usd` | verified/published revenue and expense events | `usd` |
| `risk_adjusted_noi_usd` | verified/published revenue and expense events | `usd` |

Unsupported metrics fail with no outcome. The resolver aggregates the matching target-period records and stores source IDs and aggregation context in the draft outcome evidence.

## Calibration

Calibration is requested by model, model version, and metric. The service evaluates verified or published outcomes and applies the most specific active `prediction_calibration_policy` available for the inferred domain and requested scope.

Calibration metrics include MAE, RMSE, MAPE, signed bias, absolute bias percentage, interval coverage, mean Brier score, sample size, and failure reasons. Horizon buckets are:

| Bucket | Horizon |
|---|---:|
| `0-7d` | Up to 7 days |
| `8-30d` | More than 7 through 30 days |
| `31-90d` | More than 30 through 90 days |
| `91-365d` | More than 90 days through 1 year |
| `366d+` | More than 1 year |

Gate results are:

- `pass`: sufficient sample and all configured policy checks pass;
- `fail`: sufficient sample and one or more policy checks fail;
- `insufficient_data`: fewer than the policy minimum, defaulting to 20 when no policy matches;
- `stale`: permitted by the schema for stale assessments, but not currently emitted by the service implementation.

The assessment schema stores location, crop, and horizon dimensions. The current service query aggregates the requested model/version/metric rows and populates those fields from the first matching row rather than producing separate assessments for every available location, crop, and horizon bucket. Do not describe the current CLI result as a fully grouped calibration matrix.

When a forecast scenario transitions to `published`, the database trigger checks the latest matching calibration assessment. A current `fail` blocks publication. `insufficient_data` does not block publication through this trigger, but reports surface it as a warning and reviewers should disclose the limited calibration evidence.

## Forecast And Report Boundaries

- A calibration result is evidence about historical forecast performance, not a guarantee about future accuracy.
- `fail` requires recalibration and independent review before affected forecasts are published.
- `insufficient_data` requires continued outcome collection and an explicit uncertainty disclosure.
- Forecast outputs and dashboard records remain governed records; agents cannot verify or publish them.
- Report generation surfaces failed scopes as high-severity findings and insufficient scopes as review warnings.

## Reference Classes And The Outside View

`reference_class` stores a governed comparison population with:

- versioned reference key and name;
- domain, metric, and unit;
- population definition;
- inclusion and exclusion criteria;
- geography, climate zone, production system, and crop/species dimensions;
- sample size;
- P10, P25, median, P75, and P90 values where available;
- failure rate;
- source citation, URL, and publication date;
- evidence maturity and governed lifecycle metadata.

Only verified or published reference classes can be selected. The prediction metric and unit must match the reference class exactly. The platform requires an explicit selection rationale and never chooses the highest available benchmark as an implicit fallback. No defensible reference-class match should be represented as a valid outside view.

`outside_view_comparison` records the inside estimate, reference median, adverse reference value, deviation, selection rationale, deviation rationale, disconfirming evidence, fit dimensions, fit status, and review lifecycle.

- The current service uses the reference class `p10` as `reference_adverse`.
- The current service writes `fit_status = 'good'` and does not populate `fit_dimensions` through the CLI path; reviewers should not infer a richer automated fit assessment.
- A deviation greater than 10 percent requires a non-empty deviation rationale, enforced by both service validation and the database constraint.
- Outside-view comparisons are upserted by prediction/reference-class pair.

```bash
python3 -m services.predictions outside-view \
  --prediction-id UUID \
  --reference-class-id UUID \
  --selection-rationale "Comparable rain-fed maize farms in the same climate zone" \
  --deviation-rationale "Irrigation investment supports the difference" \
  --disconfirming-evidence "Pump commissioning may miss planting"
```

Reference classes are governed records; the prediction CLI compares against an existing class but does not create one. Reference-class dampening used by the forecast/business-plan services is a separate comparison helper and should not be confused with the governed prediction-ledger outside view.

## Resolvable Probability Forecasts

Threat probabilities are resolvable questions, not timeless attributes. A question must identify a threat or narrative and define its domain, event definition, resolution criteria, resolution source, opening time, closing time, and latest resolution time. The date rule is:

```text
opens_at < closes_at <= resolves_by
```

Probability forecasts are immutable records. A new forecast supersedes an earlier one rather than editing it. Forecasts can be issued only while the question is `open` and within its open/close window.

```bash
python3 -m services.threatcasting forecast-question-create \
  --location-id UUID \
  --threat-id UUID \
  --domain climate \
  --question "Will the event occur?" \
  --event-definition "Defined event" \
  --resolution-criteria "Evidence threshold" \
  --resolution-source "Named source" \
  --opens-at ISO_TIMESTAMP \
  --closes-at ISO_TIMESTAMP \
  --resolves-by ISO_TIMESTAMP \
  --created-by HUMAN_UUID
python3 -m services.threatcasting forecast-question-status --question-id UUID --status open
python3 -m services.threatcasting probability-forecast \
  --question-id UUID --probability 0.7 \
  --source-type analyst --methodology-version v1
python3 -m services.threatcasting forecast-resolve \
  --question-id UUID --status resolved --outcome 1 \
  --evidence '[]' --notes "Resolved from governed source" \
  --resolved-by HUMAN_UUID
python3 -m services.threatcasting expert-calibrate \
  --panel-member-id UUID --domain climate
```

Resolution is blocked before `closes_at` and requires a human UUID and non-empty notes. A question can be resolved, cancelled, or invalidated. Cancelled and invalid questions have no binary outcome and receive no Brier scores. Resolved binary forecasts receive Brier scores using `score = (probability - outcome)^2`, with outcomes restricted to `0` or `1`.

## Delphi Calibration And Participation

Delphi members start with equal weight. `expert-calibrate` records Brier performance and a calibrated weight for a panel member/domain:

- fewer than 20 resolved forecasts keeps the weight at `1.0`;
- at least 20 resolved forecasts allows calibration;
- the weight is shrunk toward `1.0` according to reliability;
- the database and service clamp the weight to `0.5`-`1.5`.

The current Delphi panel service’s default `_derive_weight` returns `1.0`; creating a `delphi_expert_calibration` row does not automatically change all normal panel aggregation. Treat calibrated weights as an explicit calibration artifact until the aggregation path applies them.

Consensus, panel diversity, stopping outcomes, minority reports, probability accuracy, calibration weights, and recommendation approval remain separate concepts:

- diversity targets and assessments describe panel representation without exposing identities;
- stopping evaluations distinguish consensus, stability, participation, completion, and time limits;
- minority reports preserve dissent as governed records;
- probability scores measure forecast accuracy;
- recommendations remain drafts until a human approves them.

## References And Verification

- Prediction service: `services/predictions/service.py`
- Prediction CLI: `services/predictions/cli.py`
- Prediction schema and publication trigger: `schemas/postgres/169_prediction_calibration_outside_view.sql`
- Delphi and threat-resolution schema: `schemas/postgres/170_delphi_threat_resolution.sql`
- Probability resolver: `services/threatcasting/probability.py`
- Delphi panel weighting: `services/delphi/panel.py`
- Prediction tests: `tests/test_prediction_calibration.py`
- Reference-class tests: `tests/test_reference_class.py`
- Delphi tests: `tests/test_delphi.py`
- Forecast engine transaction: `services/forecast/engine.py`
- Forecast report findings: `services/export/report_generator.py`

Run the focused tests with:

```bash
python3 -m pytest \
  tests/test_prediction_calibration.py \
  tests/test_reference_class.py \
  tests/test_delphi.py -v
```
