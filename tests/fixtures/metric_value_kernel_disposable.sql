CREATE ROLE kokonut_runtime NOLOGIN;
CREATE ROLE kokonut_directus_runtime NOLOGIN;
CREATE SCHEMA kokonut_security;

CREATE TABLE public.organization (
    id UUID PRIMARY KEY,
    status TEXT NOT NULL
);
CREATE TABLE public.operator_identity (
    id UUID PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    secret_label TEXT
);
CREATE TABLE public.location (
    id UUID PRIMARY KEY,
    organization_id UUID
);
CREATE TABLE public.operator_scope_grant (
    operator_id UUID NOT NULL,
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    location_id UUID NOT NULL,
    organization_id UUID,
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.operator_organization_membership (
    operator_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.location_tenant_owner_verification (
    location_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.location_organization_share (
    location_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    revoked_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);
CREATE TABLE public.metric_definition (
    id UUID PRIMARY KEY,
    metric_key VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    unit VARCHAR(50),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE public.metric_value (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_id UUID NOT NULL REFERENCES public.metric_definition(id),
    location_id UUID REFERENCES public.location(id),
    period_start DATE,
    period_end DATE,
    value NUMERIC(15,4),
    unit VARCHAR(50),
    computation_method VARCHAR(100),
    source_record_ids UUID[],
    computed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    verification_notes TEXT
);

CREATE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE (tenant_id UUID, location_id UUID, actor_id UUID, actor_type TEXT)
LANGUAGE sql STABLE AS $$
    SELECT NULL::UUID,
           NULLIF(current_setting('test.location_id', TRUE), '')::UUID,
           NULLIF(current_setting('test.actor_id', TRUE), '')::UUID,
           current_setting('test.actor_type', TRUE)
$$;

CREATE FUNCTION public.operator_scope_grant_allows(
    requested_actor UUID,
    requested_resource TEXT,
    requested_action TEXT,
    requested_location UUID
)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER AS $$
    SELECT EXISTS (
        SELECT 1
          FROM public.operator_scope_grant AS grant_row
          JOIN public.operator_identity AS identity
            ON identity.id = grant_row.operator_id AND identity.enabled
          JOIN public.location AS loc ON loc.id = grant_row.location_id
         WHERE grant_row.operator_id = requested_actor
           AND grant_row.resource = requested_resource
           AND grant_row.action = requested_action
           AND grant_row.location_id = requested_location
           AND grant_row.revoked_at IS NULL
           AND (
               grant_row.organization_id IS NULL
               OR (
                   EXISTS (
                       SELECT 1
                         FROM public.operator_organization_membership AS membership
                         JOIN public.organization AS tenant
                           ON tenant.id = membership.organization_id
                          AND tenant.status = 'active'
                        WHERE membership.operator_id = grant_row.operator_id
                          AND membership.organization_id = grant_row.organization_id
                          AND membership.revoked_at IS NULL
                   )
                   AND EXISTS (
                       SELECT 1
                         FROM public.location_tenant_owner_verification AS owner
                        WHERE owner.location_id = loc.id
                          AND owner.organization_id = loc.organization_id
                          AND owner.revoked_at IS NULL
                          AND (
                              owner.organization_id = grant_row.organization_id
                              OR EXISTS (
                                  SELECT 1
                                    FROM public.location_organization_share AS share
                                   WHERE share.location_id = loc.id
                                     AND share.organization_id = grant_row.organization_id
                                     AND share.revoked_at IS NULL
                                     AND (share.expires_at IS NULL OR share.expires_at > NOW())
                              )
                          )
                   )
               )
           )
    )
$$;

INSERT INTO public.operator_identity (id) VALUES
    ('a0000000-0000-4000-8000-000000000401'),
    ('a0000000-0000-4000-8000-000000000402');
INSERT INTO public.location (id) VALUES
    ('a0000000-0000-4000-8000-000000000201'),
    ('a0000000-0000-4000-8000-000000000202');
INSERT INTO public.operator_scope_grant (
    operator_id, resource, action, location_id, organization_id
) VALUES
    ('a0000000-0000-4000-8000-000000000401', 'metric_value', 'compute', 'a0000000-0000-4000-8000-000000000201', NULL),
    ('a0000000-0000-4000-8000-000000000401', 'metric_value', 'read', 'a0000000-0000-4000-8000-000000000201', NULL),
    ('a0000000-0000-4000-8000-000000000401', 'metric_value', 'compute', 'a0000000-0000-4000-8000-000000000202', NULL),
    ('a0000000-0000-4000-8000-000000000401', 'metric_value', 'read', 'a0000000-0000-4000-8000-000000000202', NULL),
    ('a0000000-0000-4000-8000-000000000401', 'metric_value', 'verify', 'a0000000-0000-4000-8000-000000000201', NULL),
    ('a0000000-0000-4000-8000-000000000402', 'metric_value', 'verify', 'a0000000-0000-4000-8000-000000000201', NULL);
INSERT INTO public.metric_definition (id, metric_key, display_name, unit) VALUES
    ('a0000000-0000-4000-8000-000000000601', 'soil_organic_matter', 'Soil organic matter', '%');

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_runtime, kokonut_directus_runtime;
GRANT SELECT ON public.metric_definition, public.metric_value TO kokonut_runtime;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context() TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID) TO PUBLIC;
