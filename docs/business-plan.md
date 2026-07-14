# Business Plan Program

Structured business-plan generation for Kokonut Intelligence, built from the
Enterprise Planning System (EPS) and Value Stream Mapping (VSM) capabilities
already in the platform. It borrows the business-plan concept of assembling a
single coherent narrative from market, management, financial, operational, and
risk evidence — at two grains.

## Two grains

- **Organization grain** (`--org-id UUID`): rolls up every location in the
  organization — market overviews aggregated, S&OP cockpit, budget/variance,
  and operational flow per location.
- **Location grain** (`--location-id UUID`): a single-farm plan — that
  location's market overview, financial snapshot + reference-class dampening,
  its VSM current-state and bottlenecks, and SWOT.

Exactly one of `--org-id` / `--location-id` is required.

## Sections assembled

| Section | Source | Notes |
| --- | --- | --- |
| Market analysis | `services.analytics.marketplace.get_market_overview` | per-location; aggregated for org |
| Management & governance | `services.planning.sandop.cockpit` | org-scoped |
| Financial plan | `services.planning.budget` + `noi_snapshot` + reference-class | variance + latest NOI |
| Operational flow | `services.analytics.value_stream` | current-state map + bottlenecks |
| SWOT | `services.analytics.swot` | existing row, else suggested from threatcasting/CRISP |
| Executive summary | generated | short narrative |

Each section is computed best-effort: if a backing table or service is
unavailable, that section degrades to an error note rather than breaking the
whole plan. The assembler is read-only — it never writes governed data.

## Reference-class forecasting

A core business-plan safeguard against optimism bias. The subject location's
self-projection (from the forecast engine) is blended with the realized median
of comparable established locations:

```
damped = alpha * projected + (1 - alpha) * reference_median
```

`alpha` weights the subject's own (optimistic) projection. Lower alpha leans
more on the reference class (more conservative). Comparable locations are those
sharing the subject's organization with a `noi_snapshot`, excluding the subject.

- CLI: `python3 -m services.forecast.cli --reference-class --location-id UUID [--rc-metric crop_noi] [--rc-alpha 0.5]`

## SWOT framework

Structured Strengths / Weaknesses / Opportunities / Threats for an org or
location (`swot_analysis` table, schema `181_swot_analysis.sql`). Threats and
opportunities can be auto-suggested from existing `threat` and
`threat_narrative` data; strengths/weaknesses from CRISP risk bands.

- CLI: `python3 -m services.analytics.swot create|list|get|suggest`
- Report type: `python3 -m services.export.report_generator --type business_plan --location-id UUID`

## Running

```bash
python3 -m services.export.business_plan --org-id UUID
python3 -m services.export.business_plan --location-id UUID
python3 -m services.export.report_generator --type business_plan --location-id UUID
```

Tests: `python3 -m pytest tests/test_business_plan.py tests/test_swot.py tests/test_reference_class.py -v`
