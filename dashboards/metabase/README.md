# Metabase Dashboards

SQL queries and JSON import templates for Metabase BI dashboards. 98 dashboards covering farm operations, environmental trends, impact accountability, stakeholder governance, tactical intelligence, organic certification, business architecture, and more.

## Dashboard Index

### Farm Operations (00-06)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 00 | Location Overview | `sql/00_location_overview.sql` | Per-location KPIs: baselines vs actuals, crop cycles, revenue, losses, expenses |
| 01 | Farm Operations | `sql/01_farm_operations.sql` | Harvest volumes, activity counts, and operational summary |
| 02 | Crop NOI | `sql/02_crop_noi.sql` | Net Operating Income by crop with revenue, costs, and margins |
| 03 | Expense Tracker | `sql/03_expense_tracker.sql` | Expense analysis by category with direct vs shared cost breakdown |
| 04 | Harvest & Sales | `sql/04_harvest_sales.sql` | Monthly harvest volumes and sales revenue by crop |
| 05 | Loss Rate | `sql/05_loss_rate.sql` | Loss rate by crop and loss type with financial impact |
| 06 | Eagle View | `sql/06_eagle_view_overview.sql` – `sql/12_eagle_view_monthly_trend.sql` | Platform-wide overview: KPIs, financials, harvest, environment, attestations, sensors, monthly trends (7 SQL sub-queries) |

### Environmental Trends (13-19)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 13 | Environmental Trends | `sql/13_environmental_trends.sql` | Aggregated environmental indicators over time |
| 14 | Farm Operating Margin | `sql/14_farm_operating_margin.sql` | Operating margin analysis with revenue vs cost trends |
| 14 | NDVI Trend | `sql/14_ndvi_trend.sql` | Normalized Difference Vegetation Index time-series |
| 15 | Soil Carbon Trend | `sql/15_soil_carbon_trend.sql` | Soil organic carbon measurements over time |
| 16 | Biodiversity Trend | `sql/16_biodiversity_trend.sql` | Species richness and Shannon diversity index trends |
| 17 | Soil Health Trend | `sql/17_soil_health_trend.sql` | Soil health composite indicators |
| 18 | Rainfall Trend | `sql/18_rainfall_trend.sql` | Precipitation patterns and anomalies |
| 19 | Crop Diversity Trend | `sql/19_crop_diversity_trend.sql` | Crop diversity metrics over time |

### Impact Accountability (20-25)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 20 | Evidence Gap Dashboard | `sql/20_evidence_gap_dashboard.sql` | Impact claims by evidence maturity, public-claim readiness, carbon claim gaps |
| 21 | Stakeholder Feedback | `sql/21_stakeholder_feedback_dashboard.sql` | Feedback by group, consent, sentiment, review coverage, public-summary status |
| 22 | EBF Scorecard | `sql/22_ebf_scorecard.sql` | EBF pillars, rubric scores, trust graphs |
| 23 | EBF Evidence Gap | `sql/23_ebf_evidence_gap.sql` | EBF evidence gap detection and coverage |
| 23 | Evidence Gap EBF | `sql/23_evidence_gap_ebf.sql` | Evidence gaps mapped to EBF pillars |
| 24 | EBF Calibration History | `sql/24_ebf_calibration_history.sql` | EBF calibration changes over time |
| 24 | Portfolio EBF | `sql/24_portfolio_ebf.sql` | Portfolio-level EBF scores across locations |
| 25 | EBF Portfolio Messy Rollup | `sql/25_ebf_portfolio_messy_rollup.sql` | Aggregated portfolio EBF with uncertainty bands |

### Wellbeing & Governance (26-33)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 26 | Holistic Wellbeing | `sql/26_holistic_wellbeing.sql` | Holistic wellbeing metrics across dimensions |
| 27 | Participatory Governance | `sql/27_participatory_governance.sql` | Participatory governance inclusion and throughput |
| 28 | Financial Sustainability | `sql/28_financial_sustainability.sql` | Financial sustainability plan status and projections |
| 29 | Risk Mitigation | `sql/29_risk_mitigation.sql` | Risk register, mitigation status, and exposure |
| 30 | Scaling Roadmap | `sql/30_scaling_roadmap.sql` | Scaling milestones and readiness indicators |
| 31 | Green Paper Publication | `sql/31_green_paper_publication.sql` | Publication status and review coverage |
| 32 | Capital Efficiency | `sql/32_capital_efficiency.sql` | Capital efficiency scenarios, leverage ratios, regenerative cost savings |
| 33 | Governance Throughput | `sql/33_governance_throughput.sql` | Governance decision velocity and approval rates |

### Capital & Alignment (34-47)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 34 | Capital Provider Utility | `sql/34_capital_provider_utility.sql` | Capital provider value delivery and utility signals |
| 35 | Time Liberation | `sql/35_time_liberation.sql` | Time savings from automation and process improvements |
| 36 | Capital Alignment | `sql/36_capital_alignment.sql` | Capital allocation alignment with regenerative goals |
| 37 | Governance Inclusion | `sql/37_governance_inclusion.sql` | Governance participation diversity and inclusion metrics |
| 38 | Land Stewardship | `sql/38_land_stewardship.sql` | Land stewardship commitments and compliance |
| 39 | GNH Alignment | `sql/39_gnh_alignment.sql` | Gross National Happiness alignment scores |
| 40 | Cultural Preservation | `sql/40_cultural_preservation.sql` | Cultural heritage preservation indicators |
| 41 | Renewable Energy | `sql/41_renewable_energy.sql` | Renewable energy adoption and carbon intensity |
| 42 | Vulnerable Access | `sql/42_vulnerable_access.sql` | Access equity for vulnerable populations |
| 43 | Foundational Wellbeing | `sql/43_foundational_wellbeing.sql` | Basic needs and foundational wellbeing metrics |
| 44 | Regenerative Outcomes | `sql/44_regenerative_outcomes.sql` | Regenerative practice outcomes and impact |
| 45 | Community Governance | `sql/45_community_governance.sql` | Community governance mechanism health |
| 46 | Replication Readiness | `sql/46_replication_readiness.sql` | Readiness for replication to new locations |
| 47 | Adaptive Stewardship | `sql/47_adaptive_stewardship.sql` | Adaptive management response and learning |

### Scaling & Economics (48-56)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 48 | Scaling Economics | `sql/48_scaling_economics.sql` | Economic viability at scale with cost curves |
| 49 | Adoption Barriers | `sql/49_adoption_barriers.sql` | Barrier assessment and adoption readiness |
| 50 | Perpetual Value Stress | `sql/50_perpetual_value_stress.sql` | Value persistence under stress scenarios |
| 51 | Open Source Impact | `sql/51_open_source_impact.sql` | Open-source contribution and impact metrics |
| 52 | Anti-Capture Governance | `sql/52_anti_capture_governance.sql` | Anti-capture policy compliance and health |
| 53 | Redistribution Policy | `sql/53_redistribution_policy.sql` | Redistribution policy execution and equity |
| 54 | Federation Mutual Aid | `sql/54_federation_mutual_aid.sql` | Cross-node mutual aid and resource sharing |
| 55 | Algorithmic Redistribution | `sql/55_algorithmic_redistribution.sql` | Algorithmic redistribution outcomes |
| 56 | Participatory Signal | `sql/56_participatory_signal.sql` | Participatory signal experiments and binding |

### Bio-Factory & Ecology (57-66)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 57 | Bio-Factory Batches | `sql/57_bio_factory_batches.sql` | Bio-input production batches and quality |
| 58 | Input Provenance | `sql/58_input_provenance.sql` | Bio-input sourcing and provenance tracking |
| 59 | Recipe Library | `sql/59_recipe_library.sql` | Bio-recipe availability and usage |
| 60 | Quality Distribution | `sql/60_quality_distribution.sql` | Quality test results and distribution |
| 61 | Regional Inputs | `sql/61_regional_inputs.sql` | Regional input sourcing and availability |
| 62 | Ecological Interactions | `sql/62_ecological_interactions.sql` | Ecological interaction modeling and trophic analysis |
| 63 | Trophic Pyramid | `sql/63_trophic_pyramid.sql` | Trophic level biomass and energy flow |
| 64 | Pest Management | `sql/64_pest_management.sql` | Pest scouting, thresholds, interventions, resistance |
| 65 | Resource Efficiency | `sql/65_resource_efficiency.sql` | Resource use efficiency and optimization |
| 66 | Livestock Feed Intake | `sql/66_livestock_feed_intake.sql` | Livestock feed consumption and nutrition |

### Rewards & Token (67)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 67 | Token Reward Distribution | `sql/67_token_reward_distribution.sql` | Token reward allocation and distribution patterns |

### Stakeholder Intelligence (68-76)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 68 | Stakeholder Landscape | `sql/68_stakeholder_landscape.sql` | Party types, salience assessments, and relationship mapping across stakeholders |
| 69 | Stakeholder Ecosystem | `sql/69_stakeholder_ecosystem.sql` | Stakeholder relationships, risk indicators, and recommendation engine |
| 70 | Stakeholder Engagement | `sql/70_stakeholder_engagement.sql` | Engagement plans, objectives, touchpoints, and commitment health tracking |
| 71 | Stakeholder Grievance | `sql/71_stakeholder_grievance.sql` | Grievance cases, investigations, remedies, and resolution time tracking |
| 72 | Stakeholder Representation | `sql/72_stakeholder_representation.sql` | Participation rates, accessibility requests, and minority view tracking |
| 73 | Stakeholder Decision Lineage | `sql/73_stakeholder_decision_lineage.sql` | Decision tracking with participants, trade-offs, evidence, and outcomes |
| 74 | Stakeholder Trust | `sql/74_stakeholder_trust.sql` | Trust profiles, evidence, dispute performance, and risk indicators |
| 75 | Stakeholder Outcomes | `sql/75_stakeholder_outcomes.sql` | Verified stakeholder outcomes linked to capabilities and value streams |
| 76 | Stakeholder Cockpit | `sql/76_stakeholder_cockpit.sql` | Consolidated stakeholder view with salience, trust scores, and engagement counts |

### Tactical & Strategic (77-81)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 77 | Tactical Layer | `sql/77_tactical_layer.sql` | Consolidated view of fork, pin, promotion ladder, and tactical opportunities |
| 78 | Fork Opportunities | `sql/78_fork_opportunities.sql` | Cross-domain insight transfers that could create high-value targets |
| 79 | Pin Dependency | `sql/79_pin_dependency.sql` | Governed records blocked by unverified upstream data |
| 80 | Promotion Ladder | `sql/80_promotion_ladder.sql` | Data progression: sensor reading to verified metric to published credit |
| 81 | Strategic Reserve | `sql/81_strategic_reserve.sql` | Reserve health, adequacy thresholds, breach status, and drawdown headroom |

### Organic Certification (82-84)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 82 | Organic Certification Readiness | `sql/82_organic_certification_readiness.sql` | Readiness scores, compliance percentages, and transition phase tracking |
| 83 | Organic Transition Progress | `sql/83_organic_transition_progress.sql` | Transition milestones, timeline, substance-free days, and compliance trajectory |
| 84 | Organic Input Audit | `sql/84_organic_input_audit.sql` | Input compliance, prohibited substance tracking, and harvest segregation |

### Business Architecture (85-88)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 85 | Capability Dashboard | `sql/85_capability_dashboard.sql` | Capability maturity, process/service coverage, and gap analysis |
| 86 | Strategy Execution | `sql/86_strategy_execution.sql` | Objectives, initiatives, investment cases, and coherence tracking |
| 87 | Value Stream Formal | `sql/87_value_stream_formal.sql` | Stream definitions, stages, observations, and lead-time/yield metrics |
| 88 | Technology Roadmap | `sql/88_technology_roadmap.sql` | Technology areas, drivers, alternatives, requirements, and maturity assessment |

### Governance & Coordination (89-90)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 89 | Coordination Cockpit | `sql/89_coordination_cockpit.sql` | Alliances, participants, objectives, contributions, and benefits tracking |
| 90 | Governance Coordination Health | `sql/90_governance_coordination_health.sql` | Governance circles, roles, proposals, tensions, and link health |

### Environmental & Market (91-93)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 91 | PESTEL Assessment | `sql/91_pestel_assessment.sql` | Political, economic, social, technological, environmental, legal factor analysis |
| 92 | Regional Readiness | `sql/92_regional_readiness.sql` | Dimension scores, benchmarks, and readiness assessment across regions |
| 93 | Publics & Market Landscape | `sql/93_publics_market_landscape.sql` | Stakeholder publics, market segments, and influence/interest matrix |

### Additional Reports (94-100)

| # | Dashboard | SQL | Description |
|---|-----------|-----|-------------|
| 94 | Climate Impact | `sql/94_climate_impact.sql` | Carbon balance, GHG emissions, tree carbon, and regenerative scores |
| 95 | Comprehensive Status | `sql/95_comprehensive_status.sql` | Composite per-location view across all governed dimensions |
| 96 | State of Kokonut | `sql/96_state_of_kokonut.sql` | Ecosystem-level overview with funding rounds and project participation |
| 97 | DAO Proposal History | `sql/97_dao_proposal_history.sql` | Gnosis Moloch DAO governance events: proposals, votes, and processing |
| 98 | Reward Calibration | `sql/98_reward_calibration.sql` | Token reward distribution, overjustification risk, and intrinsic motivation signals |
| 99 | Training Impact | `sql/99_training_impact.sql` | Training programs, attendance, completion rates, and skill improvement |
| 100 | Data Stream Summary | `sql/100_data_stream_summary.sql` | Chronological project posts, file attachments, and blockchain anchoring status |

## SQL Sub-Queries

Some dashboards use multiple SQL files. The eagle view (06) spans 7 sub-queries:

| File | Purpose |
|------|---------|
| `sql/06_eagle_view_overview.sql` | High-level KPIs |
| `sql/07_eagle_view_financial.sql` | Financial summary |
| `sql/08_eagle_view_harvest.sql` | Harvest volumes |
| `sql/09_eagle_view_environmental.sql` | Environmental indicators |
| `sql/10_eagle_view_attestations.sql` | Attestation coverage |
| `sql/11_eagle_view_sensors.sql` | Sensor data summary |
| `sql/12_eagle_view_monthly_trend.sql` | Monthly trend lines |

## Usage

### Option 1: Manual SQL Queries
1. Open Metabase at `http://localhost:3001`
2. Go to "New" → "Native Query"
3. Select the "Kokonut Intelligence" database
4. Paste the SQL query from the `sql/` directory
5. Run the query and save it as a question
6. Create a new dashboard and add the saved questions

### Option 2: JSON Import (via API)
1. Use the Metabase API to import the JSON templates
2. Example:
   ```bash
   curl -X POST http://localhost:3001/api/dashboard \
     -H "Content-Type: application/json" \
     -H "X-Metabase-Session: YOUR_SESSION_ID" \
     -d @01_farm_operations.json
   ```

## Database Connection
- **Database**: Kokonut Intelligence (ID: 2)
- **Schema**: `public` (all tables in the `public` schema)
- **Tables**: Accessible without schema prefix

## Notes
- All queries use bare table names (e.g., `farm`, `harvest_event`) — no schema prefix
- Queries filter out rejected records by default
- NULL values are handled with COALESCE
- Dates are truncated to month level for trend analysis
- Public-safe views (`v_public_*`) are used where available for stakeholder-facing dashboards
- Dashboard JSON files are Metabase import templates, not report type definitions (reports are generated by `services/export/report_generator.py`)
