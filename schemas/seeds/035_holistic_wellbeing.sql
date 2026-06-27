-- ============================================================
-- Seed: Holistic well-being, cultural heritage, and participation metrics
-- ============================================================

INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables,
    inclusion_rules, exclusion_rules, unit, data_type, owner, version,
    update_frequency, active, validation_tests, report_usage, deprecation_policy
) VALUES
('operator_capability_score', 'Operator Capability Score', 'Composite signal for whether farm operators are gaining skills, confidence, and practical ability to operate regenerative systems.', 'Reviewed training, feedback, and practice records normalized to 0-10', ARRAY['wellbeing_metric_observation', 'stakeholder_feedback', 'stakeholder_outcome', 'farm_practice_event'], 'Use reviewed or published aggregate records only.', 'Exclude raw private feedback from public reporting.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["0 <= value <= 10", "source records reviewed"]'::jsonb, ARRAY['green_paper', 'wellbeing_report', 'cids_indicator_report'], 'Supersede through metric_version before changing public interpretation.'),
('local_language_reporting_coverage', 'Local-Language Reporting Coverage', 'Share of operator-facing reports or summaries available in the local working language for a reporting period.', 'local_language_summaries_delivered / expected_operator_summaries * 100', ARRAY['wellbeing_metric_observation', 'report_snapshot', 'stakeholder_feedback'], 'Use report delivery records and consent-safe feedback only.', 'Exclude private raw feedback text.', 'percentage', 'percentage', 'Impact Guild', 1, 'monthly', TRUE, '["0 <= value <= 100", "language recorded"]'::jsonb, ARRAY['green_paper', 'wellbeing_report'], 'Supersede through metric_version before changing public interpretation.'),
('community_trust_signal', 'Community Trust Signal', 'Aggregate public-safe signal from stakeholder feedback, privacy requests, and resolved community concerns.', 'Privacy-safe stakeholder feedback balance and review coverage normalized to 0-10', ARRAY['stakeholder_feedback', 'stakeholder_feedback_review', 'wellbeing_metric_observation'], 'Use aggregate, consent-safe feedback and review counts.', 'Exclude raw private feedback and household-level observations.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["0 <= value <= 10", "privacy-safe aggregation"]'::jsonb, ARRAY['green_paper', 'wellbeing_report'], 'Supersede through metric_version before changing public interpretation.'),
('worker_safety_signal', 'Worker Safety Signal', 'Aggregate signal for safe working conditions, unresolved harms, and corrective action follow-through.', 'Safety observations and unresolved harm counts normalized to 0-10', ARRAY['stakeholder_feedback', 'participatory_action_record', 'wellbeing_metric_observation'], 'Use reviewed safety and harm signals only.', 'Exclude unreviewed allegations from public claims.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'quarterly', TRUE, '["0 <= value <= 10", "harms reviewed before public use"]'::jsonb, ARRAY['green_paper', 'wellbeing_report'], 'Supersede through metric_version before changing public interpretation.'),
('training_access_hours', 'Training Access Hours', 'Hours of practical training, field learning, or operator capacity building made available to participants.', 'SUM(training_hours)', ARRAY['labor_event', 'guild_contribution', 'wellbeing_metric_observation'], 'Use governed training or contribution records.', 'Exclude informal estimates without source notes.', 'hours', 'numeric', 'Impact Guild', 1, 'monthly', TRUE, '["value >= 0", "source lineage present"]'::jsonb, ARRAY['green_paper', 'wellbeing_report'], 'Supersede through metric_version before changing public interpretation.'),
('benefit_distribution_transparency', 'Benefit Distribution Transparency', 'Signal that benefit allocation, public goods commitments, and value-flow rules are visible to stakeholders.', 'Published benefit allocation evidence normalized to 0-10', ARRAY['value_flow_event', 'governance_event', 'participatory_action_record', 'wellbeing_metric_observation'], 'Use published public-goods, value-flow, and governance records.', 'Exclude private household-level distribution notes.', 'score_0_10', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 10", "public summary present"]'::jsonb, ARRAY['green_paper', 'wellbeing_report'], 'Supersede through metric_version before changing public interpretation.'),
('cultural_capital_activity_count', 'Cultural Capital Activity Count', 'Count of governed cultural context records, heritage species records, local-language summaries, or community story records.', 'COUNT(cultural_context_record) WHERE status = published', ARRAY['cultural_context_record'], 'Use published, consented public summaries only for public reporting.', 'Exclude private cultural knowledge and non-consented stories.', 'count', 'count', 'Impact Guild', 1, 'quarterly', TRUE, '["value >= 0", "public records consented"]'::jsonb, ARRAY['green_paper', 'wellbeing_report', 'cids_indicator_report'], 'Supersede through metric_version before changing public interpretation.')
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
('a0000000-0000-0000-0000-000000003501', 'Holistic Well-being Summary', 'Public-safe cultural context and well-being metric summary by location.', 'holistic_wellbeing', NULL, 'dashboards/metabase/sql/26_holistic_wellbeing.sql', 1440, 'published', '{"owner":"impact_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003502', 'Participatory Governance Traceability', 'Public-safe trace from stakeholder feedback to metric proposals and actions.', 'participatory_governance', NULL, 'dashboards/metabase/sql/27_participatory_governance.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
