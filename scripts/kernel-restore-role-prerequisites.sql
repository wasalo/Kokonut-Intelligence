-- Apply as a PostgreSQL superuser before restoring a DB-only Kernel archive.
-- pg_dump archives RLS policies but intentionally omits cluster-global roles;
-- these disabled placeholders let pg_restore recreate policies and function
-- ownership without enabling any application or worker login.
BEGIN;

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_anomaly_actuation_owner',
        'kokonut_anomaly_alert_owner',
        'kokonut_anomaly_claim_owner',
        'kokonut_anomaly_effect_owner',
        'kokonut_anomaly_event_owner',
        'kokonut_anomaly_notification_owner',
        'kokonut_anomaly_read_owner',
        'kokonut_cache_invalidation_owner',
        'kokonut_climate_owner',
        'kokonut_eas_indexer_login',
        'kokonut_eas_indexer_owner',
        'kokonut_farm_activity_event_owner',
        'kokonut_financial_projection_owner',
        'kokonut_gateway_context_owner',
        'kokonut_governance_action_owner',
        'kokonut_market_data_login',
        'kokonut_market_data_owner',
        'kokonut_mobile_context_owner',
        'kokonut_mobile_credential_owner',
        'kokonut_mobile_device_revoke_owner',
        'kokonut_noi_snapshot_owner',
        'kokonut_notification_enqueue_login',
        'kokonut_notification_enqueue_owner',
        'kokonut_operator_auth',
        'kokonut_operator_auth_owner',
        'kokonut_operator_context_owner',
        'kokonut_remote_sensing_login',
        'kokonut_remote_sensing_owner',
        'kokonut_rpc_indexer_login',
        'kokonut_rpc_indexer_owner',
        'kokonut_runtime',
        'kokonut_sensor_ingestion_login',
        'kokonut_sensor_ingestion_owner',
        'kokonut_weather_forecast_owner',
        'kokonut_weather_observation_owner',
        'kokonut_worker_context_owner',
        'kokonut_worker_execution',
        'kokonut_worker_login',
        'kokonut_agent_summary_deterministic_reader',
        'kokonut_agent_commons_liberation_reader',
        'kokonut_agent_commons_liberation_login',
        'kokonut_agent_gnh_alignment_reader',
        'kokonut_agent_gnh_alignment_login',
        'kokonut_agent_regenerator_reader',
        'kokonut_agent_regenerator_login',
        'kokonut_agent_capital_efficiency_reader',
        'kokonut_agent_capital_efficiency_login',
        'kokonut_agent_financial_resilience_reader',
        'kokonut_agent_financial_resilience_login',
        'kokonut_agent_summary_deterministic_source_login',
        'kokonut_agent_summary_inspection_reader',
        'kokonut_agent_summary_inspection_login',
        'kokonut_agent_ecological_modeling_reader',
        'kokonut_agent_ecological_modeling_login',
        'kokonut_agent_feedback_reader',
        'kokonut_agent_feedback_login',
        'kokonut_agent_holistic_wellbeing_reader',
        'kokonut_agent_holistic_wellbeing_login',
        'kokonut_agent_organic_readiness_reader',
        'kokonut_agent_organic_readiness_login',
        'kokonut_agent_summary_draft_login',
        'kokonut_agent_summary_source_login',
        'kokonut_agent_summary_source_reader',
        'kokonut_agent_summary_source_view_owner',
        'kokonut_agent_ebf_source_login',
        'kokonut_agent_ebf_source_reader',
        'kokonut_agent_cids_source_login',
        'kokonut_agent_cids_source_reader',
        'kokonut_agent_delphi_source_login',
        'kokonut_agent_delphi_source_reader',
        'kokonut_ai_summary_drafter',
        'kokonut_ai_summary_reviewer',
        'kokonut_business_architecture_reader',
        'kokonut_business_canvas_creator',
        'kokonut_business_canvas_editor',
        'kokonut_business_planning_reader',
        'kokonut_competitive_reader',
        'kokonut_coordination_reader',
        'kokonut_delphi_consultation_reader',
        'kokonut_delphi_recommendation_drafter',
        'kokonut_delphi_recommendation_reviewer',
        'kokonut_governance_binding_owner',
        'kokonut_governance_identity_admin',
        'kokonut_management_reader',
        'kokonut_operating_pilot_reader',
        'kokonut_planning_reader',
        'kokonut_sequential_reader',
        'kokonut_solution_action_owner',
        'kokonut_solution_adoption_event_manager',
        'kokonut_solution_adoption_program_creator',
        'kokonut_solution_adoption_program_manager',
        'kokonut_solution_adoption_readiness_manager',
        'kokonut_solution_configuration_manager',
        'kokonut_solution_creator_owner',
        'kokonut_solution_experiment_analyst',
        'kokonut_solution_experiment_creator',
        'kokonut_solution_experiment_observer',
        'kokonut_solution_experiment_protocol_reviewer',
        'kokonut_solution_experiment_reviewer',
        'kokonut_solution_experiment_starter',
        'kokonut_solution_experiment_submitter',
        'kokonut_solution_funding_approver',
        'kokonut_solution_funding_proposer',
        'kokonut_solution_funding_reviewer',
        'kokonut_solution_funding_submitter',
        'kokonut_solution_funding_tranche_approver',
        'kokonut_solution_gate_approver',
        'kokonut_solution_gate_creator',
        'kokonut_solution_gate_evaluator',
        'kokonut_solution_gate_reviewer',
        'kokonut_solution_gate_transitioner',
        'kokonut_solution_learning_applier',
        'kokonut_solution_learning_proposal_owner',
        'kokonut_solution_learning_reviewer',
        'kokonut_solution_nonpromotion_transition_owner',
        'kokonut_solution_proposal_owner',
        'kokonut_solution_reader',
        'kokonut_solution_replication_completion_proposer',
        'kokonut_solution_replication_completion_reviewer',
        'kokonut_solution_replication_proposer',
        'kokonut_solution_replication_reviewer',
        'kokonut_solution_replication_starter',
        'kokonut_solution_retirement_execution_owner',
        'kokonut_solution_reviewer',
        'kokonut_solution_scale_gate_owner',
        'kokonut_stakeholder_identity_owner',
        'kokonut_stakeholder_identity_resolver',
        'kokonut_stakeholder_trust_reader',
        'kokonut_strategy_reader'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
                'NOCREATEROLE NOREPLICATION NOBYPASSRLS',
                role_name
            );
        ELSIF EXISTS (
            SELECT 1 FROM pg_roles
             WHERE rolname = role_name
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'security role % has unsafe role attributes', role_name;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM pg_auth_members AS membership
              JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
              JOIN pg_roles AS member_role ON member_role.oid = membership.member
             WHERE granted_role.rolname = role_name OR member_role.rolname = role_name
        ) THEN
            RAISE EXCEPTION 'security role % has role membership', role_name;
        END IF;
    END LOOP;
END;
$$;

COMMIT;
