-- Initial stakeholder engagement plan for the canonical Adelphi pilot.

INSERT INTO stakeholder_engagement_plan
    (id, name, description, stakeholder_party_id, owner_party_id, scope_type, scope_id, engagement_mode, cadence_days, status, metadata)
VALUES
    ('a0000000-0000-0000-0000-000000001100',
     'Adelphi community engagement',
     'Build a repeatable, consent-aware relationship with community stakeholders affected by the pilot.',
     'a0000000-0000-0000-0000-000000001002',
     'a0000000-0000-0000-0000-000000001000',
     'location', 'a0000000-0000-0000-0000-000000000001', 'collaborate', 90, 'draft',
     '{"source":"stakeholder_theory","privacy":"internal"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    stakeholder_party_id = EXCLUDED.stakeholder_party_id,
    owner_party_id = EXCLUDED.owner_party_id,
    scope_type = EXCLUDED.scope_type,
    scope_id = EXCLUDED.scope_id,
    engagement_mode = EXCLUDED.engagement_mode,
    cadence_days = EXCLUDED.cadence_days,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata;

INSERT INTO stakeholder_engagement_objective
    (id, plan_id, title, description, desired_outcome, success_metric, target_value, unit, priority, status, evidence)
VALUES
    ('a0000000-0000-0000-0000-000000001101',
     'a0000000-0000-0000-0000-000000001100',
     'Create accessible participation channels',
     'Ensure affected community members can participate through appropriate channels and consent boundaries.',
     'Community input is received, acknowledged, and traceably considered in relevant decisions.',
     'engagement commitments fulfilled', 90, 'percent', 5, 'proposed',
     '[{"source":"stakeholder_theory"}]'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    desired_outcome = EXCLUDED.desired_outcome,
    success_metric = EXCLUDED.success_metric,
    target_value = EXCLUDED.target_value,
    unit = EXCLUDED.unit,
    priority = EXCLUDED.priority,
    status = EXCLUDED.status,
    evidence = EXCLUDED.evidence;
