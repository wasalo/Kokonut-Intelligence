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

CREATE TABLE public.regenerative_outcome_summary (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE TABLE public.community_governance_mechanism (
    id UUID PRIMARY KEY, location_id UUID, status TEXT NOT NULL
);
CREATE TABLE public.replication_readiness_assessment (
    id UUID PRIMARY KEY, location_id UUID, status TEXT NOT NULL
);
CREATE TABLE public.adaptive_stewardship_review (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE VIEW public.v_public_regenerative_outcome_summary AS
    SELECT id, location_id FROM public.regenerative_outcome_summary WHERE status = 'published';
CREATE VIEW public.v_public_community_governance_mechanism AS
    SELECT id, location_id FROM public.community_governance_mechanism WHERE status = 'published';
CREATE VIEW public.v_public_replication_readiness_summary AS
    SELECT id, location_id FROM public.replication_readiness_assessment WHERE status = 'published';
CREATE VIEW public.v_public_adaptive_stewardship_summary AS
    SELECT id, location_id FROM public.adaptive_stewardship_review WHERE status = 'published';
INSERT INTO public.regenerative_outcome_summary VALUES
    ('e0000000-0000-4000-8000-000000000401', 'a0000000-0000-0000-0000-000000000001', 'published'),
    ('e0000000-0000-4000-8000-000000000402', 'a0000000-0000-0000-0000-000000000001', 'draft'),
    ('e0000000-0000-4000-8000-000000000403', 'a0000000-0000-0000-0000-000000000002', 'published');
INSERT INTO public.community_governance_mechanism VALUES
    ('e0000000-0000-4000-8000-000000000411', 'a0000000-0000-0000-0000-000000000001', 'published');
INSERT INTO public.replication_readiness_assessment VALUES
    ('e0000000-0000-4000-8000-000000000421', 'a0000000-0000-0000-0000-000000000001', 'published');
INSERT INTO public.adaptive_stewardship_review VALUES
    ('e0000000-0000-4000-8000-000000000431', 'a0000000-0000-0000-0000-000000000001', 'published');

-- Location-scoped fixture views for the remaining public synthesis sources.
DO $$
DECLARE
    source_pair TEXT[];
    source_index INTEGER := 501;
    source_id UUID;
BEGIN
    FOREACH source_pair SLICE 1 IN ARRAY ARRAY[
        ARRAY['time_liberation_observation', 'v_public_time_liberation_summary'],
        ARRAY['capital_alignment_assessment', 'v_public_capital_alignment_summary'],
        ARRAY['governance_inclusion_observation', 'v_public_governance_inclusion_summary'],
        ARRAY['land_stewardship_commitment', 'v_public_land_stewardship_summary'],
        ARRAY['gnh_alignment_assessment', 'v_public_gnh_alignment_summary'],
        ARRAY['cultural_preservation_plan', 'v_public_cultural_preservation_summary'],
        ARRAY['renewable_energy_plan', 'v_public_renewable_energy_summary'],
        ARRAY['vulnerable_group_access_plan', 'v_public_vulnerable_access_summary'],
        ARRAY['foundational_wellbeing_observation', 'v_public_foundational_wellbeing_summary'],
        ARRAY['financial_sustainability_plan', 'v_public_financial_sustainability_summary'],
        ARRAY['risk_mitigation_register', 'v_public_risk_mitigation_summary'],
        ARRAY['scaling_roadmap_milestone', 'v_public_scaling_roadmap_summary'],
        ARRAY['farm_launch_unit_economics', 'v_public_farm_launch_unit_economics'],
        ARRAY['adoption_barrier_assessment', 'v_public_adoption_barrier_assessment'],
        ARRAY['perpetual_value_stress_test', 'v_public_perpetual_value_stress_test']
    ] LOOP
        source_id := ('e0000000-0000-4000-8000-' || lpad(source_index::TEXT, 12, '0'))::UUID;
        EXECUTE format(
            'CREATE TABLE public.%I (id UUID PRIMARY KEY, location_id UUID, status TEXT NOT NULL)',
            source_pair[1]
        );
        EXECUTE format(
            'CREATE VIEW public.%I AS SELECT id, location_id, %L::TEXT AS public_summary FROM public.%I WHERE status = %L',
            source_pair[2], 'Synthetic source summary', source_pair[1], 'published'
        );
        EXECUTE format(
            'INSERT INTO public.%I (id, location_id, status) VALUES ($1, $2, $3)',
            source_pair[1]
        ) USING source_id, 'a0000000-0000-0000-0000-000000000001'::UUID, 'published';
        source_index := source_index + 1;
    END LOOP;
END;
$$;

-- Network-wide public view fixtures validate explicit network provenance.
CREATE TABLE public.bio_regional_input_availability (
    id UUID PRIMARY KEY, status TEXT NOT NULL
);
CREATE VIEW public.v_public_bio_regional_input_summary AS
    SELECT id, 'Synthetic public catalogue'::TEXT AS public_summary
    FROM public.bio_regional_input_availability WHERE status = 'published';
INSERT INTO public.bio_regional_input_availability VALUES
    ('e0000000-0000-4000-8000-000000000801', 'published');

CREATE TABLE public.network_scaling_target (id UUID PRIMARY KEY, status TEXT NOT NULL);
CREATE VIEW public.v_public_network_scaling_target AS
    SELECT id, 'Synthetic public catalogue'::TEXT AS public_summary
    FROM public.network_scaling_target WHERE status = 'published';
INSERT INTO public.network_scaling_target VALUES
    ('e0000000-0000-4000-8000-000000000802', 'published');

CREATE TABLE public.open_source_impact_artifact (id UUID PRIMARY KEY, status TEXT NOT NULL);
CREATE VIEW public.v_public_open_source_impact_artifact AS
    SELECT id, 'Synthetic public catalogue'::TEXT AS public_summary
    FROM public.open_source_impact_artifact WHERE status = 'published';
INSERT INTO public.open_source_impact_artifact VALUES
    ('e0000000-0000-4000-8000-000000000803', 'published');

CREATE TABLE public.green_paper_publication_review (id UUID PRIMARY KEY, status TEXT NOT NULL);
CREATE VIEW public.v_public_green_paper_publication_status AS
    SELECT id, 'Synthetic public catalogue'::TEXT AS public_summary
    FROM public.green_paper_publication_review WHERE status IN ('verified', 'published');
INSERT INTO public.green_paper_publication_review VALUES
    ('e0000000-0000-4000-8000-000000000804', 'published');

CREATE TABLE public.federation_protocol (id UUID PRIMARY KEY, status TEXT NOT NULL);
CREATE VIEW public.v_public_federation_protocol AS
    SELECT id, 'Synthetic public catalogue'::TEXT AS public_summary
    FROM public.federation_protocol WHERE status = 'published';
INSERT INTO public.federation_protocol VALUES
    ('e0000000-0000-4000-8000-000000000805', 'published');

CREATE TABLE public.participatory_signal_experiment (id UUID PRIMARY KEY, status TEXT NOT NULL);
CREATE VIEW public.v_public_participatory_signal_experiment AS
    SELECT id, 'Synthetic public catalogue'::TEXT AS public_summary
    FROM public.participatory_signal_experiment WHERE status = 'published';
INSERT INTO public.participatory_signal_experiment VALUES
    ('e0000000-0000-4000-8000-000000000806', 'published');

-- A shared source is not farm-owned: mixed manifests must accept this ID only
-- alongside the requested location's own row and report both scopes.
INSERT INTO public.farm_launch_unit_economics (id, location_id, status) VALUES
    ('e0000000-0000-4000-8000-000000000807', NULL, 'published');
INSERT INTO public.farm_launch_unit_economics (id, location_id, status) VALUES
    ('e0000000-0000-4000-8000-000000000809', 'a0000000-0000-0000-0000-000000000002', 'published');

CREATE TABLE public.cultural_context_record (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL,
    consent_given BOOLEAN NOT NULL, is_public BOOLEAN NOT NULL
);
CREATE TABLE public.wellbeing_metric_observation (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE TABLE public.participatory_action_record (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL
);
CREATE TABLE public.stakeholder_feedback (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL,
    consent_given BOOLEAN NOT NULL, is_public BOOLEAN NOT NULL
);
CREATE VIEW public.v_public_cultural_context_summary AS
    SELECT id, location_id, 'Synthetic public culture'::TEXT AS public_summary
    FROM public.cultural_context_record
    WHERE status = 'published' AND consent_given AND is_public;
CREATE VIEW public.v_public_wellbeing_metric_summary AS
    SELECT id, location_id, 'Synthetic public wellbeing'::TEXT AS public_summary
    FROM public.wellbeing_metric_observation WHERE status = 'published';
CREATE VIEW public.v_public_participatory_governance_summary AS
    SELECT id, location_id, 'Synthetic public participation'::TEXT AS public_summary
    FROM public.participatory_action_record WHERE status = 'published';
CREATE VIEW public.v_public_stakeholder_feedback_summary AS
    SELECT id, location_id, 'Synthetic consented public feedback'::TEXT AS public_summary
    FROM public.stakeholder_feedback
    WHERE status = 'published' AND consent_given AND is_public;
INSERT INTO public.cultural_context_record VALUES
    ('e0000000-0000-4000-8000-000000000601', 'a0000000-0000-0000-0000-000000000001', 'published', TRUE, TRUE);
INSERT INTO public.wellbeing_metric_observation VALUES
    ('e0000000-0000-4000-8000-000000000602', 'a0000000-0000-0000-0000-000000000001', 'published');
INSERT INTO public.participatory_action_record VALUES
    ('e0000000-0000-4000-8000-000000000603', 'a0000000-0000-0000-0000-000000000001', 'published');
INSERT INTO public.stakeholder_feedback VALUES
    ('e0000000-0000-4000-8000-000000000604', 'a0000000-0000-0000-0000-000000000001', 'published', TRUE, TRUE),
    ('e0000000-0000-4000-8000-000000000605', 'a0000000-0000-0000-0000-000000000001', 'published', FALSE, FALSE);

CREATE TABLE public.anti_capture_governance_policy (
    id UUID PRIMARY KEY, location_id UUID, status TEXT NOT NULL
);
CREATE TABLE public.commons_redistribution_policy (
    id UUID PRIMARY KEY, location_id UUID, status TEXT NOT NULL
);
CREATE TABLE public.algorithmic_redistribution_mechanism (
    id UUID PRIMARY KEY, location_id UUID, status TEXT NOT NULL
);
CREATE VIEW public.v_public_anti_capture_governance_policy AS
    SELECT id, location_id, 'Synthetic public policy'::TEXT AS public_summary
    FROM public.anti_capture_governance_policy WHERE status = 'published';
CREATE VIEW public.v_public_commons_redistribution_policy AS
    SELECT id, location_id, 'Synthetic public policy'::TEXT AS public_summary
    FROM public.commons_redistribution_policy WHERE status = 'published';
CREATE VIEW public.v_public_algorithmic_redistribution_mechanism AS
    SELECT id, location_id, 'Synthetic public mechanism'::TEXT AS public_summary
    FROM public.algorithmic_redistribution_mechanism WHERE status = 'published';
INSERT INTO public.anti_capture_governance_policy VALUES
    ('e0000000-0000-4000-8000-000000000701', 'a0000000-0000-0000-0000-000000000001', 'published'),
    ('e0000000-0000-4000-8000-000000000808', NULL, 'published');
INSERT INTO public.commons_redistribution_policy VALUES
    ('e0000000-0000-4000-8000-000000000702', 'a0000000-0000-0000-0000-000000000001', 'published'),
    ('e0000000-0000-4000-8000-000000000704', NULL, 'published');
INSERT INTO public.algorithmic_redistribution_mechanism VALUES
    ('e0000000-0000-4000-8000-000000000703', 'a0000000-0000-0000-0000-000000000001', 'published');

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
