-- Draft-only Adelphi cooperative-network example.
-- No approval, activation, publication, benefit distribution, or private evidence.

INSERT INTO coordination_alliance (
    id, name, coordination_type, purpose, scope_type, scope_id, market_cycle,
    steward_party_id, status, metadata, created_by_party_id
) VALUES (
    'a0000000-0000-0000-0000-000000002000',
    'Adelphi cooperative learning network',
    'cooperative_network',
    'Explore shared regenerative practice learning, cooperative market access, and reversible capability pilots.',
    'location',
    'a0000000-0000-0000-0000-000000000001',
    'standard',
    'a0000000-0000-0000-0000-000000001001',
    'draft',
    '{"example":true,"source":"canonical_pilot","governance":"draft_only"}'::jsonb,
    'a0000000-0000-0000-0000-000000001000'
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    purpose = EXCLUDED.purpose,
    market_cycle = EXCLUDED.market_cycle,
    status = 'draft',
    metadata = EXCLUDED.metadata;

INSERT INTO coordination_participant (
    id, alliance_id, party_id, role, status, contribution_expectation, benefit_expectation
) VALUES (
    'a0000000-0000-0000-0000-000000002001',
    'a0000000-0000-0000-0000-000000002000',
    'a0000000-0000-0000-0000-000000001002',
    'affected_party',
    'proposed',
    'Identify locally relevant learning priorities and access barriers.',
    'Receive accessible learning outputs and transparent review questions.'
)
ON CONFLICT (id) DO UPDATE SET
    status = 'proposed',
    contribution_expectation = EXCLUDED.contribution_expectation,
    benefit_expectation = EXCLUDED.benefit_expectation;

INSERT INTO coordination_objective (
    id, alliance_id, title, description, objective_type, status, evidence
) VALUES (
    'a0000000-0000-0000-0000-000000002002',
    'a0000000-0000-0000-0000-000000002000',
    'Test reciprocal field learning',
    'Draft a reversible learning exchange and assess contribution, access, and ecological safeguards before approval.',
    'knowledge',
    'draft',
    '[{"source":"pilot_design","maturity":"draft"}]'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    status = 'draft',
    evidence = EXCLUDED.evidence;
