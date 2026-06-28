-- ============================================================
-- 041_open_source_capitalist_scaling.sql — Open Source Capitalist metrics and dashboards
-- ============================================================

INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables,
    inclusion_rules, exclusion_rules, unit, data_type, owner, version,
    update_frequency, active, validation_tests, report_usage, deprecation_policy
) VALUES
('farm_launch_cost_usd', 'Farm Launch Cost USD', 'Total estimated setup, first-year operating, and verification overhead cost for launching one or more farms.', 'total_launch_cost_usd from farm_launch_unit_economics', ARRAY['farm_launch_unit_economics', 'scaling_roadmap_milestone', 'financial_sustainability_plan'], 'Use published launch economics with public assumptions.', 'Exclude private capital terms and unsupported farm-count claims.', 'USD', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["value >= 0", "assumptions documented"]'::jsonb, ARRAY['scaling_economics', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('cost_per_planned_farm_usd', 'Cost Per Planned Farm USD', 'Estimated launch capital per planned farm in a published scaling target or launch economics record.', 'total_launch_cost_usd / planned_farm_count', ARRAY['farm_launch_unit_economics', 'network_scaling_target'], 'Use records with planned farm count greater than zero.', 'Exclude already-operating farm claims without governed registry evidence.', 'USD/farm', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["value >= 0", "planned_farm_count > 0"]'::jsonb, ARRAY['scaling_economics', 'scaling_roadmap'], 'Supersede through metric_version before changing public interpretation.'),
('projected_roi_pct', 'Projected ROI %', 'Scenario-based projected return on deployed launch capital.', 'projected_annual_noi_usd / total_launch_cost_usd * 100', ARRAY['farm_launch_unit_economics', 'capital_efficiency_scenario'], 'Use planning scenarios with explicit limitations.', 'Exclude guaranteed-return, securities, or private capital claims.', 'percentage', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["scenario limitation present"]'::jsonb, ARRAY['scaling_economics', 'capital_efficiency'], 'Supersede through metric_version before changing public interpretation.'),
('cost_per_beneficiary_usd', 'Cost Per Beneficiary USD', 'Estimated launch cost divided by expected public-safe beneficiary count.', 'total_launch_cost_usd / expected_beneficiary_count', ARRAY['farm_launch_unit_economics', 'regenerative_outcome_summary'], 'Use aggregate beneficiary counts only.', 'Exclude household-level or identity-sensitive beneficiary data.', 'USD/beneficiary', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["value >= 0", "aggregate beneficiary count"]'::jsonb, ARRAY['scaling_economics', 'regenerative_outcomes'], 'Supersede through metric_version before changing public interpretation.'),
('cost_per_hectare_restored_usd', 'Cost Per Hectare Restored USD', 'Estimated launch cost divided by planned or documented regenerative hectares.', 'total_launch_cost_usd / planned_hectares', ARRAY['farm_launch_unit_economics', 'regenerative_outcome_summary'], 'Use documented hectares or published planned hectares.', 'Exclude unverified expansion acreage.', 'USD/hectare', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["value >= 0", "hectares > 0"]'::jsonb, ARRAY['scaling_economics', 'regenerative_outcomes'], 'Supersede through metric_version before changing public interpretation.'),
('downside_runway_months', 'Downside Runway Months', 'Runway remaining under a published stress-test scenario.', 'downside_runway_months from perpetual_value_stress_test', ARRAY['perpetual_value_stress_test', 'financial_sustainability_plan'], 'Use stress tests with explicit assumptions and mitigation actions.', 'Exclude unstated or private financing assumptions.', 'months', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["value >= 0", "stress_type present"]'::jsonb, ARRAY['perpetual_value_stress', 'financial_sustainability'], 'Supersede through metric_version before changing public interpretation.'),
('adoption_barrier_resolution_pct', 'Adoption Barrier Resolution %', 'Share of published adoption barriers resolved or actively mitigating.', '(resolved + mitigating barriers) / total barriers * 100', ARRAY['adoption_barrier_assessment'], 'Use published barrier assessments grouped by scope/category.', 'Exclude raw private stakeholder concerns.', 'percentage', 'numeric', 'Governance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100", "barrier category present"]'::jsonb, ARRAY['adoption_barriers', 'replication_readiness'], 'Supersede through metric_version before changing public interpretation.'),
('open_source_artifact_reuse_count', 'Open Source Artifact Reuse Count', 'Observed or documented reuse count for published open-source impact artifacts.', 'reuse_count from open_source_impact_artifact', ARRAY['open_source_impact_artifact'], 'Use artifacts with repository path or public URL.', 'Exclude private work products or unsupported external integrations.', 'count', 'integer', 'Technology Guild', 1, 'quarterly', TRUE, '["value >= 0", "artifact published"]'::jsonb, ARRAY['open_source_impact', 'green_paper'], 'Supersede through metric_version before changing public interpretation.')
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
('a0000000-0000-0000-0000-000000004101', 'Scaling Economics Summary', 'Public-safe launch cost, cost-per-farm, cost-per-hectare, cost-per-beneficiary, ROI, and payback scenarios.', 'scaling_economics', NULL, 'dashboards/metabase/sql/48_scaling_economics.sql', 1440, 'published', '{"owner":"finance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000004102', 'Adoption Barriers Summary', 'Public-safe onboarding, regulatory, cultural, market, DAO, capital, technical, and evidence-quality barriers.', 'adoption_barriers', NULL, 'dashboards/metabase/sql/49_adoption_barriers.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000004103', 'Perpetual Value Stress Tests', 'Public-safe downside runway, NOI, solvency, and mitigation scenario evidence.', 'perpetual_value_stress', NULL, 'dashboards/metabase/sql/50_perpetual_value_stress.sql', 1440, 'published', '{"owner":"finance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000004104', 'Open Source Impact Artifacts', 'Public-safe open-source schemas, dashboards, reports, agents, contracts, playbooks, and export mappings with reuse signals.', 'open_source_impact', NULL, 'dashboards/metabase/sql/51_open_source_impact.sql', 1440, 'published', '{"owner":"technology_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
