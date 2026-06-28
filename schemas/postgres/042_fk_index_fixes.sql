-- ============================================================
-- 042_fk_index_fixes.sql — Add missing FK indexes identified by audit
-- ============================================================

-- 005_environmental
CREATE INDEX IF NOT EXISTS idx_environmental_baseline_plot ON environmental_baseline(plot_id);

-- 007_modeled_outputs
CREATE INDEX IF NOT EXISTS idx_metric_version_metric ON metric_version(metric_id);

-- 011_sensor_registry
CREATE INDEX IF NOT EXISTS idx_sensor_alert_rule ON sensor_alert(alert_rule_id);
CREATE INDEX IF NOT EXISTS idx_sensor_alert_reading ON sensor_alert(reading_id);
CREATE INDEX IF NOT EXISTS idx_mrv_claim_sensor_device ON mrv_claim(sensor_device_id);
CREATE INDEX IF NOT EXISTS idx_mrv_claim_sensor_alert ON mrv_claim(sensor_alert_id);

-- 025_kokonut_framework_alignment
CREATE INDEX IF NOT EXISTS idx_impact_dimension_framework ON impact_dimension(framework_id);
CREATE INDEX IF NOT EXISTS idx_kokonut_guild_colony ON kokonut_guild(colony_instance_id);
CREATE INDEX IF NOT EXISTS idx_guild_reputation_guild ON guild_reputation_snapshot(guild_id);
CREATE INDEX IF NOT EXISTS idx_guild_reputation_contributor ON guild_reputation_snapshot(contributor_id);
CREATE INDEX IF NOT EXISTS idx_farm_zone_plot ON farm_zone(plot_id);
CREATE INDEX IF NOT EXISTS idx_farm_practice_event_zone ON farm_practice_event(zone_id);

-- 026_ground_analytics
CREATE INDEX IF NOT EXISTS idx_disease_observation_loss_event ON disease_observation(loss_event_id);

-- 027_farm_onboarding_profile
CREATE INDEX IF NOT EXISTS idx_farm_logo_file ON farm(logo_file_id);

-- 028_carbon_framework
CREATE INDEX IF NOT EXISTS idx_ghg_inventory_plot ON ghg_emissions_inventory(plot_id);
CREATE INDEX IF NOT EXISTS idx_ghg_inventory_crop_cycle ON ghg_emissions_inventory(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_ghg_inventory_emission_factor ON ghg_emissions_inventory(emission_factor_id);
CREATE INDEX IF NOT EXISTS idx_tree_inventory_plot ON tree_inventory(plot_id);
CREATE INDEX IF NOT EXISTS idx_underplanting_event_plot ON underplanting_event(plot_id);

-- 030_stakeholder_feedback
CREATE INDEX IF NOT EXISTS idx_stakeholder_feedback_plot ON stakeholder_feedback(plot_id);
CREATE INDEX IF NOT EXISTS idx_stakeholder_feedback_review_reviewer ON stakeholder_feedback_review(reviewer_id);

-- 031_impact_claims_and_cids
CREATE INDEX IF NOT EXISTS idx_stakeholder_outcome_farm ON stakeholder_outcome(farm_id);
CREATE INDEX IF NOT EXISTS idx_impact_claim_farm ON impact_claim(farm_id);
CREATE INDEX IF NOT EXISTS idx_impact_claim_stakeholder_outcome ON impact_claim(stakeholder_outcome_id);
CREATE INDEX IF NOT EXISTS idx_impact_claim_metric ON impact_claim(metric_id);
CREATE INDEX IF NOT EXISTS idx_impact_claim_reviewer ON impact_claim(reviewer_id);
CREATE INDEX IF NOT EXISTS idx_impact_claim_parent ON impact_claim(parent_claim_id);
CREATE INDEX IF NOT EXISTS idx_metric_proposal_reviewed_by ON metric_proposal(reviewed_by);
CREATE INDEX IF NOT EXISTS idx_metric_proposal_metric_def ON metric_proposal(metric_definition_id);

-- 032_ebf_scorecard
CREATE INDEX IF NOT EXISTS idx_ebf_score_rubric_band ON ebf_score(rubric_band_id);

-- 033_ebf_p1_operations
CREATE INDEX IF NOT EXISTS idx_ebf_farm_metric_profile_metric ON ebf_farm_metric_profile(metric_id);
CREATE INDEX IF NOT EXISTS idx_ebf_calibration_session_farm ON ebf_calibration_session(farm_id);
CREATE INDEX IF NOT EXISTS idx_ebf_calibration_decision_pillar ON ebf_calibration_decision(pillar_id);

-- 034_holistic_wellbeing
CREATE INDEX IF NOT EXISTS idx_participatory_action_farm ON participatory_action_record(farm_id);
CREATE INDEX IF NOT EXISTS idx_participatory_action_report_snapshot ON participatory_action_record(report_snapshot_id);

-- 036_capital_efficiency_and_utility
CREATE INDEX IF NOT EXISTS idx_capital_efficiency_farm ON capital_efficiency_scenario(farm_id);
CREATE INDEX IF NOT EXISTS idx_regen_efficiency_farm ON regenerative_efficiency_observation(farm_id);
CREATE INDEX IF NOT EXISTS idx_regen_efficiency_practice_event ON regenerative_efficiency_observation(practice_event_id);
CREATE INDEX IF NOT EXISTS idx_governance_throughput_dao_proposal ON governance_throughput_observation(dao_proposal_id);
CREATE INDEX IF NOT EXISTS idx_capital_provider_farm ON capital_provider_utility_scenario(farm_id);
CREATE INDEX IF NOT EXISTS idx_capital_provider_capital_source ON capital_provider_utility_scenario(capital_source_id);

-- 037_commons_liberation_and_stewardship
CREATE INDEX IF NOT EXISTS idx_time_liberation_farm ON time_liberation_observation(farm_id);
CREATE INDEX IF NOT EXISTS idx_capital_alignment_farm ON capital_alignment_assessment(farm_id);
CREATE INDEX IF NOT EXISTS idx_capital_alignment_capital_source ON capital_alignment_assessment(capital_source_id);
CREATE INDEX IF NOT EXISTS idx_governance_inclusion_dao_proposal ON governance_inclusion_observation(dao_proposal_id);
CREATE INDEX IF NOT EXISTS idx_land_stewardship_farm ON land_stewardship_commitment(farm_id);
CREATE INDEX IF NOT EXISTS idx_land_stewardship_tenure ON land_stewardship_commitment(tenure_rights_assessment_id);

-- 038_gnh_alignment_and_inclusion
CREATE INDEX IF NOT EXISTS idx_gnh_alignment_farm ON gnh_alignment_assessment(farm_id);
CREATE INDEX IF NOT EXISTS idx_cultural_preservation_farm ON cultural_preservation_plan(farm_id);
CREATE INDEX IF NOT EXISTS idx_cultural_preservation_context ON cultural_preservation_plan(cultural_context_record_id);
CREATE INDEX IF NOT EXISTS idx_renewable_energy_farm ON renewable_energy_plan(farm_id);
CREATE INDEX IF NOT EXISTS idx_vulnerable_access_farm ON vulnerable_group_access_plan(farm_id);
CREATE INDEX IF NOT EXISTS idx_foundational_wellbeing_farm ON foundational_wellbeing_observation(farm_id);

-- 039_regenerative_outcomes_and_stewardship
CREATE INDEX IF NOT EXISTS idx_regen_outcome_farm ON regenerative_outcome_summary(farm_id);
CREATE INDEX IF NOT EXISTS idx_community_governance_farm ON community_governance_mechanism(farm_id);
CREATE INDEX IF NOT EXISTS idx_adaptive_stewardship_farm ON adaptive_stewardship_review(farm_id);

-- 040_open_source_capitalist_scaling
CREATE INDEX IF NOT EXISTS idx_farm_launch_economics_milestone ON farm_launch_unit_economics(source_scaling_milestone_id);
CREATE INDEX IF NOT EXISTS idx_perpetual_stress_fin_sustainability ON perpetual_value_stress_test(financial_sustainability_plan_id);

INSERT INTO schema_version (version, description, applied_by)
VALUES ('fk-index-fixes-v1', 'Add missing FK indexes identified by platform audit', 'schema 042')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
