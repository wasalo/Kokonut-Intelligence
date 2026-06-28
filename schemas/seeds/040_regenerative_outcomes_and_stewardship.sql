-- ============================================================
-- 040_regenerative_outcomes_and_stewardship.sql — Regenerative outcomes metrics and dashboards
-- ============================================================

INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables,
    inclusion_rules, exclusion_rules, unit, data_type, owner, version,
    update_frequency, active, validation_tests, report_usage, deprecation_policy
) VALUES
('hectares_restored', 'Hectares Restored', 'Area under documented regenerative restoration or stewardship during the reporting period.', 'hectares_restored from regenerative_outcome_summary', ARRAY['regenerative_outcome_summary', 'farm_zone', 'underplanting_event'], 'Use published outcome summaries with source methodology.', 'Exclude planned areas without intervention evidence.', 'hectares', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["value >= 0", "methodology documented"]'::jsonb, ARRAY['regenerative_outcomes', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('species_diversity_delta', 'Species Diversity Delta', 'Change in species count or diversity index between baseline and latest observations.', 'latest_species_count - baseline_species_count or latest_shannon - baseline_shannon', ARRAY['regenerative_outcome_summary', 'species_observation'], 'Use baseline and latest observations from governed records.', 'Exclude unverified species lists or raw private observations.', 'delta', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["baseline present", "latest present"]'::jsonb, ARRAY['regenerative_outcomes', 'ebf_scorecard'], 'Supersede through metric_version before changing public interpretation.'),
('soil_carbon_delta_t_ha', 'Soil Carbon Delta t/ha', 'Change in soil carbon tonnes per hectare between baseline and latest measurement.', 'latest_soil_carbon_t_ha - baseline_soil_carbon_t_ha', ARRAY['regenerative_outcome_summary', 'soil_carbon_measurement', 'soil_sample'], 'Use reviewed baseline and latest measurements.', 'Exclude public carbon-credit claims without Level 6 evidence.', 't/ha', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["baseline present", "latest present"]'::jsonb, ARRAY['regenerative_outcomes', 'climate_impact', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('tree_survival_rate_pct', 'Tree Survival Rate %', 'Share of planted or inventoried trees/underplantings surviving at latest survey.', 'trees_surviving_count / trees_planted_count * 100', ARRAY['regenerative_outcome_summary', 'tree_inventory', 'underplanting_event'], 'Use published or verified survival counts.', 'Exclude estimates without survey date.', 'percentage', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100", "survey present"]'::jsonb, ARRAY['regenerative_outcomes', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('community_governance_participation_pct', 'Community Governance Participation %', 'Share of eligible or invited stakeholder groups represented in a documented governance mechanism.', 'represented_groups / target_groups * 100', ARRAY['community_governance_mechanism', 'governance_inclusion_observation'], 'Use public-safe group summaries.', 'Exclude raw private identity records.', 'percentage', 'numeric', 'Governance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100", "privacy-safe groups"]'::jsonb, ARRAY['community_governance', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('replication_readiness_score', 'Replication Readiness Score', 'Reviewer-assessed 0-10 readiness score based on ecological, cultural, governance, infrastructure, and evidence prerequisites.', 'Reviewer-normalized 0-10', ARRAY['replication_readiness_assessment', 'scaling_roadmap_milestone'], 'Use published readiness assessments with barriers and enablers.', 'Exclude unlimited-scaling claims.', 'score_0_10', 'numeric', 'Governance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 10", "barriers documented"]'::jsonb, ARRAY['replication_readiness', 'scaling_roadmap', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('adaptive_stewardship_action_completion_pct', 'Adaptive Stewardship Action Completion %', 'Share of corrective stewardship actions completed in the review period.', 'completed_corrective_actions / corrective_actions * 100', ARRAY['adaptive_stewardship_review'], 'Use published reviews with triggers and responsible role.', 'Exclude actions without review cadence.', 'percentage', 'numeric', 'Governance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100", "review cadence present"]'::jsonb, ARRAY['adaptive_stewardship', 'green_paper'], 'Supersede through metric_version before changing public interpretation.')
ON CONFLICT (metric_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    formula = EXCLUDED.formula,
    source_tables = EXCLUDED.source_tables,
    inclusion_rules = EXCLUDED.inclusion_rules,
    exclusion_rules = EXCLUDED.exclusion_rules,
    unit = EXCLUDED.unit,
    data_type = EXCLUDED.data_type,
    owner = EXCLUDED.owner,
    update_frequency = EXCLUDED.update_frequency,
    active = EXCLUDED.active,
    validation_tests = EXCLUDED.validation_tests,
    report_usage = EXCLUDED.report_usage,
    deprecation_policy = EXCLUDED.deprecation_policy;

INSERT INTO dashboard_dataset (id, name, description, dataset_type, location_id, query_sql, refresh_interval_minutes, status, metadata) VALUES
('a0000000-0000-0000-0000-000000004001', 'Regenerative Outcomes Summary', 'Grant-facing ecological and social outcome summary with baseline/latest values and confidence labels.', 'regenerative_outcomes', NULL, 'dashboards/metabase/sql/44_regenerative_outcomes.sql', 1440, 'published', '{"owner":"impact_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000004002', 'Community Governance Mechanisms', 'Public-safe farm/network decision methods, power distribution, participation cadence, and escalation paths.', 'community_governance', NULL, 'dashboards/metabase/sql/45_community_governance.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000004003', 'Replication Readiness Summary', 'Public-safe readiness, barriers, enablers, support structures, and minimum evidence maturity for replication.', 'replication_readiness', NULL, 'dashboards/metabase/sql/46_replication_readiness.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000004004', 'Adaptive Stewardship Summary', 'Public-safe stewardship review triggers, corrective actions, cadence, completion, and funding continuity.', 'adaptive_stewardship', NULL, 'dashboards/metabase/sql/47_adaptive_stewardship.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
