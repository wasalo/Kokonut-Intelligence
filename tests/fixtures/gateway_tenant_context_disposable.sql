-- Minimal source-compatible schema for migration 396 Gateway context checks.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE ROLE kokonut_mobile_context_owner
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_runtime
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE SCHEMA kokonut_security;
GRANT USAGE ON SCHEMA kokonut_security TO PUBLIC;
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
CREATE UNIQUE INDEX uq_gateway_context_current_owner
    ON public.location_tenant_owner_verification (location_id)
    WHERE revoked_at IS NULL;
CREATE TABLE public.api_key (
    id UUID PRIMARY KEY,
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    role_id UUID,
    scopes TEXT[],
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    name TEXT NOT NULL
);
CREATE TABLE public.capability_token (
    id UUID PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    holder TEXT NOT NULL,
    capabilities JSONB NOT NULL DEFAULT '[]',
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    max_usage INTEGER,
    usage_count INTEGER NOT NULL DEFAULT 0,
    created_by TEXT,
    metadata JSONB
);

INSERT INTO public.organization (id, status) VALUES
    ('a0000000-0000-0000-0000-000000000801', 'active'),
    ('a0000000-0000-0000-0000-000000000802', 'active');
INSERT INTO public.location (id, organization_id, status) VALUES
    ('a0000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000801', 'active'),
    ('a0000000-0000-0000-0000-000000000002',
     'a0000000-0000-0000-0000-000000000802', 'active');
INSERT INTO public.location_tenant_owner_verification (
    id, location_id, organization_id
) VALUES
    ('a0000000-0000-0000-0000-000000000901',
     'a0000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000801'),
    ('a0000000-0000-0000-0000-000000000902',
     'a0000000-0000-0000-0000-000000000002',
     'a0000000-0000-0000-0000-000000000802');

INSERT INTO public.api_key (
    id, key_hash, key_prefix, scopes, expires_at, is_active, name
) VALUES
    ('a0000000-0000-0000-0000-000000000911', repeat('a', 64), 'key-a',
     ARRAY['mobile_device:revoke:a0000000-0000-0000-0000-000000000001'],
     NOW() + INTERVAL '1 hour', TRUE, 'valid-owner-key'),
    ('a0000000-0000-0000-0000-000000000912', repeat('b', 64), 'key-b',
     ARRAY['mobile_device:revoke'], NOW() + INTERVAL '1 hour', TRUE, 'unscoped-key'),
    ('a0000000-0000-0000-0000-000000000913', repeat('d', 64), 'key-d',
     ARRAY['mobile_device:revoke:*'], NOW() + INTERVAL '1 hour', TRUE, 'wildcard-key'),
    ('a0000000-0000-0000-0000-000000000914', repeat('e', 64), 'key-e',
     ARRAY['mobile_device:revoke:a0000000-0000-0000-0000-000000000001'],
     NOW() - INTERVAL '1 hour', TRUE, 'expired-key'),
    ('a0000000-0000-0000-0000-000000000915', repeat('f', 64), 'key-f',
     ARRAY['mobile_device:revoke:a0000000-0000-0000-0000-000000000001'],
     NOW() + INTERVAL '1 hour', FALSE, 'revoked-key'),
    ('a0000000-0000-0000-0000-000000000916', repeat('9', 64), 'key-9',
     ARRAY['mobile_device:revoke:a0000000-0000-0000-0000-000000000002'],
     NOW() + INTERVAL '1 hour', TRUE, 'wrong-location-key');
INSERT INTO public.capability_token (
    id, token_hash, holder, capabilities, expires_at, max_usage, usage_count
) VALUES
    ('a0000000-0000-0000-0000-000000000921', repeat('c', 64), 'valid-capability',
     '[{"resource":"mobile_device","action":"revoke","location_id":"a0000000-0000-0000-0000-000000000001"}]'::JSONB,
     NOW() + INTERVAL '1 hour', 3, 1),
    ('a0000000-0000-0000-0000-000000000922', repeat('8', 64), 'wrong-location-capability',
     '[{"resource":"mobile_device","action":"revoke","location_id":"a0000000-0000-0000-0000-000000000002"}]'::JSONB,
     NOW() + INTERVAL '1 hour', NULL, 0),
    ('a0000000-0000-0000-0000-000000000923', repeat('7', 64), 'expired-capability',
     '[{"resource":"mobile_device","action":"revoke","location_id":"a0000000-0000-0000-0000-000000000001"}]'::JSONB,
     NOW() - INTERVAL '1 hour', NULL, 0),
    ('a0000000-0000-0000-0000-000000000924', repeat('6', 64), 'revoked-capability',
     '[{"resource":"mobile_device","action":"revoke","location_id":"a0000000-0000-0000-0000-000000000001"}]'::JSONB,
     NOW() + INTERVAL '1 hour', NULL, 0),
    ('a0000000-0000-0000-0000-000000000925', repeat('5', 64), 'unbounded-capability',
     '[{"resource":"mobile_device","action":"revoke","location_id":"a0000000-0000-0000-0000-000000000001"}]'::JSONB,
     NOW() + INTERVAL '1 hour', 0, 500),
    ('a0000000-0000-0000-0000-000000000926', repeat('4', 64), 'last-use-capability',
     '[{"resource":"mobile_device","action":"revoke","location_id":"a0000000-0000-0000-0000-000000000001"}]'::JSONB,
     NOW() + INTERVAL '1 hour', 1, 1),
    ('a0000000-0000-0000-0000-000000000927', repeat('3', 64), 'over-limit-capability',
     '[{"resource":"mobile_device","action":"revoke","location_id":"a0000000-0000-0000-0000-000000000001"}]'::JSONB,
     NOW() + INTERVAL '1 hour', 1, 2);
UPDATE public.capability_token SET revoked = TRUE
 WHERE id = 'a0000000-0000-0000-0000-000000000924';

CREATE TABLE public.gateway_context_probe (
    tenant_id UUID NOT NULL,
    value TEXT NOT NULL
);
INSERT INTO public.gateway_context_probe (tenant_id, value) VALUES
    ('a0000000-0000-0000-0000-000000000801', 'owner-row'),
    ('a0000000-0000-0000-0000-000000000802', 'other-tenant-row');
