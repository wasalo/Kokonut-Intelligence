-- Register location-scoped public views used by regenerative synthesis.
-- Shared/global governance rows remain outside this location-scoped manifest.

BEGIN;

INSERT INTO kokonut_security.ai_summary_source_reference_view (source_table, source_view_name)
VALUES
    ('regenerative_outcome_summary', 'v_public_regenerative_outcome_summary'),
    ('community_governance_mechanism', 'v_public_community_governance_mechanism'),
    ('replication_readiness_assessment', 'v_public_replication_readiness_summary'),
    ('adaptive_stewardship_review', 'v_public_adaptive_stewardship_summary')
ON CONFLICT (source_table) DO UPDATE
    SET source_view_name = EXCLUDED.source_view_name;

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
        'replication_readiness_assessment', 'adaptive_stewardship_review'
    ));

GRANT SELECT (id, location_id) ON TABLE
    public.v_public_regenerative_outcome_summary,
    public.v_public_community_governance_mechanism,
    public.v_public_replication_readiness_summary,
    public.v_public_adaptive_stewardship_summary
    TO kokonut_ai_summary_drafter;

COMMIT;
