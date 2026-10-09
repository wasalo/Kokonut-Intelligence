# Data Domain Ownership

Schema, service, test, and relationship vocabulary changes should have one
primary owning domain. The table below maps every governed domain to its
canonical tables, services, and migrations. Each domain owns its own
lifecycle vocabulary, migration ordering, service APIs, and test coverage.

## Domain Registry

### Identity

Canonical responsibility: `party`, farmer profiles, credentials, KYC,
identifiers, organizations, and member relationships.

Key tables:

- `party`, `party_identifier`, `party_relationship`
- `farmer_profile`, `farmer_role`, `farmer_consent`, `farmer_credential`,
  `farmer_credential_type`
- `kyc_verification`, `credential`
- `organization`, `organization_member`, `organization_wallet`
- `staff`, `partner`

Key services: `services/analytics/farmer_identity.py`

Key migrations: `001_locations.sql`, `064_organization.sql`,
`148_farmer_identity.sql`

### Stakeholders

Canonical responsibility: Parties, interests, salience, consent,
representation, engagement, grievances, trust, decisions, distribution,
accessibility, and minority views.

Key tables:

- `stakeholder_interest`, `stakeholder_salience_assessment`,
  `stakeholder_commitment`, `stakeholder_public`
- `stakeholder_consent`, `consent_data_type`, `stakeholder_participation`,
  `stakeholder_distribution`
- `stakeholder_engagement_plan`, `stakeholder_engagement_objective`,
  `stakeholder_engagement_outcome`, `stakeholder_touchpoint`
- `stakeholder_grievance_case`, `grievance_investigation`,
  `grievance_remedy`, `grievance_appeal`, `grievance_closure`,
  `grievance_evidence`
- `stakeholder_decision`, `stakeholder_decision_participant`,
  `stakeholder_decision_evidence`, `stakeholder_decision_outcome`,
  `stakeholder_decision_tradeoff`
- `stakeholder_minority_view`, `stakeholder_accessibility_request`
- `party_trust_evidence`, `party_trust_snapshot`,
  `relationship_risk_indicator`, `buyer_verification`
- `stakeholder_feedback`, `stakeholder_feedback_review`,
  `stakeholder_outcome`

Key services: `services/analytics/stakeholder_*.py`,
`services/feedback/controller.py`

Key migrations: `030_stakeholder_feedback.sql`,
`213_stakeholder_vocabulary.sql`, `215_stakeholder_consent.sql`,
`216_stakeholder_engagement.sql`, `218_stakeholder_grievances.sql`,
`219_stakeholder_representation.sql`, `221_stakeholder_decisions.sql`

### Farm Operations

Canonical responsibility: Locations, farms, plots, crop cycles, operational
events, harvest handling, labor, field notes, inventory, partners,
infrastructure, organic certification, and tenure rights.

Key tables:

- `location`, `farm`, `plot`, `crop_cycle`, `crop`
- `farm_activity`, `harvest_event`, `harvest_handling_record`,
  `sales_event`, `expense_event`, `loss_event`, `labor_event`,
  `field_note`, `inventory_event`
- `partner`, `infrastructure_asset`, `staff`, `file_upload`
- `farm_registry_record`, `farm_zone`, `farm_practice_event`
- `farm_onboarding_workflow`, `farm_specification`,
  `farm_financial_account`
- `organic_certification_record`, `organic_compliance_checklist`,
  `organic_input_audit`, `organic_readiness_assessment`,
  `organic_transition_plan`, `prohibited_substance_record`,
  `tenure_rights_assessment`

Key services: `services/analytics/yield_monitoring.py`,
`services/analytics/pest_management.py`,
`services/analytics/crop_rotation.py`

Key migrations: `001_locations.sql`, `002_crops.sql`,
`003_operations.sql`, `009_operations_ux.sql`,
`027_farm_onboarding_profile.sql`, `055_organic_certification.sql`

### Environmental Measurement

Canonical responsibility: Soil samples, species observations, remote sensing,
weather, sensors, environmental baselines, MRV claims, verification reviews,
and environmental data ingestion.

Key tables:

- `soil_sample`, `soil_carbon_measurement`, `soil_input_application`
- `species_observation`
- `remote_sensing_observation`, `remote_sensing_job`,
  `rs_time_series_feature`
- `weather_observation`, `weather_forecast`, `weather_time_series_feature`,
  `ncep_weather_summary`, `modis_lst_summary`, `smap_soil_moisture`,
  `sentinel1_sar_summary`, `worldclim_climate`
- `sensor_reading`, `sensor_device`, `sensor_device_health`,
  `sensor_type`, `sensor_alert`, `sensor_network_design`
- `environmental_baseline`, `location_baseline`
- `mrv_claim`, `mrv_event`, `verification_review`
- `ghg_emission_factor`, `ghg_emissions_inventory`

Key services: `services/ingestion/weather.py`,
`services/ingestion/remote_sensing_fetcher.py`,
`services/ingestion/sensor_ingester.py`,
`services/ingestion/anomaly_detector.py`,
`services/analytics/climate_data.py`

Key migrations: `005_environmental.sql`, `011_sensor_registry.sql`,
`077_telemetry_infrastructure.sql`

### Carbon and Environmental Impact

Canonical responsibility: Carbon benchmarks, tree inventory, underplanting,
regenerative practice checklists, climate impact summaries, framework phases,
operations protocols, and ecological interactions.

Key tables:

- `carbon_benchmark`, `tree_inventory`, `tree_measurement`, `tree_record`,
  `underplanting_event`
- `regenerative_practice_checklist`, `framework_phase`,
  `climate_impact_summary`, `operations_protocol`
- `ecological_interaction`, `ecological_model_run`,
  `population_dynamics_record`, `resource_consumption`
- `energy_flow_measurement`, `biocontrol_release`

Key services: `services/analytics/carbon_credits.py`,
`services/analytics/ecological_modeling.py`,
`services/analytics/tree_tracking.py`

Key migrations: `028_carbon_framework.sql`,
`046_ecological_modeling.sql`, `047_ecological_modeling_v2.sql`

### Metrics and Modeled Outputs

Canonical responsibility: Metric definitions, metric versions, metric values,
forecasts, report snapshots, dashboard datasets, AI summaries, and metric
proposals.

Key tables:

- `metric_definition`, `metric_version`, `metric_value`,
  `metric_value_source`, `metric_proposal`
- `forecast_scenario`, `forecast_output`, `forecast_accuracy`,
  `forecast_assumption`
- `report_snapshot`, `dashboard_dataset`, `ai_summary`

Key services: `services/metrics/`, `services/forecast/`,
`services/export/report_generator.py`

Key migrations: `007_modeled_outputs.sql`

### EBF Scoring and Calibration

Canonical responsibility: Ecological Benefits Framework pillars, rubric bands,
scorecards, scores, evidence links, trust graph nodes and edges, calibration
sessions and decisions, farm metric profiles, and improvement recommendations.

Key tables:

- `ebf_pillar`, `ebf_rubric_band`, `ebf_scorecard`, `ebf_score`,
  `ebf_score_evidence`, `ebf_farm_metric_profile`
- `ebf_trust_graph_node`, `ebf_trust_graph_edge`
- `ebf_calibration_session`, `ebf_calibration_decision`,
  `ebf_improvement_recommendation`

Key services: `services/scoring/`

Key migrations: `032_ebf_scorecard.sql`, `033_ebf_p1_operations.sql`

### CRISP Risk Scoring

Canonical responsibility: Carbon Risk Identification and Scoring Principles.
Configurable five-dimension risk intelligence engine with per-location weights
and composite AAA-D rating.

Key tables:

- `crisp_risk_dimension`, `crisp_risk_assessment`
- `crisp_carbon_yield_risk`, `crisp_climate_risk`, `crisp_policy_risk`,
  `crisp_financial_risk`, `crisp_implementation_risk`
- `crisp_location_weight`

Key services: `services/crisp/`

Key migrations: `076_crisp_risk_scoring.sql`

### Financial and Marketplace

Canonical responsibility: Accounts, transactions, revenue, expenses, sales,
cost allocations, NOI, cash flow, value flows, capital sources, revenue
streams, pricing, cost structures, break-even analysis, and marketplace orders.

Key tables:

- `financial_transaction`, `external_grant_tranche`,
  `external_grant_tranche_funder`, `expense_category`, `capital_source`,
  `crop_cost_allocation`, `value_flow_event`, `excluded_value_event`
- `noi_snapshot`, `cash_flow_snapshot`, `revenue_event`,
  `expense_event`, `sales_event`
- `farm_financial_account`, `dfs_financial_transaction`,
  `dfs_currency`
- `revenue_stream_definition`, `revenue_stream_contribution`,
  `pricing_model`, `cost_structure`, `cost_driver`
- `market_listing`, `market_order`, `market_alert`,
  `market_reference_data`, `marketplace_fee`,
  `marketplace_fee_distribution`
- `buyer_profile`, `buyer_segment`, `buyer_demand_signal`,
  `demand_forecast`, `demand_trend`

Key services: `services/finance/`, `services/analytics/marketplace.py`,
`services/analytics/revenue_model.py`

Key migrations: `004_finance.sql`, `070_financial_enhancements.sql`,
`141_digital_finance.sql`, `142_marketplace.sql`,
`367_external_grant_tranche.sql`

### Digital Finance

Canonical responsibility: Digital lending, crop insurance, insurance claims,
digital financial transactions, and DFS product types.

Key tables:

- `digital_lending`, `repayment_schedule`, `collateral_asset`
- `crop_insurance_policy`, `insurance_claim`
- `dfs_financial_transaction`, `dfs_currency`,
  `dfs_insurance_product_type`

Key services: `services/analytics/digital_finance.py`

Key migrations: `141_digital_finance.sql`

### Carbon Credits and Ecocredits

Canonical responsibility: Credit classes, batches, balances, adjustments,
retirements, transfers, carbon credits, buffer pools, basket deposits,
marketplace orders, bridge transactions, and retirement certificates.

Key tables:

- `credit_class`, `credit_batch`, `credit_balance`, `credit_adjustment`,
  `credit_retirement`, `credit_transfer`
- `carbon_credit`, `retirement_certificate`
- `buffer_pool_account`, `credit_basket`, `credit_basket_deposit`,
  `credit_basket_token`
- `credit_sell_order`, `credit_buy_order`, `credit_class_issuer`,
  `credit_class_allowlist`, `credit_class_methodology`,
  `credit_class_registry`, `credit_class_cobenefit`
- `credit_bridge_transaction`, `credit_batch_contract`

Key services: `services/credit_class/`,
`services/analytics/carbon_credits.py`

Key migrations: `078_carbon_credits.sql`

### Credit Lifecycle

Canonical responsibility: Credit type definitions, credit protocols, credit
allowed denominations, crediting programs, and ecocredit parameters.

Key tables:

- `credit_type`, `credit_protocol`, `credit_allowed_denom`,
  `crediting_program`, `ecocredit_param`

Key services: `services/credit_class/`

Key migrations: `078_carbon_credits.sql`

### Strategy and Governance

Canonical responsibility: Strategic plans, maps, choices, assumptions,
initiatives, KPIs, capabilities, value streams, vision/mission, SWOT, PESTEL,
competitive landscape, strategic positioning, and technology roadmaps.

Key tables:

- `strategy_plan`, `strategy_map`, `strategy_choice`,
  `strategy_assumption`, `strategy_initiative`,
  `strategy_performance_indicator`
- `business_capability`, `capability_maturity_assessment`,
  `capability_process_map`, `capability_service_map`
- `value_stream_definition`, `value_stream_stage`,
  `value_stream_stage_observation`
- `vision_mission`, `swot_analysis`, `swot_factor`, `swot_action_link`,
  `pestel_analysis`, `pestel_factor`
- `competitive_landscape`, `competitive_actor`,
  `competitive_force_observation`, `competitive_signal`
- `technology_roadmap`, `technology_area`, `technology_driver`

Key services: `services/strategy_markup/`,
`services/analytics/business_model_canvas.py`,
`services/analytics/strategy_map.py`

Key migrations: `008_governance.sql`, `307_strategy_markup_projection.sql`

### Threatcasting and Backcasting

Canonical responsibility: Threats, threat narratives, horizons, cross-impact
relationships, flags, signals, cascades, forecast questions, backcast plans,
backcast principles, assumption challenges, path comparisons, and premortems.

Key tables:

- `threat`, `threat_narrative`, `threat_horizon`,
  `threat_cross_impact`, `threat_flag`, `threat_signal`,
  `threat_cascade`, `threat_cascade_step`, `threat_forecast_question`,
  `threat_forecast_score`, `threat_forecast_resolution`,
  `threat_desirability_assessment`
- `backcast_plan`, `backcast_principle`, `backcast_principle_alignment`,
  `backcast_assumption_challenge`, `backcast_milestone_dependency`,
  `backcast_path_comparison`, `backcast_path_premortem`

Key services: `services/threatcasting/`

Key migrations: `159_threatcasting.sql`,
`160_backcasting_enhancements.sql`

### Delphi Consultation

Canonical responsibility: Real-time Delphi studies, panel members, items,
contributions, consensus history, minority reports, stopping evaluations,
recommendations, expert calibration, diversity assessments, and diversity
targets.

Key tables:

- `delphi_study`, `delphi_panel_member`, `delphi_item`,
  `delphi_contribution`, `delphi_consensus`,
  `delphi_consensus_history`
- `delphi_minority_report`, `delphi_stopping_evaluation`,
  `delphi_recommendation`
- `delphi_expert_calibration`, `delphi_diversity_assessment`,
  `delphi_diversity_target`

Key services: `services/delphi/`

Key migrations: `161_delphi.sql`

### Workflow and Lifecycle

Canonical responsibility: State models, process models, process variants,
work items, lifecycle transitions, escalations, process mining, predictive
BPM, process control, CTQ analysis, and process health.

Key tables:

- `process_model`, `process_variant`, `process_trace`,
  `process_target`, `process_kpi_snapshot`, `process_ctq`
- `work_item`, `work_item_event`, `work_item_claim`
- `lifecycle_transition`, `process_escalation`, `process_benchmark`,
  `process_capability`, `process_maturity`

Key services: `services/workflow_specs/`,
`services/analytics/process_mining.py`,
`services/analytics/predictive_bpm.py`,
`services/management/`

Key migrations: `175_management_work_items.sql`,
`182_process_mining.sql`

### Data Governance and Consent

Canonical responsibility: Consent recording and withdrawal, data retention
policies, data sharing agreements, data access logs, portability requests,
data governance categories and scopes, and consent lifecycle enforcement.

Key tables:

- `farmer_consent`, `stakeholder_consent`, `consent_data_type`,
  `data_sharing_consent`, `data_sharing_agreement`
- `data_governance_category`, `data_governance_scope`,
  `data_retention_policy`, `data_access_log`,
  `data_portability_request`

Key services: `services/analytics/data_governance.py`

Key migrations: `144_data_governance.sql`,
`298_consent_privacy_p0.sql`, `301_data_governance_p2.sql`,
`320_consent_lifecycle_public_gates.sql`

### Agent Identity and Safety

Canonical responsibility: Agent identities, capability manifests, agent tasks,
agent action logs, agent safety enforcement, and audit boundaries.

Key tables:

- `agent_identity`, `agent_capability_manifest`,
  `agent_task`, `agent_action_log`

Key services: `services/agents/safety.py`, `services/agents/tasks.py`

Key migrations: `013_prd_completion.sql`,
`029_impact_accountability_foundation.sql`

### Linked Data, IRIs, and Evidence Lineage

Canonical responsibility: IRI registry, RDF triples, named graphs, namespaces,
data stream posts, data stream files, graph nodes, graph edges, graph
projections, evidence lineage, and content hashes.

Key tables:

- `iri_registry`, `rdf_triple`, `rdf_named_graph`, `rdf_namespace`
- `data_stream_post`, `data_stream_post_comment`, `data_stream_file`
- `graph_node`, `graph_node_type`, `graph_edge`, `graph_edge_type`,
  `graph_projection`, `graph_projection_generation`
- `content_hash_entry`

Key services: `services/iri/`, `services/rdf/`,
`services/graph_projection/`, `services/data_stream/`

Key migrations: `100_data_stream.sql`, `102_iri_system.sql`,
`104_rdf_triples.sql`, `173_typed_temporal_graph.sql`

### Precision Agriculture

Canonical responsibility: Irrigation zones and scheduling, pest scouting and
interventions, crop phenology, GDD accumulation, nutrient budgets, yield
monitoring, equipment usage, prescription maps, and degree-day tracking.

Key tables:

- `irrigation_zone`, `irrigation_event`, `irrigation_schedule`,
  `irrigation_program`, `soil_moisture_target`, `water_efficiency_log`
- `pest_scouting_record`, `pest_scouting_schedule`,
  `pest_scouting_compliance`, `pest_intervention`,
  `pest_action_threshold`, `pest_degree_day_config`,
  `pest_resistance_record`, `pesticide_application_log`,
  `pesticide_impact_log`, `degree_day_record`, `pest_trap`,
  `pest_trap_catch`, `pest_rotation_check`
- `crop_gdd_config`, `crop_growth_stage`
- `nutrient_budget`, `nutrient_input`, `nutrient_removal`,
  `crop_nutrient_removal_factor`, `soil_test_recommendation`
- `yield_benchmark`, `yield_distribution`, `yield_prediction`
- `prescription_map`, `prescription_zone`
- `equipment_usage_log`

Key services: `services/analytics/precision_irrigation.py`,
`services/analytics/pest_management.py`,
`services/analytics/crop_phenology.py`,
`services/analytics/yield_monitoring.py`,
`services/analytics/nutrient_budget.py`

Key migrations: `146_precision_irrigation.sql`,
`149_pest_management.sql`, `151_nutrient_budget.sql`

### Ecological Modeling and Environmental Services

Canonical responsibility: Ecological model runs, SOC prediction, energy
monitoring, waste management, composting, landscape conservation, habitat
zones, corridors, hedgerows, pollinator health, wildlife corridors, and
biodiversity scores.

Key tables:

- `ecological_model_run`, `soc_prediction`, `soc_prediction_model`
- `energy_source`, `energy_reading`, `energy_efficiency_log`
- `waste_stream`, `waste_type`, `composting_record`, `recycling_log`
- `habitat_zone`, `wildlife_corridor`, `hedgerow_record`,
  `landscape_biodiversity_score`, `buffer_zone`,
  `buffer_zone_monitoring`
- `pollinator_habitat`, `pollinator_observation`,
  `pollinator_species_reference`, `hive_record`

Key services: `services/analytics/ecological_modeling.py`,
`services/analytics/energy_monitoring.py`,
`services/analytics/waste_management.py`,
`services/analytics/landscape_conservation.py`,
`services/analytics/pollinator_health.py`

Key migrations: `046_ecological_modeling.sql`,
`154_landscape_conservation.sql`, `155_pollinator_health.sql`

### Cooperative and Collective Operations

Canonical responsibility: Cooperatives, membership, governance, shared assets,
collective purchasing, collective market orders, meetings, motions, votes,
delegations, and conflict declarations.

Key tables:

- `cooperative`, `cooperative_type`, `cooperative_membership`,
  `cooperative_board_member`
- `cooperative_meeting`, `cooperative_motion`, `cooperative_proposal`,
  `cooperative_vote`, `cooperative_quorum`
- `cooperative_delegation`, `cooperative_distribution_decision`,
  `cooperative_conflict_declaration`
- `shared_asset`, `asset_booking`
- `collective_purchase`, `collective_purchase_participant`,
  `collective_market_order`, `collective_market_participant`

Key services: `services/analytics/cooperative.py`

Key migrations: `147_cooperative.sql`, `222_cooperative_trust.sql`

### Extension and Training

Canonical responsibility: Extension modules, advisory records, peer networks,
training programs, sessions, lessons, enrollments, learning progress, and
skill assessments.

Key tables:

- `extension_module`, `extension_advisory`
- `peer_network`, `peer_network_member`
- `training_program`, `training_session`, `training_lesson`,
  `training_enrollment`, `training_progress`
- `learning_progress`, `skill_assessment`

Key services: `services/analytics/extension.py`

Key migrations: `145_extension.sql`

### Traceability and Supply Chain

Canonical responsibility: Batch provenance, chain of custody, quality
inspections, certifications, food safety, logistics tracking, cold chain,
and shipments.

Key tables:

- `produce_batch`, `chain_of_custody`, `provenance_event`
- `quality_inspection`, `quality_grade`
- `certification_type`, `certification_verify`
- `food_safety_record`, `harvest_ingestion_log`
- `logistics_tracking`, `shipment`, `shipment_item`
- `cold_chain_record`, `storage_facility`

Key services: `services/analytics/traceability.py`

Key migrations: `143_traceability.sql`

### Bio Factory Operations

Canonical responsibility: Bio-organic fertilizer production batches, ingredient
provenance, recipe library, quality testing, ingredient composition reference,
and LAC regional input availability.

Key tables:

- `bio_factory_batch`, `bio_input_provenance`, `bio_recipe_library`
- `bio_factory_quality_test`, `bio_factory_distribution`
- `bio_ingredient_composition_reference`,
  `bio_regional_input_availability`

Key services: `services/agents/bio_factory_agent.py`

Key migrations: `043_bio_factory_operations.sql`

### Resilience, Capital, and Simulation

Canonical responsibility: Strategic reserves, reserve triggers, reserve
releases, capital capacity assessments, capital diversion, capture risk,
regenerative credit ledger, stock-flow models, simulation configs, and Monte
Carlo wrappers.

Key tables:

- `strategic_reserve`, `strategic_reserve_release`
- `capital_capacity_assessment`, `capital_diversion_observation`,
  `capital_capture_risk`, `regenerative_credit_ledger`
- `stock_flow_model`, `stock_flow_run`
- `simulation_config`, `simulation_run`, `simulation_state`,
  `what_if_scenario`

Key services: `services/strategic_reserve/`, `services/capital/`,
`services/simulation/`, `services/systems/stock_flow.py`

Key migrations: `327_strategic_reserve.sql`,
`328_strategic_reserve_preempt.sql`, `330_capital_accounting.sql`

### Guilds and KGP Protocol

Canonical responsibility: Colony instances, Kokonut guilds, guild
contributors, contributions, reputation snapshots, guild domains, guild
evidence reviews, guild tasks, guild motions, and KGP protocol deployments.

Key tables:

- `colony_instance`, `kokonut_guild`, `guild_contributor`,
  `guild_contribution`, `guild_reputation_snapshot`
- `guild_domain`, `guild_evidence_review`,
  `guild_evidence_review_event`, `guild_task`, `guild_motion`
- `kgp_protocol_deployment`, `kgp_chain_event`, `kgp_claim`,
  `kgp_indexer_cursor`

Key services: `services/guilds/`

Key migrations: `025_kokonut_framework_alignment.sql`,
`317_kgp_protocol.sql`, `318_guild_protocol_projection.sql`,
`319_guild_integrity_controls.sql`

### Innovation and Solutions

Canonical responsibility: Stage gates, experiments, adoption programs,
replication, funding cases, funding tranches, scale gates, solution
lifecycles, learning records, and solution configuration.

Key tables:

- `solution`, `solution_stage_gate`, `solution_gate_evaluation`,
  `solution_lifecycle_event`, `solution_link`
- `solution_experiment`, `solution_experiment_result`,
  `solution_experiment_observation`, `solution_experiment_analysis_run`
- `solution_adoption_program`, `solution_adoption_event`,
  `solution_adoption_cohort`, `solution_adopter_readiness`
- `solution_replication`, `solution_scale_gate`,
  `solution_learning_record`, `solution_configuration`
- `solution_funding_case`, `solution_funding_tranche`,
  `solution_funding_release`, `solution_retirement`

Key services: `services/innovation/`

Key migrations: `290_solution_funding.sql`,
`291_solution_adoption.sql`,
`292_solution_scale_learning_retirement.sql`

### Orientation and OODA

Canonical responsibility: Situation assessments, OODA cycle logs, adaptive
thresholds, feedback loops, adaptation velocity, improvement tracking, and
ML retraining.

Key tables:

- `situation_assessment`, `ooda_cycle_log`
- `adaptive_threshold`, `feedback_loop`, `action_outcome`
- `adaptation_velocity_log`, `improvement_rate`
- `assessment_dimension`, `assessment_signal`

Key services: `services/orientation/`, `services/feedback/`,
`services/systems/velocity_tracker.py`,
`services/systems/improvement_tracker.py`

Key migrations: `124_orientation.sql`,
`126_feedback_loops.sql`, `127_ooda_cycles.sql`

### Ingestion and Data Quality

Canonical responsibility: Ingestion logs, data freshness checks, data quality
rules, data quality scores, anomaly detection rules, sampling configs, device
registration, and ingestion reliability.

Key tables:

- `ingestion_log`, `data_freshness_check`, `data_freshness_config`
- `data_quality_rule`, `data_quality_score`
- `sampling_config`, `sampling_adjustment_log`, `sampling_protocol`
- `device_registration`, `mobile_device`, `mobile_form`,
  `offline_collection`

Key services: `services/ingestion/`, `services/stream/`

Key migrations: `009_operations_ux.sql`, `300_ingestion_reliability.sql`

### Events and Scheduling

Canonical responsibility: Durable event bus, event handlers, event delivery,
event dead letters, scheduled jobs, scheduled tasks, task runs, and cross-domain
insight transfer.

Key tables:

- `event_handler`, `event_handler_delivery`, `event_handler_log`,
  `event_dead_letter`, `platform_event`
- `scheduled_job`, `scheduled_task`, `task_run`, `task_resource`
- `insight_transfer`, `cross_domain_rule`

Key services: `services/events/`, `services/scheduler/`

Key migrations: `008_governance.sql`

### Platform Infrastructure

Canonical responsibility: App roles, API keys, webhooks, audit logs,
schema migrations, schema versions, export logs, gateways, sandboxes,
analysis environments, and security.

Key tables:

- `app_role`, `api_key`, `webhook`, `role_permission`,
  `role_assignment`
- `audit_log`, `schema_migration`, `schema_version`, `export_log`
- `analysis_sandbox`, `analysis_run`
- `access_audit_log`, `data_access_log`

Key services: `services/gateway/`, `services/sandbox/`,
`services/security/`, `services/migration/`

Key migrations: `008_governance.sql`

### Reporting and Dashboards

Canonical responsibility: Report snapshots, public views, public metric
summaries, dashboard datasets, CIDS export, EBF public views, and CRISP
public views.

Key tables:

- `report_snapshot`, `dashboard_dataset`
- Public views: `v_public_metric_summary`, `v_public_attestation_summary`,
  `v_public_stakeholder_feedback_summary`, `v_public_ebf_scorecard`,
  `v_public_ebf_scorecard_summary`, `v_public_ebf_pillar_summary`,
  `v_crisp_composite_rating`

Key services: `services/export/report_generator.py`,
`services/registry/cids_export.py`

Key migrations: `007_modeled_outputs.sql`, `018_public_views.sql`

### Governance and DAO

Canonical responsibility: DAO proposals, votes, treasury events, governance
circles, tensions, tactical coordination, Baal governance, and governance
framework adapters.

Key tables:

- `dao_proposal`, `dao_vote`, `governance_event`, `treasury_event`
- `governance_circle`, `governance_circle_link`, `governance_tension`,
  `governance_tension_event`, `governance_tension_link`
- `governance_tactical_item`, `governance_tactical_session`
- `governance_framework`, `baal_governance_config`, `baal_shaman`
- `governance_role`, `governance_role_assignment`,
  `governance_role_domain`, `governance_role_policy`,
  `governance_role_accountability`
- `governance_proposal`, `governance_proposal_review`,
  `governance_proposal_objection`
- `impact_claim`, `impact_framework`, `impact_dimension`

Key services: `services/governance/`

Key migrations: `008_governance.sql`, `324_baal_governance.sql`

### Impact Domains (Holistic, Financial, Commons, GNH, Capital, Regenerative)

Canonical responsibility: Governed evidence modules for holistic well-being,
financial resilience, capital efficiency, commons liberation, GNH alignment,
regenerative outcomes, open-source scaling, and Kokonut Commons governance.

Key tables:

- `cultural_context_record`, `wellbeing_metric_observation`,
  `participatory_action_record`
- `financial_sustainability_plan`, `risk_mitigation_register`,
  `scaling_roadmap_milestone`, `green_paper_publication_review`
- `capital_efficiency_scenario`, `regenerative_efficiency_observation`,
  `governance_throughput_observation`,
  `capital_provider_utility_scenario`
- `time_liberation_observation`, `capital_alignment_assessment`,
  `governance_inclusion_observation`,
  `land_stewardship_commitment`
- `gnh_alignment_assessment`, `cultural_preservation_plan`,
  `renewable_energy_plan`, `vulnerable_group_access_plan`,
  `foundational_wellbeing_observation`
- `regenerative_outcome_summary`,
  `community_governance_mechanism`,
  `replication_readiness_assessment`,
  `adaptive_stewardship_review`
- `farm_launch_unit_economic`, `network_scaling_target`,
  `adoption_barrier_assessment`, `perpetual_value_stress_test`,
  `open_source_impact_artifact`
- `anti_capture_governance_policy`, `redistribution_policy`,
  `federation_protocol`, `algorithmic_redistribution_mechanism`,
  `participatory_signal_experiment`

Key services: `services/agents/*_agent.py`,
`services/analytics/holistic_wellbeing.py`,
`services/analytics/financial_resilience.py`,
`services/analytics/capital_efficiency.py`,
`services/analytics/commons_liberation.py`,
`services/analytics/gnh_alignment.py`,
`services/analytics/regenerative_outcomes.py`,
`services/analytics/open_source_capitalist_scaling.py`,
`services/analytics/kokonut_commons_governance.py`

Key migrations: `034_holistic_wellbeing.sql`,
`035_financial_resilience_and_scaling.sql`,
`036_capital_efficiency_and_utility.sql`,
`037_commons_liberation_and_stewardship.sql`,
`038_gnh_alignment_and_inclusion.sql`,
`039_regenerative_outcomes_and_stewardship.sql`,
`040_open_source_capitalist_scaling.sql`,
`041_kokonut_commons_governance.sql`

## Ownership Rules

Each domain owns:

- Its migrations and migration ordering.
- Its service APIs and CLI commands.
- Its test coverage.
- Its lifecycle vocabulary and state machines.
- Its relationship review and cross-domain boundary enforcement.

Cross-domain relationships must be represented by an explicit associative
entity or a documented polymorphic policy. When adding a relationship across
domains, both owning domains must review and approve the change.
