-- Bounded, exact-location listing for reviewed report snapshots eligible for
-- private export. The browser receives no payload body or storage locator.

BEGIN;

CREATE OR REPLACE FUNCTION kokonut_security.list_report_snapshot_export_candidates(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    snapshot_id UUID,
    location_id UUID,
    report_name TEXT,
    report_type TEXT,
    status TEXT,
    period_start DATE,
    period_end DATE,
    snapshot_hash TEXT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD;
BEGIN
    IF SESSION_USER <> 'kokonut_runtime'
       OR requested_location_id IS NULL
       OR requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 5000 THEN
        RAISE EXCEPTION 'report snapshot export candidate query is invalid'
            USING ERRCODE = '42501';
    END IF;

    SELECT context.tenant_id, context.location_id, context.actor_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.tenant_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR NOT public.operator_scope_grant_allows(
           context_record.actor_id, 'report_snapshot_export', 'read', requested_location_id
       ) THEN
        RAISE EXCEPTION 'report snapshot export candidates require signed location read scope'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT snapshot.id,
           snapshot.location_id,
           snapshot.report_name::TEXT,
           snapshot.report_type::TEXT,
           snapshot.status::TEXT,
           snapshot.period_start,
           snapshot.period_end,
           snapshot.snapshot_hash::TEXT,
           snapshot.created_at
      FROM public.report_snapshot AS snapshot
     WHERE snapshot.location_id = requested_location_id
       AND snapshot.status IN ('verified', 'published')
       AND snapshot.snapshot_hash ~ '^[0-9a-f]{64}$'
       AND pg_catalog.jsonb_typeof(snapshot.report_data) = 'object'
       AND pg_catalog.octet_length(
           pg_catalog.convert_to(snapshot.report_data::TEXT, 'UTF8')
       ) <= 524288
     ORDER BY snapshot.created_at DESC NULLS LAST, snapshot.id DESC
     LIMIT requested_limit + 1
    OFFSET requested_offset;
END;
$$;

ALTER FUNCTION kokonut_security.list_report_snapshot_export_candidates(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_report_snapshot_export_owner;
REVOKE ALL ON FUNCTION kokonut_security.list_report_snapshot_export_candidates(UUID, INTEGER, INTEGER)
    FROM PUBLIC, kokonut_report_snapshot_export_login;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION
            kokonut_security.list_report_snapshot_export_candidates(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION
            kokonut_security.list_report_snapshot_export_candidates(UUID, INTEGER, INTEGER)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMIT;
