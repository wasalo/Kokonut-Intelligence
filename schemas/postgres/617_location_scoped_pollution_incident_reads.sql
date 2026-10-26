-- Move pollution-incident reads behind exact-grant, signed-context functions.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_incident_review_reader'
    ) THEN
        CREATE ROLE kokonut_incident_review_reader;
    END IF;
END;
$$;

ALTER ROLE kokonut_incident_review_reader
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_incident_review_reader;
GRANT SELECT (
    id, location_id, incident_date, incident_type, severity, description,
    affected_area, status, resolved, created_at
) ON TABLE public.pollution_incident
    TO kokonut_incident_review_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_incident_review_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_incident_review_reader;

DO $$
DECLARE
    column_name TEXT;
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'PUBLIC', 'kokonut_runtime', 'kokonut_directus_runtime'
    ] LOOP
        IF role_name = 'PUBLIC'
           OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE pg_catalog.format(
                'REVOKE SELECT ON TABLE public.pollution_incident FROM %s',
                CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.pollution_incident'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE SELECT (%1$I) ON TABLE public.pollution_incident FROM %2$s',
                    column_name,
                    CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON TABLE public.v_pollution_incidents FROM PUBLIC;
DO $$
DECLARE role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.v_pollution_incidents FROM %I', role_name
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_pollution_incident_review_queue(
    requested_location_id UUID,
    requested_offset INTEGER
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Pollution incident review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'waste_management', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Pollution incident review requires an exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 1000000 THEN
        RAISE EXCEPTION 'Pollution incident review offset is outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    WITH page AS MATERIALIZED (
        SELECT incident.id, incident.incident_date, incident.incident_type,
               incident.severity, incident.description, incident.affected_area,
               incident.status, incident.created_at
          FROM public.pollution_incident AS incident
         WHERE incident.location_id = requested_location_id
           AND incident.status IN ('open', 'investigating', 'remediation')
         ORDER BY CASE incident.severity
                      WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                      WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5
                  END,
                  incident.incident_date DESC, incident.created_at DESC,
                  incident.id DESC
         LIMIT 101 OFFSET requested_offset
    ), ranked AS (
        SELECT page.*,
               pg_catalog.row_number() OVER (
                   ORDER BY CASE page.severity
                                WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                                WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5
                            END,
                            page.incident_date DESC, page.created_at DESC,
                            page.id DESC
               ) AS page_ordinal
          FROM page
    ), projected AS (
        SELECT coalesce(
                   pg_catalog.jsonb_agg(
                       pg_catalog.jsonb_build_object(
                           'incident_id', ranked.id::TEXT,
                           'incident_date', ranked.incident_date::TEXT,
                           'incident_type', ranked.incident_type,
                           'severity', ranked.severity,
                           'description', ranked.description,
                           'affected_area', ranked.affected_area,
                           'status', ranked.status
                       ) ORDER BY ranked.page_ordinal
                   ) FILTER (WHERE ranked.page_ordinal <= 100),
                   '[]'::JSONB
               ) AS incidents,
               pg_catalog.count(*) > 100 AS has_more
          FROM ranked
    )
    SELECT pg_catalog.jsonb_build_object(
               'location_id', requested_location_id::TEXT,
               'offset', requested_offset,
               'incidents', projected.incidents,
               'has_more', projected.has_more
           )
      INTO result
      FROM projected;
    RETURN result;
END;
$$;

ALTER FUNCTION kokonut_security.list_location_pollution_incident_review_queue(
    UUID, INTEGER
) OWNER TO kokonut_incident_review_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_pollution_incident_review_queue(
    UUID, INTEGER
) FROM PUBLIC;

CREATE OR REPLACE FUNCTION kokonut_security.summarize_location_pollution_incidents(
    requested_location_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Pollution incident summary requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'waste_management', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Pollution incident summary requires an exact location read grant'
            USING ERRCODE = '42501';
    END IF;

    SELECT coalesce(
               pg_catalog.jsonb_agg(
                   pg_catalog.jsonb_build_object(
                       'severity', grouped.severity,
                       'status', grouped.status,
                       'record_count', grouped.record_count,
                       'first_date', grouped.first_date,
                       'last_date', grouped.last_date
                   ) ORDER BY grouped.severity, grouped.status
               ),
               '[]'::JSONB
           )
      INTO result
      FROM (
          SELECT incident.severity, incident.status,
                 pg_catalog.count(*)::BIGINT AS record_count,
                 pg_catalog.min(incident.incident_date) AS first_date,
                 pg_catalog.max(incident.incident_date) AS last_date
            FROM public.pollution_incident AS incident
           WHERE incident.location_id = requested_location_id
             AND incident.status IN ('open', 'investigating', 'remediation', 'resolved', 'closed')
           GROUP BY incident.severity, incident.status
      ) AS grouped;
    RETURN result;
END;
$$;

ALTER FUNCTION kokonut_security.summarize_location_pollution_incidents(UUID)
    OWNER TO kokonut_incident_review_reader;
REVOKE ALL ON FUNCTION kokonut_security.summarize_location_pollution_incidents(UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_pollution_incident_review_queue(
            UUID, INTEGER
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.summarize_location_pollution_incidents(
            UUID
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_pollution_incident_review_queue(
            UUID, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.summarize_location_pollution_incidents(
            UUID
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_pollution_incident_review_queue(UUID, INTEGER)
    IS 'Returns a bounded location-only pollution incident narrative queue after validating signed operator context and the exact review grant.';
COMMENT ON FUNCTION kokonut_security.summarize_location_pollution_incidents(UUID)
    IS 'Returns aggregate severity/status/date counts after validating signed operator context and the exact read grant.';

COMMIT;
