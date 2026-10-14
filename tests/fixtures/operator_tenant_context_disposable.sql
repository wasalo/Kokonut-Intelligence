-- Minimal isolated substrate for migration 394 operator-context acceptance.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE ROLE kokonut_mobile_context_owner
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_runtime
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE SCHEMA kokonut_security;
GRANT USAGE ON SCHEMA kokonut_security TO PUBLIC;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_mobile_context_owner;
CREATE TABLE kokonut_security.mobile_context_hmac_key (
    key_id SMALLINT PRIMARY KEY CHECK (key_id = 1),
    secret BYTEA NOT NULL CHECK (octet_length(secret) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
);
INSERT INTO kokonut_security.mobile_context_hmac_key (key_id, secret)
VALUES (1, public.gen_random_bytes(32));
GRANT SELECT ON kokonut_security.mobile_context_hmac_key
    TO kokonut_mobile_context_owner;

CREATE TABLE public.organization (
    id UUID PRIMARY KEY,
    status TEXT NOT NULL
);
CREATE TABLE public.location (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES public.organization(id),
    status TEXT NOT NULL
);
CREATE TABLE public.location_tenant_owner_verification (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES public.location(id),
    organization_id UUID NOT NULL REFERENCES public.organization(id),
    revoked_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_disposable_current_owner
    ON public.location_tenant_owner_verification (location_id)
    WHERE revoked_at IS NULL;
CREATE TABLE public.operator_identity (
    id UUID PRIMARY KEY,
    enabled BOOLEAN NOT NULL
);
CREATE TABLE public.operator_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id),
    session_token_hash CHAR(64) NOT NULL UNIQUE,
    csrf_token_hash CHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.operator_scope_grant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id),
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id),
    organization_id UUID REFERENCES public.organization(id),
    revoked_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_disposable_active_scope
    ON public.operator_scope_grant (operator_id, resource, action, location_id)
    WHERE revoked_at IS NULL;
CREATE TABLE public.operator_organization_membership (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id),
    organization_id UUID NOT NULL REFERENCES public.organization(id),
    revoked_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_disposable_active_membership
    ON public.operator_organization_membership (operator_id, organization_id)
    WHERE revoked_at IS NULL;
CREATE TABLE public.location_organization_share (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES public.location(id),
    organization_id UUID NOT NULL REFERENCES public.organization(id),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_disposable_active_share
    ON public.location_organization_share (location_id, organization_id)
    WHERE revoked_at IS NULL;

INSERT INTO public.organization (id, status) VALUES
    ('a0000000-0000-0000-0000-000000000801', 'active'),
    ('a0000000-0000-0000-0000-000000000802', 'active'),
    ('a0000000-0000-0000-0000-000000000803', 'active');
INSERT INTO public.location (id, organization_id, status) VALUES
    ('a0000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000801', 'active');
INSERT INTO public.location_tenant_owner_verification (
    id, location_id, organization_id
) VALUES (
    'a0000000-0000-0000-0000-000000000901',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000801'
);
INSERT INTO public.operator_identity (id, enabled) VALUES
    ('a0000000-0000-0000-0000-000000000901', TRUE),
    ('a0000000-0000-0000-0000-000000000902', TRUE),
    ('a0000000-0000-0000-0000-000000000903', TRUE),
    ('a0000000-0000-0000-0000-000000000904', TRUE),
    ('a0000000-0000-0000-0000-000000000905', FALSE),
    ('a0000000-0000-0000-0000-000000000906', TRUE),
    ('a0000000-0000-0000-0000-000000000907', TRUE);
INSERT INTO public.operator_session (
    operator_id, session_token_hash, csrf_token_hash, expires_at, revoked_at
) VALUES
    ('a0000000-0000-0000-0000-000000000901', repeat('b', 64), repeat('1', 64), NOW() + INTERVAL '1 hour', NULL),
    ('a0000000-0000-0000-0000-000000000902', repeat('c', 64), repeat('2', 64), NOW() + INTERVAL '1 hour', NULL),
    ('a0000000-0000-0000-0000-000000000903', repeat('d', 64), repeat('3', 64), NOW() + INTERVAL '1 hour', NULL),
    ('a0000000-0000-0000-0000-000000000904', repeat('e', 64), repeat('4', 64), NOW() + INTERVAL '1 hour', NULL),
    ('a0000000-0000-0000-0000-000000000905', repeat('f', 64), repeat('5', 64), NOW() + INTERVAL '1 hour', NULL),
    ('a0000000-0000-0000-0000-000000000906', repeat('a', 64), repeat('6', 64), NOW() + INTERVAL '1 hour', NOW()),
    ('a0000000-0000-0000-0000-000000000907', repeat('9', 64), repeat('7', 64), NOW() - INTERVAL '1 hour', NULL);
INSERT INTO public.operator_organization_membership (operator_id, organization_id) VALUES
    ('a0000000-0000-0000-0000-000000000901', 'a0000000-0000-0000-0000-000000000801'),
    ('a0000000-0000-0000-0000-000000000902', 'a0000000-0000-0000-0000-000000000802'),
    ('a0000000-0000-0000-0000-000000000903', 'a0000000-0000-0000-0000-000000000801'),
    ('a0000000-0000-0000-0000-000000000903', 'a0000000-0000-0000-0000-000000000802'),
    ('a0000000-0000-0000-0000-000000000904', 'a0000000-0000-0000-0000-000000000801'),
    ('a0000000-0000-0000-0000-000000000905', 'a0000000-0000-0000-0000-000000000801'),
    ('a0000000-0000-0000-0000-000000000906', 'a0000000-0000-0000-0000-000000000801'),
    ('a0000000-0000-0000-0000-000000000907', 'a0000000-0000-0000-0000-000000000803');
INSERT INTO public.location_organization_share (
    location_id, organization_id, expires_at
) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000802', NOW() + INTERVAL '1 hour'),
    ('a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000803', NOW() - INTERVAL '1 hour');
INSERT INTO public.operator_scope_grant (
    operator_id, resource, action, location_id, organization_id
) VALUES
    ('a0000000-0000-0000-0000-000000000901', 'farm_activity', 'read', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000801'),
    ('a0000000-0000-0000-0000-000000000902', 'farm_activity', 'review', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000802'),
    ('a0000000-0000-0000-0000-000000000903', 'farm_activity', 'read', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000801'),
    ('a0000000-0000-0000-0000-000000000903', 'report_snapshot', 'read', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000802'),
    ('a0000000-0000-0000-0000-000000000904', 'farm_activity', 'legacy_read', 'a0000000-0000-0000-0000-000000000001', NULL),
    ('a0000000-0000-0000-0000-000000000905', 'farm_activity', 'read', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000801'),
    ('a0000000-0000-0000-0000-000000000907', 'farm_activity', 'expired_share', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000803');

CREATE TABLE public.operator_context_probe (
    tenant_id UUID NOT NULL,
    value TEXT NOT NULL
);
INSERT INTO public.operator_context_probe (tenant_id, value) VALUES
    ('a0000000-0000-0000-0000-000000000801', 'owner-row'),
    ('a0000000-0000-0000-0000-000000000802', 'partner-row'),
    ('a0000000-0000-0000-0000-000000000803', 'expired-share-row');
