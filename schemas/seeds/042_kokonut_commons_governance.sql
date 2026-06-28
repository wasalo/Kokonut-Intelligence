-- ============================================================
-- 042_kokonut_commons_governance.sql — Kokonut Commons governance metrics and dashboards
-- ============================================================

INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables,
    inclusion_rules, exclusion_rules, unit, data_type, owner, version,
    update_frequency, active, validation_tests, report_usage, deprecation_policy
) VALUES
('anti_capture_policy_count', 'Anti-Capture Policy Count', 'Count of published governance policies with anti-capture safeguards.', 'COUNT anti_capture_governance_policy', ARRAY['anti_capture_governance_policy'], 'Use published policies with public summaries.', 'Exclude promised DAO mechanisms without policy records.', 'count', 'integer', 'Governance Guild', 1, 'quarterly', TRUE, '["policy scope present"]'::jsonb, ARRAY['anti_capture_governance', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('community_veto_enabled', 'Community Veto Enabled', 'Whether a published governance policy documents community veto or rework rights.', 'community_veto_enabled', ARRAY['anti_capture_governance_policy', 'community_governance_mechanism'], 'Use public-safe governance records.', 'Exclude informal or private veto claims.', 'boolean', 'boolean', 'Governance Guild', 1, 'quarterly', TRUE, '["public summary present"]'::jsonb, ARRAY['anti_capture_governance', 'community_governance'], 'Supersede through metric_version before changing public interpretation.'),
('commons_redistribution_pct', 'Commons Redistribution %', 'Scenario or active policy share routed to commons/public-goods purposes.', 'commons_allocation_pct', ARRAY['commons_redistribution_policy', 'financial_sustainability_plan'], 'Use policy-specific allocation percentage.', 'Do not imply majority allocation unless policy is active and published.', 'percentage', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100"]'::jsonb, ARRAY['redistribution_policy', 'financial_sustainability'], 'Supersede through metric_version before changing public interpretation.'),
('operator_or_community_allocation_pct', 'Operator Or Community Allocation %', 'Policy share routed to operators and local cooperatives.', 'operator_allocation_pct + local_cooperative_allocation_pct', ARRAY['commons_redistribution_policy'], 'Use aggregate allocation percentages only.', 'Exclude identity-sensitive recipient records.', 'percentage', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100"]'::jsonb, ARRAY['redistribution_policy'], 'Supersede through metric_version before changing public interpretation.'),
('federation_protocol_count', 'Federation Protocol Count', 'Count of public federation or mutual-aid onboarding protocols.', 'COUNT federation_protocol', ARRAY['federation_protocol'], 'Use published protocols with anti-extractive safeguards.', 'Exclude unsupported live network claims.', 'count', 'integer', 'Governance Guild', 1, 'quarterly', TRUE, '["safeguards documented"]'::jsonb, ARRAY['federation_mutual_aid', 'scaling_roadmap'], 'Supersede through metric_version before changing public interpretation.'),
('mutual_aid_support_count', 'Mutual Aid Support Count', 'Count of mutual-aid commitments listed in public federation protocols.', 'array_length(mutual_aid_commitments)', ARRAY['federation_protocol'], 'Use public protocol commitments.', 'Exclude informal private commitments.', 'count', 'integer', 'Governance Guild', 1, 'quarterly', TRUE, '["commitment text present"]'::jsonb, ARRAY['federation_mutual_aid'], 'Supersede through metric_version before changing public interpretation.'),
('redistribution_mechanism_count', 'Redistribution Mechanism Count', 'Count of proposed, pilot, or active algorithmic redistribution mechanisms.', 'COUNT algorithmic_redistribution_mechanism', ARRAY['algorithmic_redistribution_mechanism'], 'Use public mechanisms with privacy safeguards.', 'Exclude private beneficiary identities and unsupported airdrops.', 'count', 'integer', 'Finance Guild', 1, 'quarterly', TRUE, '["privacy safeguards present"]'::jsonb, ARRAY['algorithmic_redistribution'], 'Supersede through metric_version before changing public interpretation.'),
('participatory_signal_experiment_count', 'Participatory Signal Experiment Count', 'Count of public nontraditional participatory governance signal experiments.', 'COUNT participatory_signal_experiment', ARRAY['participatory_signal_experiment'], 'Use experiments with safety boundaries and decision-binding status.', 'Exclude harmful, identity-exposing, or legally binding claims without review.', 'count', 'integer', 'Governance Guild', 1, 'quarterly', TRUE, '["safety boundaries present"]'::jsonb, ARRAY['participatory_signal'], 'Supersede through metric_version before changing public interpretation.')
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
('a0000000-0000-0000-0000-000000004201', 'Anti-Capture Governance Policies', 'Public-safe anti-plutocratic governance, veto, voting cap, and enforcement policy evidence.', 'anti_capture_governance', NULL, 'dashboards/metabase/sql/52_anti_capture_governance.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000004202', 'Commons Redistribution Policies', 'Flexible public-safe redistribution policy scenarios by farm, DAO, network, or scenario.', 'redistribution_policy', NULL, 'dashboards/metabase/sql/53_redistribution_policy.sql', 1440, 'published', '{"owner":"finance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000004203', 'Federation And Mutual Aid Protocols', 'Public-safe forking, federation, mutual-aid onboarding, and anti-extractive safeguard protocols.', 'federation_mutual_aid', NULL, 'dashboards/metabase/sql/54_federation_mutual_aid.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000004204', 'Algorithmic Redistribution Mechanisms', 'Public-safe redistribution mechanisms such as targeted grants, rebates, matching, and operator support.', 'algorithmic_redistribution', NULL, 'dashboards/metabase/sql/55_algorithmic_redistribution.sql', 1440, 'published', '{"owner":"finance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000004205', 'Participatory Signal Experiments', 'Public-safe advisory meme, vibes, sentiment, story, or ranked-preference experiments with safety boundaries.', 'participatory_signal', NULL, 'dashboards/metabase/sql/56_participatory_signal.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
