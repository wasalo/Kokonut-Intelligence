-- Technology and Capability Roadmap seed data

INSERT INTO technology_roadmap
    (id, name, description, entity_type, planning_horizon_start,
     planning_horizon_end, detail_level, sponsor, owner,
     review_cadence_days, status, metadata)
VALUES
    ('a0000000-0000-0000-0000-000000000920',
     'Kokonut Platform Scale Roadmap',
     'Governed roadmap for making Kokonut DAO, Guild, farm, MRV, and intelligence infrastructure repeatable across communities.',
     'platform', '2026-01-01', '2028-12-31', 'portfolio',
     'Technology Guild', 'Platform Steward', 90, 'active',
     '{"method":"technology_roadmapping","planning_horizons":["now","next","later"],"public_derived_view":true}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    planning_horizon_start = EXCLUDED.planning_horizon_start,
    planning_horizon_end = EXCLUDED.planning_horizon_end,
    detail_level = EXCLUDED.detail_level,
    sponsor = EXCLUDED.sponsor,
    owner = EXCLUDED.owner,
    review_cadence_days = EXCLUDED.review_cadence_days,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata;

INSERT INTO technology_roadmap_requirement
    (id, roadmap_id, title, description, need_type, priority,
     target_value, unit, target_date, capability_id, status, evidence)
VALUES
    ('a0000000-0000-0000-0000-000000000921',
     'a0000000-0000-0000-0000-000000000920',
     'Replicate the platform across farms',
     'New farms should reuse the common schema, MRV, governance, and intelligence stack without bespoke platform work.',
     'business', 5, 90, 'percent reusable onboarding', '2027-06-30',
     (SELECT id FROM business_capability WHERE name = 'Technology Platform' AND guild_key = 'technology' LIMIT 1),
     'validated', '[{"source":"Kokonut Framework replication strategy","maturity":"advisory"}]'::jsonb),
    ('a0000000-0000-0000-0000-000000000922',
     'a0000000-0000-0000-0000-000000000920',
     'Make intelligence outputs evidence-ready',
     'Forecasts, scores, and agent outputs need traceable evidence, uncertainty, and human review boundaries.',
     'operational', 5, 95, 'percent outputs with lineage', '2027-03-31',
     (SELECT id FROM business_capability WHERE name = 'Impact Intelligence' AND guild_key = 'impact' LIMIT 1),
     'validated', '[{"source":"CIDS and EAS architecture","maturity":"advisory"}]'::jsonb),
    ('a0000000-0000-0000-0000-000000000923',
     'a0000000-0000-0000-0000-000000000920',
     'Scale governed agent operations',
     'Agent identity, task routing, payment, reputation, and arbitration must mature without weakening governance.',
     'business', 4, 80, 'percent governed agent tasks', '2028-06-30',
     (SELECT id FROM business_capability WHERE name = 'Agent Execution' AND guild_key = 'technology' LIMIT 1),
     'proposed', '[{"source":"Agent architecture","maturity":"developing"}]'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    priority = EXCLUDED.priority,
    target_value = EXCLUDED.target_value,
    unit = EXCLUDED.unit,
    target_date = EXCLUDED.target_date,
    capability_id = EXCLUDED.capability_id,
    status = EXCLUDED.status,
    evidence = EXCLUDED.evidence;

INSERT INTO technology_area (id, roadmap_id, name, description, sequence_order)
VALUES
    ('a0000000-0000-0000-0000-000000000924', 'a0000000-0000-0000-0000-000000000920', 'Interoperable farm infrastructure', 'Common Data Schema, onboarding, permissions, and reusable deployment patterns.', 1),
    ('a0000000-0000-0000-0000-000000000925', 'a0000000-0000-0000-0000-000000000920', 'Evidence and intelligence trust', 'Lineage, uncertainty, attestations, and decision-ready intelligence.', 2),
    ('a0000000-0000-0000-0000-000000000926', 'a0000000-0000-0000-0000-000000000920', 'Governed agent operations', 'Agent identity, task execution, payments, reputation, and review.', 3)
ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    sequence_order = EXCLUDED.sequence_order,
    status = EXCLUDED.status;

INSERT INTO technology_driver
    (id, area_id, requirement_id, name, metric_key, target_value, unit, target_date, weight)
VALUES
    ('a0000000-0000-0000-0000-000000000927', 'a0000000-0000-0000-0000-000000000924', 'a0000000-0000-0000-0000-000000000921', 'Onboarding reuse', 'farm_onboarding_reuse_pct', 90, 'percent', '2027-06-30', 8),
    ('a0000000-0000-0000-0000-000000000928', 'a0000000-0000-0000-0000-000000000925', 'a0000000-0000-0000-0000-000000000922', 'Evidence coverage', 'intelligence_lineage_coverage_pct', 95, 'percent', '2027-03-31', 10),
    ('a0000000-0000-0000-0000-000000000929', 'a0000000-0000-0000-0000-000000000926', 'a0000000-0000-0000-0000-000000000923', 'Governed task coverage', 'agent_governed_task_pct', 80, 'percent', '2028-06-30', 7)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    requirement_id = EXCLUDED.requirement_id,
    metric_key = EXCLUDED.metric_key,
    target_value = EXCLUDED.target_value,
    unit = EXCLUDED.unit,
    target_date = EXCLUDED.target_date,
    weight = EXCLUDED.weight;

INSERT INTO technology_alternative
    (id, driver_id, name, description, maturity_status, expected_maturity_date,
     estimated_cost, confidence, recommendation, decision_rationale, metadata)
VALUES
    ('a0000000-0000-0000-0000-000000000930', 'a0000000-0000-0000-0000-000000000927', 'Reusable farm deployment package', 'Template-driven schema, permissions, seed, readiness, and reporting package.', 'pilot', '2027-03-31', 25000, 0.75, 'selected', 'Highest reuse across the replication value stream.', '{"horizon":"now"}'::jsonb),
    ('a0000000-0000-0000-0000-000000000931', 'a0000000-0000-0000-0000-000000000928', 'Evidence lineage graph and confidence layer', 'Typed evidence graph with uncertainty and audience-specific projections.', 'pilot', '2027-06-30', 35000, 0.65, 'selected', 'Improves trust across MRV, intelligence, and public reporting.', '{"horizon":"next"}'::jsonb),
    ('a0000000-0000-0000-0000-000000000932', 'a0000000-0000-0000-0000-000000000929', 'Governed agent service marketplace', 'Identity, task routing, x402 payment, reputation, and human arbitration integration.', 'emerging', '2028-06-30', 60000, 0.45, 'candidate', 'Strategically important, but dependent on identity and reputation maturity.', '{"horizon":"later"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    maturity_status = EXCLUDED.maturity_status,
    expected_maturity_date = EXCLUDED.expected_maturity_date,
    estimated_cost = EXCLUDED.estimated_cost,
    confidence = EXCLUDED.confidence,
    recommendation = EXCLUDED.recommendation,
    decision_rationale = EXCLUDED.decision_rationale,
    metadata = EXCLUDED.metadata;
