CREATE TABLE public.mobile_device (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id VARCHAR(200) NOT NULL UNIQUE,
    device_name VARCHAR(300),
    device_type VARCHAR(100) DEFAULT 'phone',
    os VARCHAR(100),
    os_version VARCHAR(50),
    app_version VARCHAR(50),
    push_token TEXT,
    location_id UUID,
    user_id VARCHAR(200),
    has_camera BOOLEAN DEFAULT TRUE,
    has_gps BOOLEAN DEFAULT TRUE,
    has_offline BOOLEAN DEFAULT TRUE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    last_sync_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    device_token_hash TEXT,
    revoked_at TIMESTAMPTZ,
    tenant_organization_id UUID
);

CREATE TABLE public.mobile_device_enrollment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code_hash TEXT NOT NULL UNIQUE,
    user_id VARCHAR(200) NOT NULL,
    location_id UUID NOT NULL,
    created_by VARCHAR(200) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    consumed_device_id VARCHAR(200),
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tenant_organization_id UUID
);

INSERT INTO public.mobile_device (
    device_id, user_id, location_id, tenant_organization_id,
    device_token_hash, push_token
) VALUES (
    'role-boundary-device', 'synthetic-user',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000801', repeat('a', 64), 'push-secret'
);

INSERT INTO public.mobile_device_enrollment (
    code_hash, user_id, location_id, tenant_organization_id,
    created_by, expires_at
) VALUES (
    repeat('b', 64), 'synthetic-user',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000801', 'synthetic-operator',
    NOW() + INTERVAL '30 minutes'
);
