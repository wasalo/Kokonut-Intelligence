-- Preserve supported environmental-baseline capture through a signed,
-- location-scoped Gateway function, then remove direct shared-runtime DML.
-- The historical pilot seed continues under the database-owner identity.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_environmental_baseline_capture_owner'
    ) THEN
        CREATE ROLE kokonut_environmental_baseline_capture_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_environmental_baseline_capture_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_environmental_baseline_capture_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role
            ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role
            ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_environmental_baseline_capture_owner'
            OR member_role.rolname = 'kokonut_environmental_baseline_capture_owner'
    ) THEN
        RAISE EXCEPTION 'kokonut_environmental_baseline_capture_owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_environmental_baseline_capture_owner;
GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_environmental_baseline_capture_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_environmental_baseline_capture_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_environmental_baseline_capture_owner;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_environmental_baseline_capture_owner;
GRANT SELECT (id, farm_id) ON TABLE public.plot
    TO kokonut_environmental_baseline_capture_owner;
GRANT SELECT (id, location_id) ON TABLE public.farm
    TO kokonut_environmental_baseline_capture_owner;
GRANT INSERT (
    id, location_id, plot_id, metric_name, baseline_value, unit,
    measurement_date, measurement_method, source, evidence_urls, notes, created_by
) ON TABLE public.environmental_baseline
    TO kokonut_environmental_baseline_capture_owner;

CREATE TABLE IF NOT EXISTS kokonut_security.environmental_baseline_capture_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    baseline_id UUID NOT NULL UNIQUE
        REFERENCES public.environmental_baseline(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    response JSONB NOT NULL CHECK (pg_catalog.jsonb_typeof(response) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);
ALTER TABLE kokonut_security.environmental_baseline_capture_receipt
    OWNER TO kokonut_environmental_baseline_capture_owner;
ALTER TABLE kokonut_security.environmental_baseline_capture_receipt
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.environmental_baseline_capture_receipt
    FORCE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'kokonut_security'
           AND tablename = 'environmental_baseline_capture_receipt'
           AND policyname = 'environmental_baseline_capture_owner_scope'
    ) THEN
        CREATE POLICY environmental_baseline_capture_owner_scope
            ON kokonut_security.environmental_baseline_capture_receipt
            FOR ALL TO kokonut_environmental_baseline_capture_owner
            USING (
                operator_id = (
                    SELECT context.actor_id
                      FROM kokonut_security.current_tenant_context() AS context
                     WHERE context.actor_type = 'operator'
                )
                AND location_id = (
                    SELECT context.location_id
                      FROM kokonut_security.current_tenant_context() AS context
                     WHERE context.actor_type = 'operator'
                )
            )
            WITH CHECK (
                operator_id = (
                    SELECT context.actor_id
                      FROM kokonut_security.current_tenant_context() AS context
                     WHERE context.actor_type = 'operator'
                )
                AND location_id = (
                    SELECT context.location_id
                      FROM kokonut_security.current_tenant_context() AS context
                     WHERE context.actor_type = 'operator'
                )
            );
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'environmental_baseline'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public'
           AND tablename = 'environmental_baseline'
           AND policyname = 'environmental_baseline_capture_owner_insert'
    ) THEN
        CREATE POLICY environmental_baseline_capture_owner_insert
            ON public.environmental_baseline
            FOR INSERT TO kokonut_environmental_baseline_capture_owner
            WITH CHECK (location_id = (
                SELECT context.location_id
                  FROM kokonut_security.current_tenant_context() AS context
                 WHERE context.actor_type = 'operator'
            ));
    END IF;
END;
$$;

GRANT SELECT (
    operator_id, request_id, location_id, baseline_id, input_digest,
    response, created_at
) ON TABLE kokonut_security.environmental_baseline_capture_receipt
    TO kokonut_environmental_baseline_capture_owner;
GRANT INSERT (
    operator_id, request_id, location_id, baseline_id, input_digest, response
) ON TABLE kokonut_security.environmental_baseline_capture_receipt
    TO kokonut_environmental_baseline_capture_owner;
REVOKE ALL ON TABLE kokonut_security.environmental_baseline_capture_receipt
    FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.environmental_baseline_capture_receipt
            FROM kokonut_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.capture_location_environmental_baseline(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_plot_id UUID,
    requested_metric_name TEXT,
    requested_baseline_value NUMERIC,
    requested_unit TEXT,
    requested_measurement_date DATE,
    requested_measurement_method TEXT,
    requested_source TEXT,
    requested_evidence_urls TEXT[],
    requested_notes TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    normalized_metric_name TEXT := pg_catalog.lower(pg_catalog.btrim(requested_metric_name));
    normalized_unit TEXT := NULLIF(pg_catalog.btrim(requested_unit), '');
    normalized_method TEXT := NULLIF(pg_catalog.btrim(requested_measurement_method), '');
    normalized_source TEXT := NULLIF(pg_catalog.btrim(requested_source), '');
    normalized_notes TEXT := NULLIF(pg_catalog.btrim(requested_notes), '');
    normalized_evidence_urls TEXT[] := coalesce(requested_evidence_urls, ARRAY[]::TEXT[]);
    input_digest BYTEA;
    existing_receipt RECORD;
    baseline_uuid UUID;
    response_value JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Environmental baseline capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id,
        'environmental_baseline',
        'create',
        requested_location_id
    ) THEN
        RAISE EXCEPTION 'Environmental baseline capture requires an exact location create grant'
            USING ERRCODE = '42501';
    END IF;

    IF requested_metric_name IS NULL
       OR normalized_metric_name !~ '^[a-z][a-z0-9_]{0,99}$'
       OR requested_baseline_value IS NULL
       OR pg_catalog.abs(requested_baseline_value) > 99999999.9999
       OR requested_baseline_value <> pg_catalog.trunc(requested_baseline_value, 4)
       OR normalized_unit IS NOT NULL
          AND (pg_catalog.char_length(normalized_unit) > 50
               OR requested_unit ~ '[[:cntrl:]]')
       OR requested_measurement_date IS NULL
       OR normalized_method IS NULL
       OR pg_catalog.char_length(normalized_method) > 100
       OR requested_measurement_method ~ '[[:cntrl:]]'
       OR requested_source IS NOT NULL
          AND (pg_catalog.char_length(normalized_source) > 255
               OR requested_source ~ '[[:cntrl:]]')
       OR requested_notes IS NOT NULL
          AND (pg_catalog.char_length(normalized_notes) > 2000
               OR requested_notes ~ '[[:cntrl:]]')
       OR pg_catalog.cardinality(normalized_evidence_urls) > 10
       OR EXISTS (
            SELECT 1
              FROM pg_catalog.unnest(normalized_evidence_urls) AS url_value(evidence_url)
             WHERE url_value.evidence_url IS NULL
                OR pg_catalog.char_length(url_value.evidence_url) > 2048
                OR url_value.evidence_url !~* '^https?://'
                OR url_value.evidence_url ~ '[[:space:][:cntrl:]]'
       ) THEN
        RAISE EXCEPTION 'Environmental baseline input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    IF requested_plot_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
          FROM public.plot AS plot_row
          JOIN public.farm AS farm_row ON farm_row.id = plot_row.farm_id
         WHERE plot_row.id = requested_plot_id
           AND farm_row.location_id = requested_location_id
    ) THEN
        RAISE EXCEPTION 'Environmental baseline plot must belong to the granted location'
            USING ERRCODE = '22023';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT,
                requested_plot_id::TEXT,
                normalized_metric_name,
                requested_baseline_value,
                normalized_unit,
                requested_measurement_date,
                normalized_method,
                normalized_source,
                normalized_evidence_urls,
                normalized_notes
            )::TEXT,
            'UTF8'
        ),
        'sha256'::TEXT
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT receipt.location_id, receipt.input_digest, receipt.response
      INTO existing_receipt
      FROM kokonut_security.environmental_baseline_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.input_digest IS DISTINCT FROM input_digest
           OR existing_receipt.location_id IS DISTINCT FROM requested_location_id THEN
            RAISE EXCEPTION 'Environmental baseline request ID was reused with different input'
                USING ERRCODE = 'P0001';
        END IF;
        RETURN existing_receipt.response || pg_catalog.jsonb_build_object('replayed', TRUE);
    END IF;

    baseline_uuid := pg_catalog.gen_random_uuid();
    INSERT INTO public.environmental_baseline (
        id, location_id, plot_id, metric_name, baseline_value, unit,
        measurement_date, measurement_method, source, evidence_urls, notes, created_by
    ) VALUES (
        baseline_uuid, requested_location_id, requested_plot_id,
        normalized_metric_name, requested_baseline_value, normalized_unit,
        requested_measurement_date, normalized_method, normalized_source,
        normalized_evidence_urls, normalized_notes, context_record.actor_id
    );

    response_value := pg_catalog.jsonb_build_object(
        'baseline_id', baseline_uuid,
        'location_id', requested_location_id,
        'plot_id', requested_plot_id,
        'metric_name', normalized_metric_name,
        'baseline_value', requested_baseline_value,
        'unit', normalized_unit,
        'measurement_date', requested_measurement_date,
        'measurement_method', normalized_method,
        'source', normalized_source,
        'status', 'recorded',
        'replayed', FALSE
    );
    INSERT INTO kokonut_security.environmental_baseline_capture_receipt (
        operator_id, request_id, location_id, baseline_id, input_digest, response
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        baseline_uuid, input_digest, response_value
    );
    RETURN response_value;
END;
$$;

ALTER FUNCTION kokonut_security.capture_location_environmental_baseline(
    UUID, UUID, UUID, TEXT, NUMERIC, TEXT, DATE, TEXT, TEXT, TEXT[], TEXT
) OWNER TO kokonut_environmental_baseline_capture_owner;
REVOKE ALL ON FUNCTION kokonut_security.capture_location_environmental_baseline(
    UUID, UUID, UUID, TEXT, NUMERIC, TEXT, DATE, TEXT, TEXT, TEXT[], TEXT
) FROM PUBLIC;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        IF pg_catalog.to_regclass('public.environmental_baseline') IS NULL THEN
            RAISE EXCEPTION 'required relation public.environmental_baseline is missing';
        END IF;
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
            ON TABLE public.environmental_baseline FROM kokonut_runtime;
        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = 'public.environmental_baseline'::REGCLASS
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.environmental_baseline FROM kokonut_runtime',
                column_name
            );
        END LOOP;
        GRANT SELECT ON TABLE public.environmental_baseline TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.capture_location_environmental_baseline(
            UUID, UUID, UUID, TEXT, NUMERIC, TEXT, DATE, TEXT, TEXT, TEXT[], TEXT
        ) TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.environmental_baseline IS
    'Environmental baselines are captured through a signed, location-scoped Gateway function. kokonut_runtime retains reporting SELECT; the legacy pilot seed runs through the database-owner maintenance identity.';
COMMENT ON FUNCTION kokonut_security.capture_location_environmental_baseline(
    UUID, UUID, UUID, TEXT, NUMERIC, TEXT, DATE, TEXT, TEXT, TEXT[], TEXT
) IS
    'Creates one bounded environmental baseline under signed exact-location operator scope; plot links must match the location, operator/request retries are idempotent, and all writes commit or roll back together.';

COMMIT;
