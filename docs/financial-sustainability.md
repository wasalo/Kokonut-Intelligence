# Financial Sustainability

Kokonut tracks financial sustainability as governed planning evidence. The
system records a farm's financial model, grant exposure, reinvestment intent,
public-goods allocation, runway, and projected NOI. These are planning signals,
not guarantees of revenue, grants, solvency, or market performance.

## Implementation Status

| Capability | Status |
|------------|--------|
| Sustainability plan schema | Implemented and lifecycle-governed |
| Public sustainability view | Implemented with evidence and registry gates |
| Four sustainability metric definitions | Seeded metadata only; no registered metric calculators |
| Sustainability-state classification | Stored as a field; no discovered automatic classifier |
| Financial sustainability report | Implemented; reads public-safe view |
| Resilience synthesis agent | Implemented; read-only by default, draft `ai_summary` with `--store` |
| Dashboard | Implemented through Metabase SQL/JSON assets |
| Scenario and scaling economics | Separate planning models; not proof of live-farm outcomes |

## Canonical Record

Primary table: `financial_sustainability_plan`, defined in
`schemas/postgres/035_financial_resilience_and_scaling.sql`.

The plan includes:

- farm/location linkage;
- `farm_model`;
- revenue streams and grant dependency;
- `grant_dependency_pct`;
- `reinvestment_pct`;
- `public_goods_allocation_pct`;
- break-even month;
- `runway_months`;
- projected annual revenue;
- projected annual operating cost;
- `projected_annual_noi_usd`;
- `sustainability_status`;
- governed lifecycle `status`;
- evidence maturity;
- public summary;
- source lineage and audit fields.

The plan field names are not identical to the governed metric names:

| Plan field | Related metric name |
|------------|---------------------|
| `reinvestment_pct` | `reinvestment_rate_pct` |
| `runway_months` | `sustainability_runway_months` |
| `projected_annual_noi_usd` | Not the same as computed `crop_noi` |

## Farm Models

The database permits:

- `public_good_optimized`
- `blended`
- `for_profit`
- `cooperative`
- `research_pilot`
- `other`

These values describe the plan's operating model. They do not automatically
determine revenue, risk, classification, or publication eligibility.

## Sustainability States And Lifecycle

`sustainability_status` is a domain state and supports:

- `draft`
- `grant_dependent`
- `transitioning`
- `self_sustaining`
- `surplus_generating`
- `needs_rework`

It must not be confused with the governed lifecycle:

```text
draft → submitted → verified → published
                  ↘ rejected
```

The schema stores these sustainability states, but no discovered service derives
them automatically from inflows, costs, runway, or NOI. A state is therefore a
plan assertion requiring review, not an independently computed conclusion.

## Public Visibility

`v_public_financial_sustainability_summary` exposes only plans that satisfy all
of the following:

- `status = 'published'`;
- `evidence_maturity >= 3`;
- non-empty `public_summary`;
- associated `farm_registry_record` status `verified` or `published`.

The report, dashboard, and resilience agent read this public-safe view rather
than unrestricted draft plans. Public visibility does not establish future
financial performance or independently verify projections.

## Governed Metric Definitions

The following definitions are seeded in
`schemas/seeds/036_financial_resilience_and_scaling.sql`:

| Metric | Defined formula |
|--------|-----------------|
| `grant_dependency_pct` | `grants_received / total_inflows * 100` |
| `reinvestment_rate_pct` | `reinvestment_value / eligible_value_flowed * 100` |
| `public_goods_allocation_pct` | `public_goods_allocation / eligible_revenue * 100` |
| `sustainability_runway_months` | `running_balance / monthly_net_burn` |

These are governed metric definitions, but the current metric calculator
registry does not register calculators for them. Consequently:

- `services.metrics --compute --metric grant_dependency_pct` reports no
  calculator registered;
- `--compute --all` does not generate these values;
- no corresponding `metric_value` rows are produced by the metric engine;
- plan fields and seeded values remain planning evidence unless another reviewed
  process computes or verifies them.

Implemented operational NOI metrics are separate. `crop_noi` is calculated from
net crop revenue, direct crop costs, and allocated shared costs. It is not the
same as `projected_annual_noi_usd` on a sustainability plan.

## Seeded Adelphi Example

The pilot plan in `schemas/seeds/030_pilot_financial_resilience.sql` is a
published, maturity-3 planning record with:

| Field | Seeded value |
|-------|--------------|
| Farm model | `blended` |
| Grant dependency | 35% |
| Reinvestment | 20% |
| Public-goods allocation | 10% |
| Break-even | Month 14 |
| Runway | 9.5 months |
| Projected annual revenue | $24,500 |
| Projected annual operating cost | $15,300 |
| Projected annual NOI | $9,200 |
| Sustainability state | `transitioning` |

These are seeded projections and plan assertions. They are not proof that the
metric engine calculated or independently verified the values.

Scaling seeds contain separate conditional economics, including planned farm
launch costs, projected revenue, projected NOI, ROI, and payback. Those values
belong to scenario/planning evidence, not realized operating performance.

## Reports And Dashboard

Generate the public financial sustainability report with:

```bash
python3 -m services.export.report_generator \
  --type financial_sustainability --location-id UUID
```

The generator reads `v_public_financial_sustainability_summary`, supports the
report generator's optional period arguments, and excludes draft, unpublished,
below-maturity, and registry-ineligible plans.

Related report types include:

- `capital_efficiency`
- `scaling_economics`
- `perpetual_value_stress`
- `strategic_reserve`
- composite financial and State of Kokonut reports

Dashboard assets:

- `dashboards/metabase/sql/28_financial_sustainability.sql`
- `dashboards/metabase/28_financial_sustainability.json`

The dashboard displays grant dependency, reinvestment, public-goods allocation,
break-even month, runway, projected revenue/cost/NOI, evidence maturity, and
public summary. It queries the public view and inherits its gates. Dataset
refresh metadata and cron descriptions should not be interpreted as proof that
the underlying financial plan is recalculated automatically.

## Resilience Agent

```bash
python3 -m services.agents.resilience_agent --location-id UUID
python3 -m services.agents.resilience_agent \
  --location-id UUID --store
```

The agent reads public-safe sustainability, risk, scaling, and publication views
and synthesizes financial resilience context. By default it writes nothing.
With `--store`, it creates only a draft `ai_summary` record. It does not create
or update `financial_sustainability_plan`, calculate the four unregistered
metrics, verify projections, or publish financial claims.

The task catalogue identifies this as `financial_resilience_synthesis`, with an
optional draft `ai_summary` write and no high-risk autonomous action.

## Related Financial Models

Financial sustainability should be distinguished from adjacent models:

- `capital_efficiency_scenario` — capital deployment and regenerative output
  scenarios;
- `capital_provider_utility_scenario` — provider utility scenarios;
- `farm_launch_unit_economics` — launch economics;
- `network_scaling_target` — scaling targets;
- `perpetual_value_stress_test` — downside runway, NOI, and solvency scenarios;
- `financial_plan`, `budget_line`, and `planning_scenario` — enterprise planning
  model from `176_financial_planning.sql`;
- `crop_noi` and operating margin — computed operational metrics.

These models may inform planning reports but are not interchangeable with the
sustainability plan or proof of realized financial performance.

## Known Limitations

- Four sustainability metrics have definitions but no registered calculators.
- No automatic sustainability-state classifier was found.
- Projected NOI is not computed `crop_noi`.
- Seeded values are planning evidence, not independently verified outcomes.
- Public view publication requires maturity 3, summary, publication, and farm
  registry eligibility, not merely a populated plan.
- Resilience-agent summaries are draft outputs when stored.
- CRISP financial-risk integration currently references stale/nonexistent
  financial columns such as `noi_projection_y1` and may not be a reliable
  sustainability calculation path until corrected.
- Scenario ROI, payback, and scaling figures are conditional assumptions.

## Tests And Source References

Relevant tests:

- `tests/test_financial_resilience.py`
- `tests/test_financial_enhancements.py`
- `tests/test_open_source_capitalist_scaling.py`
- `tests/test_crisp_scoring.py`
- `tests/test_scenario_parameters.py`
- `tests/test_state_of_kokonut.py`

Primary references:

- `schemas/postgres/035_financial_resilience_and_scaling.sql`
- `schemas/postgres/036_capital_efficiency_and_utility.sql`
- `schemas/postgres/040_open_source_capitalist_scaling.sql`
- `schemas/postgres/070_financial_enhancements.sql`
- `schemas/postgres/176_financial_planning.sql`
- `schemas/postgres/321_public_financial_governance.sql`
- `schemas/seeds/030_pilot_financial_resilience.sql`
- `schemas/seeds/036_financial_resilience_and_scaling.sql`
- `services/metrics/engine.py`
- `services/export/report_generator.py`
- `services/agents/resilience_agent.py`
- `services/agents/tasks.py`
- `services/agents/safety.py`
