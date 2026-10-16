-- Minimal prior-schema contract for isolated migration 405 acceptance.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE ROLE kokonut_mobile_context_owner
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_runtime LOGIN PASSWORD 'worker-runtime-fixture'
    NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_operator_auth LOGIN PASSWORD 'worker-auth-fixture'
    NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_worker_login LOGIN PASSWORD 'worker-execution-fixture'
    NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE SCHEMA kokonut_security;
CREATE TABLE kokonut_security.mobile_context_hmac_key (
    key_id SMALLINT PRIMARY KEY CHECK (key_id = 1),
    secret BYTEA NOT NULL CHECK (octet_length(secret) = 32)
);
INSERT INTO kokonut_security.mobile_context_hmac_key (key_id, secret)
VALUES (1, public.gen_random_bytes(32));
GRANT SELECT ON kokonut_security.mobile_context_hmac_key
    TO kokonut_mobile_context_owner;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime, kokonut_operator_auth;

CREATE TABLE public.organization (
    id UUID PRIMARY KEY,
    status TEXT NOT NULL
);
CREATE TABLE public.location (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE public.location_tenant_owner_verification (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    revoked_at TIMESTAMPTZ
);
INSERT INTO public.organization (id, status) VALUES
    ('a0000000-0000-0000-0000-000000000801', 'active'),
    ('a0000000-0000-0000-0000-000000000802', 'active');
INSERT INTO public.location (id, organization_id, status) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000801', 'active'),
    ('a0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000802', 'active');
INSERT INTO public.location_tenant_owner_verification
    (id, location_id, organization_id, revoked_at) VALUES
    ('a0000000-0000-0000-0000-000000000811', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000801', NULL),
    ('a0000000-0000-0000-0000-000000000812', 'a0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000802', NULL);

ALTER TABLE public.organization ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization FORCE ROW LEVEL SECURITY;
ALTER TABLE public.location ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.location FORCE ROW LEVEL SECURITY;
ALTER TABLE public.location_tenant_owner_verification ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.location_tenant_owner_verification FORCE ROW LEVEL SECURITY;
