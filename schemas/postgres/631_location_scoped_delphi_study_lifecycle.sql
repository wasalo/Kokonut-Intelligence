-- Govern Delphi study opening and closure through exact location grants.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_study_lifecycle'
    ) THEN
        CREATE ROLE kokonut_delphi_study_lifecycle
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_study_lifecycle'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Delphi lifecycle role must remain non-login and non-inheriting';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_study_lifecycle_request (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action IN ('open', 'close')),
    result_status TEXT NOT NULL CHECK (result_status IN ('open', 'closed')),
    result_opened_at TIMESTAMPTZ NOT NULL,
    result_closed_at TIMESTAMPTZ,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_study_lifecycle_request_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi study lifecycle request history is append-only';
    RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_study_lifecycle_request_mutation()
    FROM PUBLIC;
DROP TRIGGER IF EXISTS trg_delphi_study_lifecycle_request_immutable
    ON kokonut_security.delphi_study_lifecycle_request;
CREATE TRIGGER trg_delphi_study_lifecycle_request_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_study_lifecycle_request
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_study_lifecycle_request_mutation();

ALTER TABLE kokonut_security.delphi_study_lifecycle_request
    OWNER TO kokonut_delphi_study_lifecycle;
REVOKE ALL ON TABLE kokonut_security.delphi_study_lifecycle_request FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE kokonut_security.delphi_study_lifecycle_request
    TO kokonut_delphi_study_lifecycle;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_delphi_study_lifecycle;
GRANT SELECT ON TABLE public.operator_scope_grant, public.operator_identity,
    public.location, public.operator_organization_membership,
    public.location_tenant_owner_verification, public.location_organization_share,
    public.organization
    TO kokonut_delphi_study_lifecycle;
REVOKE ALL ON TABLE public.delphi_study, public.delphi_item, public.delphi_panel_member
    FROM kokonut_delphi_study_lifecycle;
GRANT SELECT (id, location_id, status, stopping_criteria, opened_at, closed_at, updated_at)
    ON TABLE public.delphi_study TO kokonut_delphi_study_lifecycle;
GRANT UPDATE (id, status, opened_at, closed_at, updated_at)
    ON TABLE public.delphi_study TO kokonut_delphi_study_lifecycle;
GRANT SELECT (study_id) ON TABLE public.delphi_item
    TO kokonut_delphi_study_lifecycle;
GRANT SELECT (study_id, consent_status) ON TABLE public.delphi_panel_member
    TO kokonut_delphi_study_lifecycle;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_delphi_study_lifecycle;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_delphi_study_lifecycle;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_delphi_study_lifecycle;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_study_lifecycle_request
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_study_lifecycle_request
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.transition_location_delphi_study(
    requested_location_id UUID,
    requested_study_id UUID,
    requested_action TEXT,
    requested_request_id UUID
)
RETURNS TABLE (
    study_id UUID,
    location_id UUID,
    status TEXT,
    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    study_record RECORD;
    prior_record RECORD;
    consented_count BIGINT;
    required_participants INTEGER;
    payload_digest BYTEA;
    changed_status TEXT;
    changed_opened_at TIMESTAMPTZ;
    changed_closed_at TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_study_id IS NULL
       OR requested_action NOT IN ('open', 'close') THEN
        RAISE EXCEPTION 'Delphi lifecycle requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', requested_action, requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi lifecycle requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Delphi lifecycle request id is required'
            USING ERRCODE = '22023';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'study_id', requested_study_id,
                'action', requested_action
            )::TEXT,
            'UTF8'
        ),
        'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT request.location_id, request.study_id, request.action,
           request.result_status, request.result_opened_at, request.result_closed_at,
           request.payload_digest
      INTO prior_record
      FROM kokonut_security.delphi_study_lifecycle_request AS request
     WHERE request.operator_id = context_record.actor_id
       AND request.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_record.location_id IS DISTINCT FROM requested_location_id
           OR prior_record.study_id IS DISTINCT FROM requested_study_id
           OR prior_record.action IS DISTINCT FROM requested_action
           OR prior_record.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Delphi lifecycle request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        study_id := prior_record.study_id;
        location_id := prior_record.location_id;
        status := prior_record.result_status;
        opened_at := prior_record.result_opened_at;
        closed_at := prior_record.result_closed_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT study.id, study.location_id, study.status, study.stopping_criteria,
           study.opened_at, study.closed_at
      INTO study_record
      FROM public.delphi_study AS study
     WHERE study.id = requested_study_id
       AND study.location_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi study is unavailable for this location'
            USING ERRCODE = '22023';
    END IF;

    IF requested_action = 'open' THEN
        IF study_record.status IS DISTINCT FROM 'draft' THEN
            RAISE EXCEPTION 'Only a draft Delphi study can be opened'
                USING ERRCODE = '22023';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM public.delphi_item AS item
             WHERE item.study_id = requested_study_id
        ) THEN
            RAISE EXCEPTION 'A Delphi study requires at least one question before opening'
                USING ERRCODE = '22023';
        END IF;
        IF pg_catalog.jsonb_typeof(study_record.stopping_criteria) IS DISTINCT FROM 'object'
           OR pg_catalog.jsonb_typeof(study_record.stopping_criteria -> 'min_participants')
                IS DISTINCT FROM 'number' THEN
            RAISE EXCEPTION 'Delphi study minimum-participant criteria are invalid'
                USING ERRCODE = '22023';
        END IF;
        required_participants :=
            (study_record.stopping_criteria ->> 'min_participants')::INTEGER;
        SELECT pg_catalog.count(*)
          INTO consented_count
          FROM public.delphi_panel_member AS member
         WHERE member.study_id = requested_study_id
           AND member.consent_status = 'granted';
        IF required_participants < 3 OR consented_count < required_participants THEN
            RAISE EXCEPTION 'The consented Delphi panel does not meet minimum participation'
                USING ERRCODE = '22023';
        END IF;
        UPDATE public.delphi_study AS study
           SET status = 'open', opened_at = pg_catalog.clock_timestamp(),
               updated_at = pg_catalog.clock_timestamp()
         WHERE study.id = requested_study_id
         RETURNING study.status, study.opened_at, study.closed_at
              INTO changed_status, changed_opened_at, changed_closed_at;
    ELSE
        IF study_record.status IS DISTINCT FROM 'open'
           OR study_record.opened_at IS NULL
           OR study_record.closed_at IS NOT NULL THEN
            RAISE EXCEPTION 'Only an open Delphi study can be closed'
                USING ERRCODE = '22023';
        END IF;
        UPDATE public.delphi_study AS study
           SET status = 'closed', closed_at = pg_catalog.clock_timestamp(),
               updated_at = pg_catalog.clock_timestamp()
         WHERE study.id = requested_study_id
         RETURNING study.status, study.opened_at, study.closed_at
              INTO changed_status, changed_opened_at, changed_closed_at;
    END IF;

    INSERT INTO kokonut_security.delphi_study_lifecycle_request (
        operator_id, request_id, location_id, study_id, action, result_status,
        result_opened_at, result_closed_at, payload_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_study_id, requested_action, changed_status,
        changed_opened_at, changed_closed_at, payload_digest
    );

    study_id := requested_study_id;
    location_id := requested_location_id;
    status := changed_status;
    opened_at := changed_opened_at;
    closed_at := changed_closed_at;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.transition_location_delphi_study(UUID, UUID, TEXT, UUID)
    OWNER TO kokonut_delphi_study_lifecycle;
REVOKE ALL ON FUNCTION kokonut_security.transition_location_delphi_study(UUID, UUID, TEXT, UUID)
    FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.transition_location_delphi_study(
            UUID, UUID, TEXT, UUID
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.transition_location_delphi_study(
            UUID, UUID, TEXT, UUID
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.transition_location_delphi_study(UUID, UUID, TEXT, UUID)
IS 'Opens a prepared Delphi study only after its consented panel meets the configured participation minimum, or closes an open study, under an exact signed location grant with immutable idempotency receipts.';
COMMENT ON TABLE kokonut_security.delphi_study_lifecycle_request
IS 'Private append-only request receipts for authenticated location-scoped Delphi study opening and closure.';

COMMIT;
