-- Bounded, retry-safe completion events for the global scheduler executor.
-- This prepares a dedicated login; provisioning/cutover remains separate.
BEGIN;
CREATE SCHEMA IF NOT EXISTS kokonut_security;
DO $$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_scheduler_event_owner','kokonut_scheduler_login'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS', role_name);
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name AND
            (rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit OR rolreplication OR rolbypassrls
             OR (rolname = 'kokonut_scheduler_event_owner' AND rolcanlogin)))
           OR EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r
               ON r.oid = m.member OR r.oid = m.roleid WHERE r.rolname = role_name) THEN
            RAISE EXCEPTION 'unsafe scheduler role %', role_name;
        END IF;
    END LOOP;
END $$;
CREATE TABLE IF NOT EXISTS kokonut_security.scheduler_run_event_receipt (
    run_id uuid PRIMARY KEY,
    event_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE
);
ALTER TABLE kokonut_security.scheduler_run_event_receipt OWNER TO kokonut_scheduler_event_owner;
REVOKE ALL ON kokonut_security.scheduler_run_event_receipt FROM PUBLIC;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_scheduler_event_owner;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_scheduler_login;
GRANT SELECT (id, task_id, status, completed_at, duration_ms, worker_id)
    ON public.task_run TO kokonut_scheduler_event_owner;
GRANT INSERT (id, event_type, source_table, source_id, payload, priority)
    ON public.platform_event TO kokonut_scheduler_event_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_scheduler_event_owner;
CREATE OR REPLACE FUNCTION kokonut_security.enqueue_scheduler_run_event(p_run_id uuid, p_worker_id text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE run_row record; result_id uuid;
BEGIN
    SELECT id, task_id, status, duration_ms INTO run_row
      FROM public.task_run
     WHERE id = p_run_id AND worker_id = p_worker_id
       AND completed_at IS NOT NULL AND status IN ('completed','failed','timeout');
    IF NOT FOUND THEN
        RAISE EXCEPTION 'terminal scheduler run required' USING ERRCODE = '42501';
    END IF;
    INSERT INTO kokonut_security.scheduler_run_event_receipt(run_id)
        VALUES (p_run_id) ON CONFLICT DO NOTHING RETURNING event_id INTO result_id;
    IF result_id IS NULL THEN
        SELECT event_id INTO result_id FROM kokonut_security.scheduler_run_event_receipt WHERE run_id = p_run_id;
        RETURN result_id;
    END IF;
    INSERT INTO public.platform_event(id,event_type,source_table,source_id,payload,priority)
    VALUES(result_id, CASE WHEN run_row.status = 'completed' THEN 'task_completed' ELSE 'task_failed' END,
        'task_run',p_run_id,jsonb_build_object('task_id',run_row.task_id,'run_id',p_run_id,
        'status',run_row.status,'duration_ms',run_row.duration_ms),'normal');
    RETURN result_id;
END $$;
ALTER FUNCTION kokonut_security.enqueue_scheduler_run_event(uuid,text) OWNER TO kokonut_scheduler_event_owner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_scheduler_event_owner;
REVOKE ALL ON FUNCTION kokonut_security.enqueue_scheduler_run_event(uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.enqueue_scheduler_run_event(uuid,text) TO kokonut_scheduler_login;
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='kokonut_runtime') THEN
  GRANT EXECUTE ON FUNCTION kokonut_security.enqueue_scheduler_run_event(uuid,text) TO kokonut_runtime;
 END IF;
END $$;
COMMIT;
