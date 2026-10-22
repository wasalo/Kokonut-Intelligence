-- Give the Delphi facilitator a signed, exact-location, consent-aware summary
-- projection. Individual display tokens and free-text contribution reasoning
-- are deliberately excluded from this agent read path.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_view_owner'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_reader'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_agent_summary_source_login'
    ) THEN
        RAISE EXCEPTION 'agent source-reader roles from migration 543 are required';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_class
         WHERE oid = pg_catalog.to_regclass('public.delphi_study')
           AND relkind IN ('r', 'p')
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_class
         WHERE oid = pg_catalog.to_regclass('public.delphi_item')
           AND relkind IN ('r', 'p')
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_class
         WHERE oid = pg_catalog.to_regclass('public.delphi_contribution')
           AND relkind IN ('r', 'p')
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_class
         WHERE oid = pg_catalog.to_regclass('public.delphi_panel_member')
           AND relkind IN ('r', 'p')
    ) THEN
        RAISE EXCEPTION 'Delphi source tables are required';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security, kokonut_agent_source
    TO kokonut_agent_summary_source_view_owner,
       kokonut_agent_summary_source_reader,
       kokonut_agent_summary_source_login;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_agent_summary_source_view_owner,
       kokonut_agent_summary_source_reader;
REVOKE ALL PRIVILEGES ON TABLE
    public.delphi_study,
    public.delphi_item,
    public.delphi_contribution,
    public.delphi_panel_member
FROM kokonut_agent_summary_source_view_owner,
     kokonut_agent_summary_source_reader,
     kokonut_agent_summary_source_login;
GRANT SELECT ON TABLE
    public.delphi_study,
    public.delphi_item,
    public.delphi_contribution,
    public.delphi_panel_member
TO kokonut_agent_summary_source_view_owner;

DROP POLICY IF EXISTS delphi_agent_source_read ON public.delphi_study;
CREATE POLICY delphi_agent_source_read ON public.delphi_study
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (
            SELECT 1
              FROM kokonut_security.current_worker_scope('delphi', 'read') AS scope
             WHERE scope.location_id = delphi_study.location_id
        )
    );

DROP POLICY IF EXISTS delphi_agent_source_read ON public.delphi_item;
CREATE POLICY delphi_agent_source_read ON public.delphi_item
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (
            SELECT 1
              FROM public.delphi_study AS study
              JOIN kokonut_security.current_worker_scope('delphi', 'read') AS scope
                ON scope.location_id = study.location_id
             WHERE study.id = delphi_item.study_id
        )
    );

DROP POLICY IF EXISTS delphi_agent_source_read ON public.delphi_contribution;
CREATE POLICY delphi_agent_source_read ON public.delphi_contribution
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (
            SELECT 1
              FROM public.delphi_study AS study
              JOIN kokonut_security.current_worker_scope('delphi', 'read') AS scope
                ON scope.location_id = study.location_id
             WHERE study.id = delphi_contribution.study_id
        )
    );

DROP POLICY IF EXISTS delphi_agent_source_read ON public.delphi_panel_member;
CREATE POLICY delphi_agent_source_read ON public.delphi_panel_member
    FOR SELECT TO kokonut_agent_summary_source_view_owner
    USING (
        EXISTS (
            SELECT 1
              FROM public.delphi_study AS study
              JOIN kokonut_security.current_worker_scope('delphi', 'read') AS scope
                ON scope.location_id = study.location_id
             WHERE study.id = delphi_panel_member.study_id
        )
    );

CREATE OR REPLACE VIEW kokonut_agent_source.delphi_live_summary
WITH (security_barrier = true) AS
WITH scoped_studies AS (
    SELECT study.id AS study_id,
           study.location_id,
           study.title,
           study.status,
           GREATEST(
               3,
               CASE
                   WHEN jsonb_typeof(study.stopping_criteria -> 'min_participants') = 'number'
                   THEN ceil((study.stopping_criteria ->> 'min_participants')::NUMERIC)::INTEGER
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
     WHERE EXISTS (
         SELECT 1
           FROM kokonut_security.current_worker_scope('delphi', 'read') AS scope
          WHERE scope.location_id = study.location_id
     )
), eligible AS (
    SELECT contribution.study_id,
           contribution.item_id,
           member.id AS member_id,
           contribution.score::DOUBLE PRECISION AS score,
           GREATEST(0, COALESCE(member.expert_weight, 0))::DOUBLE PRECISION AS weight,
           contribution.updated_at
      FROM public.delphi_contribution AS contribution
      JOIN scoped_studies AS study ON study.study_id = contribution.study_id
      JOIN public.delphi_panel_member AS member
        ON member.id = contribution.panel_member_id
       AND member.study_id = contribution.study_id
       AND member.consent_status = 'granted'
), weighted AS (
    SELECT eligible.item_id,
           eligible.score,
           SUM(eligible.weight) OVER (
               PARTITION BY eligible.item_id
               ORDER BY eligible.score, eligible.member_id
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           ) AS cumulative_weight,
           SUM(eligible.weight) OVER (PARTITION BY eligible.item_id) AS total_weight
      FROM eligible
), weighted_medians AS (
    SELECT DISTINCT ON (item_id) item_id, score AS weighted_median
      FROM weighted
     WHERE total_weight > 0
       AND cumulative_weight >= total_weight / 2.0
     ORDER BY item_id, score
), item_stats AS (
    SELECT item.study_id,
           item.id AS item_id,
           item.label,
           item.scale,
           item.item_type,
           COUNT(DISTINCT eligible.member_id)::INTEGER AS participant_count,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY eligible.score) AS median,
           AVG(eligible.score) AS mean,
           percentile_cont(0.75) WITHIN GROUP (ORDER BY eligible.score)
             - percentile_cont(0.25) WITHIN GROUP (ORDER BY eligible.score) AS iqr,
           stddev_pop(eligible.score) AS standard_deviation,
           MAX(eligible.updated_at) AS computed_at
      FROM public.delphi_item AS item
      JOIN scoped_studies AS study ON study.study_id = item.study_id
      LEFT JOIN eligible
        ON eligible.study_id = item.study_id
       AND eligible.item_id = item.id
     GROUP BY item.study_id, item.id, item.label, item.scale, item.item_type, item.created_at
), panel_stats AS (
    SELECT member.study_id,
           COUNT(*) FILTER (WHERE member.consent_status = 'granted')::INTEGER AS participant_count
      FROM public.delphi_panel_member AS member
      JOIN scoped_studies AS study ON study.study_id = member.study_id
     GROUP BY member.study_id
)
SELECT study.study_id,
       study.location_id,
       study.title,
       study.status,
       COALESCE(panel.participant_count, 0) >= study.privacy_floor AS panel_size_available,
       CASE WHEN COALESCE(panel.participant_count, 0) >= study.privacy_floor
            THEN panel.participant_count ELSE NULL END AS panel_size,
       COALESCE(
           jsonb_agg(
               jsonb_build_object(
                   'item_id', item.item_id,
                   'label', item.label,
                   'scale', item.scale,
                   'item_type', item.item_type,
                   'results_available', item.participant_count >= study.privacy_floor,
                   'participant_count', CASE
                       WHEN item.participant_count >= study.privacy_floor
                       THEN item.participant_count ELSE NULL END,
                   'median', CASE WHEN item.participant_count >= study.privacy_floor
                                  THEN item.median ELSE NULL END,
                   'mean', CASE WHEN item.participant_count >= study.privacy_floor
                                THEN item.mean ELSE NULL END,
                   'iqr', CASE WHEN item.participant_count >= study.privacy_floor
                               THEN item.iqr ELSE NULL END,
                   'standard_deviation', CASE
                       WHEN item.participant_count >= study.privacy_floor
                       THEN item.standard_deviation ELSE NULL END,
                   'weighted_median', CASE
                       WHEN item.participant_count >= study.privacy_floor
                       THEN COALESCE(weighted_median.weighted_median, item.median)
                       ELSE NULL END,
                   'coefficient_of_variation', CASE
                       WHEN item.participant_count >= study.privacy_floor
                        AND abs(item.mean) >= 0.000000001
                       THEN round((item.standard_deviation / abs(item.mean))::NUMERIC, 4)
                       ELSE NULL END,
                   'consensus_reached', CASE
                       WHEN item.participant_count >= study.privacy_floor
                       THEN round(item.iqr::NUMERIC, 4) <= study.iqr_threshold
                       ELSE NULL END,
                   'computed_at', item.computed_at
               ) ORDER BY item.item_id
           ) FILTER (WHERE item.item_id IS NOT NULL),
           '[]'::JSONB
       ) AS items
  FROM scoped_studies AS study
  LEFT JOIN panel_stats AS panel ON panel.study_id = study.study_id
  LEFT JOIN item_stats AS item ON item.study_id = study.study_id
  LEFT JOIN weighted_medians AS weighted_median ON weighted_median.item_id = item.item_id
 GROUP BY study.study_id, study.location_id, study.title, study.status,
          study.privacy_floor, study.iqr_threshold, panel.participant_count;

ALTER VIEW kokonut_agent_source.delphi_live_summary
    OWNER TO kokonut_agent_summary_source_view_owner;

REVOKE ALL PRIVILEGES ON TABLE kokonut_agent_source.delphi_live_summary
    FROM PUBLIC,
         kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_login;
GRANT SELECT ON TABLE kokonut_agent_source.delphi_live_summary
    TO kokonut_agent_summary_source_reader;
REVOKE ALL PRIVILEGES ON TABLE
    public.delphi_study,
    public.delphi_item,
    public.delphi_contribution,
    public.delphi_panel_member
FROM kokonut_agent_summary_source_reader,
     kokonut_agent_summary_source_login;
REVOKE CREATE ON SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_reader,
         kokonut_agent_summary_source_login;
REVOKE USAGE ON SCHEMA kokonut_agent_source
    FROM kokonut_agent_summary_source_login;

DO $$
BEGIN
    IF pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_reader',
        'public.delphi_contribution', 'SELECT'
    ) OR pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_login',
        'public.delphi_contribution', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'Delphi source identities can bypass the protected projection';
    END IF;
    IF NOT pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_reader',
        'kokonut_agent_source.delphi_live_summary', 'SELECT'
    ) THEN
        RAISE EXCEPTION 'agent source reader lacks the Delphi summary projection';
    END IF;
    IF pg_catalog.has_table_privilege(
        'kokonut_agent_summary_source_login',
        'kokonut_agent_source.delphi_live_summary', 'SELECT'
    ) OR pg_catalog.has_schema_privilege(
        'kokonut_agent_summary_source_login', 'kokonut_agent_source', 'USAGE'
    ) THEN
        RAISE EXCEPTION 'agent source login bypasses the NOLOGIN reader role';
    END IF;
END;
$$;

COMMIT;
