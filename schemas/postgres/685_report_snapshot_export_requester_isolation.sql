-- Keep export request metadata and completed artifacts private to the
-- operator who created each request. Candidate snapshots remain location
-- shared under the independent report_snapshot_export:read grant.

BEGIN;

CREATE INDEX IF NOT EXISTS report_snapshot_export_request_owner_read
    ON public.report_snapshot_export_request
       (location_id, requested_by, created_at DESC, request_id DESC);

CREATE OR REPLACE FUNCTION kokonut_security.list_report_snapshot_exports(
    requested_location_id UUID,
    requested_limit INTEGER
)
RETURNS TABLE (
    request_id UUID, snapshot_id UUID, location_id UUID, status TEXT,
    attempt_count INTEGER, artifact_size BIGINT, created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, last_error_class TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD;
BEGIN
    IF SESSION_USER <> 'kokonut_runtime' OR requested_location_id IS NULL
       OR requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50 THEN
        RAISE EXCEPTION 'report snapshot export list request is invalid'
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
        RAISE EXCEPTION 'report snapshot export list requires signed location read scope'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT request.request_id, request.snapshot_id, request.location_id,
           request.status, request.attempt_count, request.artifact_size,
           request.created_at, request.updated_at, request.completed_at,
           request.last_error_class
      FROM public.report_snapshot_export_request AS request
     WHERE request.location_id = requested_location_id
       AND request.requested_by = context_record.actor_id
     ORDER BY request.created_at DESC, request.request_id DESC
     LIMIT requested_limit;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.get_report_snapshot_export(
    requested_location_id UUID,
    requested_request_id UUID
)
RETURNS TABLE (
    request_id UUID, snapshot_id UUID, location_id UUID, status TEXT,
    attempt_count INTEGER, artifact_size BIGINT, created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, last_error_class TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD;
BEGIN
    IF SESSION_USER <> 'kokonut_runtime' OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'report snapshot export detail request is invalid'
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
        RAISE EXCEPTION 'report snapshot export detail requires signed location read scope'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT request.request_id, request.snapshot_id, request.location_id,
           request.status, request.attempt_count, request.artifact_size,
           request.created_at, request.updated_at, request.completed_at,
           request.last_error_class
      FROM public.report_snapshot_export_request AS request
     WHERE request.request_id = requested_request_id
       AND request.location_id = requested_location_id
       AND request.requested_by = context_record.actor_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.authorize_report_snapshot_export_download(
    requested_location_id UUID,
    requested_request_id UUID
)
RETURNS TABLE (artifact_id UUID, artifact_sha256 TEXT, artifact_size BIGINT)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD;
        request_record RECORD;
BEGIN
    IF SESSION_USER <> 'kokonut_runtime' OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'report snapshot export download request is invalid'
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
           context_record.actor_id, 'report_snapshot_export', 'download', requested_location_id
       ) THEN
        RAISE EXCEPTION 'report snapshot export download requires signed location download scope'
            USING ERRCODE = '42501';
    END IF;
    SELECT request.* INTO request_record
      FROM public.report_snapshot_export_request AS request
      JOIN public.report_snapshot AS snapshot
        ON snapshot.id = request.snapshot_id
       AND snapshot.location_id = request.location_id
       AND snapshot.status IN ('verified', 'published')
       AND snapshot.snapshot_hash = request.source_snapshot_hash
      JOIN public.operator_identity AS requester
        ON requester.id = request.requested_by AND requester.enabled
     WHERE request.request_id = requested_request_id
       AND request.location_id = requested_location_id
       AND request.requested_by = context_record.actor_id
       AND request.status = 'completed'
       AND public.operator_scope_grant_allows(
           request.requested_by, 'report_snapshot_export', 'create', requested_location_id
       );
    IF NOT FOUND THEN
        RETURN;
    END IF;
    RETURN QUERY SELECT request_record.artifact_id,
                        request_record.artifact_sha256,
                        request_record.artifact_size;
END;
$$;

ALTER FUNCTION kokonut_security.list_report_snapshot_exports(UUID, INTEGER)
    OWNER TO kokonut_report_snapshot_export_owner;
ALTER FUNCTION kokonut_security.get_report_snapshot_export(UUID, UUID)
    OWNER TO kokonut_report_snapshot_export_owner;
ALTER FUNCTION kokonut_security.authorize_report_snapshot_export_download(UUID, UUID)
    OWNER TO kokonut_report_snapshot_export_owner;

REVOKE ALL ON FUNCTION kokonut_security.list_report_snapshot_exports(UUID, INTEGER)
    FROM PUBLIC, kokonut_report_snapshot_export_login;
REVOKE ALL ON FUNCTION kokonut_security.get_report_snapshot_export(UUID, UUID)
    FROM PUBLIC, kokonut_report_snapshot_export_login;
REVOKE ALL ON FUNCTION kokonut_security.authorize_report_snapshot_export_download(UUID, UUID)
    FROM PUBLIC, kokonut_report_snapshot_export_login;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION
            kokonut_security.list_report_snapshot_exports(UUID, INTEGER),
            kokonut_security.get_report_snapshot_export(UUID, UUID),
            kokonut_security.authorize_report_snapshot_export_download(UUID, UUID)
        TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION
            kokonut_security.list_report_snapshot_exports(UUID, INTEGER),
            kokonut_security.get_report_snapshot_export(UUID, UUID),
            kokonut_security.authorize_report_snapshot_export_download(UUID, UUID)
        FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMIT;
