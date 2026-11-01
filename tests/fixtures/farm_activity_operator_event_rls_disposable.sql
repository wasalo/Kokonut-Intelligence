-- Minimal canonical activity schema needed to replay migrations 404 and 728.
-- Operator identity, signed-context, and synthetic tenant rows are supplied by
-- operator_tenant_context_disposable.sql.

CREATE TABLE public.farm (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES public.location(id)
);

CREATE TABLE public.plot (
    id UUID PRIMARY KEY,
    farm_id UUID NOT NULL REFERENCES public.farm(id)
);

CREATE TABLE public.crop_cycle (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES public.location(id)
);

CREATE TABLE public.farm_task (
    id UUID PRIMARY KEY,
    farm_id UUID REFERENCES public.farm(id),
    location_id UUID NOT NULL REFERENCES public.location(id)
);

CREATE TABLE public.staff (id UUID PRIMARY KEY);

CREATE TABLE public.schema_version (
    version TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_by TEXT NOT NULL
);

CREATE TABLE public.farm_activity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_id UUID REFERENCES public.farm(id),
    plot_id UUID REFERENCES public.plot(id),
    crop_cycle_id UUID REFERENCES public.crop_cycle(id),
    farm_task_id UUID REFERENCES public.farm_task(id),
    location_id UUID NOT NULL REFERENCES public.location(id),
    activity_type VARCHAR(100) NOT NULL,
    activity_date DATE NOT NULL,
    description TEXT,
    labor_hours NUMERIC(8, 2),
    labor_cost NUMERIC(12, 2),
    materials_used JSONB DEFAULT '[]'::jsonb,
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(20),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

INSERT INTO public.location (id, organization_id, status)
VALUES (
    'a0000000-0000-0000-0000-000000000002',
    'a0000000-0000-0000-0000-000000000802',
    'active'
);

INSERT INTO public.location_tenant_owner_verification (
    id, location_id, organization_id
) VALUES (
    'a0000000-0000-0000-0000-000000000902',
    'a0000000-0000-0000-0000-000000000002',
    'a0000000-0000-0000-0000-000000000802'
);

INSERT INTO public.operator_scope_grant (
    operator_id, resource, action, location_id, organization_id
) VALUES
    ('a0000000-0000-0000-0000-000000000901', 'farm_activity', 'create_draft',
     'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000801'),
    ('a0000000-0000-0000-0000-000000000901', 'farm_activity', 'read_detail',
     'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000801'),
    ('a0000000-0000-0000-0000-000000000901', 'farm_activity', 'submit',
     'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000801'),
    ('a0000000-0000-0000-0000-000000000902', 'farm_activity', 'create_draft',
     'a0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000802'),
    ('a0000000-0000-0000-0000-000000000902', 'farm_activity', 'read_detail',
     'a0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000802'),
    ('a0000000-0000-0000-0000-000000000902', 'farm_activity', 'submit',
     'a0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000802');

-- Keep the parent-table behavior needed to exercise migration 404's guarded
-- Gateway triggers. Migration 728 narrows only the audit ledger reads.
GRANT SELECT, INSERT, UPDATE ON public.farm_activity TO kokonut_runtime;
-- The real runtime role receives these location-scope reference reads during
-- first provisioning; migration 404's Gateway guards invoke the canonical
-- SECURITY INVOKER operator_scope_grant_allows function as kokonut_runtime.
GRANT SELECT ON TABLE
    public.location,
    public.organization,
    public.operator_identity,
    public.operator_scope_grant,
    public.operator_organization_membership,
    public.location_tenant_owner_verification,
    public.location_organization_share
TO kokonut_runtime;
