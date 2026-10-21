-- Add the minimal AI-summary review schema after the signed-worker fixture
-- and migrations 405/419. All rows in this file are synthetic.
CREATE ROLE directus NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS NOINHERIT;

-- Minimal location-qualified source rows for migrations 523/524 and 530.
CREATE TABLE public.harvest_event (id UUID PRIMARY KEY, location_id UUID NOT NULL);
CREATE TABLE public.sales_event (
    id UUID PRIMARY KEY, location_id UUID NOT NULL,
    crop_cycle_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE TABLE public.crop_cycle (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, crop_id UUID NOT NULL
);
CREATE TABLE public.sensor_reading (id UUID PRIMARY KEY, location_id UUID NOT NULL);
CREATE TABLE public.expense_event (
    id UUID PRIMARY KEY, location_id UUID NOT NULL,
    category TEXT NOT NULL, amount NUMERIC NOT NULL, status TEXT NOT NULL
);
CREATE TABLE public.noi_snapshot (id UUID PRIMARY KEY, location_id UUID NOT NULL);
CREATE TABLE public.soil_carbon_measurement (id UUID PRIMARY KEY, location_id UUID NOT NULL);
CREATE TABLE public.species_observation (id UUID PRIMARY KEY, location_id UUID NOT NULL);
CREATE TABLE public.remote_sensing_observation (id UUID PRIMARY KEY, location_id UUID NOT NULL);
CREATE TABLE public.weather_observation (id UUID PRIMARY KEY, location_id UUID NOT NULL);
CREATE TABLE public.crop (id UUID PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE public.expense_category (id UUID PRIMARY KEY, name TEXT NOT NULL);

INSERT INTO public.harvest_event (id, location_id) VALUES
    ('e0000000-0000-4000-8000-000000000001', 'a0000000-0000-0000-0000-000000000001'),
    ('e0000000-0000-4000-8000-000000000002', 'a0000000-0000-0000-0000-000000000002');
INSERT INTO public.crop (id, name) VALUES
    ('e0000000-0000-4000-8000-000000000101', 'Synthetic crop');
INSERT INTO public.crop_cycle (id, location_id, crop_id) VALUES
    ('e0000000-0000-4000-8000-000000000102', 'a0000000-0000-0000-0000-000000000001',
     'e0000000-0000-4000-8000-000000000101');
INSERT INTO public.sales_event (id, location_id, crop_cycle_id, status) VALUES
    ('e0000000-0000-4000-8000-000000000103', 'a0000000-0000-0000-0000-000000000001',
     'e0000000-0000-4000-8000-000000000102', 'published');
INSERT INTO public.expense_category (id, name) VALUES
    ('e0000000-0000-4000-8000-000000000104', 'Operations');
INSERT INTO public.expense_event (id, location_id, category, amount, status) VALUES
    ('e0000000-0000-4000-8000-000000000105', 'a0000000-0000-0000-0000-000000000001',
     'Operations', 10, 'verified');

-- Published-view fixtures for capital-efficiency source manifests. Draft and
-- other-location rows verify that the setter cannot reference hidden records.
CREATE TABLE public.capital_efficiency_scenario (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE TABLE public.regenerative_efficiency_observation (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE TABLE public.governance_throughput_observation (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE TABLE public.capital_provider_utility_scenario (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE VIEW public.v_public_capital_efficiency_summary AS
    SELECT id, location_id FROM public.capital_efficiency_scenario WHERE status = 'published';
CREATE VIEW public.v_public_regenerative_efficiency_summary AS
    SELECT id, location_id FROM public.regenerative_efficiency_observation WHERE status = 'published';
CREATE VIEW public.v_public_governance_throughput_summary AS
    SELECT id, location_id FROM public.governance_throughput_observation WHERE status = 'published';
CREATE VIEW public.v_public_capital_provider_utility_summary AS
    SELECT id, location_id FROM public.capital_provider_utility_scenario WHERE status = 'published';
INSERT INTO public.capital_efficiency_scenario VALUES
    ('e0000000-0000-4000-8000-000000000201', 'a0000000-0000-0000-0000-000000000001', 'published'),
    ('e0000000-0000-4000-8000-000000000202', 'a0000000-0000-0000-0000-000000000001', 'draft'),
    ('e0000000-0000-4000-8000-000000000203', 'a0000000-0000-0000-0000-000000000002', 'published');
INSERT INTO public.regenerative_efficiency_observation VALUES
    ('e0000000-0000-4000-8000-000000000211', 'a0000000-0000-0000-0000-000000000001', 'published');
INSERT INTO public.governance_throughput_observation VALUES
    ('e0000000-0000-4000-8000-000000000221', 'a0000000-0000-0000-0000-000000000001', 'published');
INSERT INTO public.capital_provider_utility_scenario VALUES
    ('e0000000-0000-4000-8000-000000000231', 'a0000000-0000-0000-0000-000000000001', 'published');

CREATE TABLE public.bio_factory_batch (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE TABLE public.bio_input_provenance (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE TABLE public.bio_recipe_library (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE TABLE public.bio_factory_quality_test (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE VIEW public.v_public_bio_factory_batch_summary AS
    SELECT id, location_id FROM public.bio_factory_batch WHERE status = 'published';
CREATE VIEW public.v_public_bio_input_provenance_summary AS
    SELECT id, location_id FROM public.bio_input_provenance WHERE status = 'published';
CREATE VIEW public.v_public_bio_recipe_library_summary AS
    SELECT id, location_id FROM public.bio_recipe_library WHERE status = 'published';
CREATE VIEW public.v_public_bio_factory_quality_test_summary AS
    SELECT id, location_id FROM public.bio_factory_quality_test WHERE status = 'published';
INSERT INTO public.bio_factory_batch VALUES
    ('e0000000-0000-4000-8000-000000000301', 'a0000000-0000-0000-0000-000000000001', 'published');
INSERT INTO public.bio_input_provenance VALUES
    ('e0000000-0000-4000-8000-000000000311', 'a0000000-0000-0000-0000-000000000001', 'published');
INSERT INTO public.bio_recipe_library VALUES
    ('e0000000-0000-4000-8000-000000000321', 'a0000000-0000-0000-0000-000000000001', 'published');
INSERT INTO public.bio_factory_quality_test VALUES
    ('e0000000-0000-4000-8000-000000000331', 'a0000000-0000-0000-0000-000000000001', 'published');

DO $$
DECLARE
    source_table TEXT;
BEGIN
    FOREACH source_table IN ARRAY ARRAY[
        'harvest_event', 'sales_event', 'crop_cycle', 'sensor_reading',
        'expense_event', 'noi_snapshot', 'soil_carbon_measurement',
        'species_observation', 'remote_sensing_observation', 'weather_observation'
    ] LOOP
        EXECUTE pg_catalog.format(
            'ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', source_table
        );
        EXECUTE pg_catalog.format(
            'ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', source_table
        );
        EXECUTE pg_catalog.format(
            'CREATE POLICY ai_summary_worker_location_scope ON public.%I '
            'USING (location_id = NULLIF(current_setting(''kokonut.location_id'', TRUE), '''')::UUID)',
            source_table
        );
    END LOOP;
END;
$$;

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
