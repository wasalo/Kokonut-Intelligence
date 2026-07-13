-- 100_pest_advisory_rules.sql
-- IPM-specific advisory rules for lifecycle-aware pest management

BEGIN;

INSERT INTO advisory_rule (
    id, name, rule_type, domain, metric_source,
    threshold, operator, severity, enabled, metadata
) VALUES
    ('a0000000-0000-0000-0000-000000000100',
     'Pest Lifecycle Stage Alert', 'threshold', 'pest_management',
     'pest_lifecycle_stage',
     0, '>=', 'high', TRUE,
     '{"description":"Alert when degree-day tracking shows pest entering most damaging lifecycle stage","action":"Review scouting data and prepare targeted intervention","template":"Pest {pest_name} has entered {lifecycle_stage} stage at {location_name}. This is typically the most damaging stage. Current cumulative degree-days: {cumulative_dd}. Scouting frequency should increase."}'::jsonb),

    ('a0000000-0000-0000-0000-000000000101',
     'Scouting Schedule Overdue', 'threshold', 'pest_management',
     'scouting_overdue_count',
     0, '>', 'moderate', TRUE,
     '{"description":"Alert when scheduled scouting is overdue","action":"Dispatch scout to scheduled fields","template":"{overdue_count} scouting schedule(s) overdue at {location_name} for {pest_name}. Last scouted: {days_since} days ago (frequency: every {frequency_days} days). Missing scouting data undermines IPM decision-making."}'::jsonb),

    ('a0000000-0000-0000-0000-000000000102',
     'Spray Window Opportunity', 'threshold', 'pest_management',
     'spray_window_match',
     0, '>', 'moderate', TRUE,
     '{"description":"Alert when spray-suitable weather aligns with above-threshold pest","action":"Review weather forecast and prepare application","template":"Spray-suitable weather predicted for {date} at {location_name}. Pest {pest_name} is currently above economic threshold ({current_count} vs ET {et}). Wind: {wind_speed} km/h, Precip probability: {precip_prob}%."}'::jsonb),

    ('a0000000-0000-0000-0000-000000000103',
     'Resistance Rotation Warning', 'threshold', 'pest_management',
     'resistance_rotation_violation',
     0, '>', 'high', TRUE,
     '{"description":"Alert when same MoA class used consecutively","action":"Switch to compatible alternative mode of action","template":"Mode of action violation detected at {location_name}: {chemical_class} ({moa_code}) used twice consecutively. Last application: {days_since} days ago. Resistance risk: {risk_level}. Use a compatible alternative from {compatible_classes}."}'::jsonb),

    ('a0000000-0000-0000-0000-000000000104',
     'Biocontrol Follow-up Due', 'threshold', 'pest_management',
     'biocontrol_followup_due',
     14, '>=', 'low', TRUE,
     '{"description":"Trigger effectiveness check 14 days after biocontrol release","action":"Re-scout treated area and record effectiveness","template":"Biocontrol follow-up due at {location_name}: {method_name} was applied {days_since} days ago targeting {target_pest}. Schedule re-scout to evaluate effectiveness and determine if additional action needed."}'::jsonb)

ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    rule_type = EXCLUDED.rule_type,
    domain = EXCLUDED.domain,
    metric_source = EXCLUDED.metric_source,
    threshold = EXCLUDED.threshold,
    operator = EXCLUDED.operator,
    severity = EXCLUDED.severity,
    enabled = EXCLUDED.enabled,
    metadata = EXCLUDED.metadata;

COMMIT;
