-- Bounded, location-scoped Delphi consultation read model.
-- Participant identity, raw reasoning, facilitator drafts, and minority reports
-- remain outside this projection.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_consultation_reader'
    ) THEN
        CREATE ROLE kokonut_delphi_consultation_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_consultation_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Delphi consultation reader role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_delphi_consultation_reader'
            OR member_role.rolname = 'kokonut_delphi_consultation_reader'
    ) THEN
        RAISE EXCEPTION 'Delphi consultation reader role must not have memberships';
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_delphi_consultation_reader;
GRANT SELECT ON TABLE public.delphi_study, public.delphi_item,
    public.delphi_contribution, public.delphi_panel_member,
    public.operator_scope_grant
    TO kokonut_delphi_consultation_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_delphi_consultation_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_delphi_consultation_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_delphi_consultations(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 51,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    study_id UUID,
    title TEXT,
    description TEXT,
    variation TEXT,
    status TEXT,
    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    items JSONB
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Delphi consultation read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi consultation read requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Delphi consultation page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    WITH scoped_studies AS (
        SELECT study.id,
               study.title,
               study.description,
               study.variation,
               study.status,
               study.opened_at,
               study.closed_at,
               study.created_at,
               study.updated_at,
               GREATEST(
                   3,
                   CASE
                       WHEN jsonb_typeof(study.stopping_criteria -> 'min_participants') = 'number'
                       THEN ceil((study.stopping_criteria ->> 'min_participants')::NUMERIC)
                       ELSE 3
                   END
               ) AS privacy_floor,
               GREATEST(
                   0,
                   CASE
                       WHEN jsonb_typeof(study.stopping_criteria -> 'iqr_threshold') = 'number'
                       THEN (study.stopping_criteria ->> 'iqr_threshold')::NUMERIC
                       ELSE 1.0
                   END
               ) AS iqr_threshold
          FROM public.delphi_study AS study
         WHERE study.location_id = requested_location_id
         ORDER BY study.updated_at DESC NULLS LAST, study.id DESC
         LIMIT requested_limit
        OFFSET requested_offset
    )
    SELECT study.id,
           study.title::TEXT,
           study.description::TEXT,
           study.variation::TEXT,
           study.status::TEXT,
           study.opened_at,
           study.closed_at,
           study.created_at,
           COALESCE(
               (
                   SELECT jsonb_agg(
                       jsonb_build_object(
                           'item_id', item.id,
                           'label', item.label,
                           'description', item.description,
                           'item_type', item.item_type,
                           'scale', item.scale,
                           'minimum', item.min_value,
                           'maximum', item.max_value,
                           'results_available', stats.consented_participant_count >= study.privacy_floor,
                           'participant_count', CASE
                               WHEN stats.consented_participant_count >= study.privacy_floor
                               THEN stats.consented_participant_count
                               ELSE NULL
                           END,
                           'median', CASE
                               WHEN stats.consented_participant_count >= study.privacy_floor
                               THEN stats.median_value ELSE NULL
                           END,
                           'mean', CASE
                               WHEN stats.consented_participant_count >= study.privacy_floor
                               THEN stats.mean_value ELSE NULL
                           END,
                           'interquartile_range', CASE
                               WHEN stats.consented_participant_count >= study.privacy_floor
                               THEN stats.interquartile_range ELSE NULL
                           END,
                           'standard_deviation', CASE
                               WHEN stats.consented_participant_count >= study.privacy_floor
                               THEN stats.standard_deviation ELSE NULL
                           END,
                           'weighted_median', CASE
                               WHEN stats.consented_participant_count >= study.privacy_floor
                               THEN stats.weighted_median_value ELSE NULL
                           END,
                           'coefficient_of_variation', CASE
                               WHEN stats.consented_participant_count >= study.privacy_floor
                                    AND abs(stats.mean_value) >= 0.000000001
                               THEN round(
                                   (stats.standard_deviation / abs(stats.mean_value))::NUMERIC,
                                   4
                               )
                               ELSE NULL
                           END,
                           'consensus_reached', CASE
                               WHEN stats.consented_participant_count >= study.privacy_floor
                               THEN round(stats.interquartile_range::NUMERIC, 4)
                                    <= study.iqr_threshold
                               ELSE NULL
                           END,
                           'computed_at', stats.computed_at
                       ) ORDER BY item.created_at, item.id
                   )
                     FROM public.delphi_item AS item
                     LEFT JOIN LATERAL (
                         WITH eligible AS (
                             SELECT member.id AS member_id,
                                    contribution.score::DOUBLE PRECISION AS score,
                                    coalesce(member.expert_weight, 0)::DOUBLE PRECISION AS weight,
                                    contribution.updated_at
                               FROM public.delphi_contribution AS contribution
                               JOIN public.delphi_panel_member AS member
                                 ON member.id = contribution.panel_member_id
                                AND member.study_id = study.id
                                AND member.consent_status = 'granted'
                              WHERE contribution.item_id = item.id
                                AND contribution.study_id = study.id
                         ),
                         weighted AS (
                             SELECT score,
                                    sum(weight) OVER (
                                        ORDER BY score ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                                    ) AS cumulative_weight,
                                    sum(weight) OVER () AS total_weight
                               FROM eligible
                         )
                         SELECT count(DISTINCT eligible.member_id)::INTEGER AS consented_participant_count,
                                percentile_cont(0.5) WITHIN GROUP (
                                    ORDER BY eligible.score
                                ) AS median_value,
                                avg(eligible.score) AS mean_value,
                                percentile_cont(0.75) WITHIN GROUP (
                                    ORDER BY eligible.score
                                ) - percentile_cont(0.25) WITHIN GROUP (
                                    ORDER BY eligible.score
                                ) AS interquartile_range,
                                stddev_pop(eligible.score) AS standard_deviation,
                                (
                                    SELECT CASE
                                        WHEN coalesce(max(weighted.total_weight), 0) <= 0
                                        THEN percentile_cont(0.5) WITHIN GROUP (
                                            ORDER BY weighted.score
                                        )
                                        ELSE (
                                            SELECT selected.score
                                              FROM weighted AS selected
                                             WHERE selected.cumulative_weight
                                                   >= selected.total_weight / 2.0
                                             ORDER BY selected.score
                                             LIMIT 1
                                        )
                                    END
                                      FROM weighted
                                ) AS weighted_median_value,
                                max(eligible.updated_at) AS computed_at
                           FROM eligible
                     ) AS stats ON TRUE
                    WHERE item.study_id = study.id
               ),
               '[]'::JSONB
           ) AS items
      FROM scoped_studies AS study
     ORDER BY study.updated_at DESC NULLS LAST, study.id DESC;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_delphi_consultation_reader;
ALTER FUNCTION kokonut_security.list_location_delphi_consultations(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_delphi_consultation_reader;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_delphi_consultation_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_consultations(UUID, INTEGER, INTEGER)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_delphi_consultations(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_consultations(UUID, INTEGER, INTEGER)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_delphi_consultations(UUID, INTEGER, INTEGER) IS
    'Returns location-authorized Delphi study metadata and score aggregates from currently consenting participants only. Statistics and participant counts are suppressed below max(3, configured minimum); participant identity, display tokens, raw reasoning, metadata, recommendations, and minority reports are excluded.';

COMMIT;
