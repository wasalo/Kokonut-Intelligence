# Commons Liberation And Stewardship

Kokonut tracks commons-oriented claims as governed evidence rather than slogans. This layer answers whether farm operations are reducing operator burden, protecting community control over capital, broadening governance participation, and documenting land stewardship boundaries.

Schema: `schemas/postgres/037_commons_liberation_and_stewardship.sql`
Seeds: `schemas/seeds/038_commons_liberation_and_stewardship.sql` (metrics + dashboards), `schemas/seeds/038_pilot_commons_liberation.sql` (Adelphi pilot)

## Records

### `time_liberation_observation`

Workflow-level hours reclaimed, reporting-burden reduction, and automation or agent support observations.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, auto-generated |
| `location_id` | UUID FK → `location` | RESTRICT |
| `farm_id` | UUID FK → `farm` | SET NULL |
| `observation_date` | DATE | |
| `workflow_area` | VARCHAR(100) | |
| `baseline_hours` | NUMERIC(12,4) | ≥ 0 |
| `observed_hours` | NUMERIC(12,4) | ≥ 0 |
| `hours_reclaimed` | NUMERIC(12,4) | ≥ 0 |
| `burden_reduction_pct` | NUMERIC(8,4) | BETWEEN -100 AND 100 |
| `automation_or_agent_used` | BOOLEAN | |
| `automation_type` | VARCHAR(100) | |
| `beneficiary_group` | VARCHAR(100) | |
| `liberation_summary` | TEXT | NOT NULL |
| `public_summary` | TEXT | |
| `evidence_maturity` | INT FK → `evidence_maturity_level` | |
| `status` | lifecycle | draft → submitted → verified → published → rejected |

### `capital_alignment_assessment`

Public-safe capital-source alignment, extractive-risk level, community-control terms, and reinvestment commitments.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `location_id` | UUID FK → `location` | RESTRICT |
| `farm_id` | UUID FK → `farm` | SET NULL |
| `capital_source_id` | UUID FK → `capital_source` | SET NULL |
| `assessment_date` | DATE | |
| `provider_name` | VARCHAR(255) | |
| `provider_type` | VARCHAR(100) | NOT NULL, enum |
| `alignment_status` | VARCHAR(50) | DEFAULT 'under_review', enum |
| `extractive_risk_level` | VARCHAR(50) | enum |
| `community_control_terms` | TEXT | |
| `exit_pressure_risk` | TEXT | |
| `profit_extraction_limits` | TEXT | |
| `commons_reinvestment_commitment_pct` | NUMERIC(7,4) | BETWEEN 0 AND 100 |
| `assessment_summary` | TEXT | NOT NULL |
| `public_summary` | TEXT | |
| `evidence_maturity` | INT FK → `evidence_maturity_level` | |
| `status` | lifecycle | draft → submitted → verified → published → rejected |

### `governance_inclusion_observation`

Representation, missing groups, pseudonymous participation, and privacy-safe participation evidence.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `location_id` | UUID FK → `location` | SET NULL (network-level allowed) |
| `dao_proposal_id` | UUID FK → `dao_proposal` | SET NULL |
| `observation_date` | DATE | |
| `governance_body` | VARCHAR(255) | NOT NULL |
| `inclusion_scope` | VARCHAR(100) | NOT NULL, enum |
| `represented_groups` | TEXT[] | |
| `missing_groups` | TEXT[] | |
| `pseudonymous_participation_enabled` | BOOLEAN | |
| `marginalized_voice_count` | INTEGER | ≥ 0 |
| `total_participant_count` | INTEGER | ≥ 0 |
| `representation_coverage_pct` | NUMERIC(8,4) | BETWEEN 0 AND 100 |
| `inclusion_summary` | TEXT | NOT NULL |
| `public_summary` | TEXT | |
| `evidence_maturity` | INT FK → `evidence_maturity_level` | |
| `status` | lifecycle | draft → submitted → verified → published → rejected |

### `land_stewardship_commitment`

Stewardship model, anti-speculation terms, community benefit rights, landlord-dependency risk, and commons transition path.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `location_id` | UUID FK → `location` | RESTRICT |
| `farm_id` | UUID FK → `farm` | SET NULL |
| `tenure_rights_assessment_id` | UUID FK → `tenure_rights_assessment` | SET NULL |
| `commitment_date` | DATE | |
| `stewardship_model` | VARCHAR(100) | NOT NULL, enum |
| `landlord_dependency_risk` | VARCHAR(50) | enum |
| `anti_speculation_terms` | TEXT | |
| `community_benefit_rights` | TEXT | |
| `commons_transition_path` | TEXT | |
| `land_access_summary` | TEXT | NOT NULL |
| `public_summary` | TEXT | |
| `evidence_maturity` | INT FK → `evidence_maturity_level` | |
| `status` | lifecycle | draft → submitted → verified → published → rejected |

## Enum values

| Field | Allowed values |
|---|---|
| `stewardship_model` | `community_stewardship`, `cooperative_use`, `family_stewardship_with_public_goods`, `commons_trust_pathway`, `lease_to_stewardship`, `customary_commons`, `other` |
| `provider_type` | `dao_treasury`, `grantmaker`, `public_goods_funder`, `sponsor`, `buyer_partner`, `impact_investor`, `debt_provider`, `equity_provider`, `other` |
| `alignment_status` | `aligned`, `conditionally_aligned`, `under_review`, `misaligned`, `rejected` |
| `inclusion_scope` | `dao_committee`, `guild`, `farm_operator_group`, `stakeholder_review`, `metric_review`, `publication_review`, `other` |
| `extractive_risk_level` | `low`, `medium`, `high`, `critical`, `unknown` |
| `landlord_dependency_risk` | `low`, `medium`, `high`, `critical`, `unknown` |

## Public Views

All four views share the same privacy filter pattern:

```sql
WHERE status = 'published'
  AND evidence_maturity >= 3
  AND public_summary IS NOT NULL AND public_summary != ''
  AND EXISTS (
      SELECT 1 FROM farm_registry_record frr
      WHERE frr.location_id = <base>.location_id
        AND frr.status IN ('verified', 'published')
  )
```

| View | Base table | Notes |
|---|---|---|
| `v_public_time_liberation_summary` | `time_liberation_observation` | JOINs `evidence_maturity_level` for label |
| `v_public_capital_alignment_summary` | `capital_alignment_assessment` | JOINs `evidence_maturity_level` for label |
| `v_public_governance_inclusion_summary` | `governance_inclusion_observation` | Allows NULL `location_id` for network-level observations; LEFT JOINs location |
| `v_public_land_stewardship_summary` | `land_stewardship_commitment` | JOINs `evidence_maturity_level` for label |

## Governed Metrics

| Metric key | Owner | Unit | Update freq | Report usage |
|---|---|---|---|---|
| `operator_time_reclaimed_hours` | Impact Guild | hours | monthly | `time_liberation`, `green_paper` |
| `field_reporting_burden_reduction_pct` | Impact Guild | percentage | monthly | `time_liberation`, `green_paper` |
| `aligned_capital_share_pct` | Finance Guild | percentage | quarterly | `capital_alignment`, `green_paper` |
| `extractive_capital_risk_count` | Finance Guild | count | quarterly | `capital_alignment`, `green_paper` |
| `governance_representation_coverage_pct` | Governance Guild | percentage | quarterly | `governance_inclusion`, `green_paper` |
| `pseudonymous_participation_enabled` | Governance Guild | boolean | quarterly | `governance_inclusion`, `green_paper` |
| `land_stewardship_commitment_count` | Governance Guild | count | quarterly | `land_stewardship`, `green_paper` |
| `landlord_dependency_risk_level` | Governance Guild | risk_level | quarterly | `land_stewardship`, `green_paper` |

All metrics use `ON CONFLICT (metric_key) DO UPDATE` (idempotent). All include `deprecation_policy` and `validation_tests` JSONB.

## Agent

The commons agent (`services/agents/commons_agent.py`) synthesizes public-safe evidence from all four domains.

### Functions

| Function | Purpose |
|---|---|
| `synthesize_commons(conn, location_id)` | Queries all 4 public views, computes aggregates (total_hours_reclaimed, high_or_critical_extractive_risk_count, pseudonymous_participation_enabled_count) |
| `store_commons_summary(conn, summary, model_version)` | Writes to `ai_summary` table with `summary_type = 'commons_liberation'`, `status = 'draft'`, `source_tables` listing all 4 base tables |
| `run_commons_synthesis(location_id, store)` | Orchestrates read + optional store. Enforces `assert_agent_action_allowed("read", "time_liberation_observation")` |

### Output schema

```python
{
    "summary": { ... },
    "ai_summary_id": "UUID"  # only when --store
}
```

### Safety note

"Public-safe summaries only; private labor records, private capital terms, raw identity details, and unsupported land-transfer claims are excluded."

### CLI

```bash
python3 -m services.agents.commons_agent --location-id UUID
python3 -m services.agents.commons_agent --location-id UUID --store
```

## Report Generators

Four report types registered in `REPORT_GENERATORS`:

| Report type | Query view | Date column | Aggregate fields |
|---|---|---|---|
| `time_liberation` | `v_public_time_liberation_summary` | `observation_date` | `total_hours_reclaimed` |
| `capital_alignment` | `v_public_capital_alignment_summary` | `assessment_date` | `high_or_critical_extractive_risk_count` |
| `governance_inclusion` | `v_public_governance_inclusion_summary` | `observation_date` | `pseudonymous_participation_enabled_count` |
| `land_stewardship` | `v_public_land_stewardship_summary` | `commitment_date` | |

### Limitations

Each report includes a `limitations` array with privacy/legal guardrails:

- **time_liberation:** "not surveillance of individual workers", "private labor records excluded", "AI must reduce burdens"
- **capital_alignment:** "not private negotiations", "not future funding guarantees", "debt/equity need explicit review"
- **governance_inclusion:** "privacy-safe group summaries", "pseudonymous only with accountability", "not certification"
- **land_stewardship:** "not legal opinions", "not land transfer claims", "private household/title/lease excluded"

`governance_inclusion` supports `location_id=None` for network-wide reports (LEFT JOINs location).

### CLI

```bash
python3 -m services.export.report_generator --type time_liberation --location-id UUID
python3 -m services.export.report_generator --type capital_alignment --location-id UUID
python3 -m services.export.report_generator --type governance_inclusion --location-id UUID
python3 -m services.export.report_generator --type land_stewardship --location-id UUID
```

## Dashboards

Four Metabase dashboards with table visualizations:

| Dashboard | SQL file | JSON file | Owner | Refresh |
|---|---|---|---|---|
| Time Liberation | `35_time_liberation.sql` | `35_time_liberation.json` | impact_guild | daily 6 AM |
| Capital Alignment | `36_capital_alignment.sql` | `36_capital_alignment.json` | finance_guild | daily 6 AM |
| Governance Inclusion | `37_governance_inclusion.sql` | `37_governance_inclusion.json` | governance_guild | daily 6 AM |
| Land Stewardship | `38_land_stewardship.sql` | `38_land_stewardship.json` | governance_guild | daily 6 AM |

All have `privacy: "public_safe"` and `refresh_cron: "0 6 * * *"`.

## CRISP Integration

Commons liberation tables feed two CRISP risk dimensions:

- **Policy & Legal Risk (15% weight):** queries `land_stewardship_commitment` for `stewardship_model`, `landlord_dependency_risk`, `anti_speculation_terms`; queries `governance_inclusion_observation` for `representation_coverage_pct`, `marginalized_voice_count`
- **Implementation Risk (10% weight):** queries `governance_inclusion_observation` for `representation_coverage_pct`, `marginalized_voice_count`

## Pilot Data

The Adelphi pilot seed (`038_pilot_commons_liberation.sql`) includes 4 example records:

| Record | Key data |
|---|---|
| Time liberation | 3h reclaimed from 8h baseline (37.5% reduction), monthly_operator_reporting, automation_type=ai_summary_and_csv_templates |
| Capital alignment | Kokonut DAO and public-goods funders, aligned, low extractive risk, 10% commons reinvestment |
| Governance inclusion | 4 groups represented, 2 missing groups, 75% coverage, pseudonymous enabled |
| Land stewardship | family_stewardship_with_public_goods, low risk, explicitly excludes land-transfer claims |

### Anti-overclaiming guardrails

All pilot records include `unsupported_claims_excluded` in metadata. The test suite asserts that "100% women-based leadership" is NOT present in the pilot seed to prevent overclaiming.

## Agent Safety

All 4 tables are in `GOVERNED_COLLECTIONS` in `services/agents/safety.py`. Agents can create draft rows but cannot set status to `verified` or `published`.

The agent task `commons_liberation_synthesis` is classified as `risk: medium`, `high_risk: False`, and writes `["ai_summary:draft"]` only.

## Testing

```bash
python3 -m tests.test_commons_liberation
```

| Test | Coverage |
|---|---|
| `test_commons_schema_defines_records_and_public_views` | All 4 tables and 4 views exist; evidence_maturity >= 3 filter; farm_registry_record check; pseudonymous_participation_enabled column |
| `test_commons_seed_and_dashboards_exist` | All 8 metric keys in seed; all 4 dashboard SQL and JSON files exist; refresh_cron present |
| `test_pilot_seed_has_adelphi_examples_without_venus_claims` | Adelphi pilot data present; unsupported_claims_excluded present; no overclaiming |
| `test_commons_agent_task_catalogue_and_validation` | Task in catalogue; writes ai_summary:draft; not high_risk; missing summary caught |
| `test_commons_agent_summarizes_public_safe_records` | Full mock test of synthesize_commons() with all 4 view responses; verifies counts, totals, safety_note |
| `test_commons_report_generators_registered` | All 4 report types in REPORT_GENERATORS |
| `test_commons_report_generators_public_safe` | All 4 produce correct report_type; land_stewardship limitations include "not legal opinions" |
