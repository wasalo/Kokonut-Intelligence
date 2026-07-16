-- 100_pest_advisory_rules.sql — IPM-specific advisory rules

INSERT INTO advisory_rule (
    id, name, rule_type, domain, priority, conditions,
    recommendation_template, severity, auto_generate, requires_approval,
    cooldown_hours, max_per_day, status
) VALUES
('a0000000-0000-0000-0000-000000000100', 'Pest Lifecycle Stage Alert', 'threshold', 'pest_management', 80,
 '{"metric":"pest_lifecycle_stage","operator":"gte","threshold":0}'::jsonb,
 'Pest {pest_name} has entered the {lifecycle_stage} stage. Increase scouting and review targeted IPM intervention.', 'warning', TRUE, TRUE, 24, 5, 'active'),
('a0000000-0000-0000-0000-000000000101', 'Scouting Schedule Overdue', 'threshold', 'pest_management', 70,
 '{"metric":"scouting_overdue_count","operator":"gt","threshold":0}'::jsonb,
 '{overdue_count} scouting schedule(s) are overdue. Dispatch a scout and record the missing observation.', 'warning', TRUE, TRUE, 24, 5, 'active'),
('a0000000-0000-0000-0000-000000000102', 'Spray Window Opportunity', 'threshold', 'crop_protection', 60,
 '{"metric":"spray_window_match","operator":"gt","threshold":0}'::jsonb,
 'Spray-suitable weather aligns with above-threshold pest pressure. Review the forecast and IPM safeguards.', 'warning', TRUE, TRUE, 24, 5, 'active'),
('a0000000-0000-0000-0000-000000000103', 'Resistance Rotation Warning', 'threshold', 'pest_management', 80,
 '{"metric":"resistance_rotation_violation","operator":"gt","threshold":0}'::jsonb,
 'A mode-of-action rotation violation was detected. Review a compatible alternative before application.', 'warning', TRUE, TRUE, 24, 5, 'active'),
('a0000000-0000-0000-0000-000000000104', 'Biocontrol Follow-up Due', 'threshold', 'pest_management', 50,
 '{"metric":"biocontrol_followup_due","operator":"gte","threshold":14}'::jsonb,
 'Biocontrol follow-up is due. Re-scout the treated area and record effectiveness before further action.', 'info', TRUE, TRUE, 24, 5, 'active')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    rule_type = EXCLUDED.rule_type,
    domain = EXCLUDED.domain,
    priority = EXCLUDED.priority,
    conditions = EXCLUDED.conditions,
    recommendation_template = EXCLUDED.recommendation_template,
    severity = EXCLUDED.severity,
    auto_generate = EXCLUDED.auto_generate,
    requires_approval = EXCLUDED.requires_approval,
    cooldown_hours = EXCLUDED.cooldown_hours,
    max_per_day = EXCLUDED.max_per_day,
    status = EXCLUDED.status,
    updated_at = NOW();
