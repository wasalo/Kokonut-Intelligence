-- Extend the authenticated agent/worker lifecycle guard to terminal inserts.
-- Migration 350 attached update-only triggers; keep its immutable history and
-- add an ordered, replay-safe insert guard for those same governed tables.

BEGIN;

CREATE OR REPLACE FUNCTION public.assert_agent_safety()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
DECLARE
    caller_agent_marker TEXT;
    authenticated_worker BOOLEAN;
BEGIN
    caller_agent_marker := current_setting('app.agent_id', TRUE);
    authenticated_worker :=
        current_user = 'kokonut_worker_execution'
        OR pg_catalog.pg_has_role(
            session_user, 'kokonut_worker_execution', 'MEMBER'
        );

    -- The compatibility marker can only add a restriction. Worker role
    -- membership is checked from the authenticated connection login as well
    -- as current_user so SECURITY DEFINER functions cannot hide it.
    IF NOT authenticated_worker
       AND (caller_agent_marker IS NULL OR caller_agent_marker = '') THEN
        RETURN NEW;
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.status IN ('verified', 'published') THEN
            RAISE EXCEPTION 'Agent worker operations cannot insert terminal status % on %',
                NEW.status, TG_TABLE_NAME
                USING ERRCODE = '42501';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'UPDATE'
       AND NEW.status IS DISTINCT FROM OLD.status
       AND NEW.status IN ('verified', 'published') THEN
        RAISE EXCEPTION 'Agent worker operations cannot set status to % on %',
            NEW.status, TG_TABLE_NAME
            USING ERRCODE = '42501';
    END IF;

    RETURN NEW;
END;
$$;

DO $$
DECLARE
    target_table RECORD;
    trigger_name TEXT := 'trg_agent_safety_insert';
    target_count INTEGER := 0;
BEGIN
    IF pg_catalog.to_regprocedure('public.assert_agent_safety()') IS NULL THEN
        RAISE EXCEPTION 'migration 579 requires the migration 350 agent safety trigger function';
    END IF;

    FOR target_table IN
        SELECT DISTINCT relation_namespace.nspname AS schema_name,
                        relation.relname AS table_name
          FROM pg_catalog.pg_trigger AS trigger_row
          JOIN pg_catalog.pg_class AS relation
            ON relation.oid = trigger_row.tgrelid
          JOIN pg_catalog.pg_namespace AS relation_namespace
            ON relation_namespace.oid = relation.relnamespace
         WHERE trigger_row.tgfoid = 'public.assert_agent_safety()'::pg_catalog.regprocedure
           AND NOT trigger_row.tgisinternal
           AND (trigger_row.tgtype::INTEGER & 1) = 1
           AND (trigger_row.tgtype::INTEGER & 16) = 16
           AND relation_namespace.nspname = 'public'
           AND EXISTS (
               SELECT 1
                 FROM pg_catalog.pg_attribute AS status_column
                WHERE status_column.attrelid = relation.oid
                  AND status_column.attname = 'status'
                  AND status_column.attnum > 0
                  AND NOT status_column.attisdropped
           )
    LOOP
        EXECUTE pg_catalog.format(
            'DROP TRIGGER IF EXISTS %I ON %I.%I',
            trigger_name, target_table.schema_name, target_table.table_name
        );
        EXECUTE pg_catalog.format(
            'CREATE TRIGGER %I BEFORE INSERT ON %I.%I '
            'FOR EACH ROW WHEN (NEW.status IN (''verified'', ''published'')) '
            'EXECUTE FUNCTION public.assert_agent_safety()',
            trigger_name, target_table.schema_name, target_table.table_name
        );
        target_count := target_count + 1;
    END LOOP;

    IF target_count = 0 THEN
        RAISE EXCEPTION 'migration 579 found no governed tables with the migration 350 safety trigger';
    END IF;
END;
$$;

COMMENT ON FUNCTION public.assert_agent_safety() IS
    'Prevents authenticated kokonut_worker_execution operations from inserting or promoting governed records to verified/published. The caller-set app.agent_id compatibility marker adds this restriction but is not an identity or authorization boundary.';

COMMIT;
