# Data Dictionary

This dictionary is a domain-oriented index of the PostgreSQL schema. It documents
canonical tables, governed outputs, operational infrastructure, and public views.
It is intentionally organized by capability rather than migration number. For
complete column definitions and constraints, use the ordered files under
`schemas/postgres/`; migrations remain the schema source of truth.

Lifecycle fields generally use `draft`, `submitted`, `verified`, and `published`.
`rejected` is reserved for rework or exception paths. Payment, attestation,
review, and domain states use separate fields unless a table explicitly defines
another state machine.

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

### Ecological Modeling (v2)

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `soil_input_application` | Organic input tracking (biochar, litter, compost) | input_type, quantity_kg, residual_pct, decomposition_status |
| `pest_observation` | Monthly pest incidence tracking | pest_species, incidence_count, severity, outbreak_probability_pct, predator_count |
| `biocontrol_release` | Predator/biocontrol introductions | predator_species, release_count, effectiveness_pct, pest_reduction_pct |
| `resource_consumption` | Metered resource use (energy, water, labor) | resource_type, quantity, unit, period_start, period_end |
| `leaf_litter_measurement` | Daily litter trap collection data | litter_trap_id, fresh_weight_g, dry_weight_g, litter_rate_kg_per_day |
| `livestock_group` | Animal group registry | species, breed, animal_count, feed_type, enclosure_type |
| `feed_intake_record` | Daily feed consumption per livestock group | feed_type, quantity_kg, per_animal_kg, record_date |
| `decomposition_measurement` | Litter bag mass loss studies | initial_dry_weight_g, final_dry_weight_g, decomposition_rate_kg_per_day (auto-computed) |
| `ecological_interaction` | Species-species relationships | interaction_type, interaction_strength, species_a_trophic, species_b_trophic |
| `ecological_model_run` | Simulation model I/O | model_type, input_parameters (JSONB), output_predictions (JSONB) |
| `energy_flow_measurement` | Biomass transfer between trophic levels | from_trophic_level, to_trophic_level, biomass_transferred_kg, conversion_efficiency_pct |
| `population_dynamics_record` | Species population tracking | population_count, population_density_per_m2, growth_rate_estimate |

### Economic & Social Enhancement

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `training_session` | Individual training participation | participant_name, pre_score, post_score, improvement_pct, session_type |
| `revenue_stream_contribution` | Revenue stream breakdown | stream_name, gross_revenue, net_contribution, contribution_pct |

### Model Validation

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `prediction_accuracy_record` | Predicted vs actual comparisons | predicted_value, actual_value, absolute_error, mae, mape, r_squared |
| `feature_importance_record` | Sensitivity analysis results | feature_name, importance_score, direction, correlation_coefficient, p_value |

### Token Rewards & Calibration

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `token_reward_distribution` | On-chain and off-chain reward tracking | reward_type, token_amount, recipient_address, is_onchain, linked_metric_key |
| `reward_calibration_model` | Maps outputs to token emission rates | calibration_score, token_per_unit_output, input_metrics (JSONB), output_weights (JSONB) |

### Configurable Container Architecture

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `farm_template` | Reusable configuration bundle (Docker image) | template_type, default_zones (JSONB), default_governance_mechanism, default_impact_frameworks |
| `farm_specification` | Declarative farm config (docker-compose.yml) | zones (JSONB), governance (JSONB), token_economics (JSONB), impact_config (JSONB), template_id |
| `needs_assessment` | Structured community needs tracking | need_category, severity, urgency, mitigation_status, affected_stakeholder_groups |
| `stakeholder_aspiration` | Formal wants and aspirations | aspiration_category, priority, desired_outcome, success_criteria, timeline_months |
| `objective` | Hierarchical goal tracking | parent_id, target_value, current_value, progress_pct (auto-computed), target_date |

### Extensions to Existing Tables

| Table | New Column | Purpose | Added In |
|-------|-----------|---------|----------|
| `species_observation` | `trophic_level` | Trophic classification (producer/primary_consumer/secondary_consumer/decomposer/omnivore) | 046 |
| `species_observation` | `population_density_per_m2` | Population density for insects and soil organisms | 046 |
| `species_observation` | `conservation_status` | IUCN conservation status (critically_endangered through least_concern) | 047 |
| `farm_zone` | `strata_layer` | Syntropic vertical layer (emergent/canopy/sub_canopy/shrub/herbaceous/ground_cover/root/decomposer) | 046 |
| `pest_observation` | `predation_count` | Predation events observed per observation | 050 |
| `pest_observation` | `predation_rate_per_day` | Daily predation rate | 050 |
| `resource_consumption` | `irrigation_mm_used` | Actual irrigation applied in mm | 051 |
| `resource_consumption` | `rainfall_mm_during_period` | Rainfall during the consumption period | 051 |

### Grant Management & Network Diversity

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `grant_application_history` | Grant application tracking with cycle and renewal support | grant_name, grantor, application_status, grant_cycle_number, is_returning_applicant, amount_requested, amount_awarded, ecological_metrics_submitted |
| `regional_chapter` | Regional network/chapter registry | chapter_name, geographic_region, country, chapter_type, founding_date |
| `network_membership` | Farm-to-chapter membership links | location_id, chapter_id, membership_type, role, join_date |
| `farm_registry_record` (extended) | Grant tracking fields added | returning_applicant, grant_count, total_grants_received |

### Organic Certification & Compliance

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `organic_certification_record` | Certification lifecycle (USDA NOP, EU 2018/848, IFOAM) | standard, certification_type, certification_body, application_date, inspection_date, certification_date, expiration_date, certificate_number, status, scope, annual_fee_usd |
| `organic_transition_plan` | 2-3 year transition tracking with readiness scoring | standard, transition_start_date, expected_certification_date, current_year, total_years_required, status, readiness_score, barriers |
| `prohibited_substance_record` | Prohibited substance usage & withdrawal tracking | substance_name, substance_category, cas_number, date_used, remediation_action, withdrawal_period_days, withdrawal_end_date, compliance_status |
| `buffer_zone` | Physical separation zones (PostGIS geometry) | buffer_type, width_m, length_m, area_m2, adjacent_use, boundary_geometry, condition_status |
| `organic_input_audit` | Full input audit trail with organic/prohibited flags | input_category, input_name, input_source, organic_certified, supplier_name, is_prohibited, pre_harvest_interval_days, reentry_interval_hours |
| `harvest_handling_record` | Post-harvest organic compliance | harvest_event_id, handling_type, organic_segregated, equipment_cleaned, contamination_risk, organic_lot_number |
| `organic_compliance_checklist` | Inspector audit trail per standard requirement | certification_record_id, inspection_type, checklist_items (JSONB), non_conformances, corrective_actions_required, overall_result |
| `organic_readiness_assessment` | Composite 0-100 readiness scoring across 8 dimensions | overall_score, transition_progress_pct, soil_health_score, input_compliance_pct, pest_management_score, biodiversity_score, buffer_zone_score, record_completeness_pct, training_completion_pct, harvest_segregation_score |

### Emergency Response

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `emergency_incident` | Tracks emergency incidents with response, recovery, and lessons learned | incident_type (drought/flood/pest_outbreak/extreme_heat/frost/fire/disease_epidemic/soil_degradation/water_crisis), severity (low/medium/high/critical), detection_date, detection_method, response_actions (JSONB), recovery_date, financial_impact_usd, lessons_learned, status (detected/responding/recovering/resolved/escalated) |

### Individual Tree Tracking

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `tree_record` | Individual tree records with GPS coordinates for spatial mapping and Silvi integration | species_name, tree_tag, latitude, longitude, point_geometry (PostGIS), planting_date, height_m, dbh_cm, canopy_diameter_m, health_score, maturity_stage (seedling/juvenile/mature/mature-elder), status (alive/dead/removal/surviving) |
| `tree_measurement` | Time-series measurements for growth rate tracking | tree_record_id, measurement_date, height_m, dbh_cm, canopy_diameter_m, health_score |

### Spatial Export

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `farm_zone` (extended) | Geometry column added for spatial mapping | geometry (GEOMETRY(POLYGON, 4326)) |
| `v_spatial_zone_geojson` | Zones with GeoJSON text for export | zone_key, zone_type, geometry_geojson |
| `v_spatial_tree_geojson` | Trees with GeoJSON text for export | tree_tag, species_name, geometry_geojson |
| `v_spatial_location_geojson` | Location boundary with GeoJSON text | boundary_geojson, center_geojson |
| `v_spatial_project_summary` | Comprehensive project summary | tree_count, species_count, zone_count, zone_types |

### Drone & Raster Integration

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `remote_sensing_observation` (extended) | MSAVI column added | msavi (Modified Soil-Adjusted Vegetation Index) |
| `raster_metadata` | Metadata for GeoTIFF/orthomosaic files | raster_name, raster_type, file_url, file_format, resolution_m, bbox, capture_date, sensor, processing_pipeline |
| `spatial_cluster` | DBSCAN clustering results | cluster_method, cluster_type, tree_count, centroid_geometry, hull_geometry, compactness, eps_m, min_samples |
| `pest_hotspot` | Spatial pest/disease hotspot clusters | pest_or_disease, tree_count_affected, avg_severity, centroid_geometry, radius_m, confidence_score, recommended_action |
| `v_public_spatial_clusters` | Active clusters with GeoJSON geometry | cluster_name, tree_count, avg_health_score, dominant_species |
| `v_public_pest_hotspots` | Active pest hotspots with GeoJSON | pest_or_disease, tree_count_affected, confidence_score, recommended_action |
| `v_public_canopy_analysis` | Canopy coverage per zone | alive_trees, avg_canopy_diameter_m, estimated_canopy_cover_pct |

### True Cost Accounting & Triple Bottom Line

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `hidden_cost_observation` | Tracks hidden costs (externalities) with monetary estimates | cost_category (pollution/health/social/environmental/knowledge/intergenerational), cost_subcategory, monetary_estimate_usd, valuation_method, uncertainty_level |
| `natural_capital_valuation` | Unified monetary valuation of natural capital services | capital_type (carbon/biodiversity/water/soil/pollination/watershed/air_quality), quantity, price_per_unit_usd, total_value_usd (auto-computed) |
| `social_impact_valuation` | Monetary valuation of social capital improvements | impact_category (training/governance/cultural_preservation/health/community/gender_equity/education), beneficiaries_count, monetary_value_usd |
| `worker_safety_observation` | Workplace health and safety incidents | incident_type, severity, days_lost, medical_cost_usd |
| `living_wage_benchmark` | Living wage comparison standards | country, living_wage_hourly_usd, minimum_wage_hourly_usd |
| `lca_assessment` | Cradle-to-grave lifecycle tracking | lifecycle_stage, carbon_footprint_kg_co2e, water_footprint_liters, energy_footprint_kwh, waste_generated_kg |
| `gri_indicator` | Maps platform metrics to GRI standards | gri_code, gri_standard, platform_metric_key, platform_table |
| `materiality_assessment` | Stakeholder priority mapping | stakeholder_group, material_topic, importance_to_stakeholder, importance_to_business, priority_level (auto-computed) |
| `capital_flow_observation` | Cross-capital transfers | from_capital, to_capital, flow_value_usd, flow_type |
| `v_true_cost_statement` | Market costs + hidden costs + capital values | market_costs_usd, hidden_costs_usd, natural_capital_value_usd, social_capital_value_usd, true_profit_usd |

### Statement of Work

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `statement_of_work` | SOW document metadata | sow_name, sow_version, effective_date, client_name, contractor_name, total_contract_value, payment_terms, status |
| `sow_deliverable` | Deliverables with acceptance criteria | deliverable_name, acceptance_criteria, due_date, delivered_at, status (pending/delivered/accepted/rejected) |
| `sow_payment_schedule` | Payment milestones | milestone_name, amount, due_date, payment_status, invoice_number, paid_at |
| `sow_change_request` | Scope changes with impact assessment | change_name, impact_on_timeline, impact_on_budget, status (proposed/approved/rejected/implemented) |

### Impact Network

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `organization` | Multi-org grouping | org_key, name, org_type (cooperative/nonprofit/dao/enterprise/collective), governance_model |
| `organization_member` | Links organizations to locations/farms | membership_type (owned/affiliated/sponsored/partner), role (primary/satellite/partner/incubated) |
| `organization_wallet` | Links organizations to wallets | wallet_purpose (treasury/operations/rewards/donor_escrow) |
| `donor` | Donor identity | donor_type, wallet_address, is_anonymous |
| `funding_campaign` | Crowdfunding campaigns | campaign_type, goal_amount, raised_amount, status |
| `donation` | Individual contributions | amount, payment_method, is_recurring, linked_attestation_uid |
| `impact_payout_rule` | Automatic payout rules | payout_type, trigger_condition, payout_amount, attestation_required |
| `impact_payout_execution` | Executed payouts | metric_value, payout_amount, tx_hash, status |
| `impact_bounty` | Data collection incentives | bounty_type, reward_amount, data_requirement, max_submissions |
| `impact_bounty_submission` | Bounty claims | submission_data, evidence_cids, quality_score, reward_paid |
| `impact_office_run` | Orchestration runs | run_type, status, started_at, completed_at |
| `impact_office_step` | Orchestration steps | step_type, step_order, depends_on, step_status |
| `impact_office_alert` | Orchestration alerts | alert_type, severity, message, resolution_status |

## Impact Frameworks And Scorecards

### EBF Scorecard

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `ebf_pillar` | Evidence-Based Framework pillar definitions | pillar_key, pillar_name, framework_id |
| `ebf_rubric_band` | Score bands for each pillar | pillar_id, score_value, band_label |
| `ebf_scorecard` | Location scorecard for a reporting period | location_id, period, overall_score, status |
| `ebf_score` | Per-pillar score within a scorecard | scorecard_id, pillar_id, score_value |
| `ebf_score_evidence` | Evidence linked to an EBF score | score_id, evidence_type, evidence_url |
| `ebf_calibration_session` | Rubric calibration session | session_name, rubric_version, calibration_method |
| `ebf_calibration_decision` | Calibration decision and adjusted score | session_id, pillar_id, adjusted_score |
| `ebf_farm_metric_profile` | Location-to-pillar metric mapping | location_id, pillar_id, metric_id |
| `ebf_improvement_recommendation` | Evidence-based improvement recommendation | scorecard_id, pillar_id, recommendation |
| `ebf_trust_graph_node` | EBF trust graph node | node_type, entity_id, trust_score |
| `ebf_trust_graph_edge` | EBF trust graph relationship | source_node, target_node, weight |
| `graph_node` | Generic graph projection node | node_type, entity_id, label |
| `graph_edge` | Generic graph projection edge | source_node_id, target_node_id, edge_type |

### CRISP Risk Scoring

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `crisp_risk_dimension` | Risk dimension configuration | dimension_key, default_weight, data_sources |
| `crisp_location_weight` | Per-location dimension weight override | location_id, dimension_id, weight |
| `crisp_risk_assessment` | Periodic composite risk assessment | location_id, period_start, period_end, composite_score, rating |
| `crisp_carbon_yield_risk` | Carbon-yield scenario detail | assessment_id, scenario_minimum, scenario_realistic, risk_score |
| `crisp_climate_risk` | Climate hazard detail | assessment_id, drought_risk_score, natural_risk_rating, ssp_scenario |
| `crisp_policy_risk` | Policy and legal sub-factor detail | assessment_id, carbon_rights_score, land_tenure_score, risk_score |
| `crisp_financial_risk` | Financial risk-factor detail | assessment_id, revenue_risk_factor, liquidity_risk, risk_score |
| `crisp_implementation_risk` | Implementation sub-factor detail | assessment_id, team_strength_score, transparency_score, risk_score |
| `v_crisp_composite_rating` | Published CRISP rating view | location_id, composite_score, rating, confidence_level |
| `v_crisp_latest_assessment` | Latest assessment per location | location_id, period_end, rating, status |

### Wellbeing, GNH, And Commons

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `cultural_context_record` | Cultural context observation | context_type, description, location_id |
| `participatory_action_record` | Participatory action and outcome | action_type, participants, outcome |
| `wellbeing_metric_observation` | Wellbeing dimension observation | dimension, score, observation_date |
| `gnh_alignment_assessment` | Gross National Happiness alignment score | dimension, score, assessment_date |
| `cultural_preservation_plan` | Cultural preservation plan | plan_name, heritage_type, status |
| `renewable_energy_plan` | Renewable energy target plan | energy_type, capacity_kw, target_date |
| `vulnerable_group_access_plan` | Access plan for vulnerable groups | group_type, access_type, status |
| `foundational_wellbeing_observation` | Foundational wellbeing observation | dimension, score, observation_date |
| `energy_source` | Energy source registry | source_type, capacity, location_id |
| `renewable_energy_source` | Renewable energy source registry | renewable_type, capacity_kw, status |
| `time_liberation_observation` | Time reclaimed or burden reduced | baseline_hours, hours_reclaimed, burden_reduction_pct |
| `capital_alignment_assessment` | Capital-provider alignment assessment | provider_name, alignment_status, extractive_risk_level |
| `governance_inclusion_observation` | Inclusion and participation observation | inclusion_type, participation_rate |
| `land_stewardship_commitment` | Land stewardship commitment | commitment_type, duration_years, conditions |
| `anti_capture_governance_policy` | Anti-capture governance policy | policy_type, description, enforcement |
| `commons_redistribution_policy` | Commons redistribution policy | redistribution_type, allocation_pct |
| `algorithmic_redistribution_mechanism` | Rule-based redistribution mechanism | mechanism_name, formula, trigger |
| `federation_protocol` | Federation protocol definition | protocol_name, chain, contract_address |
| `participatory_signal_experiment` | Advisory participatory signal experiment | experiment_name, status, results |

### Regenerative Outcomes And Scaling

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `regenerative_outcome_summary` | Periodic regenerative outcome summary | period, outcome_type, score |
| `community_governance_mechanism` | Community governance mechanism | mechanism_type, description, effectiveness |
| `replication_readiness_assessment` | Replication readiness assessment | location_id, readiness_score, factors |
| `adaptive_stewardship_review` | Stewardship review and adaptation record | review_type, findings, actions |
| `adoption_barrier_assessment` | Adoption barrier assessment | barrier_type, severity, mitigation |
| `farm_launch_unit_economics` | Farm launch unit economics | revenue_per_unit, cost_per_unit, margin |
| `network_scaling_target` | Network scaling target | target_type, target_value, deadline |
| `open_source_impact_artifact` | Open-source impact artifact | artifact_type, license, download_count |
| `perpetual_value_stress_test` | Perpetual-value stress-test scenario | scenario_name, impact_score, recovery_time |
| `capital_efficiency_scenario` | Capital efficiency scenario | scenario_name, efficiency_score |
| `capital_provider_utility_scenario` | Capital-provider utility scenario | provider_id, utility_score |
| `governance_throughput_observation` | Governance throughput observation | decision_count, avg_time_hours |
| `regenerative_efficiency_observation` | Regenerative efficiency observation | resource_type, efficiency_pct |

## Risk, Orientation, And Feedback

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `situation_assessment` | Unified location situation assessment | location_id, situation_grade, crisp_rating, crisp_composite_score |
| `situation_signal` | Signal contributing to an assessment | assessment_id, signal_type, signal_key, signal_value |
| `decision_policy` | Decision rule and approval requirement | policy_name, requires_approval, timeout_hours |
| `decision_log` | Decision execution record | policy_id, entity_type, decision, decided_by |
| `decision_outcome` | Measured decision outcome | decision_id, outcome_type, measured_at |
| `ooda_cycle_log` | Observe-Orient-Decide-Act timing record | location_id, correlation_id, cycle_time_ms |
| `action_outcome` | Outcome of an action | action_type, outcome_type, measured_delta |
| `feedback_loop` | Feedback adjustment record | loop_type, previous_value, new_value, status |
| `adaptive_threshold` | Adaptive threshold configuration | threshold_key, current_value, baseline_value, adaptation_rate |
| `sampling_config` | Sensor sampling configuration | sensor_id, interval_seconds, metric |
| `sampling_adjustment_log` | Sampling interval adjustment history | config_id, old_interval, new_interval, reason |

## Systems Thinking And Trend Analysis

### Systems Thinking

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `causal_loop` | Reinforcing or balancing causal loop | loop_name, loop_type, strength |
| `causal_link` | Directed causal relationship | source_var, target_var, polarity |
| `system_variable` | Variable in a systems model | variable_name, current_value, unit |
| `stock_flow_model` | Stock-flow model definition | model_name, parameters, equations |
| `stock_flow_run` | Stock-flow simulation run | model_id, duration_days, results |
| `system_archetype` | Detected systems archetype | archetype_type, location_id, confidence |
| `leverage_assessment` | Leverage-point assessment | location_id, leverage_point, potential_score |
| `time_delay` | Action-to-effect delay | action, effect, delay_days |
| `mental_model` | Stakeholder mental-model elicitation | stakeholder_id, dimension, position |
| `structural_assumption` | Structural assumption under review | assumption_text, challenge_count |
| `structural_question` | Double-loop learning question | question_text, status, depth |
| `assumption_challenge` | Assumption challenge and resolution | assumption_text, challenge_text, outcome |
| `paradigm_shift` | Detected paradigm shift | shift_type, evidence, confidence |

### Trend Analysis

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `trend_estimate` | Least-squares trend estimate | metric_key, slope, intercept, r_squared |
| `trend_smoothing` | Smoothed time-series output | metric_key, method, smoothed_values |
| `seasonal_decomposition` | Trend, seasonal, and residual components | metric_key, trend, seasonal, residual |
| `change_point` | Detected time-series change point | metric_key, change_date, magnitude |
| `time_series_forecast` | Time-series forecast | metric_key, horizon, predicted_values |
| `forecast_accuracy` | Forecast accuracy record | forecast_id, mae, mape, r_squared |
| `trend_dashboard_metric` | Dashboard trend status | location_id, metric_key, trend_status |
| `trend_monitor_config` | Trend monitoring threshold | metric_key, alert_threshold |

## Credit Lifecycle And Marketplace

### Credit Classes, Batches, And Retirement

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `carbon_credit` | Governed legacy carbon-credit identity | credit_code, vintage_year, issuable_tonnes, retired_tonnes, status |
| `credit_adjustment` | Carbon-credit quantity adjustment | adjustment_type, delta_tonnes, trigger_source, requires_review |
| `credit_retirement` | Human-reviewed retirement request | credit_id, retired_tonnes, idempotency_key, status |
| `credit_transfer` | Governed credit transfer record | transfer_type, transferred_tonnes, from_wallet, to_wallet |
| `credit_type` | Ecocredit unit type | name, abbreviation, unit |
| `credit_class` | Methodology and eligibility definition | name, methodology, credit_type, status |
| `credit_class_cobenefit` | Credit class co-benefit | credit_class_id, impact_name, sdg_numbers |
| `credit_class_registry` | Registry linkage | credit_class_id, registry_name, registry_url |
| `crediting_program` | Crediting program | credit_class_id, name, version |
| `credit_protocol` | Credit protocol | credit_class_id, name, version, is_primary |
| `credit_class_methodology` | Approved methodology reference | credit_class_id, name, version, is_approved |
| `buffer_pool_account` | Buffer-pool account | credit_class_id, name, wallet_address |
| `credit_batch` | Batch issuance event | credit_class_id, location_id, batch_code, vintage_year, status |
| `credit_class_issuer` | Authorized class issuer | credit_class_id, issuer_address, revoked_at |
| `credit_class_creator_allowlist` | Class creator allowlist | address, entity_name, is_active |
| `credit_batch_contract` | Batch-to-chain contract link | credit_batch_id, contract_address, chain |
| `project_credit_class_enrollment` | Project enrollment in a credit class | location_id, credit_class_id, status |
| `credit_balance` | Per-account batch custody ledger | credit_batch_id, account_address, tradable_amount, retired_amount, escrowed_amount |
| `ecocredit_params` | Ecocredit module parameters | param_key, param_value, description |

### Baskets, Marketplace, And Bridge

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `credit_basket` | Fungible basket definition | name, token_denom, credit_type_id, status |
| `credit_basket_deposit` | Batch deposited into a basket | basket_id, credit_batch_id, quantity, token_amount |
| `credit_basket_token` | Basket-token holder balance | basket_id, holder_address, token_amount |
| `credit_sell_order` | Marketplace sell order and escrow | credit_batch_id, seller_address, quantity, ask_price, status |
| `credit_buy_order` | Marketplace buy order | sell_order_id, buyer_address, quantity, total_price, status |
| `credit_allowed_denom` | Allowed marketplace payment denomination | denom, chain, contract_address, is_active |
| `marketplace_fee` | Marketplace fee record | transaction_type, transaction_id, buyer_fee, seller_fee, status |
| `marketplace_fee_distribution` | Marketplace fee distribution | fee_id, recipient_address, amount, denom |
| `credit_bridge_transaction` | Cross-chain credit movement | direction, source_chain, target_chain, quantity, status |
| `origin_tx_index` | Origin transaction deduplication index | credit_class_id, origin_tx_id, origin_tx_source |
| `retirement_certificate` | Integrity-checked retirement certificate | certificate_number, retirement_id, certificate_hash |

## Data, Linked Data, And Public Views

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `data_stream_post` | Governed data-stream post | location_id, post_type, status, content |
| `data_stream_post_comment` | Comment on a data-stream post | post_id, author_id, content |
| `data_stream_file` | File attached to a post | post_id, file_name, cid |
| `iri_registry` | Deterministic Kokonut IRI registry | iri, entity_type, entity_id, version |
| `content_hash_entry` | Content hash lookup | hash_value, algorithm, entity_id |
| `data_resolver` | External metadata resolver | resolver_url, manager_address |
| `data_resolver_registration` | IRI-to-resolver registration | resolver_id, iri_id |
| `data_iri_attestor` | IRI attestor record | iri_id, attestor_address |
| `rdf_namespace` | RDF namespace definition | prefix, uri |
| `rdf_named_graph` | RDF named graph | graph_name, description |
| `rdf_triple` | RDF triple store row | subject, predicate, object, graph |
| `linkml_schema` | LinkML schema definition | schema_name, version, schema_data |
| `linkml_schema_instance` | LinkML-validated entity instance | schema_id, entity_type, entity_id |
| `linkml_directus_mapping` | LinkML-to-Directus field mapping | schema_id, collection, field |
| `app_project_metadata` | Application rendering metadata | entity_type, entity_id, metadata |
| `project_link` | Project cross-reference link | project_id, target_type, target_id |
| `project_reference_id` | External project identifier | project_id, id_type, id_value |
| `v_public_farm_summary` | Public farm aggregate view | location_id, farm_name, status |
| `v_public_metric_summary` | Verified public metric aggregate | metric_key, location_id, value, period |
| `v_public_attestation_summary` | Public Celo attestation aggregate | subject_type, subject_id, schema_uid, status |

## Database Infrastructure And Security

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `schema_version` | Base schema version record | version, applied_at, checksum |
| `schema_migration` | Ordered migration tracking | filename, checksum, applied_at |
| `api_key` | API key hash and scope record | key_hash, scope, expires_at |
| `app_role` | Application role definition | role_name, permissions |
| `audit_log` | System action audit trail | action, entity_type, actor |
| `export_log` | Export execution record | export_type, record_count, file_path |
| `scheduled_job` | Scheduled job registry | job_name, cron_expr, enabled |
| `webhook` | Outbound webhook configuration | url, event_type, secret |
| `capability_token` | Scoped capability token | token_hash, capabilities, expires_at |
| `access_audit_log` | Capability access audit | token_id, resource, action, timestamp |
| `verification_review` | Verification review result | entity_type, entity_id, result, reviewer_id |
| `approval` | Human approval record | entity_type, entity_id, decision, decided_by |
| `workflow_history` | Lifecycle transition audit | entity_type, entity_id, from_state, to_state, changed_by |
| `file_upload` | Uploaded file metadata | filename, storage_path, mime_type |

### Event Bus And Cache

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `platform_event` | Durable event queue row | event_type, status, priority, payload |
| `event_handler` | Event handler registry | handler_name, event_type, module_path |
| `event_handler_log` | Handler execution record | event_id, handler_id, status, duration_ms |
| `event_dead_letter` | Failed event disposition record | original_event_id, failure_count, error |
| `cache_entry` | Computation cache entry | cache_key, result, expires_at, hit_count |
| `cache_invalidation_rule` | Event-to-cache invalidation rule | event_type, target_computation_type, scope |

## Ingestion, Scheduling, Federation, And Analysis

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `data_freshness_config` | Freshness threshold configuration | source_system, max_age_hours, alert_threshold |
| `data_freshness_check` | Freshness check result | source_system, last_data_at, is_stale |
| `remote_sensing_job` | Remote-sensing fetch job | provider, status, last_run_at |
| `sensor_device_health` | Sensor health observation | device_id, battery_pct, signal_strength |
| `scheduled_task` | Durable scheduler task | task_name, cron_expr, module_path |
| `task_run` | Scheduler run state | task_id, status, started_at, completed_at |
| `task_resource` | Scheduler resource lease | task_run_id, resource_type, locked_by |
| `driver_registry` | External driver definition | driver_name, driver_type, config_schema |
| `driver_instance` | Installed driver configuration | driver_id, instance_name, config |
| `driver_instance_log` | Driver execution log | instance_id, status, duration_ms |
| `stream_window` | Stream aggregation window | sensor_id, metric, window_start, value |
| `stream_buffer` | Buffered stream values | buffer_key, values, count |
| `stream_alert` | Stream-processing alert | alert_type, severity, metric, threshold |
| `ingestion_log` | External ingestion execution log | source_system, target_table, status, processing_time_ms |
| `harvest_ingestion_log` | Harvest ingestion audit | source, record_count, status |
| `federation_node` | Federation node registry | node_name, url, status |
| `federation_share` | Data shared with a node | node_id, data_type, shared_at |
| `federation_query` | Federated query record | query_type, source_node, status |
| `analysis_environment` | Sandboxed analysis environment | env_name, sandbox_type, resources |
| `analysis_run` | Analysis execution record | env_id, status, started_at, completed_at |
| `analysis_sandbox` | Analysis sandbox instance | env_id, sandbox_id, status |

## Environmental Modeling And Spatial Data

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `environmental_baseline` | Baseline environmental measurement | baseline_type, value, date |
| `water_access` | Water access point and quality record | water_source, access_type, quality |
| `water_sample` | Water sample collection | sample_date, parameters, location |
| `water_analysis` | Water quality analysis | parameter, value, unit |
| `disease_observation` | Crop disease observation | disease_name, severity, crop_id |
| `irrigation_program` | Irrigation program definition | program_name, method, frequency |
| `plant_analysis` | Plant tissue or nutrient analysis | analysis_type, nutrient_values |
| `sample_plot_design` | Experimental sample-plot design | design_type, replication_count |
| `sample_plot` | Individual experimental plot | plot_id, location, treatment |
| `sampling_protocol` | Sampling protocol | protocol_name, depth_cm, frequency |
| `mitigation_approach` | Environmental mitigation approach | approach_name, description, effectiveness |
| `reporting_cadence` | Reporting cadence configuration | report_type, frequency, recipients |
| `spatial_import_log` | Spatial import execution log | file_name, record_count, status |
| `geostory` | Geospatial narrative | title, location_id, status |
| `geostory_section` | Geostory section | geostory_id, section_type, content |
| `thesaurus` | Controlled vocabulary thesaurus | thesaurus_name, version |
| `thesaurus_keyword` | Thesaurus keyword | thesaurus_id, keyword |
| `thesaurus_keyword_label` | Localized keyword label | keyword_id, language, label |
| `worldclim_climate` | WorldClim climate feature | variable, value, period |
| `ncep_weather_summary` | NCEP weather summary | variable, value, date_range |
| `modis_lst_summary` | MODIS land-surface temperature summary | mean_lst, date_range, pixel_count |
| `smap_soil_moisture` | SMAP soil moisture observation | moisture_pct, date, geometry |
| `sentinel1_sar_summary` | Sentinel-1 SAR summary | vvh_db, vv_db, date_range |
| `soc_prediction_model` | Soil-organic-carbon model configuration | model_type, parameters, accuracy |
| `soc_prediction` | Soil-organic-carbon prediction | location_id, predicted_soc, confidence |
| `computed_feature_importance` | Model feature importance | feature_name, importance_score |
| `cv_fold_result` | Cross-validation fold result | fold, rmse, r_squared |
| `rs_time_series_feature` | Remote-sensing time-series feature | feature_name, value, timestamp |
| `weather_time_series_feature` | Weather time-series feature | feature_name, value, timestamp |
| `modis_lst_time_series` | MODIS temperature time series | lst_value, date, pixel |
| `smap_moisture_time_series` | SMAP moisture time series | moisture_pct, date |
| `sentinel1_time_series` | Sentinel-1 time series | vvh, vv, date |

## Supply Chain, Procurement, Training, And Capacity

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `buyer_demand_signal` | Buyer demand signal | buyer_id, crop, quantity, price |
| `demand_forecast` | Demand forecast | crop, period, forecasted_qty |
| `market_size_estimate` | Market-size estimate | market_type, region, total_value |
| `demand_trend` | Demand trend | crop, period, trend_direction |
| `production_market_match` | Production-to-buyer match | production_id, buyer_id, match_score |
| `buyer_segment` | Buyer segment definition | segment_name, criteria, size |
| `supplier_profile` | Supplier registry | supplier_name, product_type, rating |
| `supply_agreement` | Supply agreement | supplier_id, terms, expiry_date |
| `purchase_order` | Purchase order | supplier_id, total_amount, status |
| `purchase_order_item` | Purchase-order line item | po_id, item_name, quantity, unit_cost |
| `group_buy` | Collective purchasing campaign | crop, target_qty, target_price |
| `group_buy_participation` | Group-buy participation | group_buy_id, farmer_id, quantity |
| `supplier_quality_assessment` | Supplier quality score | supplier_id, score, assessment_date |
| `shipment` | Shipment record | origin, destination, status |
| `shipment_item` | Shipment line item | shipment_id, item_name, quantity |
| `cold_chain_record` | Cold-chain observation | temperature, humidity, duration |
| `storage_facility` | Storage facility | facility_name, capacity, type |
| `transport_log` | Transport activity | vehicle_type, distance_km, fuel_cost |
| `training_program` | Training program | program_name, duration, status |
| `training_module` | Training module | program_id, title, sequence |
| `training_lesson` | Training lesson | module_id, title, content_type |
| `training_enrollment` | Training enrollment | program_id, farmer_id, status |
| `training_progress` | Training progress | enrollment_id, lesson_id, completed |
| `competency_framework` | Competency definition | competency_name, level, category |
| `credential` | Credential award | farmer_id, competency_id, awarded_at |
| `utilization_observation` | Capacity utilization reading | asset_id, utilization_pct, period |
| `equipment_usage_log` | Equipment usage period | asset_id, start_time, end_time |
| `capacity_threshold` | Capacity alert threshold | asset_id, warning_pct, critical_pct |

## Bio Factory And Content

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `bio_factory_batch` | Bio-input production batch | batch_type, quantity, status |
| `bio_input_provenance` | Bio-input sourcing record | input_type, source, quantity |
| `bio_recipe_library` | Bio-input recipe | recipe_name, ingredients, process |
| `bio_factory_distribution` | Bio-input distribution | batch_id, recipient, quantity |
| `bio_factory_quality_test` | Bio-input quality test | batch_id, test_type, result |
| `bio_ingredient_composition_reference` | Ingredient composition reference | ingredient_name, composition |
| `bio_regional_input_availability` | Regional input availability | input_type, region, available_qty |
| `content_piece` | Educational or public content | title, content_type, status |
| `content_distribution` | Content delivery record | content_id, channel, reach |
| `sensemaking_score` | Content sensemaking score | content_id, score, reviewer |

## Token Economics, DAO, And Web3

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `colony_instance` | Colony network instance | chain, colony_address, token_address |
| `kokonut_guild` | Kokonut guild record | guild_name, chain, token |
| `guild_contributor` | Guild contributor | guild_id, wallet_address, reputation |
| `guild_contribution` | Guild contribution | guild_id, contributor_id, hours |
| `guild_reputation_snapshot` | Guild reputation snapshot | guild_id, score, period |
| `dao_proposal` | DAO proposal record | proposal_id, title, status |
| `dao_proposal_extended` | Extended proposal metadata | proposal_id, vote_count, status |
| `dao_vote` | DAO vote | proposal_id, voter, vote_power |
| `governance_token` | Governance token record | token_name, chain, total_supply |
| `staking_position` | Token staking position | token_id, amount, lock_period |
| `token_balance_snapshot` | Token balance snapshot | wallet_id, balance, snapshot_date |
| `tree_token_binding` | Tree-to-token binding | tree_id, token_id, binding_date |
| `yield_distribution` | Yield distribution | epoch, recipient, amount |
| `reputation_token` | Reputation token balance | holder_id, balance, decay_rate |
| `delegation_record` | Voting delegation | delegator, delegate, weight |
| `coin_inflation_event` | Token inflation event | amount, recipient, reason |
| `fund_distribution` | Fund distribution | fund_id, recipient, amount |
| `funding_bid` | Funding bid | bid_amount, project_id, status |
| `funding_request` | Funding request | request_type, amount, justification |
| `incentive_alignment_log` | Incentive alignment observation | incentive_type, alignment_score |
| `inflation_schedule` | Inflation schedule | schedule_name, rate, effective_date |
| `value_stability_metric` | Value stability metric | metric_name, period, stability_score |
| `inflation_adjustment` | Inflation adjustment | adjustment_rate, effective_date |
| `evaluator` | Web-of-Trust evaluator | evaluator_type, reputation_score |
| `attester_reputation` | Attester reputation | attester_id, reputation, total_attestations |
| `attestation_reference` | Attestation cross-reference | attestation_id, reference_type, reference_id |
| `preference_signal` | User preference signal | signal_type, weight, entity_id |
| `ranking_algorithm` | Ranking configuration | algorithm_name, parameters |
| `ranking_result` | Ranking result | entity_id, rank, score |
| `governance_event` | On-chain governance event | event_type, tx_hash, proposal_id |
| `dapp_session` | DApp session record | wallet_address, session_token |

## Modeled Outputs And Scenarios

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `metric_version` | Metric formula version history | metric_id, formula, version, effective_date |
| `dashboard_dataset` | Dashboard dataset refresh configuration | dataset_key, sql_query, refresh_interval |
| `scenario_parameter` | Scenario parameter definition | param_name, default_value, range |
| `scenario_simulation` | Scenario simulation run | scenario_id, parameters, results |
| `ai_impact_evaluation` | AI impact evaluation | evaluation_type, score, evidence |
| `data_stream_post` | Governed data-stream output | location_id, content, status |
| `impact_estimate_post` | Impact estimation post | post_type, estimate_value, evidence |
| `category_graft` | Cross-category mapping | source_category, target_category |
| `category_relatedness` | Category relatedness score | category_a, category_b, relatedness |
| `estimate_category_assignment` | Estimate-to-category link | estimate_id, category_id |
| `expertise_category` | Expertise category | category_name, description |
| `waiting_list_entry` | Waiting-list entry | entry_type, status, position |
| `validation_round` | Impact validation round | round_number, status, deadline |
| `validator_selection` | Validator selection | round_id, validator_id, weight |
| `validator_review` | Validator review | review_id, score, comments |
| `quadratic_vote` | Quadratic validation vote | round_id, voter_id, amount |
| `validator_compensation` | Validator compensation | validator_id, amount, token |
| `periodic_validation` | Periodic validation run | period, status, results |
| `realized_impact_record` | Realized impact record | metric, value, verified |
| `impact_deviation` | Expected-versus-realized deviation | expected, actual, deviation_pct |
| `relatedness_coefficient` | Relatedness coefficient | entity_a, entity_b, coefficient |

## Common Schema Conventions

- PostgreSQL and Directus are the canonical application data layer; ClickHouse is the analytical event store.
- UUID primary keys and `created_at`/`updated_at` audit fields are common but not universal. Confirm the migration before relying on them.
- Public views must apply lifecycle, evidence maturity, consent, and registry gates defined by their source migrations.
- `metric_value` rows produced by computation are drafts and unverified until a human reviewer verifies them.
- Public carbon claims require evidence maturity 6, an evidence link, an external verifier, a methodology reference, and the required published claim state.
- Agent-generated governed records remain draft or submitted; agents cannot verify or publish them.
- Payment state, attestation state, and lifecycle state are separate concepts. Do not overload `status` when a dedicated field exists.
- Geometry fields use PostGIS types or GeoJSON projection views where spatial export is required.
- JSONB fields preserve source payloads, model inputs, evidence metadata, and structured configuration; their detailed shapes are defined by the owning service or migration.

## Source Of Truth

Use the ordered PostgreSQL migrations under `schemas/postgres/` for exact columns,
constraints, indexes, triggers, and views. Use `schemas/seeds/` for canonical
reference data, metric definitions, framework mappings, and pilot records. This
document is a navigation layer and must be updated when a migration adds a new
canonical domain object or changes a public contract.
