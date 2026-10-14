-- Empty PostgreSQL substrate for migrations 391-392 credential acceptance.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

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

CREATE TABLE public.mobile_device_enrollment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code_hash TEXT NOT NULL UNIQUE,
    user_id VARCHAR(200) NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id),
    created_by VARCHAR(200) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    consumed_device_id VARCHAR(200),
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE public.mobile_device (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id VARCHAR(200) NOT NULL UNIQUE,
    device_name VARCHAR(300),
    device_type VARCHAR(100) DEFAULT 'phone',
    os VARCHAR(100),
    os_version VARCHAR(50),
    app_version VARCHAR(50),
    user_id VARCHAR(200),
    location_id UUID REFERENCES public.location(id),
    has_camera BOOLEAN DEFAULT TRUE,
    has_gps BOOLEAN DEFAULT TRUE,
    has_offline BOOLEAN DEFAULT TRUE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    last_seen_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    device_token_hash TEXT UNIQUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO public.organization (id, status) VALUES
    ('a0000000-0000-0000-0000-000000000801', 'active'),
    ('a0000000-0000-0000-0000-000000000802', 'active');
INSERT INTO public.location (id, organization_id, status) VALUES
    ('a0000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000801', 'active'),
    ('a0000000-0000-0000-0000-000000000002',
     'a0000000-0000-0000-0000-000000000801', 'active');
INSERT INTO public.location_tenant_owner_verification (
    id, location_id, organization_id
) VALUES
    (
    'a0000000-0000-0000-0000-000000000901',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000801'
    ),
    (
    'a0000000-0000-0000-0000-000000000903',
    'a0000000-0000-0000-0000-000000000002',
    'a0000000-0000-0000-0000-000000000801'
    );
