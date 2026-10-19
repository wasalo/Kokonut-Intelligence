CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_directus_runtime NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;

CREATE TABLE public.operator_identity (
    id UUID PRIMARY KEY,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    display_name TEXT,
    enabled BOOLEAN NOT NULL
);
CREATE TABLE public.party (
    id UUID PRIMARY KEY,
    party_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE public.organization (id UUID PRIMARY KEY, status TEXT NOT NULL);
CREATE TABLE public.location (
    id UUID PRIMARY KEY,
    organization_id UUID REFERENCES public.organization(id),
    status TEXT NOT NULL
);
CREATE TABLE public.location_tenant_owner_verification (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES public.location(id),
    organization_id UUID NOT NULL REFERENCES public.organization(id),
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.operator_organization_membership (
    id UUID PRIMARY KEY,
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id),
    organization_id UUID NOT NULL REFERENCES public.organization(id),
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.location_organization_share (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES public.location(id),
    organization_id UUID NOT NULL REFERENCES public.organization(id),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.operator_scope_grant (
    id UUID PRIMARY KEY,
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id),
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id),
    organization_id UUID,
    revoked_at TIMESTAMPTZ
);

CREATE OR REPLACE FUNCTION public.operator_scope_grant_allows(
    requested_operator_id UUID,
    requested_resource TEXT,
    requested_action TEXT,
    requested_location_id UUID
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY INVOKER
AS $$
    SELECT EXISTS (
        SELECT 1
          FROM public.operator_scope_grant AS grant_row
          JOIN public.operator_identity AS identity
            ON identity.id = grant_row.operator_id AND identity.enabled
         WHERE grant_row.operator_id = requested_operator_id
           AND grant_row.resource = requested_resource
           AND grant_row.action = requested_action
           AND grant_row.location_id = requested_location_id
           AND grant_row.revoked_at IS NULL
    );
$$;

CREATE SCHEMA kokonut_security;
CREATE OR REPLACE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE (tenant_id UUID, location_id UUID, actor_id UUID, actor_type TEXT)
LANGUAGE SQL
STABLE
SECURITY DEFINER
AS $$
    SELECT NULLIF(current_setting('test.tenant_id', TRUE), '')::UUID,
           NULLIF(current_setting('test.location_id', TRUE), '')::UUID,
           NULLIF(current_setting('test.actor_id', TRUE), '')::UUID,
           NULLIF(current_setting('test.actor_type', TRUE), '');
$$;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context() TO PUBLIC;

CREATE TABLE public.governance_tension (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tension_key VARCHAR(120) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    tension_type VARCHAR(40) NOT NULL CHECK (tension_type IN (
        'unmet_interest', 'unclear_accountability', 'authority_gap',
        'authority_conflict', 'commitment_risk', 'representation_gap',
        'consent_gap', 'evidence_gap', 'harm_risk', 'policy_gap',
        'cross_circle_dependency', 'role_overload'
    )),
    severity SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5),
    urgency SMALLINT NOT NULL CHECK (urgency BETWEEN 1 AND 5),
    scope_type VARCHAR(30) NOT NULL,
    scope_id UUID,
    reported_by_party_id UUID REFERENCES public.party(id),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'triaged', 'in_progress',
                          'resolved', 'deferred', 'rejected', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE public.governance_tension_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tension_id UUID NOT NULL REFERENCES public.governance_tension(id),
    actor_party_id UUID REFERENCES public.party(id),
    from_status VARCHAR(20),
    to_status VARCHAR(20) NOT NULL,
    action VARCHAR(60) NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE public.governance_circle (
    id UUID PRIMARY KEY,
    scope_type TEXT NOT NULL,
    scope_id UUID,
    status TEXT NOT NULL
);
CREATE TABLE public.governance_role (
    id UUID PRIMARY KEY,
    circle_id UUID NOT NULL REFERENCES public.governance_circle(id),
    status TEXT NOT NULL
);
CREATE TABLE public.governance_role_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES public.governance_role(id),
    party_id UUID NOT NULL REFERENCES public.party(id),
    assignment_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    assigned_by_party_id UUID REFERENCES public.party(id),
    approved_by_party_id UUID REFERENCES public.party(id),
    mandate TEXT,
    effective_from TIMESTAMPTZ,
    review_due_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (status <> 'active' OR approved_by_party_id IS NOT NULL)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.governance_role_assignment
    TO kokonut_runtime, kokonut_directus_runtime;

INSERT INTO public.organization VALUES
    ('a0000000-0000-4000-8000-000000000101', 'active');
INSERT INTO public.location VALUES
    ('a0000000-0000-4000-8000-000000000201',
     'a0000000-0000-4000-8000-000000000101', 'active');
INSERT INTO public.location_tenant_owner_verification VALUES
    ('a0000000-0000-4000-8000-000000000301',
     'a0000000-0000-4000-8000-000000000201',
     'a0000000-0000-4000-8000-000000000101', NULL);
INSERT INTO public.operator_identity VALUES
    ('a0000000-0000-4000-8000-000000000401', 'https://id.example', 'subject-one', 'One', TRUE),
    ('a0000000-0000-4000-8000-000000000402', 'https://id.example', 'subject-two', 'Two', TRUE),
    ('a0000000-0000-4000-8000-000000000403', 'https://id.example', 'subject-three', 'Three', TRUE),
    ('a0000000-0000-4000-8000-000000000404', 'https://id.example', 'subject-disabled', 'Disabled', FALSE);
INSERT INTO public.party VALUES
    ('a0000000-0000-4000-8000-000000000501', 'person', 'Person One', 'active'),
    ('a0000000-0000-4000-8000-000000000502', 'person', 'Person Two', 'active'),
    ('a0000000-0000-4000-8000-000000000503', 'organization', 'Not a person', 'active'),
    ('a0000000-0000-4000-8000-000000000504', 'person', 'Retired Person', 'retired');
INSERT INTO public.governance_circle VALUES
    ('a0000000-0000-4000-8000-000000000801', 'location', 'a0000000-0000-4000-8000-000000000201', 'active'),
    ('a0000000-0000-4000-8000-000000000802', 'network', NULL, 'active');
INSERT INTO public.governance_role VALUES
    ('a0000000-0000-4000-8000-000000000811', 'a0000000-0000-4000-8000-000000000801', 'active'),
    ('a0000000-0000-4000-8000-000000000812', 'a0000000-0000-4000-8000-000000000802', 'active');
INSERT INTO public.operator_organization_membership VALUES
    ('a0000000-0000-4000-8000-000000000601',
     'a0000000-0000-4000-8000-000000000401',
     'a0000000-0000-4000-8000-000000000101', NULL),
    ('a0000000-0000-4000-8000-000000000602',
     'a0000000-0000-4000-8000-000000000402',
     'a0000000-0000-4000-8000-000000000101', NULL),
    ('a0000000-0000-4000-8000-000000000603',
     'a0000000-0000-4000-8000-000000000403',
     'a0000000-0000-4000-8000-000000000101', NULL);
INSERT INTO public.operator_scope_grant VALUES
    ('a0000000-0000-4000-8000-000000000700', 'a0000000-0000-4000-8000-000000000401', 'governance_roles', 'create', 'a0000000-0000-4000-8000-000000000201', 'a0000000-0000-4000-8000-000000000101', NULL),
    ('a0000000-0000-4000-8000-000000000701', 'a0000000-0000-4000-8000-000000000401', 'governance_tension', 'create', 'a0000000-0000-4000-8000-000000000201', 'a0000000-0000-4000-8000-000000000101', NULL),
    ('a0000000-0000-4000-8000-000000000702', 'a0000000-0000-4000-8000-000000000401', 'governance_tension', 'submit', 'a0000000-0000-4000-8000-000000000201', 'a0000000-0000-4000-8000-000000000101', NULL),
    ('a0000000-0000-4000-8000-000000000703', 'a0000000-0000-4000-8000-000000000402', 'governance_tension', 'submit', 'a0000000-0000-4000-8000-000000000201', 'a0000000-0000-4000-8000-000000000101', NULL),
    ('a0000000-0000-4000-8000-000000000704', 'a0000000-0000-4000-8000-000000000403', 'governance_tension', 'create', 'a0000000-0000-4000-8000-000000000201', 'a0000000-0000-4000-8000-000000000101', NULL);
