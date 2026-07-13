# Prediction Calibration And Outside View

Kokonut records scalar forecasts in `prediction_ledger` while retaining each domain table as its source of truth. Every ledger record identifies its model, version, metric, domain, location, crop context, issuance time, target period, horizon, interval, and source record.

## Outcome Workflow

1. Forecast execution writes `forecast_output` and a submitted ledger record atomically.
2. An actual outcome is linked through `prediction_outcome`.
3. Outcomes are drafts unless a human UUID verifies them.
4. Evaluation consumes only verified or published outcomes.
5. Signed error is always `predicted - actual`; positive values mean overprediction.
6. Evaluation records signed error, absolute error, squared error, percentage error where defined, interval coverage, and Brier score for binary predictions.

```bash
python3 -m services.predictions record-forecast --output-id UUID
python3 -m services.predictions record-outcome --prediction-id UUID --source-table harvest_event --source-id UUID --actual-at 2027-03-31T00:00:00+00:00 --actual-value 20 --unit tonnes --verified-by UUID
python3 -m services.predictions resolve-outcome --prediction-id UUID
python3 -m services.predictions verify-outcome --outcome-id UUID --verified-by UUID
python3 -m services.predictions evaluate --prediction-id UUID
python3 -m services.predictions calibrate --model kokonut_forecast_engine --version v2026.07 --metric total_yield_tonnes
```

Calibration is reported by model, version, metric/domain, horizon bucket, location, and crop when those dimensions are available. A result is `pass`, `fail`, `insufficient_data`, or `stale`. Insufficient data is not represented as success. Forecast publication is blocked when a current assessment explicitly fails policy; computation and submission remain available.

## Reference Classes

`reference_class` stores governed comparison populations with explicit inclusion/exclusion criteria, sample size, P10/P25/median/P75/P90, failure rate, applicability dimensions, source citation, and evidence maturity. Only verified or published reference classes can be selected.

`outside_view_comparison` records the inside estimate, reference median, adverse percentile, fit, disconfirming evidence, selection rationale, and deviation rationale. A deviation greater than 10 percent requires rationale. The platform never selects the highest available benchmark as an implicit fallback; no defensible match produces insufficient evidence.

```bash
python3 -m services.predictions outside-view --prediction-id UUID --reference-class-id UUID --selection-rationale "Comparable rain-fed maize farms in the same climate zone" --deviation-rationale "Irrigation investment supports the difference" --disconfirming-evidence "Pump commissioning may miss planting"
```

## Probability Resolution

Threat probabilities are resolvable questions, not timeless attributes. Each question defines the event, closing date, resolution criteria, and source. Forecasts are immutable. A human resolves, cancels, or invalidates the question after forecast close; resolved binary forecasts receive Brier scores.

Delphi members start with equal weight. A calibrated weight is available only after at least 20 resolved forecasts in the same domain and is shrunk toward 1.0 within a 0.5–1.5 range. Consensus, panel diversity, stopping outcome, minority reports, probability accuracy, and recommendation approval remain separate concepts.
