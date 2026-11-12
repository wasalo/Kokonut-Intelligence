-- Global scheduler execution state, separate from definition administration.
BEGIN;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_scheduler_login;
GRANT SELECT ON public.scheduled_task, public.task_run, public.task_resource
    TO kokonut_scheduler_login;
GRANT SELECT (migration_id, checksum, status) ON public.schema_migration TO kokonut_scheduler_login;
GRANT UPDATE (last_run_at,last_status,next_run_at,retry_at,retry_attempt,
    run_window_at,lease_owner,lease_token,lease_expires_at,updated_at,
    last_duration_ms,consecutive_failures)
    ON public.scheduled_task TO kokonut_scheduler_login;
GRANT INSERT (id,task_id,status,worker_id,lease_token,heartbeat_at,attempt_count,
    retry_count,allow_overlap,scheduled_for) ON public.task_run TO kokonut_scheduler_login;
GRANT UPDATE (status,completed_at,duration_ms,error_message,stdout,heartbeat_at)
    ON public.task_run TO kokonut_scheduler_login;
GRANT UPDATE (current_running) ON public.task_resource TO kokonut_scheduler_login;
-- Queue-health columns exclude payloads, destinations and credentials.
GRANT SELECT (status,lease_expires_at,created_at) ON public.platform_event TO kokonut_scheduler_login;
GRANT SELECT (status,lease_expires_at,available_at) ON public.notification_outbox TO kokonut_scheduler_login;
COMMIT;
