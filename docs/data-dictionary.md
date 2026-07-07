# Data Dictionary

## Governed Metric Definitions

| Metric Key | Display Name | Formula | Source Tables | Update Freq | Report Usage | Validation |
|-----------|-------------|---------|--------------|-------------|--------------|------------|
| `crop_revenue` | Crop Revenue | SUM(sales_event.total_amount) WHERE verified | sales_event, crop_cycle | Daily | Crop NOI Dashboard, Eagle View Financial, Annual Impact Report | value >= 0 |
| `net_crop_revenue` | Net Crop Revenue | crop_revenue - returns - discounts | sales_event, crop_cycle | Daily | Crop NOI Dashboard, Eagle View Financial | value >= 0 |
| `direct_crop_cost` | Direct Crop Cost | SUM(expense) WHERE direct allocation | expense_event, crop_cycle | Daily | Crop NOI Dashboard, Eagle View Financial | value >= 0 |
| `allocated_shared_cost` | Allocated Shared Cost | SUM(crop_cost_allocation.allocated) | crop_cost_allocation | Daily | Crop NOI Dashboard | value >= 0 |
| `crop_noi` | Crop NOI | net_revenue - direct_costs - allocated_costs | noi_snapshot, crop_cycle | Daily | Crop NOI Dashboard, Eagle View Financial, Fortune 500 | matches formula derivation |
| `loss_rate_pct` | Loss Rate % | 1 - (net_harvest / gross_harvest) | harvest_event | Daily | Loss Rate Dashboard, Eagle View Harvest | 0 <= value <= 100 |
| `operating_margin_pct` | Operating Margin % | crop_noi / net_revenue * 100 | noi_snapshot | Daily | Eagle View Financial, Crop NOI Dashboard | -100 <= value <= 100 |
| `baseline_revenue` | Baseline Revenue | location.baseline_revenue | location | Once | Fortune 500, Forecast Engine | value >= 0 |
| `baseline_asset_value` | Baseline Asset Value | location.baseline_asset_value | location | Once | Fortune 500 | value >= 0 |
| `baseline_cash_flow` | Baseline Cash Flow | location.baseline_cash_flow | location | Once | Fortune 500, Forecast Engine | value >= 0 |
| `baseline_cost` | Baseline Cost | location.baseline_cost | location | Once | Fortune 500, Forecast Engine | value >= 0 |
| `value_flowed` | Value Flowed | SUM(verified, non-excluded flows) | value_flow_event | Weekly | Value Flow Report, Revenue Multiplier | value >= 0 |
| `wallet_retention` | Wallet Retention | Active in current + prior period | wallet_activity_event | Monthly | Value Flow Report, Revenue Multiplier | 0 <= value <= 100 |
| `digital_lego_usage` | Digital Lego Usage | COUNT(distinct verified protocols) | digital_lego_usage | Weekly | Value Flow Report, Revenue Multiplier | value >= 0 |
| `soil_carbon_delta` | Soil Carbon Delta | after_carbon - baseline_carbon | soil_carbon_measurement | Quarterly | Eagle View Environmental, Environmental Trends | per-plot deltas |
| `biodiversity_delta` | Biodiversity Delta | after_count - baseline_count | species_observation | Quarterly | Eagle View Environmental, Crop Diversity Trend | includes Shannon index |
| `attestation_coverage` | Attestation Coverage | published / eligible * 100 | attestation_record | Monthly | Eagle View Attestations, MRV Dashboard | 0 <= value <= 100 |

All metrics include `validation_tests` (JSONB), `report_usage` (TEXT[]), and `deprecation_policy` (TEXT). See `schemas/seeds/022_metric_governance.sql` for full governance data.

## Core Entity Glossary

### Master Data

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `location` | Physical or ecosystem unit | name, slug, boundary, baseline_* |
| `farm` | Operational farm entity | location_id, farm_type, total_area |
| `plot` | Operational land subdivision | farm_id, area, soil_type, water_source |
| `crop` | Crop type and variety | name, variety, crop_category |
| `crop_cycle` | Crop-specific production cycle | plot_id, crop_id, planting_date, status |
| `partner` | Institution, buyer, funder, vendor | name, partner_type |
| `infrastructure_asset` | Physical infrastructure | location_id, asset_type, capacity |
| `staff` | Workers and team members | location_id, role |

### Operational Facts

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `farm_activity` | General field activity log | activity_type, activity_date, status |
| `harvest_event` | Quantity harvested | quantity, unit, quality_grade, loss_* |
| `sales_event` | Sales transaction | buyer, quantity, total_amount, payment_status |
| `expense_event` | Expense record | category, amount, allocation_method, status |
| `loss_event` | Loss/incident record | loss_type, quantity, estimated_value |
| `labor_event` | Labor hours and cost | hours_worked, hourly_rate, role |
| `field_note` | Qualitative observations | note_type, content, images |

### Impact Accountability

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `evidence_maturity_level` | 0-6 evidence maturity reference model | level, label, public_claim_allowed |
| `stakeholder_feedback` | Private-by-default stakeholder feedback | feedback_type, stakeholder_group, consent_given, is_public, evidence_maturity |
| `stakeholder_feedback_review` | Review and escalation trail for feedback | feedback_id, action, response_text, due_at |
| `stakeholder_outcome` | CIDS StakeholderOutcome-compatible outcome record | stakeholder_group, outcome_name, importance, framework links |
| `impact_claim` | Extended social/ecological/financial/governance claim lifecycle | claim_type, claim_category, public_claim, evidence_maturity |
| `metric_proposal` | Participatory metric proposal and review workflow | proposed_by_role, metric_name, status, discussion_notes |

### Financial Facts

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `financial_transaction` | Canonical cash/crypto transaction | transaction_type, amount, currency |
| `expense_category` | Governed expense taxonomy | name, code, is_direct |
| `crop_cost_allocation` | Shared cost allocation | allocation_method, allocated_amount |
| `value_flow_event` | Governed value-flow record | flow_type, amount, verified |
| `revenue_event` | Canonical revenue fact | revenue_type, amount_usd, payment_status, status |
| `noi_snapshot` | Crop/farm/location NOI output | noi, operating_margin_pct |
| `cash_flow_snapshot` | Periodic cash-flow reporting | net_cash_flow, running_balance |

### Environmental

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `soil_sample` | Soil test | ph, organic_matter_pct, nutrients |
| `soil_carbon_measurement` | Before/after carbon | carbon_tonnes_per_ha, is_baseline |
| `species_observation` | Biodiversity count | species_name, count, method |
| `remote_sensing_observation` | NDVI/NDRE | ndvi, ndre, canopy_cover_pct |
| `weather_observation` | Weather data | temperature_c, precipitation_mm |
| `sensor_type` | Sensor type definition | name, sensor_type, min_value, max_value |
| `sensor_device` | Registered sensor device | name, sensor_type_id, location_id, status |
| `sensor_reading` | Device reading | sensor_id, value, unit, quality |
| `alert_rule` | Threshold-based rule | sensor_type_id, operator, threshold, severity, cooldown_minutes |
| `sensor_alert` | Triggered alert | alert_rule_id, reading_id, severity, status |
| `mrv_claim` | Structured verification claim | claim_type, claim_data, status |
| `mrv_event` | Kokonut MRV event payload metadata | measurement_type, payload_cid, payload_hash, private_payload_hash |

### Web3 & Attestation

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `wallet_profile` | Wallet identity | address, chain, role |
| `wallet_activity_event` | Chain transaction | tx_hash, activity_type, value |
| `digital_lego_usage` | Protocol interaction | protocol_id, action_type, amount |
| `attestation_schema` | EAS schema definition | schema_uid, chain, schema_text |
| `attestation_record` | Verification attestation | attestation_uid, status, claim_data |
| `attestation_request` | EAS request metadata before signing/submission | subject_type, payload_cid, payload_hash, execution_status |
| `treasury_event` | Token flow | flow_direction, amount, token |
| `chain_indexer_status` | Ingestion health tracking | chain, indexer_type, last_synced_block |

#### EAS Celo Schemas

| Schema | UID | Chain | Use Case |
|--------|-----|-------|----------|
| `kokonut-mrv` | `0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54` | Celo | MRV claims (location, crop, quantity, evidence) |
| `kokonut-impact` | `0xb99bb4b2a55218b8f4df1f0bd4c39400711809f13ef5d150d2903648c6590dfe` | Celo | Environmental impact (soil carbon, biodiversity, NDVI) |
| `kokonut-financial` | `0x75b42beb85dd852134dfaff3de41b8dc361ed0cb2bf93ce3009c8ec082de905b` | Celo | Financial summaries (NOI, revenue, costs) |
| `kokonut-harvest` | `0xb359f9756e3cb3597e4048dccae2842083359906fbae8dc8c0e9af8ac1b3ccff` | Celo | Harvest verification (quantity, quality, date) |
| `kokonut-compliance` | `0x59632edcf1d04be0c2dcfd572282bbd4dac518e7a92872ec45ade29876ef95f5` | Celo | Partner compliance and audit trails |

#### EAS Celo Contracts

| Contract | Address | Chain |
|----------|---------|-------|
| EAS | `0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92` | Celo |
| SchemaRegistry | `0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34` | Celo |
| KokonutResolver | `0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad` | Celo |

### Registry, Inventory, Maintenance, And Agents

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `farm_registry_record` | Kokonut Common Data Schema onboarding record | registry_slug, project_date, forecasted_budget, founders, record_hash |
| `tenure_rights_assessment` | Tenure, rights, and community-effects onboarding assessment | tenure_type, nearby_area_survey, community_effects_forecast, risk_level |
| `inventory_event` | Inventory, input, and bioinput movement | item_name, item_type, event_type, quantity |
| `maintenance_event` | Asset inspection, repair, and upkeep | maintenance_type, work_performed, cost, next_service_date |
| `agent_identity` | Agent metadata and marketplace reference | agent_name, capability_manifest_cid, agent_state |
| `agent_capability_manifest` | Versioned agent capability manifest | version, manifest, manifest_cid, manifest_hash |
| `agent_task` | Agent task execution and review record | task_type, inputs, output_cid, execution_status, review_status |
| `agent_action_log` | Agent action audit trail | action, collection, record_id, action_result |

### Analytics & Configuration

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `metric_value` | Computed governed metric results | metric_id, location_id, value, period |
| `revenue_multiplier_config` | DB-backed dimension constants | config_key, config_value |
| `forecast_output` | Forecast engine outputs | metric_name, value, crop_cycle_id |
| `v_crop_forecast_summary` | Species/crop forecast summary view | total_annual_forecasted_revenue_usd, forecasted_harvest_count, forecasted_plot_count, crop_survival_rate_pct |
| `v_public_farm_places` | Public Data Hub places view | farm, plot, zone, logo_url, flora/fauna counts |
| `v_public_flora_fauna_summary` | Public flora/fauna observations by farm place | species_category, species_name, plot, observation totals |
| `v_public_project_carbon_credit_index` | Project-level carbon credit index view | forecasted, planned, realized, and total carbon credit value |

### Carbon & Regenerative Framework

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `ghg_emission_factor` | GHG emission factors (IPCC, regional) | factor_key, category, emission_factor, unit, region |
| `ghg_emissions_inventory` | Transport, machinery, input emissions | category, quantity, co2e_kg, co2e_tonnes |
| `tree_inventory` | Above-ground carbon (allometric model) | species_name, tree_count, biomass_estimate_kg, carbon_estimate_tonnes |
| `underplanting_event` | Companion species planting records | species_name, species_role, planting_date, survival_count |
| `carbon_benchmark` | Tree system carbon benchmarks | tree_system, total_carbon_tonnes_ha, sequestration_rate_tonnes_co2e_ha_year |
| `regenerative_practice_checklist` | Scored 5-principle assessment (0-5 each) | principle_key, score, evidence_path |
| `framework_phase` | Framework implementation phase tracking | framework_key, phase, phase_status, review_cadence |
| `climate_impact_summary` | Annual climate-impact summary | reporting_year, sequestration, emissions, net_climate_impact, regenerative_score |
| `operations_protocol` | Versioned handbook sections | protocol_key, section, content, version, review_cadence |
| `v_regenerative_score_summary` | Regenerative practice score summary view | total_score, score_pct, principles_assessed |
| `v_ghg_emissions_summary` | GHG emissions summary by category view | total_co2e_tonnes, category, reporting_period |
| `v_carbon_balance` | Carbon balance (sequestration vs emissions) view | net_climate_impact, carbon_position |
| `v_framework_phase_status` | Current framework phase per location view | framework_key, phase, phase_status |

### Ingestion & Observability

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `price_observation` | Commodity price data | commodity_code, price_date, price_per_unit, source |
| `ingestion_log` | External data fetch log | source_system, target_table, status, processing_time_ms |
| `workflow_history` | State transition audit | entity_type, entity_id, from_state, to_state, changed_by |
| `approval` | Approval records | entity_type, entity_id, decision, decided_by |
| `file_upload` | Uploaded files | filename, storage_path, mime_type |

### Modeled Outputs

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `forecast_scenario` | Scenario assumptions | scenario_type, assumptions |
| `forecast_output` | Forecast result | metric_name, value, confidence_* |
| `metric_definition` | Governed semantic metric | metric_key, formula, version |
| `report_snapshot` | Frozen report output | report_data, snapshot_hash |
| `ai_summary` | Agent-generated narrative | content, source_record_ids |
