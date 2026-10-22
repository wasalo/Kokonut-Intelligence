-- Register ecological-modeling synthesis behind the signed, exact-location
-- worker source boundary. Legacy analytics relation names resolve only to
-- narrow projections in kokonut_agent_source.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_view_owner'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_reader'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_login'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_ai_summary_drafter'
    ) THEN
        RAISE EXCEPTION 'signed synthesis source roles from migration 541 are required';
    END IF;
END;
$$;

ALTER TABLE public.ai_summary_agent_draft_request
    DROP CONSTRAINT IF EXISTS ai_summary_agent_draft_request_registered_type_check;
ALTER TABLE public.ai_summary_agent_draft_request
    ADD CONSTRAINT ai_summary_agent_draft_request_registered_type_check
    CHECK (summary_type IN (
        'operations', 'financial', 'environmental', 'combined',
        'bio_factory', 'capital_efficiency', 'commons_liberation',
        'stakeholder_feedback', 'gnh_alignment', 'holistic_wellbeing',
        'kokonut_commons', 'open_source_capitalist', 'financial_resilience',
        'regenerative_outcomes', 'organic_readiness', 'ecological_modeling'
    )) NOT VALID;
COMMENT ON CONSTRAINT ai_summary_agent_draft_request_registered_type_check
    ON public.ai_summary_agent_draft_request IS
    'Allows new signed-worker receipts only for the four deterministic and twelve registered shared synthesis summary types; existing legacy receipts remain readable.';

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
        'prohibited_substance_record', 'ecological_interaction',
        'energy_flow_measurement', 'population_dynamics_record',
        'soil_input_application', 'pest_observation', 'biocontrol_release',
        'resource_consumption', 'livestock_group', 'feed_intake_record',
        'token_reward_distribution', 'reward_calibration_model'
    ));

-- Existing public-safe projections define lifecycle and farm-registry
-- eligibility. Species conservation gets a new minimal row projection because
-- the existing public views expose only aggregate richness, not source IDs.
CREATE OR REPLACE VIEW public.v_public_ecological_species_conservation AS
SELECT observation.id,
       observation.location_id,
       observation.species_name,
       observation.conservation_status,
       observation.count,
       observation.status
  FROM public.species_observation AS observation
  JOIN public.location AS farm ON farm.id = observation.location_id
 WHERE farm.status = 'active'
   AND observation.status IN ('verified', 'published')
   AND observation.conservation_status IS NOT NULL
   AND EXISTS (
       SELECT 1 FROM public.farm_registry_record AS registry
        WHERE registry.location_id = farm.id
          AND registry.status IN ('verified', 'published')
   );
REVOKE ALL PRIVILEGES ON TABLE public.v_public_ecological_species_conservation
FROM PUBLIC;
COMMENT ON VIEW public.v_public_ecological_species_conservation IS
    'Minimal verified species conservation projection; excludes observer, evidence, and narrative fields.';

INSERT INTO kokonut_security.ai_summary_source_reference_view
    (source_table, source_view_name, source_scope)
VALUES
    ('ecological_interaction', 'v_public_ecological_interaction_summary', 'location'),
    ('energy_flow_measurement', 'v_public_energy_flow_summary', 'location'),
    ('population_dynamics_record', 'v_public_population_dynamics_summary', 'location'),
    ('soil_input_application', 'v_public_soil_input_retention', 'location'),
    ('pest_observation', 'v_public_pest_trends', 'location'),
    ('biocontrol_release', 'v_public_biocontrol_effectiveness', 'location'),
    ('resource_consumption', 'v_public_resource_efficiency', 'location'),
    ('species_observation', 'v_public_ecological_species_conservation', 'location'),
    ('token_reward_distribution', 'v_public_token_reward_distribution', 'location'),
    ('reward_calibration_model', 'v_public_reward_calibration', 'location')
ON CONFLICT (source_table) DO UPDATE
    SET source_view_name = EXCLUDED.source_view_name,
        source_scope = EXCLUDED.source_scope;

GRANT USAGE ON SCHEMA public, kokonut_security, kokonut_agent_source
    TO kokonut_agent_summary_source_view_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_summary_source_view_owner;
GRANT CREATE ON SCHEMA kokonut_agent_source
    TO kokonut_agent_summary_source_view_owner;

-- The view owner reads only the columns needed by the legacy calculations and
-- row-reference IDs. The source login and reader receive no base-table access.
GRANT SELECT (
    id, location_id, interaction_type, interaction_strength, status
) ON TABLE public.v_public_ecological_interaction_summary
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, from_trophic_level, to_trophic_level,
    biomass_transferred_kg, conversion_efficiency_pct, status
) ON TABLE public.v_public_energy_flow_summary
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, species_name, species_common_name, trophic_level,
    record_date, population_count, status
) ON TABLE public.v_public_population_dynamics_summary
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, input_type, input_name, quantity_kg, residual_pct,
    application_date, residual_measurement_date, status
) ON TABLE public.v_public_soil_input_retention
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, observation_date, pest_species, pest_common_name,
    pest_category, severity, incidence_count, affected_area_pct,
    outbreak_probability_pct, temperature_c, humidity_pct, predator_count,
    natural_enemy_present, status
) ON TABLE public.v_public_pest_trends
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (id, location_id)
ON TABLE public.v_public_biocontrol_effectiveness
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, resource_type, unit, component, quantity, is_estimated,
    status
) ON TABLE public.v_public_resource_efficiency
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, livestock_group_id, record_date, quantity_kg,
    per_animal_kg, status
) ON TABLE public.v_public_livestock_feed_intake
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (id, location_id, reward_type, token_type, token_amount,
    usd_value, linked_metric_key, linked_metric_value, distribution_method,
    is_onchain, status)
ON TABLE public.v_public_token_reward_distribution
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (id, location_id, model_name, model_type, run_date,
    input_metrics, output_weights, calibration_score,
    total_tokens_distributed, token_per_unit_output, epoch,
    confidence_level, status)
ON TABLE public.v_public_reward_calibration
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (id, location_id, species_name, conservation_status, count, status)
ON TABLE public.v_public_ecological_species_conservation
TO kokonut_agent_summary_source_view_owner;

GRANT SELECT (id, location_id, quantity, status)
ON TABLE public.harvest_event TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (id, status)
ON TABLE public.location TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (location_id, status)
ON TABLE public.farm_registry_record TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, release_date, predator_species, predator_common_name,
    predator_category, target_pest, release_count, effectiveness_pct,
    pest_reduction_pct, release_density_per_m2, follow_up_date, status
) ON TABLE public.biocontrol_release
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, group_name, species, breed, animal_count, feed_type,
    average_weight_kg, status
) ON TABLE public.livestock_group
TO kokonut_agent_summary_source_view_owner;
GRANT SELECT (
    id, location_id, livestock_group_id, record_date, quantity_kg,
    per_animal_kg, status
) ON TABLE public.feed_intake_record
TO kokonut_agent_summary_source_view_owner;

CREATE OR REPLACE VIEW kokonut_agent_source.ecological_interaction
WITH (security_barrier = true) AS
SELECT source_row.location_id, source_row.interaction_type,
       source_row.interaction_strength, source_row.status
  FROM public.v_public_ecological_interaction_summary AS source_row
 WHERE EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = source_row.location_id
 );

CREATE OR REPLACE VIEW kokonut_agent_source.energy_flow_measurement
WITH (security_barrier = true) AS
SELECT source_row.location_id, source_row.from_trophic_level,
       source_row.to_trophic_level, source_row.biomass_transferred_kg,
       source_row.conversion_efficiency_pct, source_row.status
  FROM public.v_public_energy_flow_summary AS source_row
 WHERE EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = source_row.location_id
 );

CREATE OR REPLACE VIEW kokonut_agent_source.population_dynamics_record
WITH (security_barrier = true) AS
SELECT source_row.location_id, source_row.species_name,
       source_row.species_common_name, source_row.trophic_level,
       source_row.record_date, source_row.population_count, source_row.status
  FROM public.v_public_population_dynamics_summary AS source_row
 WHERE EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = source_row.location_id
 );

CREATE OR REPLACE VIEW kokonut_agent_source.soil_input_application
WITH (security_barrier = true) AS
SELECT source_row.location_id, source_row.input_type, source_row.input_name,
       source_row.quantity_kg, source_row.residual_pct,
       source_row.application_date, source_row.residual_measurement_date,
       source_row.status
  FROM public.v_public_soil_input_retention AS source_row
 WHERE EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = source_row.location_id
 );

CREATE OR REPLACE VIEW kokonut_agent_source.pest_observation
WITH (security_barrier = true) AS
SELECT source_row.location_id, source_row.observation_date,
       source_row.pest_species, source_row.pest_common_name,
       source_row.pest_category, source_row.severity,
       source_row.incidence_count, source_row.affected_area_pct,
       source_row.outbreak_probability_pct, source_row.temperature_c,
       source_row.humidity_pct, source_row.predator_count,
       source_row.natural_enemy_present, source_row.status
  FROM public.v_public_pest_trends AS source_row
 WHERE EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = source_row.location_id
 );

-- Existing public biocontrol projection omits category and release density.
-- Read those two fields only through this location/lifecycle-scoped view.
CREATE OR REPLACE VIEW kokonut_agent_source.biocontrol_release
WITH (security_barrier = true) AS
SELECT release.location_id, release.predator_species,
       release.predator_common_name, release.predator_category,
       release.target_pest, release.release_count,
       release.effectiveness_pct, release.pest_reduction_pct,
       release.release_density_per_m2, release.release_date,
       release.follow_up_date, release.status
  FROM public.biocontrol_release AS release
  JOIN public.location AS farm ON farm.id = release.location_id
 WHERE farm.status = 'active'
   AND release.status IN ('verified', 'published')
   AND EXISTS (
       SELECT 1 FROM public.farm_registry_record AS registry
        WHERE registry.location_id = farm.id
          AND registry.status IN ('verified', 'published')
   )
   AND EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = release.location_id
   );

CREATE OR REPLACE VIEW kokonut_agent_source.resource_consumption
WITH (security_barrier = true) AS
SELECT source_row.location_id, source_row.resource_type, source_row.unit,
       source_row.component, source_row.quantity, source_row.is_estimated,
       source_row.status
  FROM public.v_public_resource_efficiency AS source_row
 WHERE EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = source_row.location_id
 );

-- Keep ecological aliases separate from deterministic-summary source views
-- with the same legacy relation names. Replacing those shared views would
-- remove columns and fail against an established deployment.
CREATE OR REPLACE VIEW kokonut_agent_source.ecological_harvest_event
WITH (security_barrier = true) AS
SELECT harvest.location_id, harvest.quantity, harvest.status
  FROM public.harvest_event AS harvest
  JOIN public.location AS farm ON farm.id = harvest.location_id
 WHERE farm.status = 'active'
   AND harvest.status IN ('verified', 'published')
   AND EXISTS (
       SELECT 1 FROM public.farm_registry_record AS registry
        WHERE registry.location_id = farm.id
          AND registry.status IN ('verified', 'published')
   )
   AND EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = harvest.location_id
   );

CREATE OR REPLACE VIEW kokonut_agent_source.location
WITH (security_barrier = true) AS
SELECT farm.id
  FROM public.location AS farm
 WHERE farm.status = 'active'
   AND EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = farm.id
   );

CREATE OR REPLACE VIEW kokonut_agent_source.ecological_species_observation
WITH (security_barrier = true) AS
SELECT source_row.location_id, source_row.species_name,
       source_row.conservation_status, source_row.count, source_row.status
  FROM public.v_public_ecological_species_conservation AS source_row
 WHERE EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = source_row.location_id
 );

CREATE OR REPLACE VIEW kokonut_agent_source.livestock_group
WITH (security_barrier = true) AS
SELECT livestock.id, livestock.location_id, livestock.group_name,
       livestock.species, livestock.breed, livestock.animal_count,
       livestock.feed_type, livestock.average_weight_kg, livestock.status
  FROM public.livestock_group AS livestock
  JOIN public.location AS farm ON farm.id = livestock.location_id
 WHERE livestock.status = 'active'
   AND farm.status = 'active'
   AND EXISTS (
       SELECT 1 FROM public.farm_registry_record AS registry
        WHERE registry.location_id = farm.id
          AND registry.status IN ('verified', 'published')
   )
   AND EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = livestock.location_id
   );

CREATE OR REPLACE VIEW kokonut_agent_source.feed_intake_record
WITH (security_barrier = true) AS
SELECT intake.id, intake.location_id, intake.livestock_group_id,
       intake.record_date, intake.quantity_kg, intake.per_animal_kg,
       intake.status
  FROM public.feed_intake_record AS intake
  JOIN public.livestock_group AS livestock
    ON livestock.id = intake.livestock_group_id
   AND livestock.location_id = intake.location_id
  JOIN public.location AS farm ON farm.id = intake.location_id
 WHERE livestock.status = 'active'
   AND farm.status = 'active'
   AND intake.status IN ('verified', 'published')
   AND EXISTS (
       SELECT 1 FROM public.farm_registry_record AS registry
        WHERE registry.location_id = farm.id
          AND registry.status IN ('verified', 'published')
   )
   AND EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = intake.location_id
   );

CREATE OR REPLACE VIEW kokonut_agent_source.token_reward_distribution
WITH (security_barrier = true) AS
SELECT source_row.location_id, source_row.reward_type, source_row.token_type,
       source_row.token_amount, source_row.usd_value,
       source_row.linked_metric_key, source_row.linked_metric_value,
       source_row.distribution_method, source_row.is_onchain, source_row.status
  FROM public.v_public_token_reward_distribution AS source_row
 WHERE EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = source_row.location_id
 );

CREATE OR REPLACE VIEW kokonut_agent_source.reward_calibration_model
WITH (security_barrier = true) AS
SELECT source_row.location_id, source_row.model_name, source_row.model_type,
       source_row.run_date, source_row.input_metrics, source_row.output_weights,
       source_row.calibration_score, source_row.total_tokens_distributed,
       source_row.token_per_unit_output, source_row.epoch,
       source_row.confidence_level, source_row.status
  FROM public.v_public_reward_calibration AS source_row
 WHERE EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = source_row.location_id
 );

-- Row-level manifests use the same approved public projections and therefore
-- identify only verified/published rows. Four unregistered joins remain table
-- hints because the shared manifest limit is ten sources.
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_ecological_interaction_summary
WITH (security_barrier = true) AS
SELECT id, location_id FROM public.v_public_ecological_interaction_summary
 WHERE EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope WHERE scope.location_id = v_public_ecological_interaction_summary.location_id);
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_energy_flow_summary
WITH (security_barrier = true) AS
SELECT id, location_id FROM public.v_public_energy_flow_summary
 WHERE EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope WHERE scope.location_id = v_public_energy_flow_summary.location_id);
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_population_dynamics_summary
WITH (security_barrier = true) AS
SELECT id, location_id FROM public.v_public_population_dynamics_summary
 WHERE EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope WHERE scope.location_id = v_public_population_dynamics_summary.location_id);
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_soil_input_retention
WITH (security_barrier = true) AS
SELECT id, location_id FROM public.v_public_soil_input_retention
 WHERE EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope WHERE scope.location_id = v_public_soil_input_retention.location_id);
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_pest_trends
WITH (security_barrier = true) AS
SELECT id, location_id FROM public.v_public_pest_trends
 WHERE EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope WHERE scope.location_id = v_public_pest_trends.location_id);
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_biocontrol_effectiveness
WITH (security_barrier = true) AS
SELECT id, location_id FROM public.v_public_biocontrol_effectiveness
 WHERE EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope WHERE scope.location_id = v_public_biocontrol_effectiveness.location_id);
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_resource_efficiency
WITH (security_barrier = true) AS
SELECT id, location_id FROM public.v_public_resource_efficiency
 WHERE EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope WHERE scope.location_id = v_public_resource_efficiency.location_id);
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_ecological_species_conservation
WITH (security_barrier = true) AS
SELECT id, location_id FROM public.v_public_ecological_species_conservation
 WHERE EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope WHERE scope.location_id = v_public_ecological_species_conservation.location_id);
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_token_reward_distribution
WITH (security_barrier = true) AS
SELECT id, location_id FROM public.v_public_token_reward_distribution
 WHERE EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope WHERE scope.location_id = v_public_token_reward_distribution.location_id);
CREATE OR REPLACE VIEW kokonut_agent_source.v_public_reward_calibration
WITH (security_barrier = true) AS
SELECT id, location_id FROM public.v_public_reward_calibration
 WHERE EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope WHERE scope.location_id = v_public_reward_calibration.location_id);

ALTER VIEW kokonut_agent_source.ecological_interaction OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.energy_flow_measurement OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.population_dynamics_record OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.soil_input_application OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.pest_observation OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.biocontrol_release OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.resource_consumption OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.ecological_harvest_event OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.location OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.ecological_species_observation OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.livestock_group OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.feed_intake_record OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.token_reward_distribution OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.reward_calibration_model OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_ecological_interaction_summary OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_energy_flow_summary OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_population_dynamics_summary OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_soil_input_retention OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_pest_trends OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_biocontrol_effectiveness OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_resource_efficiency OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_ecological_species_conservation OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_token_reward_distribution OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_reward_calibration OWNER TO kokonut_agent_summary_source_view_owner;

REVOKE ALL PRIVILEGES ON TABLE
    kokonut_agent_source.ecological_interaction,
    kokonut_agent_source.energy_flow_measurement,
    kokonut_agent_source.population_dynamics_record,
    kokonut_agent_source.soil_input_application,
    kokonut_agent_source.pest_observation,
    kokonut_agent_source.biocontrol_release,
    kokonut_agent_source.resource_consumption,
    kokonut_agent_source.ecological_harvest_event,
    kokonut_agent_source.location,
    kokonut_agent_source.ecological_species_observation,
    kokonut_agent_source.livestock_group,
    kokonut_agent_source.feed_intake_record,
    kokonut_agent_source.token_reward_distribution,
    kokonut_agent_source.reward_calibration_model,
    kokonut_agent_source.v_public_ecological_interaction_summary,
    kokonut_agent_source.v_public_energy_flow_summary,
    kokonut_agent_source.v_public_population_dynamics_summary,
    kokonut_agent_source.v_public_soil_input_retention,
    kokonut_agent_source.v_public_pest_trends,
    kokonut_agent_source.v_public_biocontrol_effectiveness,
    kokonut_agent_source.v_public_resource_efficiency,
    kokonut_agent_source.v_public_ecological_species_conservation,
    kokonut_agent_source.v_public_token_reward_distribution,
    kokonut_agent_source.v_public_reward_calibration
FROM PUBLIC, kokonut_agent_summary_source_login,
     kokonut_agent_summary_source_reader;
GRANT SELECT ON TABLE
    kokonut_agent_source.ecological_interaction,
    kokonut_agent_source.energy_flow_measurement,
    kokonut_agent_source.population_dynamics_record,
    kokonut_agent_source.soil_input_application,
    kokonut_agent_source.pest_observation,
    kokonut_agent_source.biocontrol_release,
    kokonut_agent_source.resource_consumption,
    kokonut_agent_source.ecological_harvest_event,
    kokonut_agent_source.location,
    kokonut_agent_source.ecological_species_observation,
    kokonut_agent_source.livestock_group,
    kokonut_agent_source.feed_intake_record,
    kokonut_agent_source.token_reward_distribution,
    kokonut_agent_source.reward_calibration_model,
    kokonut_agent_source.v_public_ecological_interaction_summary,
    kokonut_agent_source.v_public_energy_flow_summary,
    kokonut_agent_source.v_public_population_dynamics_summary,
    kokonut_agent_source.v_public_soil_input_retention,
    kokonut_agent_source.v_public_pest_trends,
    kokonut_agent_source.v_public_biocontrol_effectiveness,
    kokonut_agent_source.v_public_resource_efficiency,
    kokonut_agent_source.v_public_ecological_species_conservation,
    kokonut_agent_source.v_public_token_reward_distribution,
    kokonut_agent_source.v_public_reward_calibration
TO kokonut_agent_summary_source_reader;

GRANT SELECT (id, location_id) ON TABLE
    public.v_public_ecological_interaction_summary,
    public.v_public_energy_flow_summary,
    public.v_public_population_dynamics_summary,
    public.v_public_soil_input_retention,
    public.v_public_pest_trends,
    public.v_public_biocontrol_effectiveness,
    public.v_public_resource_efficiency,
    public.v_public_ecological_species_conservation,
    public.v_public_token_reward_distribution,
    public.v_public_reward_calibration
TO kokonut_ai_summary_drafter;

REVOKE ALL PRIVILEGES ON TABLE
    public.ecological_interaction,
    public.energy_flow_measurement,
    public.population_dynamics_record,
    public.soil_input_application,
    public.pest_observation,
    public.biocontrol_release,
    public.resource_consumption,
    public.harvest_event,
    public.location,
    public.farm_registry_record,
    public.species_observation,
    public.livestock_group,
    public.feed_intake_record,
    public.token_reward_distribution,
    public.reward_calibration_model,
    public.v_public_ecological_interaction_summary,
    public.v_public_energy_flow_summary,
    public.v_public_population_dynamics_summary,
    public.v_public_soil_input_retention,
    public.v_public_pest_trends,
    public.v_public_biocontrol_effectiveness,
    public.v_public_resource_efficiency,
    public.v_public_ecological_species_conservation,
    public.v_public_livestock_feed_intake,
    public.v_public_token_reward_distribution,
    public.v_public_reward_calibration
FROM kokonut_agent_summary_source_login,
     kokonut_agent_summary_source_reader;

REVOKE CREATE ON SCHEMA kokonut_agent_source
FROM kokonut_agent_summary_source_view_owner,
     kokonut_agent_summary_source_reader,
     kokonut_agent_summary_source_login;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.unnest(ARRAY[
            'ecological_interaction', 'energy_flow_measurement',
            'population_dynamics_record', 'soil_input_application',
            'pest_observation', 'biocontrol_release', 'resource_consumption',
            'harvest_event', 'species_observation', 'livestock_group',
            'feed_intake_record', 'token_reward_distribution', 'location',
            'farm_registry_record',
            'reward_calibration_model'
        ]) AS source(table_name)
        WHERE pg_catalog.has_table_privilege(
            'kokonut_agent_summary_source_reader',
            'public.' || source.table_name, 'SELECT'
        ) OR pg_catalog.has_table_privilege(
            'kokonut_agent_summary_source_login',
            'public.' || source.table_name, 'SELECT'
        )
    ) THEN
        RAISE EXCEPTION 'ecological synthesis reader or login can bypass scoped source views';
    END IF;

    IF pg_catalog.has_schema_privilege(
        'kokonut_agent_summary_source_view_owner',
        'kokonut_agent_source', 'CREATE'
    ) OR pg_catalog.has_schema_privilege(
        'kokonut_agent_summary_source_reader',
        'kokonut_agent_source', 'CREATE'
    ) OR pg_catalog.has_schema_privilege(
        'kokonut_agent_summary_source_login',
        'kokonut_agent_source', 'CREATE'
    ) THEN
        RAISE EXCEPTION 'ecological source roles retain source-schema CREATE';
    END IF;
END;
$$;

COMMIT;
