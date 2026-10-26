-- Create private, exact-location Delphi study drafts through signed Gateway scope.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_recommendation_drafter'
    ) THEN
        RAISE EXCEPTION 'Delphi study drafter role prerequisites are missing';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_recommendation_drafter'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Delphi study drafter role must remain non-login and non-inheriting';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_study_draft_request (
    operator_id UUID NOT NULL
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL
        REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL UNIQUE
        REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    payload_digest BYTEA NOT NULL
        CHECK (pg_catalog.octet_length(payload_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.now(),
    PRIMARY KEY (operator_id, request_id)
);

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_study_draft_request_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi study draft request history is append-only';
    RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_study_draft_request_mutation()
    FROM PUBLIC;
DROP TRIGGER IF EXISTS trg_delphi_study_draft_request_immutable
    ON kokonut_security.delphi_study_draft_request;
CREATE TRIGGER trg_delphi_study_draft_request_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_study_draft_request
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_study_draft_request_mutation();

ALTER TABLE kokonut_security.delphi_study_draft_request
    OWNER TO kokonut_delphi_recommendation_drafter;
REVOKE ALL ON TABLE kokonut_security.delphi_study_draft_request FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE kokonut_security.delphi_study_draft_request
    TO kokonut_delphi_recommendation_drafter;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_study_draft_request
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_study_draft_request
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

REVOKE ALL ON TABLE public.delphi_study
    FROM kokonut_delphi_recommendation_drafter;
GRANT SELECT (id, location_id, title, description, variation, status,
              facilitator_type, stopping_criteria, created_by, created_at,
              updated_at)
    ON TABLE public.delphi_study
    TO kokonut_delphi_recommendation_drafter;
GRANT UPDATE (id) ON TABLE public.delphi_study
    TO kokonut_delphi_recommendation_drafter;
GRANT INSERT (id, location_id, title, description, variation, status,
              facilitator_type, stopping_criteria, created_by)
    ON TABLE public.delphi_study
    TO kokonut_delphi_recommendation_drafter;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_delphi_study_draft(
    requested_location_id UUID,
    requested_title TEXT,
    requested_description TEXT,
    requested_variation TEXT,
    requested_facilitator_type TEXT,
    requested_stopping_criteria JSONB,
    requested_request_id UUID
)
RETURNS TABLE (
    study_id UUID,
    title TEXT,
    status TEXT,
    created_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    prior_record RECORD;
    normalized_title TEXT;
    normalized_description TEXT;
    request_payload JSONB;
    request_digest BYTEA;
    created_study_id UUID;
    created_at_value TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Delphi study draft requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'draft', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi study draft requires an active location grant'
            USING ERRCODE = '42501';
    END IF;

    normalized_title := pg_catalog.btrim(requested_title);
    normalized_description := NULLIF(pg_catalog.btrim(requested_description), '');
    IF requested_request_id IS NULL
       OR normalized_title IS NULL
       OR pg_catalog.length(normalized_title) NOT BETWEEN 1 AND 255
       OR (normalized_description IS NOT NULL
           AND pg_catalog.length(normalized_description) > 4000)
       OR requested_variation IS NULL
       OR requested_variation NOT IN (
           'classic', 'policy', 'argument', 'disaggregative', 'real_time', 'fast_track'
       )
       OR requested_facilitator_type IS NULL
       OR requested_facilitator_type NOT IN ('agent', 'human', 'hybrid')
       THEN
        RAISE EXCEPTION 'Delphi study draft payload is invalid'
            USING ERRCODE = '22023';
    END IF;

    IF pg_catalog.jsonb_typeof(requested_stopping_criteria) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'Delphi study stopping criteria must be an object'
            USING ERRCODE = '22023';
    END IF;
    IF requested_stopping_criteria - ARRAY[
           'max_duration_hours', 'stability_pct', 'min_participants', 'iqr_threshold'
       ] <> '{}'::JSONB
       OR NOT (requested_stopping_criteria ?& ARRAY[
           'max_duration_hours', 'stability_pct', 'min_participants', 'iqr_threshold'
       ]) THEN
        RAISE EXCEPTION 'Delphi study stopping criteria fields are invalid'
            USING ERRCODE = '22023';
    END IF;
    IF pg_catalog.jsonb_typeof(requested_stopping_criteria -> 'max_duration_hours')
           IS DISTINCT FROM 'number'
       OR pg_catalog.jsonb_typeof(requested_stopping_criteria -> 'stability_pct')
           IS DISTINCT FROM 'number'
       OR pg_catalog.jsonb_typeof(requested_stopping_criteria -> 'min_participants')
           IS DISTINCT FROM 'number'
       OR pg_catalog.jsonb_typeof(requested_stopping_criteria -> 'iqr_threshold')
           IS DISTINCT FROM 'number' THEN
        RAISE EXCEPTION 'Delphi study stopping criteria values must be numbers'
            USING ERRCODE = '22023';
    END IF;
    IF (requested_stopping_criteria ->> 'max_duration_hours')::NUMERIC
           NOT BETWEEN 1 AND 8760
       OR pg_catalog.trunc((requested_stopping_criteria ->> 'max_duration_hours')::NUMERIC)
           <> (requested_stopping_criteria ->> 'max_duration_hours')::NUMERIC
       OR (requested_stopping_criteria ->> 'stability_pct')::NUMERIC
           NOT BETWEEN 0 AND 100
       OR (requested_stopping_criteria ->> 'min_participants')::NUMERIC
           NOT BETWEEN 3 AND 10000
       OR pg_catalog.trunc((requested_stopping_criteria ->> 'min_participants')::NUMERIC)
           <> (requested_stopping_criteria ->> 'min_participants')::NUMERIC
       OR (requested_stopping_criteria ->> 'iqr_threshold')::NUMERIC
           NOT BETWEEN 0 AND 2 THEN
        RAISE EXCEPTION 'Delphi study stopping criteria are invalid'
            USING ERRCODE = '22023';
    END IF;

    request_payload := pg_catalog.jsonb_build_object(
        'title', normalized_title,
        'description', normalized_description,
        'variation', requested_variation,
        'facilitator_type', requested_facilitator_type,
        'stopping_criteria', requested_stopping_criteria
    );
    request_digest := public.digest(
        pg_catalog.convert_to(request_payload::TEXT, 'UTF8'), 'sha256'
    );

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT request.location_id, request.payload_digest, study.id,
           study.title, study.status, study.created_at
      INTO prior_record
      FROM kokonut_security.delphi_study_draft_request AS request
      JOIN public.delphi_study AS study ON study.id = request.study_id
     WHERE request.operator_id = context_record.actor_id
       AND request.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_record.location_id IS DISTINCT FROM requested_location_id
           OR prior_record.payload_digest IS DISTINCT FROM request_digest THEN
            RAISE EXCEPTION 'Delphi study request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        study_id := prior_record.id;
        title := prior_record.title;
        status := prior_record.status;
        created_at := prior_record.created_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    INSERT INTO public.delphi_study AS created_study (
        id, location_id, title, description, variation, status,
        facilitator_type, stopping_criteria, created_by
    ) VALUES (
        pg_catalog.gen_random_uuid(), requested_location_id, normalized_title,
        normalized_description, requested_variation, 'draft',
        requested_facilitator_type, requested_stopping_criteria,
        context_record.actor_id
    )
    RETURNING created_study.id, created_study.created_at
         INTO created_study_id, created_at_value;

    INSERT INTO kokonut_security.delphi_study_draft_request (
        operator_id, request_id, location_id, study_id, payload_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        created_study_id, request_digest
    );

    study_id := created_study_id;
    title := normalized_title;
    status := 'draft';
    created_at := created_at_value;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.create_location_delphi_study_draft(
    UUID, TEXT, TEXT, TEXT, TEXT, JSONB, UUID
) OWNER TO kokonut_delphi_recommendation_drafter;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_delphi_recommendation_drafter;
REVOKE ALL ON FUNCTION kokonut_security.create_location_delphi_study_draft(
    UUID, TEXT, TEXT, TEXT, TEXT, JSONB, UUID
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.create_location_delphi_study_draft(
            UUID, TEXT, TEXT, TEXT, TEXT, JSONB, UUID
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_location_delphi_study_draft(
            UUID, TEXT, TEXT, TEXT, TEXT, JSONB, UUID
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_delphi_study_draft(
    UUID, TEXT, TEXT, TEXT, TEXT, JSONB, UUID
) IS 'Creates an idempotent private Delphi study draft for an operator with a signed exact-location delphi:draft grant.';
COMMENT ON TABLE kokonut_security.delphi_study_draft_request IS
    'Private immutable request receipts for authenticated location-scoped Delphi study draft creation.';

COMMIT;
