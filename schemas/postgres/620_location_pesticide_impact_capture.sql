-- Add tenant-authorized, recorded-only pesticide-impact reporting.
-- Capture records what an operator reports; it does not authorize pesticide use.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_pesticide_impact_writer'
    ) THEN
        CREATE ROLE kokonut_pesticide_impact_writer;
    END IF;
END;
$$;

ALTER ROLE kokonut_pesticide_impact_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

ALTER TABLE public.pesticide_impact_log
    ADD COLUMN IF NOT EXISTS created_by_operator_id UUID
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_pesticide_impact_creator
    ON public.pesticide_impact_log (created_by_operator_id, created_at DESC)
    WHERE created_by_operator_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.pesticide_impact_capture_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    record_id UUID NOT NULL UNIQUE
        REFERENCES public.pesticide_impact_log(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

DO $$
DECLARE
    column_name TEXT;
    role_name TEXT;
    role_sql TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'PUBLIC', 'kokonut_runtime', 'kokonut_directus_runtime'
    ] LOOP
        IF role_name = 'PUBLIC'
           OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            role_sql := CASE
                WHEN role_name = 'PUBLIC' THEN 'PUBLIC'
                ELSE pg_catalog.quote_ident(role_name)
            END;
            EXECUTE pg_catalog.format(
                'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
                'ON TABLE public.pesticide_impact_log FROM %s', role_sql
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.pesticide_impact_log'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%1$I) ON TABLE public.pesticide_impact_log FROM %2$s',
                    column_name, role_sql
                );
                EXECUTE pg_catalog.format(
                    'REVOKE UPDATE (%1$I) ON TABLE public.pesticide_impact_log FROM %2$s',
                    column_name, role_sql
                );
                EXECUTE pg_catalog.format(
                    'REVOKE REFERENCES (%1$I) ON TABLE public.pesticide_impact_log FROM %2$s',
                    column_name, role_sql
                );
            END LOOP;
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.pesticide_impact_capture_receipt FROM %s',
                role_sql
            );
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_pesticide_impact_writer;
GRANT INSERT (
    id, location_id, application_date, product_name, active_ingredient,
    toxicity_class, application_rate, rate_unit, area_treated_m2,
    bloom_stage_at_application, pollinator_distance_m,
    pollinator_safe_period_days, pollinator_mortality_observed,
    mortality_pct, notes, status, created_by_operator_id
) ON TABLE public.pesticide_impact_log TO kokonut_pesticide_impact_writer;
GRANT SELECT (
    operator_id, request_id, location_id, record_id, input_digest, created_at
) ON TABLE public.pesticide_impact_capture_receipt TO kokonut_pesticide_impact_writer;
GRANT INSERT (
    operator_id, request_id, location_id, record_id, input_digest
) ON TABLE public.pesticide_impact_capture_receipt TO kokonut_pesticide_impact_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_pesticide_impact_writer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_pesticide_impact_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_pesticide_impact_writer;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_pesticide_impact(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_application_date DATE,
    requested_product_name TEXT,
    requested_active_ingredient TEXT,
    requested_toxicity_class TEXT,
    requested_application_rate NUMERIC,
    requested_rate_unit TEXT,
    requested_area_treated_m2 NUMERIC,
    requested_bloom_stage TEXT,
    requested_pollinator_distance_m NUMERIC,
    requested_safe_period_days INTEGER,
    requested_mortality_observed BOOLEAN,
    requested_mortality_pct NUMERIC,
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
    normalized_product TEXT := NULLIF(pg_catalog.btrim(requested_product_name), '');
    normalized_ingredient TEXT := NULLIF(pg_catalog.btrim(requested_active_ingredient), '');
    normalized_rate_unit TEXT := NULLIF(pg_catalog.btrim(requested_rate_unit), '');
    normalized_bloom_stage TEXT := NULLIF(pg_catalog.btrim(requested_bloom_stage), '');
    normalized_notes TEXT := NULLIF(pg_catalog.btrim(requested_notes), '');
    input_digest BYTEA;
    existing_receipt RECORD;
    record_uuid UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Pesticide capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'pollinator_health', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Pesticide capture requires an exact location create grant'
            USING ERRCODE = '42501';
    END IF;

    IF requested_application_date IS NULL OR requested_application_date > CURRENT_DATE
       OR requested_toxicity_class IS NULL OR requested_toxicity_class NOT IN (
           'low', 'moderate', 'high', 'very_high'
       )
       OR requested_mortality_observed IS NULL
       OR normalized_product IS NOT NULL
          AND (pg_catalog.char_length(normalized_product) > 200
               OR requested_product_name ~ '[[:cntrl:]]')
       OR normalized_ingredient IS NOT NULL
          AND (pg_catalog.char_length(normalized_ingredient) > 200
               OR requested_active_ingredient ~ '[[:cntrl:]]')
       OR normalized_rate_unit IS NOT NULL
          AND (pg_catalog.char_length(normalized_rate_unit) > 32
               OR requested_rate_unit ~ '[[:cntrl:]]')
       OR normalized_bloom_stage IS NOT NULL
          AND (pg_catalog.char_length(normalized_bloom_stage) > 100
               OR requested_bloom_stage ~ '[[:cntrl:]]')
       OR normalized_notes IS NOT NULL
          AND (pg_catalog.char_length(normalized_notes) > 2000
               OR requested_notes ~ '[[:cntrl:]]')
       OR requested_application_rate IS NOT NULL
          AND (requested_application_rate < 0 OR requested_application_rate > 99999999)
       OR requested_application_rate IS NULL AND normalized_rate_unit IS NOT NULL
       OR requested_area_treated_m2 IS NOT NULL
          AND (requested_area_treated_m2 < 0 OR requested_area_treated_m2 > 9999999999)
       OR requested_pollinator_distance_m IS NOT NULL
          AND (requested_pollinator_distance_m < 0 OR requested_pollinator_distance_m > 99999999)
       OR requested_safe_period_days IS NOT NULL
          AND (requested_safe_period_days < 0 OR requested_safe_period_days > 36500)
       OR requested_mortality_pct IS NOT NULL
          AND (requested_mortality_pct < 0 OR requested_mortality_pct > 100) THEN
        RAISE EXCEPTION 'Pesticide report input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT,
                requested_application_date,
                normalized_product,
                normalized_ingredient,
                requested_toxicity_class,
                requested_application_rate,
                normalized_rate_unit,
                requested_area_treated_m2,
                normalized_bloom_stage,
                requested_pollinator_distance_m,
                requested_safe_period_days,
                requested_mortality_observed,
                requested_mortality_pct,
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
    SELECT receipt.location_id, receipt.record_id, receipt.input_digest
      INTO existing_receipt
      FROM public.pesticide_impact_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.input_digest IS DISTINCT FROM input_digest
           OR existing_receipt.location_id IS DISTINCT FROM requested_location_id THEN
            RAISE EXCEPTION 'Pesticide request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'record_id', existing_receipt.record_id,
            'location_id', requested_location_id,
            'toxicity_class', requested_toxicity_class,
            'application_date', requested_application_date,
            'status', 'recorded',
            'replayed', TRUE
        );
    END IF;

    record_uuid := pg_catalog.gen_random_uuid();
    INSERT INTO public.pesticide_impact_log (
        id, location_id, application_date, product_name, active_ingredient,
        toxicity_class, application_rate, rate_unit, area_treated_m2,
        bloom_stage_at_application, pollinator_distance_m,
        pollinator_safe_period_days, pollinator_mortality_observed,
        mortality_pct, notes, status, created_by_operator_id
    ) VALUES (
        record_uuid, requested_location_id, requested_application_date,
        normalized_product, normalized_ingredient, requested_toxicity_class,
        requested_application_rate, normalized_rate_unit,
        requested_area_treated_m2, normalized_bloom_stage,
        requested_pollinator_distance_m, requested_safe_period_days,
        requested_mortality_observed, requested_mortality_pct,
        normalized_notes, 'recorded', context_record.actor_id
    );
    INSERT INTO public.pesticide_impact_capture_receipt (
        operator_id, request_id, location_id, record_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        record_uuid, input_digest
    );
    RETURN pg_catalog.jsonb_build_object(
        'record_id', record_uuid,
        'location_id', requested_location_id,
        'toxicity_class', requested_toxicity_class,
        'application_date', requested_application_date,
        'status', 'recorded',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_pesticide_impact(
    UUID, UUID, DATE, TEXT, TEXT, TEXT, NUMERIC, TEXT, NUMERIC, TEXT,
    NUMERIC, INTEGER, BOOLEAN, NUMERIC, TEXT
) OWNER TO kokonut_pesticide_impact_writer;
REVOKE ALL ON FUNCTION kokonut_security.create_location_pesticide_impact(
    UUID, UUID, DATE, TEXT, TEXT, TEXT, NUMERIC, TEXT, NUMERIC, TEXT,
    NUMERIC, INTEGER, BOOLEAN, NUMERIC, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION kokonut_security.create_location_pesticide_impact('
            'UUID, UUID, DATE, TEXT, TEXT, TEXT, NUMERIC, TEXT, NUMERIC, TEXT, '
            'NUMERIC, INTEGER, BOOLEAN, NUMERIC, TEXT) TO kokonut_runtime';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        EXECUTE 'REVOKE ALL ON FUNCTION kokonut_security.create_location_pesticide_impact('
            'UUID, UUID, DATE, TEXT, TEXT, TEXT, NUMERIC, TEXT, NUMERIC, TEXT, '
            'NUMERIC, INTEGER, BOOLEAN, NUMERIC, TEXT) FROM kokonut_directus_runtime';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_pesticide_impact(
    UUID, UUID, DATE, TEXT, TEXT, TEXT, NUMERIC, TEXT, NUMERIC, TEXT,
    NUMERIC, INTEGER, BOOLEAN, NUMERIC, TEXT
) IS 'Records a location-scoped pesticide application report after signed exact-location create authorization; it remains recorded until independent review and never authorizes pesticide use.';

COMMIT;
