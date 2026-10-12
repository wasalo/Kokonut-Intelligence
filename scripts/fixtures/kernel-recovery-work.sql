-- Synthetic durable-state development seed, never an ordered migration.
-- Apply only through kernel-recovery-fixture.py after restoring the current schema.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
LOCK TABLE scheduled_task, task_run, platform_event, event_handler,
           event_handler_delivery, event_dead_letter IN EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM scheduled_task) OR EXISTS (SELECT 1 FROM task_run)
       OR EXISTS (SELECT 1 FROM platform_event) OR EXISTS (SELECT 1 FROM event_dead_letter)
       OR EXISTS (SELECT 1 FROM event_handler_delivery) THEN
        RAISE EXCEPTION 'Recovery seed requires empty work tables';
    END IF;
    IF EXISTS (SELECT 1 FROM event_handler WHERE handler_name LIKE 'kernel_recovery_fixture_%') THEN
        RAISE EXCEPTION 'Recovery fixture already exists';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='task_run' AND column_name='scheduled_for') THEN
        RAISE EXCEPTION 'Current run-window schema required';
    END IF;
END $$;

INSERT INTO scheduled_task
    (id,name,module_path,command_args,cron_expression,is_enabled,allow_overlap,
     dependency_mode,run_window_at,last_status,retry_attempt,retry_at,
     lease_owner,lease_token,lease_expires_at)
VALUES ('f0000000-0000-4000-8000-000000000001','kernel_recovery_fixture_freshness',
    'services.ingestion.data_freshness','["--check"]','0 * * * *',false,false,
    'same_window','2026-10-10T10:00:00Z','running',1,'2026-10-10T10:05:00Z',
    'fixture-former-worker','f0000000-0000-4000-8000-000000000002','2026-10-10T10:01:00Z');
INSERT INTO task_run
    (id,task_id,status,worker_id,lease_token,heartbeat_at,scheduled_for,attempt_count,
     started_at,completed_at,allow_overlap)
VALUES
    ('f0000000-0000-4000-8000-000000000003','f0000000-0000-4000-8000-000000000001',
     'running','fixture-former-worker','f0000000-0000-4000-8000-000000000002',
     '2026-10-10T10:00:30Z','2026-10-10T10:00:00Z',2,'2026-10-10T10:00:00Z',NULL,false),
    ('f0000000-0000-4000-8000-000000000004','f0000000-0000-4000-8000-000000000001',
     'completed','fixture-earlier-worker',NULL,'2026-10-10T09:00:30Z',
     '2026-10-10T09:00:00Z',1,'2026-10-10T09:00:00Z','2026-10-10T09:00:30Z',false);

INSERT INTO platform_event
    (id,event_type,payload,status,lease_owner,lease_expires_at,retry_count,max_retries)
VALUES ('f0000000-0000-4000-8000-000000000005','kernel_recovery_fixture',
    '{"synthetic_recovery_fixture":true}','processing','fixture-former-worker',
    '2026-10-10T10:01:00Z',1,3);
-- Disabled synthetic handlers do not authorize or execute a domain operation.
INSERT INTO event_handler
    (id,handler_name,event_type,module_path,function_name,is_enabled)
VALUES
    ('f0000000-0000-4000-8000-000000000006','kernel_recovery_fixture_success',
     'kernel_recovery_fixture','services.cache.events','handle_metric_computed',false),
    ('f0000000-0000-4000-8000-000000000007','kernel_recovery_fixture_error',
     'kernel_recovery_fixture','services.cache.events','handle_crisp_scored',false);
INSERT INTO event_handler_delivery (event_id,handler_id,status,attempt_count)
VALUES
    ('f0000000-0000-4000-8000-000000000005','f0000000-0000-4000-8000-000000000006','success',1),
    ('f0000000-0000-4000-8000-000000000005','f0000000-0000-4000-8000-000000000007','error',2);
INSERT INTO event_handler_log (event_id,handler_id,status,error_message)
VALUES
    ('f0000000-0000-4000-8000-000000000005','f0000000-0000-4000-8000-000000000006','success',NULL),
    ('f0000000-0000-4000-8000-000000000005','f0000000-0000-4000-8000-000000000007','error','Synthetic fixture failure');
INSERT INTO event_dead_letter
    (id,original_event_id,event_type,payload,failure_count,last_error,disposition)
VALUES ('f0000000-0000-4000-8000-000000000008','f0000000-0000-4000-8000-000000000009',
    'kernel_recovery_fixture','{"synthetic_recovery_fixture":true}',3,
    'Synthetic fixture failure','pending');
COMMIT;
