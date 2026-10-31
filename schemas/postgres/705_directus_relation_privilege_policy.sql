-- Preserve ordered-migration Directus relation denials after role bootstrap.
-- The compatibility provisioner grants broad DML on public/kokonut; this
-- catalog records the migration-owned exceptions it must reapply afterward.
BEGIN;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;

CREATE TABLE IF NOT EXISTS kokonut_security.directus_relation_privilege_policy (
    schema_name TEXT NOT NULL
        CHECK (schema_name IN ('public', 'kokonut')),
    relation_name TEXT NOT NULL
        CHECK (relation_name ~ '^[a-z_][a-z0-9_]{0,62}$'),
    access_mode TEXT NOT NULL
        CHECK (access_mode IN ('read_only', 'no_access')),
    source_migration TEXT NOT NULL
        CHECK (source_migration ~ '^[0-9]{3}_[a-z0-9_]+[.]sql$'),
    PRIMARY KEY (schema_name, relation_name)
);

COMMENT ON TABLE kokonut_security.directus_relation_privilege_policy IS
    'Migration-owned Directus runtime relation exceptions. Every ordered migration that denies Directus relation access must add or update its policy row so the optional Directus role provisioner cannot restore that access.';

REVOKE ALL PRIVILEGES
    ON TABLE kokonut_security.directus_relation_privilege_policy
    FROM PUBLIC;
DO $$
DECLARE role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime'
    ] LOOP
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name
        ) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE '
                'kokonut_security.directus_relation_privilege_policy FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END;
$$;

-- `no_access` preserves full relation denials, including private receipts,
-- operator events, and tenant-scoped source rows whose reads moved to Gateway
-- functions. `read_only` preserves migration-owned DML denials while leaving
-- existing reporting reads available. 695/696/697/704 intentionally do not
-- appear here: those migrations narrow kokonut_runtime only.
INSERT INTO kokonut_security.directus_relation_privilege_policy
    (schema_name, relation_name, access_mode, source_migration)
VALUES
    ('public', 'farm_activity_operator_event', 'no_access', '404_gateway_farm_activity_operations.sql'),
    ('public', 'operator_governance_party_binding', 'no_access', '437_governance_operator_binding_and_actions.sql'),
    ('public', 'governance_role_assignment', 'read_only', '438_governance_role_assignment_proposals.sql'),
    ('public', 'governance_role_assignment_request', 'no_access', '438_governance_role_assignment_proposals.sql'),
    ('public', 'governance_role_assignment_decision', 'no_access', '440_governance_role_assignment_review.sql'),
    ('public', 'governance_tactical_item', 'read_only', '445_governance_tactical_content_mutations.sql'),
    ('public', 'governance_tactical_action_event', 'no_access', '441_governance_tactical_actions.sql'),
    ('public', 'governance_definition_action_event', 'no_access', '442_governance_definition_lifecycle.sql'),
    ('public', 'governance_circle', 'read_only', '443_governance_definition_mutations.sql'),
    ('public', 'governance_role', 'read_only', '443_governance_definition_mutations.sql'),
    ('public', 'governance_definition_mutation_event', 'no_access', '443_governance_definition_mutations.sql'),
    ('public', 'governance_tactical_session', 'read_only', '445_governance_tactical_content_mutations.sql'),
    ('public', 'governance_tactical_session_creation_event', 'no_access', '444_governance_tactical_session_creation.sql'),
    ('public', 'governance_tactical_content_event', 'no_access', '445_governance_tactical_content_mutations.sql'),
    ('public', 'party_location_identity_case', 'no_access', '448_location_scoped_identity_resolution.sql'),
    ('public', 'party_location_identity_decision', 'no_access', '448_location_scoped_identity_resolution.sql'),
    ('public', 'delphi_recommendation_review_decision', 'no_access', '450_location_scoped_delphi_recommendation_review.sql'),
    ('public', 'delphi_recommendation_draft_request', 'no_access', '451_location_scoped_delphi_recommendation_drafts.sql'),
    ('public', 'business_model_canvas_create_request', 'no_access', '463_location_scoped_business_canvas_create.sql'),
    ('public', 'business_model_canvas_kernel_edit_request', 'no_access', '464_location_scoped_business_canvas_edit.sql'),
    ('public', 'solution_retirement_review_event', 'no_access', '475_location_solution_retirement_review.sql'),
    ('public', 'solution_retirement_proposal_event', 'no_access', '476_location_solution_retirement_proposal.sql'),
    ('public', 'solution_learning_proposal_event', 'no_access', '477_location_solution_learning_proposal.sql'),
    ('public', 'solution_gate_evaluation_submission_receipt', 'no_access', '483_location_solution_gate_evaluation.sql'),
    ('public', 'solution_gate_approval_submission_receipt', 'no_access', '484_location_solution_gate_review.sql'),
    ('public', 'solution_gate_transition_submission_receipt', 'no_access', '486_location_solution_gate_transition.sql'),
    ('public', 'solution_experiment_review_submission_receipt', 'no_access', '487_location_solution_experiment_review.sql'),
    ('public', 'solution_funding_proposal_receipt', 'no_access', '488_location_solution_funding_proposals.sql'),
    ('public', 'solution_funding_submission_receipt', 'no_access', '489_location_solution_funding_submission.sql'),
    ('public', 'solution_funding_approval_receipt', 'no_access', '491_location_solution_funding_approval.sql'),
    ('public', 'solution_funding_tranche_approval_receipt', 'no_access', '492_location_solution_funding_tranche_review.sql'),
    ('public', 'solution_replication_proposal_receipt', 'no_access', '494_location_solution_replication_proposal.sql'),
    ('public', 'solution_replication_review_receipt', 'no_access', '495_location_solution_replication_review.sql'),
    ('public', 'solution_replication_activation_receipt', 'no_access', '496_location_solution_replication_activation.sql'),
    ('public', 'solution_replication_completion_proposal', 'no_access', '498_location_solution_replication_completion_review.sql'),
    ('public', 'solution_replication_completion_review_receipt', 'no_access', '498_location_solution_replication_completion_review.sql'),
    ('public', 'solution_learning_review_receipt', 'no_access', '499_location_solution_learning_review.sql'),
    ('public', 'solution_learning_record', 'read_only', '500_location_solution_learning_application.sql'),
    ('public', 'solution_learning_application_receipt', 'no_access', '500_location_solution_learning_application.sql'),
    ('public', 'solution_scale_gate_assessment', 'no_access', '501_location_solution_scale_gate_evaluation_review.sql'),
    ('public', 'solution_scale_gate', 'no_access', '501_location_solution_scale_gate_evaluation_review.sql'),
    ('public', 'solution_retirement_transition_event', 'no_access', '502_location_solution_retirement_execution.sql'),
    ('public', 'solution_nonpromotion_transition_receipt', 'no_access', '503_location_solution_nonpromotion_stage_transition.sql'),
    ('public', 'location_solution_creation_receipt', 'no_access', '504_location_solution_create.sql'),
    ('public', 'solution_gate_definition_receipt', 'no_access', '505_location_solution_gate_definition.sql'),
    ('public', 'solution_stage_gate', 'no_access', '505_location_solution_gate_definition.sql'),
    ('public', 'solution_experiment_creation_receipt', 'no_access', '506_location_solution_experiment_create.sql'),
    ('public', 'solution_experiment', 'read_only', '509_location_solution_experiment_start.sql'),
    ('public', 'solution_experiment_submission_receipt', 'no_access', '507_location_solution_experiment_submission.sql'),
    ('public', 'solution_experiment_protocol_approval_receipt', 'no_access', '508_location_solution_experiment_protocol_review.sql'),
    ('public', 'solution_experiment_start_receipt', 'no_access', '509_location_solution_experiment_start.sql'),
    ('public', 'solution_experiment_observation_capture_receipt', 'no_access', '510_location_solution_experiment_observation_capture.sql'),
    ('public', 'solution_experiment_observation', 'no_access', '510_location_solution_experiment_observation_capture.sql'),
    ('public', 'solution_experiment_analysis_source', 'no_access', '511_location_solution_experiment_sequential_analysis.sql'),
    ('public', 'solution_experiment_analysis_receipt', 'no_access', '511_location_solution_experiment_sequential_analysis.sql'),
    ('public', 'solution_experiment_analysis_run', 'no_access', '511_location_solution_experiment_sequential_analysis.sql'),
    ('public', 'solution_experiment_completion_receipt', 'no_access', '512_location_solution_experiment_completion.sql'),
    ('public', 'solution_adoption_program_creation_receipt', 'no_access', '513_location_solution_adoption_program_create.sql'),
    ('public', 'solution_adopter_readiness', 'read_only', '514_location_solution_adoption_write_boundary.sql'),
    ('public', 'solution_configuration', 'read_only', '514_location_solution_adoption_write_boundary.sql'),
    ('public', 'solution_adopter_readiness_assessment', 'no_access', '516_location_solution_adoption_readiness_review.sql'),
    ('public', 'solution_adopter_readiness_review', 'no_access', '516_location_solution_adoption_readiness_review.sql'),
    ('public', 'solution_configuration_legacy_approval_archive', 'no_access', '517_location_solution_configuration_draft_review.sql'),
    ('public', 'solution_configuration_draft_receipt', 'no_access', '517_location_solution_configuration_draft_review.sql'),
    ('public', 'solution_configuration_submission_receipt', 'no_access', '517_location_solution_configuration_draft_review.sql'),
    ('public', 'solution_configuration_review_receipt', 'no_access', '517_location_solution_configuration_draft_review.sql'),
    ('public', 'solution_adoption_program', 'read_only', '518_location_solution_adoption_program_review.sql'),
    ('public', 'solution_adoption_program_submission_receipt', 'no_access', '518_location_solution_adoption_program_review.sql'),
    ('public', 'solution_adoption_program_review_receipt', 'no_access', '518_location_solution_adoption_program_review.sql'),
    ('public', 'solution_adoption_program_revision', 'no_access', '519_location_solution_adoption_program_revision.sql'),
    ('public', 'solution_adoption_program_revision_receipt', 'no_access', '519_location_solution_adoption_program_revision.sql'),
    ('public', 'solution_adoption_program_consent_policy', 'no_access', '520_location_solution_adoption_consent_events.sql'),
    ('public', 'solution_adoption_program_consent_policy_receipt', 'no_access', '520_location_solution_adoption_consent_events.sql'),
    ('public', 'solution_adoption_event_capture_receipt', 'no_access', '520_location_solution_adoption_consent_events.sql'),
    ('public', 'solution_adoption_event', 'no_access', '520_location_solution_adoption_consent_events.sql'),
    ('public', 'operating_demand_signal', 'read_only', '563_location_operating_pilot_demand_review_decision.sql'),
    ('public', 'operating_demand_draft_receipt', 'no_access', '552_location_operating_pilot_demand_draft.sql'),
    ('public', 'operating_demand_draft_submission_receipt', 'no_access', '559_location_operating_pilot_demand_draft_submission.sql'),
    ('public', 'operating_demand_draft_revision_receipt', 'no_access', '562_location_operating_pilot_demand_draft_revision.sql'),
    ('public', 'operating_demand_review_decision', 'no_access', '563_location_operating_pilot_demand_review_decision.sql'),
    ('public', 'operating_capacity_profile', 'read_only', '558_location_operating_pilot_capacity_review_decision.sql'),
    ('public', 'operating_capacity_draft_receipt', 'no_access', '553_location_operating_pilot_capacity_draft.sql'),
    ('public', 'operating_capacity_draft_revision_receipt', 'no_access', '555_location_operating_pilot_capacity_draft_revision.sql'),
    ('public', 'operating_capacity_draft_submission_receipt', 'no_access', '556_location_operating_pilot_capacity_draft_submission.sql'),
    ('public', 'operating_capacity_review_decision', 'no_access', '558_location_operating_pilot_capacity_review_decision.sql'),
    ('public', 'work_item', 'read_only', '566_location_operating_pilot_work_claim_allocation.sql'),
    ('public', 'work_item_claim', 'no_access', '564_location_operating_pilot_work_opportunities.sql'),
    ('public', 'work_item_selection_event', 'no_access', '564_location_operating_pilot_work_opportunities.sql'),
    ('public', 'operating_work_claim_receipt', 'no_access', '564_location_operating_pilot_work_opportunities.sql'),
    ('public', 'operating_work_claim_review_receipt', 'no_access', '565_location_operating_pilot_work_claim_review.sql'),
    ('public', 'operating_work_claim_allocation_receipt', 'no_access', '566_location_operating_pilot_work_claim_allocation.sql'),
    ('public', 'operating_resource_request_draft', 'no_access', '568_location_own_operating_pilot_resource_requests.sql'),
    ('public', 'operating_resource_request_draft_receipt', 'no_access', '568_location_own_operating_pilot_resource_requests.sql'),
    ('public', 'operating_resource_request', 'no_access', '570_location_operating_pilot_resource_draft_submission.sql'),
    ('public', 'operating_resource_request_draft_revision_receipt', 'no_access', '569_location_operating_pilot_resource_draft_revision.sql'),
    ('public', 'operating_resource_request_draft_submission_receipt', 'no_access', '570_location_operating_pilot_resource_draft_submission.sql'),
    ('public', 'operating_resource_request_review_decision', 'no_access', '572_location_operating_pilot_resource_review_decision.sql'),
    ('public', 'operating_resource_request_fulfillment_receipt', 'no_access', '573_location_operating_pilot_resource_fulfillment.sql'),
    ('public', 'operating_pilot_competency_draft', 'no_access', '576_location_operating_pilot_competency_draft_lifecycle.sql'),
    ('public', 'operating_pilot_competency_draft_receipt', 'no_access', '576_location_operating_pilot_competency_draft_lifecycle.sql'),
    ('public', 'operating_pilot_competency_revision_receipt', 'no_access', '576_location_operating_pilot_competency_draft_lifecycle.sql'),
    ('public', 'operating_pilot_competency_submission_receipt', 'no_access', '576_location_operating_pilot_competency_draft_lifecycle.sql'),
    ('public', 'operating_pilot_competency_review_decision', 'no_access', '577_location_operating_pilot_competency_review.sql'),
    ('public', 'operating_learning_plan', 'no_access', '609_location_operating_pilot_learning_plan_review_queue.sql'),
    ('public', 'operating_pilot_learning_plan_draft_receipt', 'no_access', '609_location_operating_pilot_learning_plan_review_queue.sql'),
    ('public', 'operating_pilot_learning_plan_revision_receipt', 'no_access', '607_location_operating_pilot_learning_plan_revision.sql'),
    ('public', 'operating_pilot_learning_plan_submission_receipt', 'no_access', '609_location_operating_pilot_learning_plan_review_queue.sql'),
    ('public', 'operating_pilot_learning_plan_review_decision', 'no_access', '610_location_operating_pilot_learning_plan_review_decision.sql'),
    ('public', 'operating_pilot_learning_plan_activation_receipt', 'no_access', '629_location_operating_pilot_learning_plan_activation.sql'),
    ('public', 'operating_coaching_session', 'no_access', '611_location_scoped_operating_coaching_sessions.sql'),
    ('public', 'operating_pilot_coaching_session_receipt', 'no_access', '611_location_scoped_operating_coaching_sessions.sql'),
    ('public', 'waste_stream_capture_receipt', 'no_access', '613_location_waste_stream_capture.sql'),
    ('public', 'composting_capture_receipt', 'no_access', '614_location_composting_capture.sql'),
    ('public', 'recycling_log', 'no_access', '618_location_scoped_waste_summary_reader.sql'),
    ('public', 'recycling_capture_receipt', 'no_access', '615_location_recycling_capture.sql'),
    ('public', 'pollution_incident', 'no_access', '617_location_scoped_pollution_incident_reads.sql'),
    ('public', 'pollution_incident_operation_receipt', 'no_access', '616_location_pollution_incident_gateway.sql'),
    ('public', 'v_pollution_incidents', 'no_access', '617_location_scoped_pollution_incident_reads.sql'),
    ('public', 'waste_stream', 'no_access', '618_location_scoped_waste_summary_reader.sql'),
    ('public', 'composting_record', 'no_access', '618_location_scoped_waste_summary_reader.sql'),
    ('public', 'v_waste_summary', 'no_access', '618_location_scoped_waste_summary_reader.sql'),
    ('public', 'v_composting_efficiency', 'no_access', '618_location_scoped_waste_summary_reader.sql'),
    ('public', 'pollinator_observation', 'read_only', '693_runtime_pollinator_capture_writes_read_only.sql'),
    ('public', 'pollinator_observation_capture_receipt', 'no_access', '619_location_pollinator_observation_capture.sql'),
    ('public', 'pesticide_impact_log', 'read_only', '693_runtime_pollinator_capture_writes_read_only.sql'),
    ('public', 'pesticide_impact_capture_receipt', 'no_access', '620_location_pesticide_impact_capture.sql'),
    ('public', 'pollinator_habitat', 'read_only', '693_runtime_pollinator_capture_writes_read_only.sql'),
    ('public', 'pollinator_habitat_capture_receipt', 'no_access', '621_location_pollinator_habitat_capture.sql'),
    ('public', 'hive_record', 'read_only', '692_runtime_pollinator_hive_writes_read_only.sql'),
    ('public', 'pollinator_hive_capture_receipt', 'no_access', '622_location_pollinator_hive_capture.sql'),
    ('public', 'pollinator_hive_inspection', 'read_only', '692_runtime_pollinator_hive_writes_read_only.sql'),
    ('public', 'pollinator_hive_inspection_capture_receipt', 'no_access', '623_location_pollinator_hive_inspection_capture.sql'),
    ('public', 'pollinator_habitat_lifecycle_event', 'no_access', '624_location_pollinator_habitat_lifecycle.sql'),
    ('public', 'pollinator_hive_lifecycle_event', 'no_access', '625_location_pollinator_hive_lifecycle.sql'),
    ('public', 'pollinator_review_decision', 'no_access', '626_location_pollinator_independent_review.sql'),
    ('public', 'delphi_minority_report', 'read_only', '642_location_scoped_delphi_minority_report_submission.sql'),
    ('public', 'delphi_stopping_evaluation', 'no_access', '639_location_scoped_delphi_stopping_evaluation.sql'),
    ('public', 'delphi_minority_report_review_decision', 'no_access', '640_location_scoped_delphi_minority_report_review.sql'),
    ('public', 'report_snapshot_export_request', 'no_access', '683_location_scoped_report_snapshot_exports.sql'),
    ('public', 'report_snapshot_export_attempt', 'no_access', '683_location_scoped_report_snapshot_exports.sql'),
    ('public', 'governance_tension_action_request', 'no_access', '700_governance_tension_location_actions.sql'),
    ('public', 'extension_peer_network_create_receipt', 'no_access', '701_location_scoped_extension_learning_writes.sql'),
    ('public', 'extension_learning_progress_update_receipt', 'no_access', '701_location_scoped_extension_learning_writes.sql'),
    ('public', 'landscape_capture_receipt', 'no_access', '702_location_landscape_capture.sql'),
    ('public', 'metric_value_compute_receipt', 'no_access', '703_location_scoped_metric_value_kernel.sql'),
    ('public', 'metric_value_verification_receipt', 'no_access', '703_location_scoped_metric_value_kernel.sql'),
    ('public', 'metric_value_operator_audit', 'no_access', '703_location_scoped_metric_value_kernel.sql')
ON CONFLICT (schema_name, relation_name) DO UPDATE
    SET access_mode = EXCLUDED.access_mode,
        source_migration = EXCLUDED.source_migration;

COMMIT;
