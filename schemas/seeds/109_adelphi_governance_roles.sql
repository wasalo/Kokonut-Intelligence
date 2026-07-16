-- Canonical Adelphi pilot circles and role definitions.

INSERT INTO governance_circle (
    circle_key, name, purpose, description, scope_type, scope_id, status, metadata
)
VALUES (
    'adelphi-stakeholder-stewardship',
    'Adelphi Stakeholder Stewardship',
    'Ensure affected stakeholder interests are identified, represented, consented, and followed through.',
    'Initial Kokonut Adelphi role-and-circle governance pilot.',
    'location',
    'a0000000-0000-0000-0000-000000000001'::uuid,
    'active',
    '{"pilot": true, "governance_model": "kokonut_role_circle"}'::jsonb
)
ON CONFLICT (circle_key) DO UPDATE SET
    name = EXCLUDED.name,
    purpose = EXCLUDED.purpose,
    description = EXCLUDED.description,
    scope_type = EXCLUDED.scope_type,
    scope_id = EXCLUDED.scope_id,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

WITH circle AS (
    SELECT id FROM governance_circle WHERE circle_key = 'adelphi-stakeholder-stewardship'
), roles(role_key, name, purpose) AS (
    VALUES
        ('stakeholder-steward', 'Stakeholder Steward', 'Maintain affected-party interests, representation, consent, and follow-through.'),
        ('circle-steward', 'Circle Steward', 'Maintain circle purpose, scope, role coverage, and review health.'),
        ('evidence-custodian', 'Evidence Custodian', 'Maintain evidence lineage, verification state, and uncertainty notes.'),
        ('consent-custodian', 'Consent Custodian', 'Verify consent before engagement, publication, or data use.'),
        ('grievance-owner', 'Grievance Owner', 'Coordinate grievance acknowledgement, investigation, remedy, and closure.'),
        ('ecological-proxy-steward', 'Ecological Proxy Steward', 'Maintain nature and future-generation proxy authority and review.'),
        ('market-relationship-owner', 'Market Relationship Owner', 'Coordinate buyer, cooperative, and partner commitments.'),
        ('governance-facilitator', 'Governance Facilitator', 'Facilitate structured governance sessions without owning substantive decisions.'),
        ('governance-recorder', 'Governance Recorder', 'Maintain proposal, objection, decision, and outcome records.')
)
INSERT INTO governance_role (circle_id, role_key, name, purpose, status, metadata)
SELECT circle.id, roles.role_key, roles.name, roles.purpose, 'active', '{"pilot": true}'::jsonb
FROM circle CROSS JOIN roles
ON CONFLICT (circle_id, role_key) DO UPDATE SET
    name = EXCLUDED.name,
    purpose = EXCLUDED.purpose,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

WITH role_data(role_key, accountability, priority) AS (
    VALUES
        ('stakeholder-steward', 'Maintain an evidence-backed map of affected stakeholder interests.', 1),
        ('stakeholder-steward', 'Ensure participation, consent, and minority views are recorded.', 1),
        ('circle-steward', 'Review circle purpose, scope, role coverage, and unresolved governance tensions.', 1),
        ('evidence-custodian', 'Maintain source links, evidence maturity, verification state, and uncertainty notes.', 1),
        ('consent-custodian', 'Check effective consent before governed engagement and public use.', 1),
        ('grievance-owner', 'Ensure grievances receive an owner, investigation, remedy, and documented closure.', 1),
        ('ecological-proxy-steward', 'Ensure ecological and future-generation impacts have active proxy authority.', 1),
        ('market-relationship-owner', 'Track partner commitments, risks, performance, and remedies.', 1),
        ('governance-facilitator', 'Keep governance sessions structured around tensions and concrete next actions.', 2),
        ('governance-recorder', 'Maintain complete governance proposal, objection, approval, and outcome lineage.', 1)
)
INSERT INTO governance_role_accountability (role_id, accountability, priority)
SELECT r.id, role_data.accountability, role_data.priority
FROM governance_role r
JOIN governance_circle c ON c.id = r.circle_id
JOIN role_data ON role_data.role_key = r.role_key
WHERE c.circle_key = 'adelphi-stakeholder-stewardship'
ON CONFLICT (role_id, accountability) DO UPDATE SET
    priority = EXCLUDED.priority,
    status = 'active';
