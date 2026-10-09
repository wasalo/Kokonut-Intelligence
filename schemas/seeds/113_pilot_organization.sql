-- Canonical organization required for organization-grain reporting.

INSERT INTO organization (
    id, org_key, name, org_type, description, governance_model, status,
    source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000000700'::uuid,
    'kokonut-adelphi',
    'Kokonut Adelphi',
    'cooperative',
    'Adelphi syntropic farm in Sabana Grande de Boya, Dominican Republic.',
    'moloch_dao',
    'active',
    'pilot_seed',
    'org-kokonut-adelphi',
    '{"record_type":"organization","privacy":"public_summary"}'
)
ON CONFLICT (id) DO UPDATE SET
    org_key = EXCLUDED.org_key,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    governance_model = EXCLUDED.governance_model,
    status = EXCLUDED.status,
    source_system = EXCLUDED.source_system,
    source_id = EXCLUDED.source_id,
    source_raw = EXCLUDED.source_raw,
    updated_at = NOW();

UPDATE location
SET organization_id = 'a0000000-0000-0000-0000-000000000700'::uuid
WHERE id = 'a0000000-0000-0000-0000-000000000001'::uuid;
