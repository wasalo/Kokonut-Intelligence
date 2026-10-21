-- Add the minimal AI-summary review schema after the signed-worker fixture
-- and migrations 405/419. All rows in this file are synthetic.
CREATE ROLE directus NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS NOINHERIT;

CREATE TABLE public.operator_identity (
    id UUID PRIMARY KEY
);
CREATE TABLE public.operator_scope_grant (
    id UUID PRIMARY KEY DEFAULT public.gen_random_uuid(),
    operator_id UUID NOT NULL,
    location_id UUID NOT NULL,
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    revoked_at TIMESTAMPTZ
);
CREATE TABLE public.ai_summary (
    id UUID PRIMARY KEY DEFAULT public.gen_random_uuid(),
    subject_type TEXT NOT NULL,
    subject_id UUID NOT NULL,
    summary_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source_tables TEXT[],
    model_version TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    created_by UUID,
    CONSTRAINT chk_ai_summary_agent_draft_only CHECK (
        created_by IS NULL OR status IN ('draft', 'submitted', 'rejected')
    )
);
CREATE TABLE public.lifecycle_transition (
    id UUID PRIMARY KEY DEFAULT public.gen_random_uuid(),
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    transitioned_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    actor_id UUID,
    actor_type TEXT
);
CREATE TABLE public.agent_worker_ai_summary_test_result (
    summary_id UUID NOT NULL
);
GRANT SELECT ON TABLE public.agent_worker_ai_summary_test_result TO kokonut_runtime;

CREATE OR REPLACE FUNCTION public.fn_record_lifecycle_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status IS NOT DISTINCT FROM NEW.status THEN
        RETURN NEW;
    END IF;
    INSERT INTO public.lifecycle_transition (
        entity_type, entity_id, from_status, to_status, actor_id, actor_type
    ) VALUES (
        TG_TABLE_NAME, NEW.id, OLD.status, NEW.status,
        NULLIF(pg_catalog.current_setting('kokonut.actor_id', TRUE), '')::UUID,
        NULLIF(pg_catalog.current_setting('kokonut.actor_type', TRUE), '')
    );
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_lt_ai_summary
AFTER UPDATE OF status ON public.ai_summary
FOR EACH ROW EXECUTE FUNCTION public.fn_record_lifecycle_transition();

CREATE OR REPLACE FUNCTION public.operator_scope_grant_allows(
    requested_operator_id UUID,
    requested_resource TEXT,
    requested_action TEXT,
    requested_location_id UUID
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY INVOKER
AS $$
    SELECT EXISTS (
        SELECT 1
          FROM public.operator_scope_grant AS grant_row
         WHERE grant_row.operator_id = requested_operator_id
           AND grant_row.resource = requested_resource
           AND grant_row.action = requested_action
           AND grant_row.location_id = requested_location_id
           AND grant_row.revoked_at IS NULL
    )
$$;

GRANT USAGE ON SCHEMA public TO kokonut_runtime, directus;
GRANT SELECT, UPDATE ON TABLE public.ai_summary TO kokonut_runtime, directus;

INSERT INTO public.operator_identity (id) VALUES
    ('a0000000-0000-0000-0000-000000000902');
INSERT INTO public.operator_scope_grant (
    operator_id, location_id, resource, action
) VALUES (
    'a0000000-0000-0000-0000-000000000902',
    'a0000000-0000-0000-0000-000000000001',
    'ai_summary', 'review'
);
INSERT INTO public.ai_summary (
    id, subject_type, subject_id, summary_type, content,
    source_tables, model_version, status, created_by
) VALUES (
    'c0000000-0000-4000-8000-000000000099', 'location',
    'a0000000-0000-0000-0000-000000000001', 'operations',
    'Legacy unattributed summary remains blocked from approval.',
    ARRAY['harvest_event'], 'legacy-v1', 'draft', NULL
);
