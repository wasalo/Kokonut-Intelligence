# Capital Efficiency And Utility

Kokonut Intelligence tracks capital efficiency as governed scenario evidence.
The module answers how much output, public-goods value, regenerative savings,
governance speed, and capital-provider utility are visible from published
records. All figures are planning evidence — not investment advice, securities
offerings, or guaranteed return projections.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    Capital Efficiency Domain                      │
│                                                                   │
│  ┌────────────────────┐  ┌──────────────────────────────────────┐│
│  │ 4 Governed Tables   │  │ 4 Public Views                       ││
│  │ (036, extended 070) │  │ (evidence_maturity >= 3,             ││
│  │                     │  │  farm_registry_record gate)           ││
│  └────────┬───────────┘  └──────────────────┬───────────────────┘│
│           │                                  │                    │
│  ┌────────┴──────────────────────────────────┴──────────────────┐│
│  │ 3 Report Generators        │  Agent Synthesis                ││
│  │ capital_efficiency         │  capital_efficiency_agent        ││
│  │ governance_throughput      │  (queries 4 public views,        ││
│  │ capital_provider_utility   │   stores draft ai_summary)       ││
│  └────────────────────────────┴─────────────────────────────────┘│
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │ 6 Governed Metrics + 3 Metabase Dashboards                   ││
│  └──────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

## Scenario types & provider types

### Capital efficiency scenario types

| Value | Description |
|---|---|
| `farm_establishment` | Initial farm setup capital and output |
| `practice_upgrade` | Capital for adopting or upgrading a regenerative practice |
| `public_goods_loop` | Capital deployed with explicit public-goods allocation |
| `replication` | Capital for replicating a proven model at another location |
| `sponsor_supported` | Capital from a sponsor with public-goods expectations |
| `partner_infrastructure` | Capital for shared infrastructure (e.g. biofactory) |
| `other` | Miscellaneous capital deployment scenario |

### Capital provider utility types

| Value | Description |
|---|---|
| `grantmaker` | Grant-based capital with public-goods expectations |
| `sponsor` | Sponsor-supported capital with verification/reporting outputs |
| `dao_treasury` | DAO treasury allocation via governance process |
| `impact_investor` | Impact investment with blended return expectations |
| `buyer_partner` | Buyer-partner advance or pre-purchase commitment |
| `public_goods_funder` | Funder focused on public-goods output |
| `other` | Miscellaneous capital provider |

### Governance decision results

| Value | Description |
|---|---|
| `approved` | Proposal approved by governance process |
| `rejected` | Proposal rejected |
| `cancelled` | Proposal withdrawn or cancelled |
| `deferred` | Decision deferred to a later date |
| `executed` | Proposal approved and executed on-chain |
| `unknown` | Decision outcome not yet recorded |

## Database tables

### `capital_efficiency_scenario`

Tracks scenario-level capital deployed, output value, public-goods value, and
leverage ratios. Extended in migration 070 with IRR/NPV columns.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID PK | auto-generated | |
| `location_id` | UUID FK → `location` | NOT NULL, RESTRICT | |
| `farm_id` | UUID FK → `farm` | SET NULL | |
| `scenario_name` | VARCHAR(255) | NOT NULL | |
| `scenario_type` | VARCHAR(100) | NOT NULL, CHECK | one of 7 scenario types |
| `period_start` | DATE | NOT NULL | |
| `period_end` | DATE | nullable | |
| `capital_deployed_usd` | NUMERIC(18,2) | NOT NULL, >= 0 | |
| `gross_output_value_usd` | NUMERIC(18,2) | >= 0 | |
| `net_output_value_usd` | NUMERIC(18,2) | | |
| `public_goods_value_usd` | NUMERIC(18,2) | >= 0 | |
| `capital_leverage_ratio` | NUMERIC(12,4) | >= 0 | `(gross_output + public_goods) / capital_deployed` |
| `irr_pct` | NUMERIC(10,4) | | added in 070 |
| `npv_usd` | NUMERIC(18,2) | | added in 070 |
| `discount_rate_pct` | NUMERIC(8,4) | DEFAULT 8.0 | added in 070 |
| `efficiency_summary` | TEXT | NOT NULL | internal narrative |
| `public_summary` | TEXT | | required for public views |
| `evidence_maturity` | INTEGER | DEFAULT 1 | FK → `evidence_maturity_level` |
| `status` | VARCHAR(50) | DEFAULT 'draft', CHECK | draft/submitted/verified/published/rejected |
| `metadata` | JSONB | DEFAULT '{}' | |
| `source_system` | VARCHAR(100) | | |
| `source_id` | VARCHAR(255) | | |
| `source_raw` | JSONB | | |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | |
| `created_by` | UUID | | |
| `updated_by` | UUID | | |

**Indexes:** `idx_capital_efficiency_location`, `idx_capital_efficiency_type`, `idx_capital_efficiency_status`, `idx_capital_efficiency_farm`

### `regenerative_efficiency_observation`

Practice-level cost savings, incremental output, implementation cost, and
payback signals.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID PK | auto-generated | |
| `location_id` | UUID FK → `location` | NOT NULL, RESTRICT | |
| `farm_id` | UUID FK → `farm` | SET NULL | |
| `practice_event_id` | UUID FK → `farm_practice_event` | SET NULL | |
| `observation_date` | DATE | NOT NULL | |
| `practice_type` | VARCHAR(100) | NOT NULL | e.g. `bioinput_production` |
| `baseline_cost_usd` | NUMERIC(18,2) | >= 0 | |
| `observed_cost_usd` | NUMERIC(18,2) | >= 0 | |
| `cost_savings_pct` | NUMERIC(8,4) | BETWEEN -100 AND 100 | `(baseline - observed) / baseline * 100` |
| `incremental_output_value_usd` | NUMERIC(18,2) | | |
| `implementation_cost_usd` | NUMERIC(18,2) | >= 0 | |
| `payback_months` | NUMERIC(10,2) | >= 0 | `implementation_cost / monthly_savings` |
| `efficiency_summary` | TEXT | NOT NULL | |
| `public_summary` | TEXT | | |
| `evidence_maturity` | INTEGER | DEFAULT 1 | |
| `status` | VARCHAR(50) | DEFAULT 'draft', CHECK | |
| `metadata` | JSONB | DEFAULT '{}' | |
| `source_system` | VARCHAR(100) | | |
| `source_id` | VARCHAR(255) | | |
| `source_raw` | JSONB | | |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | |
| `created_by` | UUID | | |
| `updated_by` | UUID | | |

**Indexes:** `idx_regen_efficiency_location`, `idx_regen_efficiency_practice`, `idx_regen_efficiency_status`, `idx_regen_efficiency_farm`, `idx_regen_efficiency_practice_event`

### `governance_throughput_observation`

DAO/community proposal creation, decision, execution, and latency
observations.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID PK | auto-generated | |
| `location_id` | UUID FK → `location` | SET NULL | nullable for network-wide |
| `dao_proposal_id` | UUID FK → `dao_proposal` | SET NULL | |
| `proposal_code` | VARCHAR(100) | NOT NULL | e.g. `P001` |
| `venue` | VARCHAR(100) | | e.g. `daohaus` |
| `proposal_type` | VARCHAR(100) | | e.g. `farm_funding` |
| `proposal_created_at` | TIMESTAMPTZ | NOT NULL | |
| `decision_at` | TIMESTAMPTZ | | |
| `executed_at` | TIMESTAMPTZ | | |
| `decision_latency_days` | NUMERIC(10,2) | | `decision_at - proposal_created_at` |
| `execution_latency_days` | NUMERIC(10,2) | | `executed_at - proposal_created_at` |
| `decision_result` | VARCHAR(50) | CHECK | approved/rejected/cancelled/deferred/executed/unknown |
| `governance_summary` | TEXT | NOT NULL | |
| `public_summary` | TEXT | | |
| `evidence_maturity` | INTEGER | DEFAULT 1 | |
| `status` | VARCHAR(50) | DEFAULT 'draft', CHECK | |
| `metadata` | JSONB | DEFAULT '{}' | |
| `source_system` | VARCHAR(100) | | |
| `source_id` | VARCHAR(255) | | |
| `source_raw` | JSONB | | |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | |
| `created_by` | UUID | | |
| `updated_by` | UUID | | |

**UNIQUE:** `(proposal_code, source_system, source_id)`
**Indexes:** `idx_governance_throughput_location`, `idx_governance_throughput_proposal`, `idx_governance_throughput_status`, `idx_governance_throughput_dao_proposal`

### `capital_provider_utility_scenario`

Public-safe sponsor, funder, DAO, buyer, or investor utility scenario with
explicit limitations.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID PK | auto-generated | |
| `location_id` | UUID FK → `location` | NOT NULL, RESTRICT | |
| `farm_id` | UUID FK → `farm` | SET NULL | |
| `capital_source_id` | UUID FK → `capital_source` | SET NULL | |
| `scenario_name` | VARCHAR(255) | NOT NULL | |
| `provider_type` | VARCHAR(100) | NOT NULL, CHECK | one of 7 provider types |
| `capital_amount_usd` | NUMERIC(18,2) | NOT NULL, >= 0 | |
| `expected_financial_return_usd` | NUMERIC(18,2) | >= 0 | |
| `expected_public_goods_value_usd` | NUMERIC(18,2) | >= 0 | |
| `expected_verification_outputs` | INTEGER | >= 0 | |
| `expected_payback_months` | NUMERIC(10,2) | >= 0 | |
| `utility_score` | NUMERIC(5,2) | BETWEEN 0 AND 10 | reviewer-normalized |
| `utility_summary` | TEXT | NOT NULL | |
| `public_summary` | TEXT | | |
| `limitations` | TEXT[] | DEFAULT '{}' | explicit public limitations |
| `evidence_maturity` | INTEGER | DEFAULT 1 | |
| `status` | VARCHAR(50) | DEFAULT 'draft', CHECK | |
| `metadata` | JSONB | DEFAULT '{}' | |
| `source_system` | VARCHAR(100) | | |
| `source_id` | VARCHAR(255) | | |
| `source_raw` | JSONB | | |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | |
| `created_by` | UUID | | |
| `updated_by` | UUID | | |

**Indexes:** `idx_capital_provider_location`, `idx_capital_provider_type`, `idx_capital_provider_status`, `idx_capital_provider_farm`, `idx_capital_provider_capital_source`

## Public views

All 4 views follow the same public-safety pattern: `status = 'published'`,
`evidence_maturity >= 3`, non-empty `public_summary`, and a verified/published
`farm_registry_record` for the location. The governance throughput view allows
`location_id IS NULL` for network-wide observations.

| View | Source table | Registry gate | Special |
|---|---|---|---|
| `v_public_capital_efficiency_summary` | `capital_efficiency_scenario` | required | joins `evidence_maturity_level` |
| `v_public_regenerative_efficiency_summary` | `regenerative_efficiency_observation` | required | joins `evidence_maturity_level` |
| `v_public_governance_throughput_summary` | `governance_throughput_observation` | required when location-scoped | allows `location_id IS NULL` |
| `v_public_capital_provider_utility_summary` | `capital_provider_utility_scenario` | required | joins `evidence_maturity_level`, exposes `limitations[]` |

**Filter conditions (all views):**
```sql
WHERE status = 'published'
  AND evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = <table>.location_id
        AND fr.status IN ('verified', 'published')
  )
```

## Governed metrics

Six metrics seeded in `037_capital_efficiency_and_utility.sql`:

| Metric key | Formula | Source tables | Owner | Validation |
|---|---|---|---|---|
| `capital_efficiency_usd_per_output` | `gross_output_value_usd / capital_deployed_usd` | `capital_efficiency_scenario` | Finance Guild | `capital_deployed_usd > 0`, `value >= 0` |
| `regenerative_cost_savings_pct` | `(baseline_cost_usd - observed_cost_usd) / baseline_cost_usd * 100` | `regenerative_efficiency_observation`, `farm_practice_event` | Finance Guild | `-100 <= value <= 100`, `baseline_cost_usd > 0` |
| `practice_payback_months` | `implementation_cost_usd / monthly_savings_or_incremental_value` | `regenerative_efficiency_observation` | Finance Guild | `value >= 0`, `assumptions documented` |
| `governance_decision_latency_days` | `decision_at - proposal_created_at` | `governance_throughput_observation`, `governance_event`, `dao_proposal` | Governance Guild | `value >= 0`, `proposal_code present` |
| `capital_leverage_ratio` | `(gross_output_value_usd + public_goods_value_usd) / capital_deployed_usd` | `capital_efficiency_scenario` | Finance Guild | `capital_deployed_usd > 0`, `value >= 0` |
| `capital_provider_utility_score` | Reviewer-normalized 0-10 scenario score | `capital_provider_utility_scenario` | Finance Guild | `0 <= value <= 10`, `limitations present` |

**Inclusion rules:** Use published scenarios with documented assumptions.
**Exclusion rules:** Exclude draft scenarios, guaranteed-return claims, and
private capital terms.

## Report generators

Three report types registered in `services/export/report_generator.py`:

### `capital_efficiency`

```bash
python3 -m services.export.report_generator --type capital_efficiency --location-id UUID
```

Queries `v_public_capital_efficiency_summary` and
`v_public_regenerative_efficiency_summary` with optional date range filters.
Returns:

```json
{
  "report_type": "capital_efficiency",
  "location_id": "UUID",
  "location_name": "Adelphi",
  "scenarios": [...],
  "regenerative_efficiency": [...],
  "limitations": [
    "Capital efficiency and payback values are scenario evidence, not guaranteed returns.",
    "Private capital terms and draft financial assumptions are excluded.",
    "Regenerative savings should be recalculated as additional verified expense, output, and practice records mature."
  ],
  "generated_at": "2026-07-21T..."
}
```

### `governance_throughput`

```bash
python3 -m services.export.report_generator --type governance_throughput --location-id UUID
```

Queries `v_public_governance_throughput_summary` with optional location and
date range filters. Computes `average_decision_latency_days`. Supports
network-wide queries (`--location-id` optional). Returns:

```json
{
  "report_type": "governance_throughput",
  "location_id": "UUID",
  "observations": [...],
  "average_decision_latency_days": 5.21,
  "limitations": [
    "Governance throughput reflects published proposal timestamps only.",
    "Off-platform discussion, informal consensus, and private negotiation time may be excluded.",
    "Fast decisions are not automatically better decisions; risk gates and stakeholder review still apply."
  ],
  "generated_at": "2026-07-21T..."
}
```

### `capital_provider_utility`

```bash
python3 -m services.export.report_generator --type capital_provider_utility --location-id UUID
```

Queries `v_public_capital_provider_utility_summary`, ordered by
`utility_score DESC`. Returns:

```json
{
  "report_type": "capital_provider_utility",
  "location_id": "UUID",
  "location_name": "Adelphi",
  "scenarios": [...],
  "limitations": [
    "Capital-provider utility scenarios are planning evidence, not an offer of securities or guaranteed returns.",
    "Private funder terms, side letters, and unpublished negotiations are excluded.",
    "Public-goods, verification, and learning outputs should be evaluated alongside financial risk."
  ],
  "generated_at": "2026-07-21T..."
}
```

The `capital_efficiency` report is also a section in the `comprehensive_status`
composite report.

## Agent synthesis

`services/agents/capital_efficiency_agent.py` (191 lines) queries all 4 public
views, computes aggregates, and optionally stores a draft `ai_summary` for
human review.

### What it does

1. Asserts read permission on `capital_efficiency_scenario` (via `safety.py`)
2. Queries `v_public_capital_efficiency_summary` (ordered by period_start DESC)
3. Queries `v_public_regenerative_efficiency_summary` (ordered by observation_date DESC)
4. Queries `v_public_governance_throughput_summary` (ordered by proposal_created_at DESC)
5. Queries `v_public_capital_provider_utility_summary` (ordered by utility_score DESC)
6. Computes `total_capital_deployed_usd` and `average_decision_latency_days`
7. Generates a text synthesis with counts and safety note
8. Optionally stores a draft `ai_summary` row (`summary_type='capital_efficiency'`)

### Safety boundaries

- **Read:** `assert_agent_action_allowed("read", "capital_efficiency_scenario", ...)` — enforces read-only for agents
- **Write:** `assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})` — agents can only draft, never publish
- **Output:** `validate_output("capital_efficiency_synthesis", output)` requires a `summary` field
- **Safety note:** "Public-safe scenario evidence only; private capital terms, securities-style return promises, and draft assumptions are excluded."

### CLI

```bash
python3 -m services.agents.capital_efficiency_agent [--location-id UUID] [--store]
```

- Without `--store`: returns JSON synthesis to stdout
- With `--store`: also writes a draft `ai_summary` row for human review

### Task catalogue

```python
"capital_efficiency_synthesis": {
    "description": "Summarize public-safe capital efficiency, regenerative payback, governance throughput, and capital-provider utility scenarios.",
    "risk": "medium",
    "writes": ["ai_summary:draft"],
    "high_risk": False,
}
```

## Dashboards

Three Metabase dashboard cards with daily 06:00 refresh, `public_safe` privacy,
and guild ownership.

| Dashboard | SQL source | Owner | Refresh |
|---|---|---|---|
| `32_capital_efficiency.json` | `32_capital_efficiency.sql` | finance_guild | `0 6 * * *` |
| `33_governance_throughput.json` | `33_governance_throughput.sql` | governance_guild | `0 6 * * *` |
| `34_capital_provider_utility.json` | `34_capital_provider_utility.sql` | finance_guild | `0 6 * * *` |

**Capital efficiency dashboard** joins `v_public_capital_efficiency_summary`
with `location` and LEFT JOINs `v_public_regenerative_efficiency_summary` to
show scenarios alongside practice-level savings.

**Governance throughput dashboard** selects from
`v_public_governance_throughput_summary` with `COALESCE(l.name, 'Network')`
for network-wide proposals.

**Capital provider utility dashboard** joins
`v_public_capital_provider_utility_summary` with `location`, ordered by
`utility_score DESC`.

## Governance & safety

- `capital_efficiency_scenario` is registered in `GOVERNED_COLLECTIONS`
  (`services/agents/safety.py`), meaning agents cannot set its status to
  `verified` or `published`.
- All public views enforce `evidence_maturity >= 3` (reviewed record or higher),
  `status = 'published'`, non-empty `public_summary`, and a verified/published
  `farm_registry_record` for the location.
- The governance throughput view allows `location_id IS NULL` for network-wide
  observations that are not tied to a specific farm.
- Capital-provider utility scenarios must include explicit `limitations[]`
  (e.g. "not an offer of securities or guaranteed return").
- Report generators include explicit limitation disclaimers in every output.
- IRR/NPV columns exist in the schema (migration 070) but are not yet wired
  up with computation code — they are schema-ready for future use.

## Testing

```bash
python3 -m tests.test_capital_efficiency
```

| Test | Coverage |
|---|---|
| `test_capital_efficiency_schema_defines_records_and_public_views` | All 4 tables, all 4 views, evidence_maturity >= 3, farm_registry_record, utility_score CHECK |
| `test_capital_efficiency_seed_and_dashboards_exist` | 6 metric keys in seed, 3 dashboard SQL + 3 JSON files exist, refresh_cron present |
| `test_pilot_seed_has_efficiency_governance_and_utility_examples` | Adelphi scenario, bioinput_production, governance observation, sponsor utility, securities disclaimer |
| `test_capital_efficiency_agent_task_catalogue_and_validation` | Task exists, writes ai_summary:draft, not high_risk, validation rejects empty output |
| `test_capital_efficiency_agent_summarizes_public_safe_records` | Mocked synthesis returns correct counts for all 4 record types, average latency, safety_note |
| `test_capital_efficiency_report_generators_registered` | All 3 report types in REPORT_GENERATORS |
| `test_capital_efficiency_report_generators_public_safe` | All 3 generators produce correct report_type, contain disclaimer strings |
