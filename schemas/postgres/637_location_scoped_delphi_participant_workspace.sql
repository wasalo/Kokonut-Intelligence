-- Pseudonymous participant workspace and same-member Delphi contribution writes.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_participant'
    ) THEN
        RAISE EXCEPTION 'Delphi participant role must be installed before migration 637';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_participant'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) OR EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_delphi_participant'
            OR member_role.rolname = 'kokonut_delphi_participant'
    ) THEN
        RAISE EXCEPTION 'Delphi participant role must remain isolated and non-login';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_participant_contribution_request (
    session_id UUID NOT NULL
        REFERENCES kokonut_security.delphi_participant_session(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    contribution_id UUID NOT NULL
        REFERENCES public.delphi_contribution(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (session_id, request_id)
);

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_participant_contribution_request_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi participant contribution request history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_delphi_participant_contribution_request_immutable
    ON kokonut_security.delphi_participant_contribution_request;
CREATE TRIGGER trg_delphi_participant_contribution_request_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_participant_contribution_request
    FOR EACH ROW EXECUTE FUNCTION
        kokonut_security.prevent_delphi_participant_contribution_request_mutation();

ALTER TABLE kokonut_security.delphi_participant_contribution_request
    OWNER TO kokonut_delphi_participant;
REVOKE ALL ON TABLE kokonut_security.delphi_participant_contribution_request FROM PUBLIC;

GRANT SELECT (id, title, status, stopping_criteria, opened_at, closed_at)
    ON TABLE public.delphi_study TO kokonut_delphi_participant;
GRANT UPDATE (id) ON TABLE public.delphi_study TO kokonut_delphi_participant;
GRANT SELECT (id, study_id, item_type, label, description, scale,
              min_value, max_value, created_at)
    ON TABLE public.delphi_item TO kokonut_delphi_participant;
GRANT SELECT (id, study_id, consent_status, expert_weight)
    ON TABLE public.delphi_panel_member TO kokonut_delphi_participant;
GRANT SELECT (id, study_id, item_id, panel_member_id, score, reasoning, updated_at)
    ON TABLE public.delphi_contribution TO kokonut_delphi_participant;
GRANT INSERT (id, study_id, item_id, panel_member_id, score, reasoning)
    ON TABLE public.delphi_contribution TO kokonut_delphi_participant;
GRANT UPDATE (score, reasoning, updated_at)
    ON TABLE public.delphi_contribution TO kokonut_delphi_participant;
GRANT SELECT (item_id) ON TABLE public.delphi_consensus
    TO kokonut_delphi_participant;
GRANT INSERT (study_id, item_id, median, mean, iqr, stddev, cv,
              participant_count, weighted_median, consensus_reached, computed_at)
    ON TABLE public.delphi_consensus TO kokonut_delphi_participant;
GRANT UPDATE (median, mean, iqr, stddev, cv, participant_count,
              weighted_median, consensus_reached, computed_at)
    ON TABLE public.delphi_consensus TO kokonut_delphi_participant;
GRANT INSERT (study_id, item_id, median, iqr, participant_count)
    ON TABLE public.delphi_consensus_history TO kokonut_delphi_participant;
GRANT SELECT, INSERT ON TABLE kokonut_security.delphi_participant_contribution_request
    TO kokonut_delphi_participant;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_delphi_participant;
GRANT EXECUTE ON FUNCTION public.gen_random_uuid()
    TO kokonut_delphi_participant;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_delphi_participant_workspace(
    requested_session_token TEXT,
    requested_limit INTEGER DEFAULT 50,
    requested_offset INTEGER DEFAULT 0
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    session_digest BYTEA;
    session_record RECORD;
    study_record RECORD;
    item_values JSONB := '[]'::JSONB;
    has_more BOOLEAN := FALSE;
BEGIN
    IF requested_session_token IS NULL OR requested_session_token !~ '^[0-9a-f]{64}$'
       OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Delphi participant workspace request is invalid'
            USING ERRCODE = '22023';
    END IF;
    session_digest := public.digest(
        pg_catalog.convert_to(requested_session_token, 'UTF8'), 'sha256'
    );

    SELECT session.id, session.location_id, session.study_id,
           session.panel_member_id, session.status, session.expires_at,
           member.consent_status
      INTO session_record
      FROM kokonut_security.delphi_participant_session AS session
      JOIN public.delphi_panel_member AS member
        ON member.id = session.panel_member_id
       AND member.study_id = session.study_id
     WHERE session.session_token_digest = session_digest;
    IF NOT FOUND OR session_record.status IS DISTINCT FROM 'active'
       OR session_record.expires_at <= pg_catalog.clock_timestamp()
       OR session_record.consent_status IS DISTINCT FROM 'granted' THEN
        RAISE EXCEPTION 'Delphi participant session is invalid or unavailable'
            USING ERRCODE = '42501';
    END IF;

    SELECT study.id, study.title, study.status, study.opened_at, study.closed_at
      INTO study_record
      FROM public.delphi_study AS study
     WHERE study.id = session_record.study_id
       AND study.location_id = session_record.location_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi participant study is unavailable'
            USING ERRCODE = '42501';
    END IF;

    IF study_record.status IN ('open', 'closed') THEN
        WITH participant_items AS (
            SELECT item.id,
                   item.label,
                   item.description,
                   item.item_type,
                   item.scale,
                   item.min_value,
                   item.max_value,
                   item.created_at,
                   contribution.score AS my_score,
                   contribution.reasoning AS my_reasoning,
                   contribution.updated_at AS my_updated_at
              FROM public.delphi_item AS item
              LEFT JOIN public.delphi_contribution AS contribution
                ON contribution.item_id = item.id
               AND contribution.study_id = item.study_id
               AND contribution.panel_member_id = session_record.panel_member_id
             WHERE item.study_id = study_record.id
             ORDER BY item.created_at, item.id
             OFFSET requested_offset
             LIMIT requested_limit + 1
        ), numbered_items AS (
            SELECT page.*,
                   pg_catalog.row_number() OVER (
                       ORDER BY page.created_at, page.id
                   ) AS ordinal
              FROM participant_items AS page
        )
        SELECT COALESCE(
                   pg_catalog.jsonb_agg(
                       pg_catalog.jsonb_build_object(
                           'item_id', page.id,
                           'label', page.label,
                           'description', page.description,
                           'item_type', page.item_type,
                           'scale', page.scale,
                           'minimum', page.min_value,
                           'maximum', page.max_value,
                           'my_score', page.my_score,
                           'my_reasoning', page.my_reasoning,
                           'my_updated_at', page.my_updated_at
                       ) ORDER BY page.ordinal
                   ) FILTER (WHERE page.ordinal <= requested_limit),
                   '[]'::JSONB
               ),
               pg_catalog.count(*) > requested_limit
          INTO item_values, has_more
          FROM numbered_items AS page;
    END IF;

    RETURN pg_catalog.jsonb_build_object(
        'study', pg_catalog.jsonb_build_object(
            'study_id', study_record.id,
            'title', study_record.title,
            'status', study_record.status,
            'opened_at', study_record.opened_at,
            'closed_at', study_record.closed_at
        ),
        'items', item_values,
        'has_more', has_more,
        'limit', requested_limit,
        'offset', requested_offset
    );
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_delphi_participant_contribution(
    requested_session_token TEXT,
    requested_csrf_token TEXT,
    requested_item_id UUID,
    requested_score NUMERIC,
    requested_reasoning TEXT,
    requested_request_id UUID
)
RETURNS TABLE (
    status TEXT,
    item_id UUID,
    contribution_id UUID,
    updated_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    session_digest BYTEA;
    csrf_digest BYTEA;
    payload_digest BYTEA;
    session_record RECORD;
    study_record RECORD;
    item_record RECORD;
    receipt_record RECORD;
    previous_contribution RECORD;
    computed RECORD;
    normalized_score NUMERIC(8,4);
    min_participants INTEGER;
    iqr_threshold NUMERIC;
    reached BOOLEAN;
    result_id UUID;
    result_updated_at TIMESTAMPTZ;
    changed BOOLEAN := FALSE;
BEGIN
    IF requested_session_token IS NULL OR requested_session_token !~ '^[0-9a-f]{64}$'
       OR requested_csrf_token IS NULL OR requested_csrf_token !~ '^[0-9a-f]{64}$'
       OR requested_item_id IS NULL OR requested_score IS NULL
       OR requested_score::TEXT IN ('NaN', 'Infinity', '-Infinity')
       OR requested_score <> pg_catalog.round(requested_score, 4)
       OR requested_reasoning IS NOT NULL
          AND pg_catalog.char_length(requested_reasoning) > 4000
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Delphi participant contribution fields are invalid'
            USING ERRCODE = '22023';
    END IF;
    normalized_score := requested_score::NUMERIC(8,4);
    session_digest := public.digest(
        pg_catalog.convert_to(requested_session_token, 'UTF8'), 'sha256'
    );
    csrf_digest := public.digest(
        pg_catalog.convert_to(requested_csrf_token, 'UTF8'), 'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        pg_catalog.encode(session_digest, 'hex') || ':' || requested_request_id::TEXT, 0
    ));

    SELECT session.id, session.location_id, session.study_id,
           session.panel_member_id, session.status, session.expires_at,
           session.csrf_token_digest, member.consent_status
      INTO session_record
      FROM kokonut_security.delphi_participant_session AS session
      JOIN public.delphi_panel_member AS member
        ON member.id = session.panel_member_id
       AND member.study_id = session.study_id
     WHERE session.session_token_digest = session_digest
     FOR UPDATE OF session;
    IF NOT FOUND OR session_record.csrf_token_digest IS DISTINCT FROM csrf_digest
       OR session_record.status IS DISTINCT FROM 'active'
       OR session_record.expires_at <= pg_catalog.clock_timestamp()
       OR session_record.consent_status IS DISTINCT FROM 'granted' THEN
        RAISE EXCEPTION 'Delphi participant session is invalid or unavailable'
            USING ERRCODE = '42501';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'item_id', requested_item_id,
                'score', normalized_score,
                'reasoning', requested_reasoning
            )::TEXT,
            'UTF8'
        ),
        'sha256'
    );
    SELECT receipt.payload_digest, receipt.contribution_id, contribution.updated_at
      INTO receipt_record
      FROM kokonut_security.delphi_participant_contribution_request AS receipt
      JOIN public.delphi_contribution AS contribution
        ON contribution.id = receipt.contribution_id
     WHERE receipt.session_id = session_record.id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF receipt_record.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Delphi contribution request id was reused with changed content'
                USING ERRCODE = '55000';
        END IF;
        status := 'submitted';
        item_id := requested_item_id;
        contribution_id := receipt_record.contribution_id;
        updated_at := receipt_record.updated_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT study.id, study.status, study.stopping_criteria
      INTO study_record
      FROM public.delphi_study AS study
     WHERE study.id = session_record.study_id
       AND study.location_id = session_record.location_id
     FOR UPDATE;
    IF NOT FOUND OR study_record.status IS DISTINCT FROM 'open' THEN
        RAISE EXCEPTION 'Delphi study is not open for participant contributions'
            USING ERRCODE = '55000';
    END IF;
    SELECT item.id, item.min_value, item.max_value
      INTO item_record
      FROM public.delphi_item AS item
     WHERE item.id = requested_item_id
       AND item.study_id = study_record.id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi questionnaire item is unavailable'
            USING ERRCODE = '22023';
    END IF;
    IF normalized_score < item_record.min_value
       OR normalized_score > item_record.max_value THEN
        RAISE EXCEPTION 'Delphi participant score is outside the configured range'
            USING ERRCODE = '22023';
    END IF;

    SELECT contribution.id, contribution.score, contribution.reasoning,
           contribution.updated_at
      INTO previous_contribution
      FROM public.delphi_contribution AS contribution
     WHERE contribution.item_id = requested_item_id
       AND contribution.panel_member_id = session_record.panel_member_id
     FOR UPDATE;
    IF FOUND
       AND previous_contribution.score IS NOT DISTINCT FROM normalized_score
       AND previous_contribution.reasoning IS NOT DISTINCT FROM requested_reasoning THEN
        result_id := previous_contribution.id;
        result_updated_at := previous_contribution.updated_at;
    ELSE
        INSERT INTO public.delphi_contribution (
            id, study_id, item_id, panel_member_id, score, reasoning
        ) VALUES (
            public.gen_random_uuid(), study_record.id, requested_item_id,
            session_record.panel_member_id, normalized_score, requested_reasoning
        )
        ON CONFLICT (item_id, panel_member_id)
        DO UPDATE SET score = EXCLUDED.score,
                      reasoning = EXCLUDED.reasoning,
                      updated_at = pg_catalog.clock_timestamp()
        RETURNING id, updated_at INTO result_id, result_updated_at;
        changed := TRUE;
    END IF;

    IF changed THEN
        WITH eligible AS (
            SELECT contribution.score::DOUBLE PRECISION AS score,
                   COALESCE(member.expert_weight, 0)::DOUBLE PRECISION AS weight
              FROM public.delphi_contribution AS contribution
              JOIN public.delphi_panel_member AS member
                ON member.id = contribution.panel_member_id
               AND member.study_id = contribution.study_id
               AND member.consent_status = 'granted'
             WHERE contribution.study_id = study_record.id
               AND contribution.item_id = requested_item_id
        ), distribution AS (
            SELECT score,
                   weight,
                   pg_catalog.sum(weight) OVER (
                       ORDER BY score ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                   ) AS cumulative_weight,
                   pg_catalog.sum(weight) OVER () AS total_weight
              FROM eligible
        )
        SELECT pg_catalog.percentile_cont(0.5) WITHIN GROUP (ORDER BY score) AS median,
               pg_catalog.avg(score) AS mean,
               pg_catalog.round((
                   pg_catalog.percentile_cont(0.75) WITHIN GROUP (ORDER BY score)
                   - pg_catalog.percentile_cont(0.25) WITHIN GROUP (ORDER BY score)
               )::NUMERIC, 4) AS iqr,
               pg_catalog.stddev_pop(score) AS stddev,
               CASE WHEN pg_catalog.abs(pg_catalog.avg(score)) < 0.000000001
                    THEN NULL
                    ELSE pg_catalog.round(
                        (pg_catalog.stddev_pop(score)
                         / pg_catalog.abs(pg_catalog.avg(score)))::NUMERIC, 4
                    )
               END AS cv,
               pg_catalog.count(*)::INTEGER AS participant_count,
               CASE
                   WHEN COALESCE(pg_catalog.max(total_weight), 0) <= 0
                   THEN pg_catalog.percentile_cont(0.5) WITHIN GROUP (ORDER BY score)
                   ELSE (
                       SELECT selected.score
                         FROM distribution AS selected
                        WHERE selected.cumulative_weight >= selected.total_weight / 2.0
                        ORDER BY selected.score
                        LIMIT 1
                   )
               END AS weighted_median
          INTO computed
          FROM distribution;

        min_participants := GREATEST(
            1,
            CASE
                WHEN pg_catalog.jsonb_typeof(
                    study_record.stopping_criteria -> 'min_participants'
                ) = 'number'
                THEN pg_catalog.ceil(
                    (study_record.stopping_criteria ->> 'min_participants')::NUMERIC
                )::INTEGER
                ELSE 3
            END
        );
        iqr_threshold := GREATEST(
            0,
            CASE
                WHEN pg_catalog.jsonb_typeof(
                    study_record.stopping_criteria -> 'iqr_threshold'
                ) = 'number'
                THEN (study_record.stopping_criteria ->> 'iqr_threshold')::NUMERIC
                ELSE 1.0
            END
        );
        reached := computed.iqr IS NOT NULL
            AND computed.participant_count >= min_participants
            AND computed.iqr <= iqr_threshold;

        UPDATE public.delphi_consensus AS consensus
           SET median = computed.median,
               mean = computed.mean,
               iqr = computed.iqr,
               stddev = computed.stddev,
               cv = computed.cv,
               participant_count = computed.participant_count,
               weighted_median = computed.weighted_median,
               consensus_reached = reached,
               computed_at = pg_catalog.clock_timestamp()
         WHERE consensus.item_id = requested_item_id;
        IF NOT FOUND THEN
            INSERT INTO public.delphi_consensus (
                study_id, item_id, median, mean, iqr, stddev, cv,
                participant_count, weighted_median, consensus_reached, computed_at
            ) VALUES (
                study_record.id, requested_item_id, computed.median, computed.mean,
                computed.iqr, computed.stddev, computed.cv, computed.participant_count,
                computed.weighted_median, reached, pg_catalog.clock_timestamp()
            );
        END IF;

        INSERT INTO public.delphi_consensus_history (
            study_id, item_id, median, iqr, participant_count
        ) VALUES (
            study_record.id, requested_item_id, computed.median,
            computed.iqr, computed.participant_count
        );
    END IF;

    INSERT INTO kokonut_security.delphi_participant_contribution_request (
        session_id, request_id, payload_digest, contribution_id
    ) VALUES (
        session_record.id, requested_request_id, payload_digest, result_id
    );
    status := 'submitted';
    item_id := requested_item_id;
    contribution_id := result_id;
    updated_at := result_updated_at;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.prevent_delphi_participant_contribution_request_mutation()
    OWNER TO kokonut_delphi_participant;
ALTER FUNCTION kokonut_security.get_location_delphi_participant_workspace(TEXT, INTEGER, INTEGER)
    OWNER TO kokonut_delphi_participant;
ALTER FUNCTION kokonut_security.submit_location_delphi_participant_contribution(
    TEXT, TEXT, UUID, NUMERIC, TEXT, UUID
) OWNER TO kokonut_delphi_participant;

REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_participant_contribution_request_mutation()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.get_location_delphi_participant_workspace(
    TEXT, INTEGER, INTEGER
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_delphi_participant_contribution(
    TEXT, TEXT, UUID, NUMERIC, TEXT, UUID
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.get_location_delphi_participant_workspace(
            TEXT, INTEGER, INTEGER
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_delphi_participant_contribution(
            TEXT, TEXT, UUID, NUMERIC, TEXT, UUID
        ) TO kokonut_runtime;
        REVOKE ALL ON TABLE kokonut_security.delphi_participant_contribution_request
            FROM kokonut_runtime;
        -- Existing runtime table grants are not changed by this capability.
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_participant_contribution_request
            FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.get_location_delphi_participant_workspace(
            TEXT, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.submit_location_delphi_participant_contribution(
            TEXT, TEXT, UUID, NUMERIC, TEXT, UUID
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE kokonut_security.delphi_participant_contribution_request IS
'Append-only, digest-only idempotency receipt for pseudonymous participant contribution requests.';
COMMENT ON FUNCTION kokonut_security.get_location_delphi_participant_workspace(TEXT, INTEGER, INTEGER) IS
'Returns only one active consenting participant’s study questions and their own answers; draft studies expose no questions.';
COMMENT ON FUNCTION kokonut_security.submit_location_delphi_participant_contribution(TEXT, TEXT, UUID, NUMERIC, TEXT, UUID) IS
'Validates an active session and CSRF digest, serializes with withdrawal and study closure, upserts only the session member contribution, and refreshes consensus plus history atomically.';

COMMIT;
