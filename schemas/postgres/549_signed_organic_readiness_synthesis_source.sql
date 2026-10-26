-- Register organic-readiness synthesis with the signed source worker.
-- Analytics keep their legacy query implementation, but the worker resolves
-- their relation names only to narrow location-filtered views in the source
-- schema. Published view IDs provide bounded, independently checked lineage.

BEGIN;

-- A worker-created draft may use the new task only after the code registry and
-- the database receipt constraint are updated together.
ALTER TABLE public.ai_summary_agent_draft_request
    DROP CONSTRAINT IF EXISTS ai_summary_agent_draft_request_registered_type_check;
ALTER TABLE public.ai_summary_agent_draft_request
    ADD CONSTRAINT ai_summary_agent_draft_request_registered_type_check
    CHECK (summary_type IN (
        'operations',
        'financial',
        'environmental',
        'combined',
        'bio_factory',
        'capital_efficiency',
        'commons_liberation',
        'stakeholder_feedback',
        'gnh_alignment',
        'holistic_wellbeing',
        'kokonut_commons',
        'open_source_capitalist',
        'financial_resilience',
        'regenerative_outcomes',
        'organic_readiness'
    )) NOT VALID;
COMMENT ON CONSTRAINT ai_summary_agent_draft_request_registered_type_check
    ON public.ai_summary_agent_draft_request IS
    'Allows new signed-worker receipts only for the four deterministic and eleven registered shared synthesis summary types; existing legacy receipts remain readable.';

-- All source relations are location-owned. The checklist contributes only an
-- exact-location count and has no public row-reference projection.
ALTER TABLE kokonut_security.ai_summary_source_manifest
    DROP CONSTRAINT IF EXISTS ai_summary_source_manifest_source_table_check;
ALTER TABLE kokonut_security.ai_summary_source_manifest
    ADD CONSTRAINT ai_summary_source_manifest_source_table_check CHECK (source_table IN (
        'harvest_event', 'sales_event', 'crop_cycle', 'sensor_reading',
        'expense_event', 'noi_snapshot', 'soil_carbon_measurement',
        'species_observation', 'remote_sensing_observation', 'weather_observation',
        'crop', 'expense_category', 'capital_efficiency_scenario',
        'regenerative_efficiency_observation', 'governance_throughput_observation',
        'capital_provider_utility_scenario', 'bio_factory_batch',
        'bio_input_provenance', 'bio_recipe_library', 'bio_factory_quality_test',
        'regenerative_outcome_summary', 'community_governance_mechanism',
        'replication_readiness_assessment', 'adaptive_stewardship_review',
        'time_liberation_observation', 'capital_alignment_assessment',
        'governance_inclusion_observation', 'land_stewardship_commitment',
        'gnh_alignment_assessment', 'cultural_preservation_plan',
        'renewable_energy_plan', 'vulnerable_group_access_plan',
        'foundational_wellbeing_observation', 'financial_sustainability_plan',
        'risk_mitigation_register', 'scaling_roadmap_milestone',
        'farm_launch_unit_economics', 'adoption_barrier_assessment',
        'perpetual_value_stress_test', 'cultural_context_record',
        'wellbeing_metric_observation', 'participatory_action_record',
        'stakeholder_feedback', 'anti_capture_governance_policy',
        'commons_redistribution_policy', 'algorithmic_redistribution_mechanism',
        'bio_regional_input_availability', 'network_scaling_target',
        'open_source_impact_artifact', 'green_paper_publication_review',
        'federation_protocol', 'participatory_signal_experiment',
        'organic_readiness_assessment', 'organic_transition_plan',
        'organic_input_audit', 'buffer_zone', 'harvest_handling_record',
        'organic_certification_record', 'organic_compliance_checklist',
        'prohibited_substance_record'
    ));

INSERT INTO kokonut_security.ai_summary_source_reference_view
    (source_table, source_view_name, source_scope)
VALUES
    ('organic_readiness_assessment', 'v_public_organic_readiness', 'location'),
    ('organic_transition_plan', 'v_public_organic_transition', 'location'),
    ('organic_input_audit', 'v_public_organic_input_audit', 'location'),
    ('buffer_zone', 'v_public_buffer_zone_status', 'location'),
    ('harvest_handling_record', 'v_public_harvest_segregation', 'location'),
    ('organic_certification_record', 'v_public_organic_certifications', 'location'),
    ('prohibited_substance_record', 'v_public_prohibited_substance_audit', 'location')
ON CONFLICT (source_table) DO UPDATE
    SET source_view_name = EXCLUDED.source_view_name,
        source_scope = EXCLUDED.source_scope;

-- The source-view owner is NOLOGIN and has no role memberships. Remove stale
-- raw-table grants before giving it only the columns needed by the legacy
-- analytics functions. The reader itself receives no public-table access.
REVOKE ALL PRIVILEGES ON TABLE
    public.organic_readiness_assessment,
    public.organic_transition_plan,
    public.organic_input_audit,
    public.buffer_zone,
    public.harvest_handling_record,
    public.organic_certification_record,
    public.organic_compliance_checklist,
    public.prohibited_substance_record
FROM kokonut_agent_summary_source_view_owner,
     kokonut_agent_summary_source_reader,
     kokonut_agent_summary_source_login;

GRANT SELECT (id, location_id) ON TABLE public.organic_compliance_checklist
TO kokonut_agent_summary_source_view_owner;

GRANT SELECT (
    id, location_id, assessment_date, standard, overall_score,
    transition_progress_pct, soil_health_score, input_compliance_pct,
    pest_management_score, biodiversity_score, buffer_zone_score,
    record_completeness_pct, training_completion_pct,
    harvest_segregation_score, barriers, recommendations
) ON TABLE public.v_public_organic_readiness
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, standard, transition_start_date,
    expected_certification_date, current_year, total_years_required, status,
    prohibited_substance_free_date, buffer_zone_established_date,
    record_keeping_ready_date, training_completed_date,
    organic_management_plan_date, readiness_score, barriers
) ON TABLE public.v_public_organic_transition
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, application_date, input_category, input_source,
    organic_certified, is_prohibited
) ON TABLE public.v_public_organic_input_audit
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, buffer_name, buffer_type, width_m, length_m, area_m2,
    adjacent_use, condition_status, establishment_date, last_inspection_date
) ON TABLE public.v_public_buffer_zone_status
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, organic_segregated, equipment_cleaned,
    temperature_controlled, buyer_requirements_met, contamination_risk,
    organic_lot_number
) ON TABLE public.v_public_harvest_segregation
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (id, location_id) ON TABLE
    public.v_public_organic_certifications
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (id, location_id, compliance_status, withdrawal_end_date)
ON TABLE public.v_public_prohibited_substance_audit
TO kokonut_agent_summary_source_view_owner;

GRANT CREATE ON SCHEMA kokonut_agent_source
TO kokonut_agent_summary_source_view_owner;

CREATE OR REPLACE VIEW kokonut_agent_source.organic_readiness_assessment
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id, source_row.assessment_date,
       source_row.standard, source_row.overall_score,
       source_row.transition_progress_pct, source_row.soil_health_score,
       source_row.input_compliance_pct, source_row.pest_management_score,
       source_row.biodiversity_score, source_row.buffer_zone_score,
       source_row.record_completeness_pct, source_row.training_completion_pct,
       source_row.harvest_segregation_score, source_row.barriers,
       source_row.recommendations
  FROM public.v_public_organic_readiness AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
ALTER VIEW kokonut_agent_source.organic_readiness_assessment
    OWNER TO kokonut_agent_summary_source_view_owner;

CREATE OR REPLACE VIEW kokonut_agent_source.organic_transition_plan
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id, source_row.standard,
       source_row.transition_start_date, source_row.expected_certification_date,
       source_row.current_year, source_row.total_years_required, source_row.status,
       source_row.prohibited_substance_free_date,
       source_row.buffer_zone_established_date, source_row.record_keeping_ready_date,
       source_row.training_completed_date, source_row.organic_management_plan_date,
       source_row.readiness_score, source_row.barriers
  FROM public.v_public_organic_transition AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
ALTER VIEW kokonut_agent_source.organic_transition_plan
    OWNER TO kokonut_agent_summary_source_view_owner;

CREATE OR REPLACE VIEW kokonut_agent_source.organic_input_audit
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id, source_row.application_date,
       source_row.input_category, source_row.input_source,
       source_row.organic_certified, source_row.is_prohibited
  FROM public.v_public_organic_input_audit AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
ALTER VIEW kokonut_agent_source.organic_input_audit
    OWNER TO kokonut_agent_summary_source_view_owner;

CREATE OR REPLACE VIEW kokonut_agent_source.buffer_zone
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id, source_row.buffer_name,
       source_row.buffer_type, source_row.width_m, source_row.length_m,
       source_row.area_m2, source_row.adjacent_use, source_row.condition_status,
       source_row.establishment_date, source_row.last_inspection_date
  FROM public.v_public_buffer_zone_status AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
ALTER VIEW kokonut_agent_source.buffer_zone
    OWNER TO kokonut_agent_summary_source_view_owner;

CREATE OR REPLACE VIEW kokonut_agent_source.harvest_handling_record
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id, source_row.organic_segregated,
       source_row.equipment_cleaned, source_row.temperature_controlled,
       source_row.buyer_requirements_met, source_row.contamination_risk,
       source_row.organic_lot_number
  FROM public.v_public_harvest_segregation AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
ALTER VIEW kokonut_agent_source.harvest_handling_record
    OWNER TO kokonut_agent_summary_source_view_owner;

CREATE OR REPLACE VIEW kokonut_agent_source.organic_certification_record
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id
  FROM public.v_public_organic_certifications AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
ALTER VIEW kokonut_agent_source.organic_certification_record
    OWNER TO kokonut_agent_summary_source_view_owner;

-- The old completeness contract counts these rows only; it never reads their
-- findings, identities, evidence, or narrative fields.
CREATE OR REPLACE VIEW kokonut_agent_source.organic_compliance_checklist
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id
  FROM public.organic_compliance_checklist AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
ALTER VIEW kokonut_agent_source.organic_compliance_checklist
    OWNER TO kokonut_agent_summary_source_view_owner;

CREATE OR REPLACE VIEW kokonut_agent_source.prohibited_substance_record
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id, source_row.compliance_status,
       source_row.withdrawal_end_date
  FROM public.v_public_prohibited_substance_audit AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
ALTER VIEW kokonut_agent_source.prohibited_substance_record
    OWNER TO kokonut_agent_summary_source_view_owner;

-- Provenance wrappers intentionally expose only stable record IDs and exact
-- location ownership. They mirror the same public projections used above, so
-- the existing immutable manifest verifier can reconcile counts and IDs.
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_organic_readiness
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id
  FROM public.v_public_organic_readiness AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_organic_transition
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id
  FROM public.v_public_organic_transition AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_organic_input_audit
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id
  FROM public.v_public_organic_input_audit AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_buffer_zone_status
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id
  FROM public.v_public_buffer_zone_status AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_organic_harvest_segregation
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id
  FROM public.v_public_harvest_segregation AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_organic_certifications
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id
  FROM public.v_public_organic_certifications AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_organic_prohibited_substance_audit
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id
  FROM public.v_public_prohibited_substance_audit AS source_row
 WHERE EXISTS (
     SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
      WHERE scope.location_id = source_row.location_id
 );

ALTER VIEW kokonut_agent_source.v_public_organic_readiness
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_organic_transition
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_organic_input_audit
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_buffer_zone_status
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_organic_harvest_segregation
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_organic_certifications
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_organic_prohibited_substance_audit
    OWNER TO kokonut_agent_summary_source_view_owner;

REVOKE ALL PRIVILEGES ON TABLE
    kokonut_agent_source.organic_readiness_assessment,
    kokonut_agent_source.organic_transition_plan,
    kokonut_agent_source.organic_input_audit,
    kokonut_agent_source.buffer_zone,
    kokonut_agent_source.harvest_handling_record,
    kokonut_agent_source.organic_certification_record,
    kokonut_agent_source.organic_compliance_checklist,
    kokonut_agent_source.prohibited_substance_record,
    kokonut_agent_source.v_public_organic_readiness,
    kokonut_agent_source.v_public_organic_transition,
    kokonut_agent_source.v_public_organic_input_audit,
    kokonut_agent_source.v_public_buffer_zone_status,
    kokonut_agent_source.v_public_organic_harvest_segregation,
    kokonut_agent_source.v_public_organic_certifications,
    kokonut_agent_source.v_public_organic_prohibited_substance_audit
FROM PUBLIC, kokonut_agent_summary_source_login,
     kokonut_agent_summary_source_reader;
GRANT SELECT ON TABLE
    kokonut_agent_source.organic_readiness_assessment,
    kokonut_agent_source.organic_transition_plan,
    kokonut_agent_source.organic_input_audit,
    kokonut_agent_source.buffer_zone,
    kokonut_agent_source.harvest_handling_record,
    kokonut_agent_source.organic_certification_record,
    kokonut_agent_source.organic_compliance_checklist,
    kokonut_agent_source.prohibited_substance_record,
    kokonut_agent_source.v_public_organic_readiness,
    kokonut_agent_source.v_public_organic_transition,
    kokonut_agent_source.v_public_organic_input_audit,
    kokonut_agent_source.v_public_buffer_zone_status,
    kokonut_agent_source.v_public_organic_harvest_segregation,
    kokonut_agent_source.v_public_organic_certifications,
    kokonut_agent_source.v_public_organic_prohibited_substance_audit
TO kokonut_agent_summary_source_reader;

GRANT SELECT (id, location_id) ON TABLE
    public.v_public_organic_readiness,
    public.v_public_organic_transition,
    public.v_public_organic_input_audit,
    public.v_public_buffer_zone_status,
    public.v_public_harvest_segregation,
    public.v_public_organic_certifications,
    public.v_public_prohibited_substance_audit
TO kokonut_ai_summary_drafter;

REVOKE ALL PRIVILEGES ON TABLE
    public.v_public_organic_readiness,
    public.v_public_organic_transition,
    public.v_public_organic_input_audit,
    public.v_public_buffer_zone_status,
    public.v_public_harvest_segregation,
    public.v_public_organic_certifications,
    public.v_public_prohibited_substance_audit
FROM kokonut_agent_summary_source_reader,
     kokonut_agent_summary_source_login;

REVOKE CREATE ON SCHEMA kokonut_agent_source
FROM kokonut_agent_summary_source_view_owner,
     kokonut_agent_summary_source_reader,
     kokonut_agent_summary_source_login;

DO $$
BEGIN
    IF pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_reader',
        'public.organic_readiness_assessment', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_reader',
        'public.organic_transition_plan', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_reader',
        'public.organic_input_audit', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_reader',
        'public.buffer_zone', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_reader',
        'public.harvest_handling_record', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_reader',
        'public.organic_certification_record', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_reader',
        'public.organic_compliance_checklist', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_reader',
        'public.prohibited_substance_record', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'organic synthesis reader can bypass scoped source views';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.unnest(ARRAY[
              'organic_readiness_assessment', 'organic_transition_plan',
              'organic_input_audit', 'buffer_zone', 'harvest_handling_record',
              'organic_certification_record', 'organic_compliance_checklist',
              'prohibited_substance_record', 'v_public_organic_readiness',
              'v_public_organic_transition', 'v_public_organic_input_audit',
              'v_public_buffer_zone_status', 'v_public_organic_harvest_segregation',
              'v_public_organic_certifications',
              'v_public_organic_prohibited_substance_audit'
          ]) AS source_relation(relation_name)
         WHERE NOT pg_catalog.has_table_privilege(
             'kokonut_agent_summary_source_reader',
             pg_catalog.format('kokonut_agent_source.%I', relation_name), 'SELECT'
         )
    ) THEN
        RAISE EXCEPTION 'organic synthesis reader is missing a scoped source view';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_agent_summary_source_view_owner'
            OR member_role.rolname = 'kokonut_agent_summary_source_view_owner'
    ) THEN
        RAISE EXCEPTION 'agent synthesis source view owner must have no role memberships';
    END IF;
END;
$$;

COMMENT ON SCHEMA kokonut_agent_source IS
    'Signed exact-location source views for deterministic summaries, shared synthesis, Delphi, and organic readiness; organic analytics relations contain only query-required columns.';

COMMIT;
