-- Reconcile agent permission field lists with the current agent tables.
-- Directus permissions are data, so update existing installations as well as
-- the config/directus/permissions.sql bootstrap source.

DO $$
BEGIN
    IF to_regclass('public.directus_permissions') IS NULL THEN
        RETURN;
    END IF;

    UPDATE directus_permissions
    SET fields = CASE
        WHEN collection = 'agent_identity' AND action = 'create'
            THEN 'agent_name,agent_state,metadata,operator_wallet'
        WHEN collection = 'agent_task' AND action = 'create'
            THEN 'task_type,inputs,subject_id,subject_type,requested_by'
        WHEN collection = 'agent_task' AND action = 'update'
            THEN 'execution_status,output,error_message'
        ELSE fields
    END
    WHERE collection IN ('agent_identity', 'agent_task')
      AND action IN ('create', 'update')
      AND policy IN (
          'b1000000-0000-0000-0000-000000000007',
          'b1000000-0000-0000-0000-000000000008'
      );
END $$;
