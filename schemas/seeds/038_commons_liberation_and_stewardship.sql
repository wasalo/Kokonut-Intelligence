-- ============================================================
-- 038_commons_liberation_and_stewardship.sql — Commons liberation metrics and dashboards
-- ============================================================

INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables,
    inclusion_rules, exclusion_rules, unit, data_type, owner, version,
    update_frequency, active, validation_tests, report_usage, deprecation_policy
) VALUES
('operator_time_reclaimed_hours', 'Operator Time Reclaimed Hours', 'Hours of operator, steward, or community time reclaimed through workflow simplification, automation, agent assistance, or reduced reporting burden.', 'baseline_hours - observed_hours', ARRAY['time_liberation_observation', 'labor_event', 'ai_summary', 'report_snapshot'], 'Use published observations with documented baseline and observed hours.', 'Exclude unreviewed productivity claims or surveillance-derived private labor data.', 'hours', 'numeric', 'Impact Guild', 1, 'monthly', TRUE, '["value >= 0", "baseline documented"]'::jsonb, ARRAY['time_liberation', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('field_reporting_burden_reduction_pct', 'Field Reporting Burden Reduction %', 'Observed reduction in administrative or field-reporting time after tooling, templates, agents, or local-language reporting changes.', '(baseline_hours - observed_hours) / baseline_hours * 100', ARRAY['time_liberation_observation'], 'Use governed observations with operator-facing public summary.', 'Exclude claims without operator-visible benefit.', 'percentage', 'numeric', 'Impact Guild', 1, 'monthly', TRUE, '["-100 <= value <= 100", "baseline_hours > 0"]'::jsonb, ARRAY['time_liberation', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('aligned_capital_share_pct', 'Aligned Capital Share %', 'Share of assessed capital sources classified as aligned or conditionally aligned with community-control and public-goods terms.', 'aligned_or_conditional_assessments / total_assessments * 100', ARRAY['capital_alignment_assessment', 'capital_source'], 'Use published capital alignment assessments only.', 'Exclude private terms unless summarized safely.', 'percentage', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100", "assessment status published"]'::jsonb, ARRAY['capital_alignment', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('extractive_capital_risk_count', 'Extractive Capital Risk Count', 'Count of published capital alignment assessments with high or critical extractive-risk level.', 'COUNT(capital_alignment_assessment WHERE extractive_risk_level IN high, critical)', ARRAY['capital_alignment_assessment'], 'Use published assessments with public summaries.', 'Exclude unreviewed allegations and private negotiations.', 'count', 'count', 'Finance Guild', 1, 'quarterly', TRUE, '["value >= 0", "risk level present"]'::jsonb, ARRAY['capital_alignment', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('governance_representation_coverage_pct', 'Governance Representation Coverage %', 'Share of intended stakeholder or contributor groups represented in a governed committee, guild, review, or publication process.', 'represented_groups / target_groups * 100', ARRAY['governance_inclusion_observation'], 'Use public-safe representation summaries.', 'Exclude raw identity details and private protected-class records.', 'percentage', 'numeric', 'Governance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100", "privacy-safe representation"]'::jsonb, ARRAY['governance_inclusion', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('pseudonymous_participation_enabled', 'Pseudonymous Participation Enabled', 'Boolean signal that a governance body allows privacy-preserving or pseudonymous participation where appropriate.', 'pseudonymous_participation_enabled', ARRAY['governance_inclusion_observation'], 'Use published governance inclusion observations.', 'Exclude anonymous participation that bypasses safety or accountability gates.', 'boolean', 'boolean', 'Governance Guild', 1, 'quarterly', TRUE, '["value in true,false"]'::jsonb, ARRAY['governance_inclusion', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('land_stewardship_commitment_count', 'Land Stewardship Commitment Count', 'Count of published stewardship commitments that document anti-speculation terms, community benefit rights, or commons transition paths.', 'COUNT(land_stewardship_commitment WHERE status = published)', ARRAY['land_stewardship_commitment', 'tenure_rights_assessment'], 'Use published stewardship commitments and tenure assessments.', 'Exclude unsupported claims of ownership transfer or landlord abolition.', 'count', 'count', 'Governance Guild', 1, 'quarterly', TRUE, '["value >= 0", "public summary present"]'::jsonb, ARRAY['land_stewardship', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('landlord_dependency_risk_level', 'Landlord Dependency Risk Level', 'Published qualitative risk signal for dependence on landlord, lease, or speculative ownership structures.', 'Reviewer-assessed risk level', ARRAY['land_stewardship_commitment', 'tenure_rights_assessment'], 'Use reviewed tenure and stewardship evidence.', 'Exclude legal conclusions without source evidence.', 'risk_level', 'text', 'Governance Guild', 1, 'quarterly', TRUE, '["risk in low,medium,high,critical,unknown"]'::jsonb, ARRAY['land_stewardship', 'green_paper'], 'Supersede through metric_version before changing public interpretation.')
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
('a0000000-0000-0000-0000-000000003801', 'Time Liberation Summary', 'Public-safe time reclaimed, reporting-burden reduction, and automation/agent support observations.', 'time_liberation', NULL, 'dashboards/metabase/sql/35_time_liberation.sql', 1440, 'published', '{"owner":"impact_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003802', 'Capital Alignment Summary', 'Public-safe capital alignment, extractive-risk, community-control, and commons reinvestment summary.', 'capital_alignment', NULL, 'dashboards/metabase/sql/36_capital_alignment.sql', 1440, 'published', '{"owner":"finance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003803', 'Governance Inclusion Summary', 'Public-safe governance representation, pseudonymous participation, and missing-group summary.', 'governance_inclusion', NULL, 'dashboards/metabase/sql/37_governance_inclusion.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003804', 'Land Stewardship Summary', 'Public-safe stewardship model, anti-speculation terms, community benefit rights, and landlord-dependency risk.', 'land_stewardship', NULL, 'dashboards/metabase/sql/38_land_stewardship.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
