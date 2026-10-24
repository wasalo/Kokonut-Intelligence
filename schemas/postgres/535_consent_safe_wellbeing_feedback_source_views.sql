-- Register consent-filtered public views for wellbeing and feedback synthesis.
-- Raw private aggregates remain outside the attached row-reference manifest.

BEGIN;

INSERT INTO kokonut_security.ai_summary_source_reference_view (source_table, source_view_name)
VALUES
    ('cultural_context_record', 'v_public_cultural_context_summary'),
    ('wellbeing_metric_observation', 'v_public_wellbeing_metric_summary'),
    ('participatory_action_record', 'v_public_participatory_governance_summary'),
    ('stakeholder_feedback', 'v_public_stakeholder_feedback_summary')
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
        'perpetual_value_stress_test', 'cultural_context_record',
        'wellbeing_metric_observation', 'participatory_action_record',
        'stakeholder_feedback'
    ));

GRANT SELECT (id, location_id) ON TABLE
    public.v_public_cultural_context_summary,
    public.v_public_wellbeing_metric_summary,
    public.v_public_participatory_governance_summary,
    public.v_public_stakeholder_feedback_summary
    TO kokonut_ai_summary_drafter;

COMMIT;
