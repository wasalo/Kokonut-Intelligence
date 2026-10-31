-- Location-scoped, identity-minimized extension-learning mutations.
-- Legacy CLI/service writers remain available; this adds a bounded Gateway
-- contract without changing the existing runtime/Directus table grants.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_extension_learning_writer'
    ) THEN
        CREATE ROLE kokonut_extension_learning_writer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_extension_learning_writer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Extension-learning writer role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_extension_learning_writer'
            OR member_role.rolname = 'kokonut_extension_learning_writer'
    ) THEN
        RAISE EXCEPTION 'Extension-learning writer role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.extension_peer_network_create_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    network_id UUID NOT NULL UNIQUE REFERENCES public.peer_network(id) ON DELETE RESTRICT,
    request_digest TEXT NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    network_name TEXT NOT NULL,
    network_type TEXT NOT NULL,
    network_status TEXT NOT NULL,
    network_created_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

CREATE TABLE IF NOT EXISTS public.extension_learning_progress_update_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    progress_id UUID NOT NULL REFERENCES public.learning_progress(id) ON DELETE RESTRICT,
    request_digest TEXT NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    response JSONB NOT NULL
        CHECK (jsonb_typeof(response) = 'object'
            AND response - ARRAY[
                'progress_id', 'location_id', 'module_id', 'progress_pct',
                'score', 'time_spent_min', 'status', 'completed_at',
                'updated_at', 'request_id'
            ]::TEXT[] = '{}'::JSONB
            AND response ?& ARRAY[
                'progress_id', 'location_id', 'module_id', 'progress_pct',
                'score', 'time_spent_min', 'status', 'completed_at',
                'updated_at', 'request_id'
            ]::TEXT[]),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

CREATE INDEX IF NOT EXISTS idx_extension_peer_network_create_receipt_location
    ON public.extension_peer_network_create_receipt(location_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_extension_learning_update_receipt_location
    ON public.extension_learning_progress_update_receipt(location_id, created_at DESC);

CREATE OR REPLACE FUNCTION public.prevent_extension_learning_receipt_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'extension-learning request receipts are append-only'
        USING ERRCODE = '55000';
    RETURN NULL;
END;
$$;
REVOKE ALL ON FUNCTION public.prevent_extension_learning_receipt_mutation()
    FROM PUBLIC;
DROP TRIGGER IF EXISTS trg_extension_peer_network_receipt_immutable
    ON public.extension_peer_network_create_receipt;
CREATE TRIGGER trg_extension_peer_network_receipt_immutable
    BEFORE UPDATE OR DELETE ON public.extension_peer_network_create_receipt
    FOR EACH ROW EXECUTE FUNCTION public.prevent_extension_learning_receipt_mutation();
DROP TRIGGER IF EXISTS trg_extension_learning_progress_receipt_immutable
    ON public.extension_learning_progress_update_receipt;
CREATE TRIGGER trg_extension_learning_progress_receipt_immutable
    BEFORE UPDATE OR DELETE ON public.extension_learning_progress_update_receipt
    FOR EACH ROW EXECUTE FUNCTION public.prevent_extension_learning_receipt_mutation();

REVOKE ALL ON TABLE public.extension_peer_network_create_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.extension_learning_progress_update_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.extension_peer_network_create_receipt
    FROM kokonut_runtime, kokonut_directus_runtime;
REVOKE ALL ON TABLE public.extension_learning_progress_update_receipt
    FROM kokonut_runtime, kokonut_directus_runtime;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_extension_learning_writer;
GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_extension_learning_writer;

-- The grant checker is SECURITY INVOKER. Give this bounded function owner only
-- the authorization columns required for a live, exact-location grant check.
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_extension_learning_writer;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_extension_learning_writer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_extension_learning_writer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_extension_learning_writer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_extension_learning_writer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_extension_learning_writer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_extension_learning_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_extension_learning_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_extension_learning_writer;

CREATE OR REPLACE FUNCTION kokonut_security.extension_compact_json_text(
    requested_value JSONB
)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
SET search_path = pg_catalog
AS $$
    SELECT CASE jsonb_typeof(requested_value)
        WHEN 'object' THEN '{' || COALESCE((
            SELECT string_agg(
                       to_jsonb(pair.key)::TEXT || ':' ||
                       kokonut_security.extension_compact_json_text(pair.value),
                       ',' ORDER BY pair.key COLLATE "C"
                   )
              FROM pg_catalog.jsonb_each(requested_value) AS pair
        ), '') || '}'
        WHEN 'array' THEN '[' || COALESCE((
            SELECT string_agg(
                       kokonut_security.extension_compact_json_text(item.value),
                       ',' ORDER BY item.ordinality
                   )
              FROM pg_catalog.jsonb_array_elements(requested_value)
                   WITH ORDINALITY AS item(value, ordinality)
        ), '') || ']'
        WHEN 'string' THEN to_jsonb(requested_value #>> '{}')::TEXT
        ELSE requested_value::TEXT
    END;
$$;
ALTER FUNCTION kokonut_security.extension_compact_json_text(JSONB)
    OWNER TO kokonut_extension_learning_writer;
REVOKE ALL ON FUNCTION kokonut_security.extension_compact_json_text(JSONB)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.extension_compact_json_text(JSONB)
    TO kokonut_extension_learning_writer;

CREATE OR REPLACE FUNCTION kokonut_security.extension_learning_grant_allows(
    requested_operator_id UUID,
    requested_action TEXT,
    requested_location_id UUID
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
    SELECT requested_action IN ('create_peer_network', 'update_progress')
       AND EXISTS (
            SELECT 1
              FROM public.operator_scope_grant AS grant_row
              JOIN public.operator_identity AS identity
                ON identity.id = grant_row.operator_id AND identity.enabled
              JOIN public.location AS loc ON loc.id = grant_row.location_id
             WHERE grant_row.operator_id = requested_operator_id
               AND grant_row.resource = 'extension_learning'
               AND grant_row.action = requested_action
               AND grant_row.location_id = requested_location_id
               AND grant_row.revoked_at IS NULL
               AND (
                    grant_row.organization_id IS NULL
                    OR (
                        EXISTS (
                            SELECT 1
                              FROM public.operator_organization_membership AS membership
                              JOIN public.organization AS tenant
                                ON tenant.id = membership.organization_id
                               AND tenant.status = 'active'
                              JOIN public.location_tenant_owner_verification AS owner
                                ON owner.location_id = loc.id
                               AND owner.organization_id = loc.organization_id
                               AND owner.revoked_at IS NULL
                             WHERE membership.operator_id = grant_row.operator_id
                               AND membership.organization_id = grant_row.organization_id
                               AND membership.revoked_at IS NULL
                        )
                        AND (
                            EXISTS (
                                SELECT 1
                                  FROM public.location_tenant_owner_verification AS owner
                                 WHERE owner.location_id = loc.id
                                   AND owner.organization_id = grant_row.organization_id
                                   AND owner.revoked_at IS NULL
                            )
                            OR EXISTS (
                                SELECT 1
                                  FROM public.location_organization_share AS share
                                 WHERE share.location_id = loc.id
                                   AND share.organization_id = grant_row.organization_id
                                   AND share.revoked_at IS NULL
                                   AND (share.expires_at IS NULL OR share.expires_at > NOW())
                            )
                        )
                    )
               )
       );
$$;
ALTER FUNCTION kokonut_security.extension_learning_grant_allows(UUID, TEXT, UUID)
    OWNER TO kokonut_extension_learning_writer;
REVOKE ALL ON FUNCTION kokonut_security.extension_learning_grant_allows(UUID, TEXT, UUID)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.extension_learning_grant_allows(UUID, TEXT, UUID)
    TO kokonut_extension_learning_writer;

GRANT SELECT (id, location_id, network_name, network_type, status, created_at),
      INSERT (network_name, description, network_type, location_id, max_members,
              meeting_cadence, language, status, metadata)
    ON TABLE public.peer_network TO kokonut_extension_learning_writer;

GRANT SELECT (id, location_id, module_id, progress_pct, score, time_spent_min,
              completed_at, status, metadata, updated_at),
      UPDATE (progress_pct, score, time_spent_min, completed_at, status, metadata, updated_at)
    ON TABLE public.learning_progress TO kokonut_extension_learning_writer;

GRANT SELECT (operator_id, request_id, location_id, network_id, request_digest,
              network_name, network_type, network_status, network_created_at, created_at),
      INSERT (operator_id, request_id, location_id, network_id, request_digest,
              network_name, network_type, network_status, network_created_at)
    ON TABLE public.extension_peer_network_create_receipt
    TO kokonut_extension_learning_writer;
GRANT SELECT (operator_id, request_id, location_id, progress_id, request_digest, response, created_at),
      INSERT (operator_id, request_id, location_id, progress_id, request_digest, response)
    ON TABLE public.extension_learning_progress_update_receipt
    TO kokonut_extension_learning_writer;

CREATE OR REPLACE FUNCTION kokonut_security.create_extension_peer_network(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_network_name TEXT,
    requested_description TEXT,
    requested_network_type TEXT,
    requested_max_members INTEGER,
    requested_meeting_cadence TEXT,
    requested_language TEXT,
    requested_metadata JSONB
)
RETURNS TABLE (
    peer_network_id UUID,
    location_id UUID,
    network_name TEXT,
    network_type TEXT,
    status TEXT,
    created_at TIMESTAMPTZ,
    request_id UUID,
    created BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    actor_id UUID;
    normalized_name TEXT;
    normalized_description TEXT;
    normalized_cadence TEXT;
    normalized_language TEXT;
    normalized_metadata JSONB;
    request_digest TEXT;
    existing_receipt public.extension_peer_network_create_receipt%ROWTYPE;
    inserted_network_id UUID;
    inserted_location_id UUID;
    inserted_network_name TEXT;
    inserted_network_type TEXT;
    inserted_network_status TEXT;
    inserted_network_created_at TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Peer-network creation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    actor_id := context_record.actor_id;
    IF NOT kokonut_security.extension_learning_grant_allows(
        actor_id, 'create_peer_network', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Peer-network creation requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;

    normalized_name := NULLIF(BTRIM(requested_network_name), '');
    normalized_description := NULLIF(BTRIM(requested_description), '');
    normalized_cadence := NULLIF(BTRIM(requested_meeting_cadence), '');
    normalized_language := NULLIF(BTRIM(requested_language), '');
    normalized_metadata := COALESCE(requested_metadata, '{}'::JSONB);
    IF normalized_name IS NULL OR CHAR_LENGTH(normalized_name) > 255
       OR (requested_description IS NOT NULL AND CHAR_LENGTH(requested_description) > 10000)
       OR (normalized_cadence IS NOT NULL AND CHAR_LENGTH(normalized_cadence) > 100)
       OR normalized_language IS NULL OR CHAR_LENGTH(normalized_language) > 50
       OR requested_network_type IS NULL
       OR requested_network_type NOT IN (
           'learning_group', 'mentorship', 'community_of_practice',
           'farmer_field_school', 'cooperative', 'other'
       )
       OR (requested_max_members IS NOT NULL AND requested_max_members < 1)
       OR jsonb_typeof(normalized_metadata) IS DISTINCT FROM 'object'
       OR octet_length(kokonut_security.extension_compact_json_text(normalized_metadata)) > 8192 THEN
        RAISE EXCEPTION 'Peer-network creation arguments are invalid'
            USING ERRCODE = '22023';
    END IF;

    request_digest := encode(public.digest(convert_to(
        jsonb_build_object(
            'location_id', requested_location_id,
            'network_name', normalized_name,
            'description', normalized_description,
            'network_type', requested_network_type,
            'max_members', requested_max_members,
            'meeting_cadence', normalized_cadence,
            'language', normalized_language,
            'metadata', normalized_metadata
        )::TEXT, 'UTF8'), 'sha256'), 'hex');
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(actor_id::TEXT || ':' || requested_request_id::TEXT, 0)
    );

    SELECT receipt.* INTO existing_receipt
      FROM public.extension_peer_network_create_receipt AS receipt
     WHERE receipt.operator_id = actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.request_digest IS DISTINCT FROM request_digest THEN
            RAISE EXCEPTION 'Peer-network request identifier conflicts with prior content'
                USING ERRCODE = '23505';
        END IF;
        RETURN QUERY SELECT existing_receipt.network_id,
                            existing_receipt.location_id,
                            existing_receipt.network_name,
                            existing_receipt.network_type,
                            existing_receipt.network_status,
                            existing_receipt.network_created_at,
                            requested_request_id,
                            FALSE;
        RETURN;
    END IF;

    INSERT INTO public.peer_network (
        network_name, description, network_type, location_id, max_members,
        meeting_cadence, language, status, metadata
    ) VALUES (
        normalized_name, normalized_description, requested_network_type,
        requested_location_id, requested_max_members, normalized_cadence,
        normalized_language, 'active', normalized_metadata
    ) RETURNING id, location_id, network_name, network_type, status, created_at
      INTO inserted_network_id, inserted_location_id, inserted_network_name,
           inserted_network_type, inserted_network_status, inserted_network_created_at;

    INSERT INTO public.extension_peer_network_create_receipt (
        operator_id, request_id, location_id, network_id, request_digest,
        network_name, network_type, network_status, network_created_at
    ) VALUES (
        actor_id, requested_request_id, requested_location_id, inserted_network_id,
        request_digest, inserted_network_name, inserted_network_type,
        inserted_network_status, inserted_network_created_at
    );

    RETURN QUERY SELECT inserted_network_id, inserted_location_id,
                        inserted_network_name,
                        inserted_network_type,
                        inserted_network_status, inserted_network_created_at,
                        requested_request_id, TRUE;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.update_extension_learning_progress(
    requested_location_id UUID,
    requested_progress_id UUID,
    requested_request_id UUID,
    requested_status TEXT,
    requested_score NUMERIC,
    requested_progress_pct NUMERIC,
    requested_time_spent_min_delta INTEGER,
    requested_metadata_patch JSONB
)
RETURNS TABLE (
    progress_id UUID,
    location_id UUID,
    module_id UUID,
    progress_pct NUMERIC,
    score NUMERIC,
    time_spent_min INTEGER,
    status TEXT,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    request_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    actor_id UUID;
    normalized_metadata_patch JSONB;
    request_digest TEXT;
    existing_receipt public.extension_learning_progress_update_receipt%ROWTYPE;
    current_progress_time_spent INTEGER;
    result_progress_id UUID;
    result_location_id UUID;
    result_module_id UUID;
    result_progress_pct NUMERIC;
    result_score NUMERIC;
    result_time_spent_min INTEGER;
    result_status TEXT;
    result_completed_at TIMESTAMPTZ;
    result_updated_at TIMESTAMPTZ;
    receipt_response JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_progress_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Progress update requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    actor_id := context_record.actor_id;
    IF NOT kokonut_security.extension_learning_grant_allows(
        actor_id, 'update_progress', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Progress update requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;

    normalized_metadata_patch := COALESCE(requested_metadata_patch, '{}'::JSONB);
    IF (requested_status IS NOT NULL AND requested_status NOT IN
          ('not_started', 'in_progress', 'completed', 'failed', 'expired'))
       OR (requested_score IS NOT NULL AND (
          requested_score::TEXT IN ('NaN', 'Infinity', '-Infinity')
          OR requested_score < 0 OR requested_score > 100))
       OR (requested_progress_pct IS NOT NULL AND (
          requested_progress_pct::TEXT IN ('NaN', 'Infinity', '-Infinity')
          OR requested_progress_pct < 0 OR requested_progress_pct > 100))
       OR (requested_time_spent_min_delta IS NOT NULL AND
          requested_time_spent_min_delta NOT BETWEEN 1 AND 1440)
       OR jsonb_typeof(normalized_metadata_patch) IS DISTINCT FROM 'object'
       OR octet_length(kokonut_security.extension_compact_json_text(normalized_metadata_patch)) > 8192
       OR (requested_status IS NULL AND requested_score IS NULL
          AND requested_progress_pct IS NULL
          AND requested_time_spent_min_delta IS NULL
          AND normalized_metadata_patch = '{}'::JSONB) THEN
        RAISE EXCEPTION 'Progress update arguments are invalid'
            USING ERRCODE = '22023';
    END IF;

    request_digest := encode(public.digest(convert_to(
        jsonb_build_object(
            'location_id', requested_location_id,
            'progress_id', requested_progress_id,
            'status', requested_status,
            'score', requested_score,
            'progress_pct', requested_progress_pct,
            'time_spent_min_delta', requested_time_spent_min_delta,
            'metadata_patch', normalized_metadata_patch
        )::TEXT, 'UTF8'), 'sha256'), 'hex');
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(actor_id::TEXT || ':' || requested_request_id::TEXT, 0)
    );

    SELECT receipt.* INTO existing_receipt
      FROM public.extension_learning_progress_update_receipt AS receipt
     WHERE receipt.operator_id = actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.progress_id IS DISTINCT FROM requested_progress_id
           OR existing_receipt.request_digest IS DISTINCT FROM request_digest THEN
            RAISE EXCEPTION 'Progress request identifier conflicts with prior content'
                USING ERRCODE = '23505';
        END IF;
        RETURN QUERY SELECT
            (existing_receipt.response ->> 'progress_id')::UUID,
            (existing_receipt.response ->> 'location_id')::UUID,
            (existing_receipt.response ->> 'module_id')::UUID,
            (existing_receipt.response ->> 'progress_pct')::NUMERIC,
            (existing_receipt.response ->> 'score')::NUMERIC,
            (existing_receipt.response ->> 'time_spent_min')::INTEGER,
            existing_receipt.response ->> 'status',
            (existing_receipt.response ->> 'completed_at')::TIMESTAMPTZ,
            (existing_receipt.response ->> 'updated_at')::TIMESTAMPTZ,
            (existing_receipt.response ->> 'request_id')::UUID;
        RETURN;
    END IF;

    SELECT progress.time_spent_min INTO current_progress_time_spent
      FROM public.learning_progress AS progress
     WHERE progress.id = requested_progress_id
       AND progress.location_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Progress record does not exist at the requested location'
            USING ERRCODE = 'P0002';
    END IF;
    IF requested_time_spent_min_delta IS NOT NULL
       AND COALESCE(current_progress_time_spent, 0) >
           2147483647 - requested_time_spent_min_delta THEN
        RAISE EXCEPTION 'Progress time total exceeds the supported range'
            USING ERRCODE = '22003';
    END IF;

    UPDATE public.learning_progress AS progress
       SET status = COALESCE(requested_status, progress.status),
           score = COALESCE(requested_score, progress.score),
           progress_pct = COALESCE(requested_progress_pct, progress.progress_pct),
           time_spent_min = CASE
               WHEN requested_time_spent_min_delta IS NULL THEN progress.time_spent_min
               ELSE COALESCE(progress.time_spent_min, 0) + requested_time_spent_min_delta
           END,
           completed_at = CASE
               WHEN requested_status = 'completed' THEN clock_timestamp()
               ELSE progress.completed_at
           END,
           metadata = COALESCE(progress.metadata, '{}'::JSONB) || normalized_metadata_patch,
           updated_at = clock_timestamp()
     WHERE progress.id = requested_progress_id
       AND progress.location_id = requested_location_id
    RETURNING progress.id, progress.location_id, progress.module_id,
              progress.progress_pct, progress.score, progress.time_spent_min,
              progress.status, progress.completed_at, progress.updated_at
      INTO result_progress_id, result_location_id, result_module_id,
           result_progress_pct, result_score, result_time_spent_min,
           result_status, result_completed_at, result_updated_at;

    receipt_response := jsonb_build_object(
        'progress_id', result_progress_id,
        'location_id', result_location_id,
        'module_id', result_module_id,
        'progress_pct', result_progress_pct,
        'score', result_score,
        'time_spent_min', result_time_spent_min,
        'status', result_status,
        'completed_at', result_completed_at,
        'updated_at', result_updated_at,
        'request_id', requested_request_id
    );
    INSERT INTO public.extension_learning_progress_update_receipt (
        operator_id, request_id, location_id, progress_id, request_digest, response
    ) VALUES (
        actor_id, requested_request_id, requested_location_id,
        requested_progress_id, request_digest, receipt_response
    );

    RETURN QUERY SELECT result_progress_id, result_location_id,
                        result_module_id, result_progress_pct,
                        result_score, result_time_spent_min,
                        result_status, result_completed_at,
                        result_updated_at, requested_request_id;
END;
$$;

ALTER FUNCTION kokonut_security.create_extension_peer_network(
    UUID, UUID, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, JSONB
) OWNER TO kokonut_extension_learning_writer;
ALTER FUNCTION kokonut_security.update_extension_learning_progress(
    UUID, UUID, UUID, TEXT, NUMERIC, NUMERIC, INTEGER, JSONB
) OWNER TO kokonut_extension_learning_writer;

REVOKE ALL ON FUNCTION kokonut_security.create_extension_peer_network(
    UUID, UUID, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, JSONB
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.update_extension_learning_progress(
    UUID, UUID, UUID, TEXT, NUMERIC, NUMERIC, INTEGER, JSONB
) FROM PUBLIC;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_extension_learning_writer;
REVOKE ALL ON FUNCTION kokonut_security.extension_compact_json_text(JSONB)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.extension_learning_grant_allows(UUID, TEXT, UUID)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.create_extension_peer_network(
    UUID, UUID, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, JSONB
) TO kokonut_runtime;
GRANT EXECUTE ON FUNCTION kokonut_security.update_extension_learning_progress(
    UUID, UUID, UUID, TEXT, NUMERIC, NUMERIC, INTEGER, JSONB
) TO kokonut_runtime;

COMMENT ON TABLE public.extension_peer_network_create_receipt IS
    'Private immutable idempotency and audit receipts for exact-location Gateway peer-network creation.';
COMMENT ON TABLE public.extension_learning_progress_update_receipt IS
    'Private immutable idempotency and audit receipts for exact-location learning-progress updates; response snapshots contain no participant identity.';
COMMENT ON FUNCTION kokonut_security.create_extension_peer_network(
    UUID, UUID, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, JSONB
) IS
    'Creates an active peer network only under signed operator location context and the exact extension_learning:create_peer_network grant; stores an immutable request receipt atomically.';
COMMENT ON FUNCTION kokonut_security.update_extension_learning_progress(
    UUID, UUID, UUID, TEXT, NUMERIC, NUMERIC, INTEGER, JSONB
) IS
    'Updates one exact-location learning-progress row under signed operator context; preserves legacy metadata-merge and completion timestamp behavior and returns an identity-minimized immutable retry receipt.';

COMMIT;
