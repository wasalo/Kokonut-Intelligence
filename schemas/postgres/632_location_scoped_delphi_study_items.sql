-- Add questionnaire items only to exact-location Delphi study drafts.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_item_drafter'
    ) THEN
        CREATE ROLE kokonut_delphi_item_drafter
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_item_drafter'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Delphi item drafter role must remain non-login and non-inheriting';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_study_item_request (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    item_id UUID NOT NULL UNIQUE REFERENCES public.delphi_item(id) ON DELETE RESTRICT,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_study_item_request_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi study item request history is append-only';
    RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_study_item_request_mutation()
    FROM PUBLIC;
DROP TRIGGER IF EXISTS trg_delphi_study_item_request_immutable
    ON kokonut_security.delphi_study_item_request;
CREATE TRIGGER trg_delphi_study_item_request_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_study_item_request
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_study_item_request_mutation();

ALTER TABLE kokonut_security.delphi_study_item_request
    OWNER TO kokonut_delphi_item_drafter;
REVOKE ALL ON TABLE kokonut_security.delphi_study_item_request FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE kokonut_security.delphi_study_item_request
    TO kokonut_delphi_item_drafter;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_delphi_item_drafter;
GRANT SELECT ON TABLE public.operator_scope_grant, public.operator_identity,
    public.location, public.operator_organization_membership,
    public.location_tenant_owner_verification, public.location_organization_share,
    public.organization
    TO kokonut_delphi_item_drafter;
REVOKE ALL ON TABLE public.delphi_study, public.delphi_item
    FROM kokonut_delphi_item_drafter;
GRANT SELECT (id, location_id, status)
    ON TABLE public.delphi_study TO kokonut_delphi_item_drafter;
GRANT UPDATE (id) ON TABLE public.delphi_study TO kokonut_delphi_item_drafter;
GRANT SELECT (id, study_id, item_type, label, description, scale, min_value,
              max_value, created_at)
    ON TABLE public.delphi_item TO kokonut_delphi_item_drafter;
GRANT INSERT (id, study_id, item_type, label, description, scale, min_value,
              max_value, created_at)
    ON TABLE public.delphi_item TO kokonut_delphi_item_drafter;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_delphi_item_drafter;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_delphi_item_drafter;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_delphi_item_drafter;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_study_item_request
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_study_item_request
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_delphi_study_item(
    requested_location_id UUID,
    requested_study_id UUID,
    requested_item_type TEXT,
    requested_label TEXT,
    requested_description TEXT,
    requested_scale TEXT,
    requested_min_value NUMERIC,
    requested_max_value NUMERIC,
    requested_request_id UUID
)
RETURNS TABLE (
    item_id UUID,
    study_id UUID,
    location_id UUID,
    item_type TEXT,
    label TEXT,
    description TEXT,
    scale TEXT,
    min_value NUMERIC,
    max_value NUMERIC,
    created_at TIMESTAMPTZ,
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
    normalized_label TEXT;
    normalized_description TEXT;
    normalized_min NUMERIC;
    normalized_max NUMERIC;
    request_digest BYTEA;
    created_item_id UUID;
    created_at_value TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_study_id IS NULL THEN
        RAISE EXCEPTION 'Delphi item draft requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'draft', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi item draft requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_request_id IS NULL
       OR requested_item_type IS NULL
       OR requested_item_type NOT IN ('issue', 'goal', 'option')
       OR requested_scale IS NULL
       OR requested_scale NOT IN (
           'desirability', 'feasibility_technical',
           'feasibility_political', 'probability'
       ) THEN
        RAISE EXCEPTION 'Delphi item draft type, scale, or request id is invalid'
            USING ERRCODE = '22023';
    END IF;

    normalized_label := pg_catalog.btrim(requested_label);
    normalized_description := NULLIF(pg_catalog.btrim(requested_description), '');
    IF normalized_label IS NULL
       OR pg_catalog.length(normalized_label) NOT BETWEEN 1 AND 255
       OR (normalized_description IS NOT NULL
           AND pg_catalog.length(normalized_description) > 4000)
       OR requested_min_value IS NULL
       OR requested_max_value IS NULL
       OR requested_min_value >= requested_max_value
       OR requested_min_value < -9999.9999
       OR requested_max_value > 9999.9999
       OR pg_catalog.round(requested_min_value, 4) <> requested_min_value
       OR pg_catalog.round(requested_max_value, 4) <> requested_max_value THEN
        RAISE EXCEPTION 'Delphi item draft fields are invalid'
            USING ERRCODE = '22023';
    END IF;
    normalized_min := requested_min_value;
    normalized_max := requested_max_value;

    request_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'study_id', requested_study_id,
                'item_type', requested_item_type,
                'label', normalized_label,
                'description', normalized_description,
                'scale', requested_scale,
                'min_value', normalized_min,
                'max_value', normalized_max
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

    SELECT request.location_id, request.study_id, request.payload_digest,
           item.id, item.item_type, item.label, item.description, item.scale,
           item.min_value, item.max_value, item.created_at
      INTO prior_record
      FROM kokonut_security.delphi_study_item_request AS request
      JOIN public.delphi_item AS item ON item.id = request.item_id
     WHERE request.operator_id = context_record.actor_id
       AND request.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_record.location_id IS DISTINCT FROM requested_location_id
           OR prior_record.study_id IS DISTINCT FROM requested_study_id
           OR prior_record.payload_digest IS DISTINCT FROM request_digest THEN
            RAISE EXCEPTION 'Delphi study item request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        item_id := prior_record.id;
        study_id := prior_record.study_id;
        location_id := prior_record.location_id;
        item_type := prior_record.item_type;
        label := prior_record.label;
        description := prior_record.description;
        scale := prior_record.scale;
        min_value := prior_record.min_value;
        max_value := prior_record.max_value;
        created_at := prior_record.created_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT study.id, study.location_id, study.status
      INTO study_record
      FROM public.delphi_study AS study
     WHERE study.id = requested_study_id
       AND study.location_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi study is unavailable for this location'
            USING ERRCODE = '22023';
    END IF;
    IF study_record.status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'Delphi questions can only be added to a draft study'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.delphi_item AS created_item (
        id, study_id, item_type, label, description, scale, min_value, max_value,
        created_at
    ) VALUES (
        pg_catalog.gen_random_uuid(), requested_study_id, requested_item_type,
        normalized_label, normalized_description, requested_scale,
        normalized_min, normalized_max, pg_catalog.clock_timestamp()
    )
    RETURNING created_item.id, created_item.created_at
         INTO created_item_id, created_at_value;
    INSERT INTO kokonut_security.delphi_study_item_request (
        operator_id, request_id, location_id, study_id, item_id, payload_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_study_id, created_item_id, request_digest
    );

    item_id := created_item_id;
    study_id := requested_study_id;
    location_id := requested_location_id;
    item_type := requested_item_type;
    label := normalized_label;
    description := normalized_description;
    scale := requested_scale;
    min_value := normalized_min;
    max_value := normalized_max;
    created_at := created_at_value;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.create_location_delphi_study_item(
    UUID, UUID, TEXT, TEXT, TEXT, TEXT, NUMERIC, NUMERIC, UUID
) OWNER TO kokonut_delphi_item_drafter;
REVOKE ALL ON FUNCTION kokonut_security.create_location_delphi_study_item(
    UUID, UUID, TEXT, TEXT, TEXT, TEXT, NUMERIC, NUMERIC, UUID
) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.create_location_delphi_study_item(
            UUID, UUID, TEXT, TEXT, TEXT, TEXT, NUMERIC, NUMERIC, UUID
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_location_delphi_study_item(
            UUID, UUID, TEXT, TEXT, TEXT, TEXT, NUMERIC, NUMERIC, UUID
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_delphi_study_item(
    UUID, UUID, TEXT, TEXT, TEXT, TEXT, NUMERIC, NUMERIC, UUID
) IS 'Creates or replays a bounded questionnaire item for an exact-location Delphi draft under a signed delphi:draft grant.';
COMMENT ON TABLE kokonut_security.delphi_study_item_request IS
    'Private append-only request receipts for location-scoped Delphi questionnaire item creation.';

COMMIT;
