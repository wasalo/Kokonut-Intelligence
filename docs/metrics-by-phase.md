# Metrics by Development Phase

This document outlines which metrics are enabled by each development phase, how they are measured individually, and what answers they enable collectively.

## Overview

The Kokonut Intelligence Platform is built across 62 schema phases (001-062), each adding governed tables, analytics, and metrics. This document maps:

1. **What each phase added** — tables, views, analytics functions
2. **Which metrics each phase enabled** — governed metric definitions and computed outputs
3. **What questions each metric answers individually** — single-metric insights
4. **What questions metrics answer collectively** — cross-metric intelligence

The platform currently supports **17 governed metrics**, **50+ analytics functions**, **16 agents**, and **55 report types**.

## How to Read This Document

Each tier groups related phases and answers a collective question. Within each tier, individual phases are listed with their metrics. At the end of each tier, the collective question is answered by combining metrics across phases.

---

## Tier 1: Foundation (Phases 001-008)

**Collective Question: "What is the financial and operational baseline of this farm, and how does it compare to current performance?"**

### Phase 001 — Locations & Master Data

| What Was Added | Tables |
|----------------|--------|
| Location/farm registry with PostGIS geometry | `location`, `farm`, `plot` |
| Farm registry record with onboarding contract | `farm_registry_record` |
| Baseline fields for before/after comparison | `location.baseline_revenue/asset_value/cash_flow/cost` |

**Metrics Enabled:** `baseline_revenue`, `baseline_asset_value`, `baseline_cash_flow`, `baseline_cost`

**Individual Questions:**
- baseline_revenue: "What was the farm earning before Kokonut intervention?"
- baseline_asset_value: "What was the starting asset/productive value?"
- baseline_cash_flow: "What was the pre-intervention net cash flow?"
- baseline_cost: "What were the pre-intervention operating costs?"

### Phase 002 — Crops & Crop Cycles

| What Was Added | Tables |
|----------------|--------|
| Crop catalog with expected yields | `crop` |
| Crop cycles linking crops to plots | `crop_cycle` |

**Metrics Enabled:** `crop_revenue`, `loss_rate_pct`

**Individual Questions:**
- crop_revenue: "How much gross revenue did this crop generate?"
- loss_rate_pct: "What percentage of harvested output was lost before sale?"

### Phase 003 — Operations

| What Was Added | Tables |
|----------------|--------|
| Farm activities, harvest events, loss events, labor, field notes | `farm_activity`, `harvest_event`, `loss_event`, `labor_event`, `field_note` |

**Metrics Enabled:** `loss_rate_pct` (1 - net_harvest / gross_harvest)

### Phase 004 — Finance

| What Was Added | Tables |
|----------------|--------|
| Expense tracking, revenue events, cost allocation, NOI snapshots | `expense_event`, `revenue_event`, `crop_cost_allocation`, `noi_snapshot`, `cash_flow_snapshot`, `value_flow_event` |

**Metrics Enabled:** `direct_crop_cost`, `allocated_shared_cost`, `crop_noi`, `operating_margin_pct`, `value_flowed`

**Individual Questions:**
- crop_noi: "What is the net operating profit from this crop?"
- operating_margin_pct: "What is the profitability margin?"
- value_flowed: "How much verified value moved through Kokonut activity?"

### Phase 005 — Environmental

| What Was Added | Tables |
|----------------|--------|
| Soil sampling, carbon measurement, species observation, remote sensing | `soil_sample`, `soil_carbon_measurement`, `species_observation`, `remote_sensing_observation` |

**Metrics Enabled:** `soil_carbon_delta`, `biodiversity_delta`

**Individual Questions:**
- soil_carbon_delta: "Has soil carbon increased since intervention?"
- biodiversity_delta: "Has species richness increased?"

### Phase 006 — Web3 & Engagement

| What Was Added | Tables |
|----------------|--------|
| Wallet profiles, digital lego tracking, attestations | `wallet_profile`, `digital_lego_usage`, `attestation_record` |

**Metrics Enabled:** `wallet_retention`, `digital_lego_usage`

### Phase 007 — Modeled Outputs

| What Was Added | Tables |
|----------------|--------|
| Forecast scenarios, metric definitions, report snapshots | `forecast_scenario`, `forecast_output`, `metric_definition`, `metric_value`, `report_snapshot` |

**Metrics Enabled:** All 17 metrics stored in `metric_value`

### Phase 008 — Governance

| What Was Added | Tables |
|----------------|--------|
| Audit logging, schema migration, roles | `audit_log`, `schema_migration`, `role` |

### Tier 1 Collective Insight

> **"What is the financial and operational baseline?"**
>
> Combining baseline metrics with current financial metrics and environmental baselines: "This farm earned $12,000 baseline revenue, now earns $24,500 (2x improvement). Soil carbon increased from 24.5 to 27.9 t/ha (+14%). Species count increased from 8 to 14 (+75%). NOI is $9,200 with 82% operating margin."

---

## Tier 2: Governance & Infrastructure (Phases 009-024)

**Collective Question: "Can we trust the data, and how do external market conditions affect our revenue projections?"**

### Key Phases

| Phase | What Was Added | Key Capability |
|-------|---------------|----------------|
| 009 | Workflow history, approvals | Lifecycle enforcement |
| 010 | Commodity price observations | Market data for projections |
| 011 | IoT sensor types and readings | Real-time monitoring |
| 013 | MRV claims, impact claims | Evidence maturity gating |
| 016 | Revenue multiplier config | 10-dimension opportunity analysis |
| 018 | Public-safe aggregate views | Governed public exposure |
| 024 | Metric governance enforcement | Formula version tracking |

**Metrics Enabled:** `attestation_coverage`

**Individual Question:** attestation_coverage: "What percentage of eligible claims have been attested on-chain?"

### Tier 2 Collective Insight

> **"Can we trust the data?"**
>
> Workflow enforcement, metric versioning, evidence maturity gating, and public view governance collectively ensure: "All metrics are computed from verified data, versioned formulas, and exposed only through governed public views. Revenue projections account for market price volatility through the revenue multiplier's 10-dimension analysis."

---

## Tier 3: Frameworks & Impact (Phases 025-033)

**Collective Question: "Are we actually making a difference?"**

### Key Phases

| Phase | What Was Added | Key Capability |
|-------|---------------|----------------|
| 025 | Impact frameworks, SDGs, 8 Forms of Capital | Framework alignment |
| 026 | Plant analysis, disease observation | Ground analytics |
| 028 | Carbon framework, tree inventory, benchmarks | Carbon accounting |
| 029 | Evidence maturity levels (0-6) | Evidence gating |
| 031 | Impact claims, CIDS export | Blockchain verification |
| 032 | EBF scorecard with 5 pillars | Performance scoring |

### Tier 3 Collective Insight

> **"Are we actually making a difference?"**
>
> EBF scorecard shows 7.2/10 across 5 pillars. Impact claims document measurable outcomes with evidence maturity Level 4+. Carbon framework confirms 57.5 tCO2e sequestered. Biodiversity tracking confirms 37 species with Shannon index 1.12. CIDS export makes all claims blockchain-verifiable.

---

## Tier 4: Wellbeing & Governance (Phases 034-041)

**Collective Question: "Are people and communities thriving?"**

### Key Phases

| Phase | What Was Added | Key Capability |
|-------|---------------|----------------|
| 034 | Cultural context, well-being metrics | Holistic wellbeing |
| 035 | Financial sustainability, risk mitigation | Financial resilience |
| 036 | Capital efficiency, governance throughput | Capital utility |
| 037 | Time liberation, governance inclusion | Commons liberation |
| 038 | GNH alignment (9 domains), cultural preservation | Happiness metrics |
| 039 | Regenerative outcomes, community governance | Regeneration evidence |
| 041 | Anti-capture governance, redistribution | Commons governance |

### Tier 4 Collective Insight

> **"Are people and communities thriving?"**
>
> GNH alignment scores 78/100 across 9 domains. Regenerative outcomes show 154 trees planted (91.6% survival), 36 training hours, 12 beneficiaries. Financial sustainability projects 9.5 months runway. Commons governance implements anti-capture with quadratic voting and community veto.

---

## Tier 5: Operations & Specialization (Phases 043-055)

**Collective Question: "Can we scale regeneratively while maintaining organic integrity?"**

### Key Phases

| Phase | What Was Added | Key Capability |
|-------|---------------|----------------|
| 043 | Bio-organic fertilizer production | Local input production |
| 046-047 | Ecological modeling, pest management | Ecosystem intelligence |
| 048 | Training sessions, revenue streams | Human capacity + revenue diversity |
| 049 | Prediction accuracy, feature importance | Model validation |
| 050 | Livestock feed, token rewards | Animal husbandry + Web3 rewards |
| 053 | Farm templates, objectives | Configurable containers |
| 054 | Grant applications, network diversity | Funding intelligence |
| 055 | Organic certification readiness | Compliance intelligence |

### Tier 5 Collective Insight

> **"Can we scale regeneratively while maintaining organic integrity?"**
>
> Bio-factory produces 3 batches of organic inputs locally. Organic certification scores 72.5/100 readiness with 14/18 checklist items passing. Ecological modeling confirms trophic balance and pest management effectiveness. Training shows 64% average improvement. Grant network manages 2 applications with $25K awarded.

---

## Tier 6: Resilience & True Cost (Phases 056-062)

**Collective Question: "What is the full triple-bottom-line picture when we account for hidden costs?"**

### Key Phases

| Phase | What Was Added | Key Capability |
|-------|---------------|----------------|
| 056 | Emergency incident tracking | Crisis response |
| 057 | Individual tree records with GPS | Precision forestry |
| 058 | Farm zone geometry, GeoJSON/KML export | Spatial intelligence |
| 059 | MSAVI, spatial clustering, pest hotspots | Remote sensing intelligence |
| 060 | Worst/base/best case parameters | Scenario intelligence |
| 061 | Departments, job roles, tasks, phases | Organizational intelligence |
| 062 | Hidden costs, natural/social capital valuation, LCA, GRI, systems thinking | True cost intelligence |

### Tier 6 Collective Insight

> **"What is the full triple-bottom-line picture?"**
>
> True cost statement reveals: Market profit $9,200, but after accounting for $1,100 in hidden environmental/health/social costs and adding $4,733 in natural capital value (carbon + biodiversity + water + soil + pollination) and $7,700 in social capital value (training + governance + culture + health + community), the **true profit is $20,533** — a 123% improvement over market-only accounting.

---

## Cross-Phase Collective Insights

| Collective Question | Metrics/Analytics Combined |
|--------------------|---------------------------|
| "Is this farm regenerative?" | soil_carbon_delta + biodiversity_delta + regenerative_score + carbon_balance + trophic_balance |
| "Is this farm financially sustainable?" | crop_noi + operating_margin_pct + value_flowed + financial_sustainability + capital_efficiency |
| "Is this farm governance-justified?" | attestation_coverage + governance_throughput + governance_inclusion + anti_capture_governance |
| "Is this farm culturally respectful?" | holistic_wellbeing + gnh_alignment + cultural_preservation + stakeholder_feedback |
| "Is this farm scaling without extraction?" | adoption_barriers + perpetual_value_stress + open_source_impact + redistribution_policy |
| "Is this farm organic-ready?" | organic_readiness_score + input_compliance + buffer_adequacy + harvest_segregation |
| "Is this farm spatially intelligent?" | tree_density + canopy_cover + habitat_connectivity + spatial_clusters + pest_hotspots |
| "Is this farm crisis-resilient?" | emergency_response_time + financial_sustainability + capital_efficiency |
| "What is the true cost of production?" | market_costs + hidden_costs + natural_capital_value + social_capital_value = true_profit |
| "How does this farm compare to benchmarks?" | carbon_benchmark + ebf_scorecard + organic_readiness + living_wage_ratio |

---

## Metric Reference

### 17 Governed Metrics

| # | Metric Key | Phase | Formula |
|---|-----------|-------|---------|
| 1 | baseline_revenue | 001 | location.baseline_revenue |
| 2 | baseline_asset_value | 001 | location.baseline_asset_value |
| 3 | baseline_cash_flow | 001 | location.baseline_cash_flow |
| 4 | baseline_cost | 001 | location.baseline_cost |
| 5 | crop_revenue | 002 | SUM(sales_event.total_amount) WHERE verified |
| 6 | net_crop_revenue | 002 | crop_revenue - returns - discounts |
| 7 | direct_crop_cost | 004 | SUM(expense_event.amount) WHERE direct |
| 8 | allocated_shared_cost | 04 | SUM(crop_cost_allocation.allocated_amount) |
| 9 | crop_noi | 004 | net_crop_revenue - direct_crop_cost - allocated_shared_cost |
| 10 | loss_rate_pct | 003 | 1 - (net_harvest / gross_harvest) |
| 11 | operating_margin_pct | 004 | crop_noi / net_crop_revenue * 100 |
| 12 | value_flowed | 004 | SUM(value_flow_event.amount) WHERE verified |
| 13 | wallet_retention | 006 | COUNT(DISTINCT active wallets) |
| 14 | digital_lego_usage | 006 | COUNT(DISTINCT verified protocols) |
| 15 | soil_carbon_delta | 005 | after碳 - baseline碳 |
| 16 | biodiversity_delta | 005 | after_species - baseline_species |
| 17 | attestation_coverage | 013 | published / eligible * 100 |

### Platform Capabilities

| Category | Count | Description |
|----------|-------|-------------|
| Governed metrics | 17 | Computed and stored in metric_value |
| Analytics functions | 50+ | Python functions computing derived indicators |
| Agents | 16 | AI synthesis agents (draft-only, cannot publish) |
| Report types | 55 | Structured report snapshots with hash verification |
| Public views | 90+ | Governed views with consent/privacy controls |
| Schema tables | 100+ | Governed tables with lifecycle status |
| Seed files | 69 | Idempotent pilot data |
| Test files | 49 | Comprehensive test coverage |
| Dashboards | 53 | Metabase BI dashboards |
