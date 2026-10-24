-- Register location-scoped safe views for commons, GNH, resilience, and
-- open-source-capitalist synthesis. Network-wide catalogues stay excluded.

BEGIN;

INSERT INTO kokonut_security.ai_summary_source_reference_view (source_table, source_view_name)
VALUES
    ('time_liberation_observation', 'v_public_time_liberation_summary'),
    ('capital_alignment_assessment', 'v_public_capital_alignment_summary'),
    ('governance_inclusion_observation', 'v_public_governance_inclusion_summary'),
    ('land_stewardship_commitment', 'v_public_land_stewardship_summary'),
    ('gnh_alignment_assessment', 'v_public_gnh_alignment_summary'),
    ('cultural_preservation_plan', 'v_public_cultural_preservation_summary'),
    ('renewable_energy_plan', 'v_public_renewable_energy_summary'),
    ('vulnerable_group_access_plan', 'v_public_vulnerable_access_summary'),
    ('foundational_wellbeing_observation', 'v_public_foundational_wellbeing_summary'),
    ('financial_sustainability_plan', 'v_public_financial_sustainability_summary'),
    ('risk_mitigation_register', 'v_public_risk_mitigation_summary'),
    ('scaling_roadmap_milestone', 'v_public_scaling_roadmap_summary'),
    ('farm_launch_unit_economics', 'v_public_farm_launch_unit_economics'),
    ('adoption_barrier_assessment', 'v_public_adoption_barrier_assessment'),
    ('perpetual_value_stress_test', 'v_public_perpetual_value_stress_test')
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
        'replication_readiness_assessment', 'adaptive_stewardship_review',
        'time_liberation_observation', 'capital_alignment_assessment',
        'governance_inclusion_observation', 'land_stewardship_commitment',
        'gnh_alignment_assessment', 'cultural_preservation_plan',
        'renewable_energy_plan', 'vulnerable_group_access_plan',
        'foundational_wellbeing_observation', 'financial_sustainability_plan',
        'risk_mitigation_register', 'scaling_roadmap_milestone',
        'farm_launch_unit_economics', 'adoption_barrier_assessment',
        'perpetual_value_stress_test'
    ));

GRANT SELECT (id, location_id) ON TABLE
    public.v_public_time_liberation_summary,
    public.v_public_capital_alignment_summary,
    public.v_public_governance_inclusion_summary,
    public.v_public_land_stewardship_summary,
    public.v_public_gnh_alignment_summary,
    public.v_public_cultural_preservation_summary,
    public.v_public_renewable_energy_summary,
    public.v_public_vulnerable_access_summary,
    public.v_public_foundational_wellbeing_summary,
    public.v_public_financial_sustainability_summary,
    public.v_public_risk_mitigation_summary,
    public.v_public_scaling_roadmap_summary,
    public.v_public_farm_launch_unit_economics,
    public.v_public_adoption_barrier_assessment,
    public.v_public_perpetual_value_stress_test
    TO kokonut_ai_summary_drafter;

COMMIT;
