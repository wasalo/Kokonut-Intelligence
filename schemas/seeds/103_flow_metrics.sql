-- ============================================================
-- 103_flow_metrics.sql - VSM flow / lead-time / quality metrics
-- ============================================================
-- Governed metric definitions for value-stream analysis of the
-- data -> governance -> publication pipeline. These are computed as
-- DRAFT metric_value rows by the metric engine; a human must verify
-- them before they are exposed in public aggregate views.

INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables,
    inclusion_rules, exclusion_rules, unit, data_type, owner, version,
    update_frequency, active, category
) VALUES
(
    'governed_lead_time_days',
    'Governed Lead Time (days)',
    'Average elapsed time from a record first entering draft to it reaching published, for lifecycle entities at a location.',
    'avg(epoch(published_at - first_draft_at) / 86400)',
    ARRAY['lifecycle_transition','data_stream_post','ai_summary','impact_claim','report_snapshot','stakeholder_feedback','farm_activity','harvest_event','agent_task'],
    'Entity reached published within the reporting period.',
    'Entities never published are excluded.',
    'days', 'numeric', 'platform-integrity', 1, 'daily', TRUE, 'lead_time'
),
(
    'first_time_through_yield_pct',
    'First-Time-Through Yield (%)',
    'Share of lifecycle entities that reached published without ever entering a rejected state.',
    'published_without_rejection / published * 100',
    ARRAY['lifecycle_transition'],
    'Entity reached published within the reporting period.',
    'Entities never published are excluded.',
    'percent', 'percentage', 'platform-integrity', 1, 'daily', TRUE, 'quality'
),
(
    'rework_rate_pct',
    'Rework Rate (%)',
    'Share of lifecycle entities that reached published but required at least one rejected (rework) transition.',
    'published_with_rejection / published * 100',
    ARRAY['lifecycle_transition'],
    'Entity reached published within the reporting period.',
    'Entities never published are excluded.',
    'percent', 'percentage', 'platform-integrity', 1, 'daily', TRUE, 'quality'
)
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
    category = EXCLUDED.category,
    updated_at = now();
