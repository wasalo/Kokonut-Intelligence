-- ============================================================
-- 039_gnh_alignment_and_inclusion.sql — GNH alignment metrics and dashboards
-- ============================================================

INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables,
    inclusion_rules, exclusion_rules, unit, data_type, owner, version,
    update_frequency, active, validation_tests, report_usage, deprecation_policy
) VALUES
('gnh_alignment_score', 'GNH Alignment Score', 'Reviewer-assessed 0-10 alignment signal by Gross National Happiness domain using governed evidence.', 'Reviewer-normalized 0-10 by domain', ARRAY['gnh_alignment_assessment'], 'Use published domain assessments with safeguards and gaps.', 'Exclude Bhutan-readiness claims without local review.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["0 <= value <= 10", "domain present"]'::jsonb, ARRAY['gnh_alignment', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('cultural_preservation_activity_count', 'Cultural Preservation Activity Count', 'Count of published cultural preservation plans or implemented cultural integration activities.', 'COUNT(cultural_preservation_plan WHERE status = published)', ARRAY['cultural_preservation_plan', 'cultural_context_record'], 'Use consented and published public summaries only.', 'Exclude private cultural knowledge and non-consented stories.', 'count', 'count', 'Impact Guild', 1, 'quarterly', TRUE, '["value >= 0", "consent protocol present"]'::jsonb, ARRAY['cultural_preservation', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('local_language_access_coverage_pct', 'Local-Language Access Coverage %', 'Share of operator-facing or community-facing evidence workflows available in the local working language.', 'local_language_accessible_workflows / target_workflows * 100', ARRAY['cultural_preservation_plan', 'wellbeing_metric_observation', 'report_snapshot'], 'Use reviewed local-language plans and delivery records.', 'Exclude unsupported translation promises.', 'percentage', 'numeric', 'Impact Guild', 1, 'monthly', TRUE, '["0 <= value <= 100", "language present"]'::jsonb, ARRAY['cultural_preservation', 'holistic_wellbeing', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('renewable_energy_share_pct', 'Renewable Energy Share %', 'Planned or implemented share of farm energy use served by renewable sources.', 'renewable_kwh / total_energy_kwh * 100', ARRAY['renewable_energy_plan'], 'Use published renewable energy plans and mark planned versus implemented status.', 'Exclude implemented claims without operational evidence.', 'percentage', 'numeric', 'Climate Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100", "implementation_status present"]'::jsonb, ARRAY['renewable_energy', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('fossil_energy_displacement_estimate', 'Fossil Energy Displacement Estimate', 'Estimated annual CO2e displacement from planned or implemented renewable energy infrastructure.', 'renewable_kwh * fossil_grid_or_generator_factor', ARRAY['renewable_energy_plan', 'ghg_emission_factor'], 'Use conservative estimates and publish implementation status.', 'Exclude carbon-credit claims without third-party verification.', 'tCO2e', 'numeric', 'Climate Guild', 1, 'quarterly', TRUE, '["value >= 0", "methodology documented"]'::jsonb, ARRAY['renewable_energy', 'climate_impact', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('vulnerable_group_access_coverage_pct', 'Vulnerable Group Access Coverage %', 'Share of identified access barriers addressed by published accommodations or participation pathways.', 'addressed_access_barriers / identified_access_barriers * 100', ARRAY['vulnerable_group_access_plan', 'governance_inclusion_observation'], 'Use public-safe group summaries, not raw identity data.', 'Exclude private disability, household, or protected-class details.', 'percentage', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100", "privacy-safe grouping"]'::jsonb, ARRAY['vulnerable_access', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('foundational_wellbeing_score', 'Foundational Well-being Score', 'Public-safe 0-10 signal for happiness, peace, safety, food security, basic needs, dignity, or belonging.', 'Reviewer-normalized score by wellbeing domain', ARRAY['foundational_wellbeing_observation', 'wellbeing_metric_observation', 'stakeholder_feedback'], 'Use published or aggregate consent-safe observations.', 'Exclude raw private feedback and household-level details.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["0 <= value <= 10", "domain present"]'::jsonb, ARRAY['foundational_wellbeing', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('peace_and_safety_signal', 'Peace And Safety Signal', 'Public-safe signal for perceived safety, conflict reduction, and peaceful participation in farm or governance processes.', 'Reviewed safety and peace observations normalized to 0-10', ARRAY['foundational_wellbeing_observation', 'wellbeing_metric_observation', 'stakeholder_feedback'], 'Use reviewed aggregate or published summaries.', 'Exclude unreviewed allegations or private raw safety reports.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["0 <= value <= 10", "harms reviewed before public use"]'::jsonb, ARRAY['foundational_wellbeing', 'green_paper'], 'Supersede through metric_version before changing public interpretation.')
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
('a0000000-0000-0000-0000-000000003901', 'GNH Alignment Summary', 'Public-safe Gross National Happiness domain alignment summary with safeguards and gaps.', 'gnh_alignment', NULL, 'dashboards/metabase/sql/39_gnh_alignment.sql', 1440, 'published', '{"owner":"impact_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003902', 'Cultural Preservation Summary', 'Public-safe cultural preservation, local-language, consent, and local-reviewer planning summary.', 'cultural_preservation', NULL, 'dashboards/metabase/sql/40_cultural_preservation.sql', 1440, 'published', '{"owner":"impact_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003903', 'Renewable Energy Summary', 'Public-safe renewable energy plan summary with planned versus implemented status.', 'renewable_energy', NULL, 'dashboards/metabase/sql/41_renewable_energy.sql', 1440, 'published', '{"owner":"climate_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003904', 'Vulnerable Access Summary', 'Public-safe vulnerable group access, accommodations, and participation pathway planning summary.', 'vulnerable_access', NULL, 'dashboards/metabase/sql/42_vulnerable_access.sql', 1440, 'published', '{"owner":"impact_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003905', 'Foundational Well-being Summary', 'Public-safe happiness, peace, safety, basic needs, dignity, and belonging signals.', 'foundational_wellbeing', NULL, 'dashboards/metabase/sql/43_foundational_wellbeing.sql', 1440, 'published', '{"owner":"impact_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
