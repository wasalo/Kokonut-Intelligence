-- Dispatch authenticated synthesis receipts through the durable scheduler.
-- Every request maps to one fixed worker_cli command and remains draft-only.
BEGIN;

ALTER TABLE public.scheduled_task
    ADD COLUMN is_one_shot BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN one_shot_completed_at TIMESTAMPTZ;

DO $$
DECLARE
    role_oid OID;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_runtime'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_scheduler_login'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_ai_summary_drafter'
    ) THEN
        RAISE EXCEPTION 'synthesis one-shot dispatch role prerequisites are missing';
    END IF;

    SELECT oid INTO role_oid FROM pg_catalog.pg_roles
     WHERE rolname = 'kokonut_ai_summary_dispatcher';
    IF role_oid IS NULL THEN
        CREATE ROLE kokonut_ai_summary_dispatcher
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
        SELECT oid INTO role_oid FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_ai_summary_dispatcher';
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE oid = role_oid
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'synthesis dispatcher role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members AS membership
         WHERE membership.roleid = role_oid OR membership.member = role_oid
    ) THEN
        RAISE EXCEPTION 'synthesis dispatcher role must have no memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_ai_summary_dispatcher;
GRANT SELECT (id, name, module_path, command_args, is_one_shot,
              one_shot_completed_at, last_status, retry_at)
    ON public.scheduled_task TO kokonut_ai_summary_dispatcher;
GRANT INSERT (name, module_path, cron_expression, priority, timeout_seconds,
              max_retries, retry_delay_seconds, depends_on, is_enabled,
              next_run_at, command_args, allow_overlap, dependency_mode,
              is_one_shot)
    ON public.scheduled_task TO kokonut_ai_summary_dispatcher;
GRANT EXECUTE ON FUNCTION kokonut_security.create_location_ai_summary_operator_task_request(
    UUID, TEXT, TEXT, UUID
) TO kokonut_ai_summary_dispatcher;

CREATE OR REPLACE FUNCTION kokonut_security.enqueue_location_ai_summary_operator_task_request(
    requested_location_id UUID,
    requested_task_key TEXT,
    requested_summary_type TEXT,
    requested_request_id UUID
)
RETURNS TABLE (
    request_id UUID,
    location_id UUID,
    task_key TEXT,
    summary_type TEXT,
    created_at TIMESTAMPTZ,
    replayed BOOLEAN,
    scheduled_task_id UUID,
    dispatch_status TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    receipt RECORD;
    schedule RECORD;
    schedule_name TEXT;
    schedule_args JSONB;
    schedule_id UUID;
    schedule_status TEXT;
BEGIN
    SELECT * INTO STRICT receipt
      FROM kokonut_security.create_location_ai_summary_operator_task_request(
          requested_location_id,
          requested_task_key,
          requested_summary_type,
          requested_request_id
      );

    schedule_name := 'operator-ai-summary-' || receipt.request_id::TEXT;
    IF receipt.task_key = 'ai_summary_synthesis' THEN
        schedule_args := pg_catalog.jsonb_build_array(
            '--location-id', receipt.location_id::TEXT,
            '--summary-type', receipt.summary_type,
            '--request-id', receipt.request_id::TEXT,
            '--persist-draft',
            '--deterministic-only'
        );
    ELSE
        schedule_args := pg_catalog.jsonb_build_array(
            '--location-id', receipt.location_id::TEXT,
            '--task-key', receipt.task_key,
            '--request-id', receipt.request_id::TEXT,
            '--persist-draft',
            '--source-only'
        );
    END IF;

    INSERT INTO public.scheduled_task (
        name, module_path, cron_expression, priority, timeout_seconds,
        max_retries, retry_delay_seconds, depends_on, is_enabled, next_run_at,
        command_args, allow_overlap, dependency_mode, is_one_shot
    ) VALUES (
        schedule_name,
        'services.agents.worker_cli',
        '0 0 1 1 *',
        'normal',
        900,
        3,
        60,
        ARRAY[]::UUID[],
        TRUE,
        pg_catalog.clock_timestamp(),
        schedule_args,
        FALSE,
        'last_completed',
        TRUE
    )
    ON CONFLICT (name) DO NOTHING
    RETURNING id INTO schedule_id;

    SELECT task.id, task.module_path, task.command_args, task.is_one_shot,
           task.one_shot_completed_at, task.last_status, task.retry_at
      INTO schedule
      FROM public.scheduled_task AS task
     WHERE task.name = schedule_name;
    IF NOT FOUND
       OR schedule.module_path IS DISTINCT FROM 'services.agents.worker_cli'
       OR schedule.command_args IS DISTINCT FROM schedule_args
       OR schedule.is_one_shot IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'synthesis request conflicts with an existing scheduler task'
            USING ERRCODE = '22023';
    END IF;

    schedule_status := CASE
        WHEN schedule.one_shot_completed_at IS NOT NULL
             AND schedule.last_status = 'completed' THEN 'completed'
        WHEN schedule.one_shot_completed_at IS NOT NULL THEN 'failed'
        WHEN schedule.last_status = 'running' THEN 'running'
        WHEN schedule.retry_at IS NOT NULL THEN 'retrying'
        ELSE 'queued'
    END;
    RETURN QUERY SELECT receipt.request_id, receipt.location_id, receipt.task_key,
                        receipt.summary_type, receipt.created_at, receipt.replayed,
                        schedule.id, schedule_status;
END;
$$;

REVOKE ALL ON FUNCTION kokonut_security.create_location_ai_summary_operator_task_request(
    UUID, TEXT, TEXT, UUID
) FROM kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.enqueue_location_ai_summary_operator_task_request(
    UUID, TEXT, TEXT, UUID
) FROM PUBLIC, directus, kokonut_scheduler_login,
         kokonut_agent_task_summary_writer, kokonut_worker_execution,
         kokonut_ai_summary_reviewer, kokonut_ai_summary_drafter;
GRANT EXECUTE ON FUNCTION kokonut_security.enqueue_location_ai_summary_operator_task_request(
    UUID, TEXT, TEXT, UUID
) TO kokonut_runtime;

GRANT UPDATE (one_shot_completed_at)
    ON public.scheduled_task TO kokonut_scheduler_login;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_ai_summary_dispatcher;
ALTER FUNCTION kokonut_security.enqueue_location_ai_summary_operator_task_request(
    UUID, TEXT, TEXT, UUID
) OWNER TO kokonut_ai_summary_dispatcher;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_ai_summary_dispatcher;

COMMENT ON COLUMN public.scheduled_task.is_one_shot IS
    'True only for durable queued operator requests; the scheduler never repeats a terminal one-shot task.';
COMMENT ON COLUMN public.scheduled_task.one_shot_completed_at IS
    'Terminal one-shot marker set after success, exhausted retries, or expired final lease.';
COMMENT ON ROLE kokonut_ai_summary_dispatcher IS
    'NOLOGIN owner of the fixed authenticated synthesis enqueue function; can insert only bounded scheduled-task columns.';

DO $$
BEGIN
    IF pg_catalog.has_function_privilege(
           'kokonut_runtime',
           'kokonut_security.create_location_ai_summary_operator_task_request(uuid,text,text,uuid)',
           'EXECUTE'
       )
       OR NOT pg_catalog.has_function_privilege(
           'kokonut_runtime',
           'kokonut_security.enqueue_location_ai_summary_operator_task_request(uuid,text,text,uuid)',
           'EXECUTE'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_ai_summary_dispatcher', 'public.scheduled_task', 'UPDATE'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_ai_summary_dispatcher', 'public.scheduled_task', 'DELETE'
       )
       OR pg_catalog.has_table_privilege(
           'kokonut_scheduler_login', 'public.scheduled_task', 'INSERT'
       )
       OR NOT pg_catalog.has_column_privilege(
           'kokonut_scheduler_login', 'public.scheduled_task',
           'one_shot_completed_at', 'UPDATE'
       ) THEN
        RAISE EXCEPTION 'authenticated synthesis dispatch grants exceed their bounded contracts';
    END IF;
END;
$$;

COMMIT;
