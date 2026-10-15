-- Synthetic-only setup for migration 398 acceptance in a disposable database.
BEGIN;

INSERT INTO public.organization (id, org_key, name, status)
VALUES
    ('e1000000-0000-4000-8000-000000000001', 'codex-revoke-owner-a', 'Codex Revoke Owner A', 'active'),
    ('e1000000-0000-4000-8000-000000000002', 'codex-revoke-owner-b', 'Codex Revoke Owner B', 'active');

INSERT INTO public.location (id, name, slug, status, organization_id)
VALUES
    ('e2000000-0000-4000-8000-000000000001', 'Codex Revoke Location A', 'codex-revoke-location-a', 'active', 'e1000000-0000-4000-8000-000000000001'),
    ('e2000000-0000-4000-8000-000000000002', 'Codex Revoke Location B', 'codex-revoke-location-b', 'active', 'e1000000-0000-4000-8000-000000000002');

INSERT INTO public.location_tenant_owner_verification (
    id, location_id, organization_id, decision_reference, confirmed_by
)
VALUES
    ('e3000000-0000-4000-8000-000000000001', 'e2000000-0000-4000-8000-000000000001', 'e1000000-0000-4000-8000-000000000001', 'codex-disposable-revoke-a', 'codex-test'),
    ('e3000000-0000-4000-8000-000000000002', 'e2000000-0000-4000-8000-000000000002', 'e1000000-0000-4000-8000-000000000002', 'codex-disposable-revoke-b', 'codex-test');

INSERT INTO public.mobile_device (
    device_id, location_id, tenant_organization_id, device_token_hash, status
)
VALUES
    ('codex-revoke-owner', 'e2000000-0000-4000-8000-000000000001', 'e1000000-0000-4000-8000-000000000001', repeat('1', 64), 'active'),
    ('codex-revoke-cross-tenant', 'e2000000-0000-4000-8000-000000000002', 'e1000000-0000-4000-8000-000000000002', repeat('2', 64), 'active'),
    ('codex-revoke-capability', 'e2000000-0000-4000-8000-000000000001', 'e1000000-0000-4000-8000-000000000001', repeat('3', 64), 'active'),
    ('codex-revoke-operator', 'e2000000-0000-4000-8000-000000000001', 'e1000000-0000-4000-8000-000000000001', repeat('4', 64), 'active');

INSERT INTO public.api_key (id, name, key_hash, key_prefix, scopes, expires_at, is_active)
VALUES
    ('e6000000-0000-4000-8000-000000000001', 'Codex disposable revoke key', repeat('a', 64), 'codex-a', ARRAY['mobile_device:revoke:e2000000-0000-4000-8000-000000000001'], statement_timestamp() + INTERVAL '1 hour', TRUE),
    ('e6000000-0000-4000-8000-000000000002', 'Codex wrong-action key', repeat('b', 64), 'codex-b', ARRAY['mobile_device:read:e2000000-0000-4000-8000-000000000001'], statement_timestamp() + INTERVAL '1 hour', TRUE),
    ('e6000000-0000-4000-8000-000000000003', 'Codex wrong-location key', repeat('c', 64), 'codex-c', ARRAY['mobile_device:revoke:e2000000-0000-4000-8000-000000000002'], statement_timestamp() + INTERVAL '1 hour', TRUE);

INSERT INTO public.capability_token (
    id, token_hash, holder, capabilities, expires_at, max_usage, usage_count
)
VALUES (
    'e7000000-0000-4000-8000-000000000001', repeat('d', 64), 'codex-disposable-revoker',
    '[{"resource":"mobile_device","action":"revoke","location_id":"e2000000-0000-4000-8000-000000000001"}]'::JSONB,
    statement_timestamp() + INTERVAL '1 hour', NULL, 0
);

INSERT INTO public.operator_identity (id, issuer, subject, display_name, enabled)
VALUES ('e4000000-0000-4000-8000-000000000001', 'https://codex.invalid', 'disposable-revoker', 'Codex Disposable Revoker', TRUE);

INSERT INTO public.operator_session (
    id, operator_id, session_token_hash, csrf_token_hash, expires_at
)
VALUES (
    'e5000000-0000-4000-8000-000000000001',
    'e4000000-0000-4000-8000-000000000001',
    repeat('e', 64), repeat('f', 64),
    statement_timestamp() + INTERVAL '1 hour'
);

INSERT INTO public.operator_organization_membership (
    operator_id, organization_id, granted_by
)
VALUES ('e4000000-0000-4000-8000-000000000001', 'e1000000-0000-4000-8000-000000000001', 'codex-test');

INSERT INTO public.operator_scope_grant (
    operator_id, resource, action, location_id, granted_by, organization_id
)
VALUES (
    'e4000000-0000-4000-8000-000000000001', 'mobile_device', 'revoke',
    'e2000000-0000-4000-8000-000000000001', 'codex-test',
    'e1000000-0000-4000-8000-000000000001'
);

ALTER TABLE public.mobile_device ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mobile_device FORCE ROW LEVEL SECURITY;

COMMIT;
