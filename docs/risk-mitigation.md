# Risk Mitigation

Kokonut uses a governed risk register to make mitigation, insurance scope, oversight, technical support, and residual risk explicit.

## Records

| Table | Purpose |
|---|---|
| `risk_mitigation_register` | Material risks with mitigation strategy, owner, review cadence, insurance scope, oversight, technical support, and residual risk |
| `v_public_risk_mitigation_summary` | Public-safe published risk register entries with sufficient evidence, summary text, and registry eligibility |

### `risk_mitigation_register`

Each record is scoped to a `location_id` and may optionally reference a `farm_id`. The required fields are:

- `risk_category`
- `risk_description`
- `mitigation_strategy`

Optional risk and control fields include `likelihood`, `impact_level`, `insurance_scope`, `oversight_mechanism`, `technical_support_provider`, `owner_role`, `review_cadence`, `residual_risk_level`, `review_date`, `next_review_date`, and `public_summary`.

The table also stores `evidence_maturity`, `metadata`, `source_system`, `source_id`, `source_raw`, creator/updater identifiers, and timestamps. The `location_id` foreign key restricts location deletion; the optional `farm_id` is set to NULL when its farm is deleted.

Allowed lifecycle states are `draft`, `submitted`, `verified`, `published`, and `rejected`. `likelihood` accepts `low`, `medium`, `high`, or `unknown`; `impact_level` and `residual_risk_level` accept `low`, `medium`, `high`, `critical`, or `unknown`.

## Risk Categories

- `climate`
- `market`
- `operational`
- `financial`
- `governance`
- `policy`
- `evidence_quality`
- `community`
- `technical`
- `other`

## Governed Metric

`risk_mitigation_coverage_pct` is defined as:

```text
mitigated_material_risks / material_risks * 100
```

The metric definition uses published register entries with an owner and review cadence, excludes draft and rejected risks, and validates that the result is between 0 and 100. The database seed defines the metric and its report usage; metric computation and human verification remain separate governed actions.

## Commands

```bash
python3 -m services.export.report_generator --type risk_mitigation --location-id UUID
python3 -m services.agents.resilience_agent --location-id UUID
# Store the resilience agent's output as a draft AI summary for human review
python3 -m services.agents.resilience_agent --location-id UUID --store
```

The resilience agent reads public-safe financial, risk, scaling, and Green Paper publication views. It reports counts and high/critical risk signals, but its optional stored output is an `ai_summary` in `draft` status and cannot verify or publish governed records.

Insurance details may remain private when policy documents include sensitive commercial or personal information. Public reports summarize insurance scope only when safe to publish. Public summaries must not expose private policy documents, personal information, draft terms, or unpublished assumptions.

## Public Publication Gates

`v_public_risk_mitigation_summary` includes a register row only when all of these conditions hold:

- `status = 'published'`;
- `evidence_maturity >= 3`;
- `public_summary` is non-empty after trimming;
- the location has a `farm_registry_record` with `status IN ('verified', 'published')`.

The view exposes public risk and control fields, evidence maturity and label, and metadata. It does not expose the register's source/audit lineage columns. A published risk row is not proof that the residual risk has been eliminated; it is a governed, public-safe record of the current assessment and controls.

## Report And Dashboard

The risk mitigation report reads only from `v_public_risk_mitigation_summary`, orders entries by `next_review_date` and `risk_category`, and supports optional date filtering on `review_date`. Rows with a NULL `review_date` remain included when a period filter is applied.

Report limitations state that the report summarizes published entries only, insurance may be partial when policy documents are private or unavailable, and residual risk is a reviewer-assessed signal that should be revisited on the listed cadence.

The public-safe dashboard is:

- `dashboards/metabase/29_risk_mitigation.json`
- SQL dataset: `dashboards/metabase/sql/29_risk_mitigation.sql`

The dashboard is owned by the Governance Guild, marked `public_safe`, and configured for daily refresh at `06:00`.

---

## CRISP Risk Scoring

The CRISP (Carbon Risk Identification and Scoring Principles) engine provides five-factor internal risk intelligence for farms, adapted from Solid World's SW-CRISP framework.

### Five Risk Dimensions

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| Carbon Yield | 40% | Likelihood of meeting carbon/biomass yield targets via scenario modeling |
| Climate Catastrophe | 25% | Probability of drought, flood, heat, fire, storm, water stress |
| Policy & Legal | 15% | Certification, regulatory, carbon rights, land tenure, community alignment |
| Financial Viability | 10% | Revenue diversity, cost structure, liquidity, market price exposure |
| Implementation | 10% | Track record, team strength, network, transparency |

### Rating Scale

| Rating | Score | Meaning |
|--------|-------|---------|
| AAA | 0–<20 | Prime — lowest risk |
| AA | 20–<44 | Very low risk |
| A | 44–<69 | Low risk |
| B | 69–<80 | Neutral — moderate risk |
| C | 80–<91 | High risk |
| D | 91–100 | Junk — highest risk |

### Adaptive Weights

Weights can be overridden per-location via `crisp_location_weight` to account for site-specific risk profiles (e.g., higher climate weight for drought-prone regions). Active overrides replace defaults for their dimension and the scoring engine normalizes the effective weights to sum to 1.0. Overrides record an optional reason and are constrained to the 0..1 range.

CRISP is a separate internal risk-assessment system. It consumes risk-register data for climate scoring, but a CRISP assessment is not itself a risk-register entry.

### Commands

```bash
# Individual dimension
python3 -m services.crisp --carbon-yield --location-id UUID
python3 -m services.crisp --climate --location-id UUID
python3 -m services.crisp --policy --location-id UUID
python3 -m services.crisp --financial --location-id UUID
python3 -m services.crisp --implementation --location-id UUID

# Composite rating
python3 -m services.crisp --composite --location-id UUID --period-start 2025-01-01 --period-end 2025-12-31

# Compute and persist
python3 -m services.crisp --rate --location-id UUID --period-start 2025-01-01 --period-end 2025-12-31

# Show weights
python3 -m services.crisp --weights --location-id UUID
```

All CRISP CLI flags are mutually exclusive. `--composite` is read-only and requires a location and assessment period. `--rate` computes and persists an assessment, initially governed as `draft`; persistence is not verification or publication. `--ssp` accepts `SSP1`, `SSP2`, or `SSP5`, but the current scoring thresholds are unchanged by the selected scenario.

### Database Tables

| Table | Purpose |
|-------|---------|
| `crisp_risk_dimension` | Dimension definitions with default weights |
| `crisp_location_weight` | Per-location weight overrides |
| `crisp_risk_assessment` | Master assessment per location per period |
| `crisp_carbon_yield_risk` | Carbon yield scenario detail |
| `crisp_climate_risk` | Climate hazard scoring detail |
| `crisp_policy_risk` | Policy & legal risk detail |
| `crisp_financial_risk` | Financial viability detail |
| `crisp_implementation_risk` | Implementation risk detail |
| `v_crisp_composite_rating` | Public composite view containing published assessments only and resolved effective weights |
| `v_crisp_latest_assessment` | Internal latest-assessment view across all lifecycle statuses |

CRISP assessments carry `period_start`, `period_end`, methodology version, five dimension scores, composite score, rating, confidence, evidence maturity, lifecycle status, reviewer notes, and audit metadata. The assessment is unique per location, period, and methodology version. Scores are constrained to 0..100, ratings to `AAA`, `AA`, `A`, `B`, `C`, or `D`, and confidence to `high`, `moderate`, `low`, or `insufficient_evidence`.

Higher CRISP scores mean higher risk. The `AAA` band is the lowest-risk band, while `D` is the highest-risk band. Overall confidence is limited by the least mature scored dimension. CRISP scores are modeled risk intelligence and should be presented with their evidence confidence and uncertainty, not as certifications, guarantees, or automatic decisions.

The climate dimension uses active risk-register entries as mitigation inputs. Each active mitigation reduces the natural climate-risk factor by 5%, with a floor of 0.5. The `SSP` value is recorded in the climate detail and uncertainty notes, but does not currently change the calculation.

Known implementation boundaries are documented in `docs/crisp-risk-scoring.md`, including the missing gateway `CRISPEngine` reference, the unwritten `article_6_score`, the missing LLM-chat `crisp_dimension_score` view, the lack of a dedicated CRISP report/dashboard, and the absence of an event emission after assessment persistence.

## References And Tests

- Risk-register schema and public view: `schemas/postgres/035_financial_resilience_and_scaling.sql`
- Metric and dashboard seed: `schemas/seeds/036_financial_resilience_and_scaling.sql`
- Risk report: `services/export/report_generator.py`
- Resilience agent: `services/agents/resilience_agent.py`
- CRISP schema and views: `schemas/postgres/076_crisp_risk_scoring.sql`
- CRISP methodology: `docs/crisp-risk-scoring.md`
- Focused tests: `tests/test_financial_resilience.py`, `tests/test_crisp_scoring.py`, `tests/test_schema_introspection_risks.py`, and `tests/test_strategy_risk_evidence.py`
