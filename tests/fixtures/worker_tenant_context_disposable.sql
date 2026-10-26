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

-- Minimal migration-350 trigger contract for migration 578 acceptance.
CREATE TABLE public.agent_safety_probe (
    id INTEGER PRIMARY KEY,
    status TEXT NOT NULL
);
INSERT INTO public.agent_safety_probe (id, status) VALUES
    (1, 'submitted'),
    (2, 'submitted'),
    (3, 'submitted'),
    (4, 'submitted');

CREATE OR REPLACE FUNCTION public.agent_safety_security_definer_update_probe(
    target_id INTEGER,
    next_status TEXT
)
RETURNS VOID
LANGUAGE SQL
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
    UPDATE public.agent_safety_probe
       SET status = next_status
     WHERE id = target_id
$$;

CREATE OR REPLACE FUNCTION public.agent_safety_security_definer_insert_probe(
    target_id INTEGER,
    next_status TEXT
)
RETURNS VOID
LANGUAGE SQL
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
    INSERT INTO public.agent_safety_probe (id, status)
    VALUES (target_id, next_status)
$$;

CREATE OR REPLACE FUNCTION public.assert_agent_safety()
RETURNS TRIGGER AS $$
DECLARE
    agent_id TEXT;
BEGIN
    agent_id := current_setting('app.agent_id', TRUE);
    IF agent_id IS NULL OR agent_id = '' THEN
        RETURN NEW;
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status
       AND NEW.status IN ('verified', 'published') THEN
        RAISE EXCEPTION 'Agent % cannot set status to % on %',
            agent_id, NEW.status, TG_TABLE_NAME;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_agent_safety_probe
    BEFORE UPDATE ON public.agent_safety_probe
    FOR EACH ROW
    WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION public.assert_agent_safety();

ALTER TABLE public.organization ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization FORCE ROW LEVEL SECURITY;
ALTER TABLE public.location ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.location FORCE ROW LEVEL SECURITY;
ALTER TABLE public.location_tenant_owner_verification ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.location_tenant_owner_verification FORCE ROW LEVEL SECURITY;
