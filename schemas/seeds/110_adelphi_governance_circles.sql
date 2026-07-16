-- Adjacent circles for the Adelphi role-and-circle governance pilot.

INSERT INTO governance_circle (circle_key, name, purpose, scope_type, scope_id, status, metadata)
VALUES
    ('adelphi-ecological-stewardship', 'Adelphi Ecological Stewardship', 'Protect ecological and future-generation interests in Adelphi decisions.', 'location', 'a0000000-0000-0000-0000-000000000001'::uuid, 'active', '{"pilot": true}'::jsonb),
    ('adelphi-market-relationships', 'Adelphi Market Relationships', 'Coordinate buyer, cooperative, and partner commitments for Adelphi.', 'location', 'a0000000-0000-0000-0000-000000000001'::uuid, 'active', '{"pilot": true}'::jsonb),
    ('adelphi-evidence-measurement', 'Adelphi Evidence and Measurement', 'Maintain evidence quality, verification, and uncertainty for Adelphi governance.', 'location', 'a0000000-0000-0000-0000-000000000001'::uuid, 'active', '{"pilot": true}'::jsonb)
ON CONFLICT (circle_key) DO UPDATE SET
    name = EXCLUDED.name,
    purpose = EXCLUDED.purpose,
    scope_type = EXCLUDED.scope_type,
    scope_id = EXCLUDED.scope_id,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

WITH definitions(circle_key, role_key, name, purpose) AS (
    VALUES
        ('adelphi-ecological-stewardship', 'ecological-impact-reviewer', 'Ecological Impact Reviewer', 'Review ecological and future-generation impacts before approval.'),
        ('adelphi-market-relationships', 'market-relationship-owner', 'Market Relationship Owner', 'Coordinate market partner commitments, risks, and remedies.'),
        ('adelphi-evidence-measurement', 'evidence-custodian', 'Evidence Custodian', 'Maintain evidence lineage, verification state, and uncertainty notes.')
)
INSERT INTO governance_role (circle_id, role_key, name, purpose, status, metadata)
SELECT c.id, d.role_key, d.name, d.purpose, 'active', '{"pilot": true}'::jsonb
FROM definitions d
JOIN governance_circle c ON c.circle_key = d.circle_key
ON CONFLICT (circle_id, role_key) DO UPDATE SET
    name = EXCLUDED.name,
    purpose = EXCLUDED.purpose,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
