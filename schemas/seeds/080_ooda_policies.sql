-- ============================================================
-- 080_ooda_policies.sql — Default OODA decision policies
-- ============================================================
-- Seeds the 5 default decision policies for the OODA loop.

INSERT INTO decision_policy (
    policy_name, policy_type, description, is_enabled, priority,
    trigger_event_type, trigger_situation_grade, trigger_dimension,
    trigger_score_min, trigger_score_max,
    action_type, action_config,
    requires_approval, approval_role,
    cooldown_minutes, max_executions_per_day, risk_level
) VALUES
(
    'critical_situation_intervention',
    'rule',
    'Create intervention draft when situation is critical',
    TRUE, 100,
    NULL, 'critical', NULL,
    NULL, NULL,
    'create_intervention_draft',
    '{"priority": "high", "draft_type": "emergency_intervention"}'::jsonb,
    TRUE, 'admin',
    120, 5, 'high'
),
(
    'warning_situation_alert',
    'rule',
    'Send alert notification when situation is warning',
    TRUE, 80,
    NULL, 'warning', NULL,
    NULL, NULL,
    'send_alert_notification',
    '{"channel": "directus", "severity": "warning", "include_dimensions": true}'::jsonb,
    TRUE, 'operator',
    60, 10, 'medium'
),
(
    'climate_dimension_critical',
    'rule',
    'Trigger reassessment when climate risk is critical',
    TRUE, 90,
    NULL, NULL, 'climate',
    NULL, 30.0,
    'trigger_reassessment',
    '{"assessment_type": "deep", "focus_frameworks": ["climate_risk", "ecological_modeling"]}'::jsonb,
    TRUE, 'operator',
    30, 8, 'medium'
),
(
    'anomaly_cluster_investigation',
    'rule',
    'Create data stream post when anomaly cluster detected',
    TRUE, 70,
    'anomaly_cluster', NULL, NULL,
    NULL, NULL,
    'create_data_stream_post',
    '{"post_type": "monitoring_report", "auto_generate_summary": true}'::jsonb,
    TRUE, 'operator',
    45, 6, 'low'
),
(
    'adaptive_sampling_high_uncertainty',
    'rule',
    'Increase sampling rate when uncertainty is high',
    TRUE, 60,
    NULL, NULL, NULL,
    NULL, 40.0,
    'adjust_sampling_rate',
    '{"adjustment": "increase", "factor": 0.5, "reason": "high_uncertainty"}'::jsonb,
    TRUE, 'operator',
    240, 4, 'low'
)
ON CONFLICT (policy_name) DO NOTHING;
