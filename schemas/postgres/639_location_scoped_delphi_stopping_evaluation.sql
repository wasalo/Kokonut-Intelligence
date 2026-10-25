-- Evaluate Delphi stopping rules from currently consented responses.
-- Evaluation is advisory: it never closes a study or publishes a recommendation.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_delphi_stopping'
    ) THEN
        CREATE ROLE kokonut_delphi_stopping
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_stopping'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) OR EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_delphi_stopping'
            OR member_role.rolname = 'kokonut_delphi_stopping'
    ) THEN
        RAISE EXCEPTION 'Delphi stopping role must remain isolated and non-login';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_stopping_evaluation_request (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    result JSONB NOT NULL CHECK (pg_catalog.jsonb_typeof(result) = 'object'),
    evaluated_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);
CREATE INDEX IF NOT EXISTS idx_delphi_stopping_evaluation_scope_time
    ON public.delphi_stopping_evaluation(study_id, item_id, evaluated_at DESC)
    WHERE scope = 'item';
ALTER TABLE public.delphi_stopping_evaluation
    ALTER COLUMN median_shift TYPE NUMERIC(14,6);

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_stopping_request_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi stopping evaluation requests are append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_delphi_stopping_request_immutable
    ON kokonut_security.delphi_stopping_evaluation_request;
CREATE TRIGGER trg_delphi_stopping_request_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_stopping_evaluation_request
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_stopping_request_mutation();

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_stopping_evaluation_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi stopping evaluations are append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_delphi_stopping_evaluation_immutable
    ON public.delphi_stopping_evaluation;
CREATE TRIGGER trg_delphi_stopping_evaluation_immutable
    BEFORE UPDATE OR DELETE ON public.delphi_stopping_evaluation
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_stopping_evaluation_mutation();

REVOKE ALL ON TABLE public.delphi_stopping_evaluation,
    kokonut_security.delphi_stopping_evaluation_request FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_stopping_request_mutation()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_stopping_evaluation_mutation()
    FROM PUBLIC;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_delphi_stopping;
GRANT SELECT ON TABLE public.operator_identity, public.operator_scope_grant,
    public.location, public.operator_organization_membership,
    public.location_tenant_owner_verification, public.location_organization_share,
    public.organization TO kokonut_delphi_stopping;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_delphi_stopping;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_delphi_stopping;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT) TO kokonut_delphi_stopping;
GRANT SELECT (id, location_id, status, stopping_criteria, opened_at, closed_at)
    ON TABLE public.delphi_study TO kokonut_delphi_stopping;
GRANT UPDATE (id) ON TABLE public.delphi_study TO kokonut_delphi_stopping;
GRANT SELECT (id, study_id) ON TABLE public.delphi_item TO kokonut_delphi_stopping;
GRANT SELECT (id, study_id, consent_status) ON TABLE public.delphi_panel_member
    TO kokonut_delphi_stopping;
GRANT UPDATE (id) ON TABLE public.delphi_panel_member
    TO kokonut_delphi_stopping;
GRANT SELECT ON TABLE kokonut_security.delphi_participant_consent_event
    TO kokonut_delphi_stopping;
GRANT SELECT (study_id, item_id, panel_member_id, score)
    ON TABLE public.delphi_contribution TO kokonut_delphi_stopping;
GRANT SELECT, INSERT ON TABLE public.delphi_stopping_evaluation,
    kokonut_security.delphi_stopping_evaluation_request TO kokonut_delphi_stopping;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_stopping_evaluation_request
            FROM kokonut_runtime;
        REVOKE ALL ON TABLE public.delphi_stopping_evaluation FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_stopping_request_mutation()
            FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_stopping_evaluation_mutation()
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_stopping_evaluation_request
            FROM kokonut_directus_runtime;
        REVOKE ALL ON TABLE public.delphi_stopping_evaluation
            FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_stopping_request_mutation()
            FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_stopping_evaluation_mutation()
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.evaluate_location_delphi_stopping(
    requested_location_id UUID,
    requested_study_id UUID,
    requested_request_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    study_record RECORD;
    item_record RECORD;
    distribution RECORD;
    prior_record RECORD;
    criteria JSONB;
    now_value TIMESTAMPTZ := pg_catalog.clock_timestamp();
    required_participants INTEGER;
    max_duration_hours INTEGER;
    stability_threshold NUMERIC;
    iqr_threshold NUMERIC;
    latest_consent_change TIMESTAMPTZ;
    previous_iqr NUMERIC;
    previous_median NUMERIC;
    prior_evaluation_found BOOLEAN;
    current_iqr NUMERIC;
    current_median NUMERIC;
    stability_change NUMERIC;
    median_shift NUMERIC;
    consensus_met BOOLEAN;
    participation_met BOOLEAN;
    stability_met BOOLEAN;
    duration_exceeded BOOLEAN;
    should_stop BOOLEAN;
    item_outcome TEXT;
    study_outcome TEXT;
    item_results JSONB := '[]'::JSONB;
    item_count INTEGER := 0;
    stopped_count INTEGER := 0;
    all_consensus BOOLEAN := TRUE;
    all_participation BOOLEAN := TRUE;
    all_stability BOOLEAN := TRUE;
    has_missing_stability_history BOOLEAN := FALSE;
    payload_digest BYTEA;
    prior_request RECORD;
    response JSONB;
    stop_reasons TEXT[] := ARRAY[]::TEXT[];
BEGIN
    IF requested_location_id IS NULL OR requested_study_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Delphi stopping evaluation identifiers are required'
            USING ERRCODE = '22023';
    END IF;
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'Delphi stopping evaluation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'evaluate_stopping', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi stopping evaluation requires a current location grant'
            USING ERRCODE = '42501';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'study_id', requested_study_id,
                'action', 'evaluate_stopping'
            )::TEXT,
            'UTF8'
        ),
        'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
    ));
    SELECT receipt.payload_digest, receipt.result
      INTO prior_request
      FROM kokonut_security.delphi_stopping_evaluation_request AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_request.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Delphi stopping request id was reused with changed scope'
                USING ERRCODE = '55000';
        END IF;
        RETURN prior_request.result || '{"replayed":true}'::JSONB;
    END IF;

    SELECT study.id, study.location_id, study.status,
           study.stopping_criteria, study.opened_at, study.closed_at
      INTO study_record
      FROM public.delphi_study AS study
     WHERE study.id = requested_study_id
       AND study.location_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND OR study_record.status IS DISTINCT FROM 'open'
       OR study_record.opened_at IS NULL OR study_record.closed_at IS NOT NULL THEN
        RAISE EXCEPTION 'Delphi stopping evaluation requires an open study'
            USING ERRCODE = '55000';
    END IF;

    criteria := study_record.stopping_criteria;
    IF pg_catalog.jsonb_typeof(criteria) IS DISTINCT FROM 'object'
       OR pg_catalog.jsonb_typeof(criteria -> 'min_participants') IS DISTINCT FROM 'number'
       OR pg_catalog.jsonb_typeof(criteria -> 'max_duration_hours') IS DISTINCT FROM 'number'
       OR pg_catalog.jsonb_typeof(criteria -> 'stability_pct') IS DISTINCT FROM 'number'
       OR pg_catalog.jsonb_typeof(criteria -> 'iqr_threshold') IS DISTINCT FROM 'number' THEN
        RAISE EXCEPTION 'Delphi stopping criteria are invalid'
            USING ERRCODE = '22023';
    END IF;
    IF (criteria ->> 'min_participants')::NUMERIC NOT BETWEEN 3 AND 10000
       OR pg_catalog.trunc((criteria ->> 'min_participants')::NUMERIC)
             <> (criteria ->> 'min_participants')::NUMERIC
       OR (criteria ->> 'max_duration_hours')::NUMERIC NOT BETWEEN 1 AND 8760
       OR pg_catalog.trunc((criteria ->> 'max_duration_hours')::NUMERIC)
             <> (criteria ->> 'max_duration_hours')::NUMERIC
       OR (criteria ->> 'stability_pct')::NUMERIC NOT BETWEEN 0 AND 100
       OR (criteria ->> 'iqr_threshold')::NUMERIC NOT BETWEEN 0 AND 2 THEN
        RAISE EXCEPTION 'Delphi stopping criteria are outside the supported range'
            USING ERRCODE = '22023';
    END IF;
    required_participants := (criteria ->> 'min_participants')::INTEGER;
    max_duration_hours := (criteria ->> 'max_duration_hours')::INTEGER;
    stability_threshold := (criteria ->> 'stability_pct')::NUMERIC;
    iqr_threshold := (criteria ->> 'iqr_threshold')::NUMERIC;
    duration_exceeded := now_value >= study_record.opened_at
        + pg_catalog.make_interval(hours => max_duration_hours);

    -- Lock active consent rows so withdrawal cannot race the calculation.
    PERFORM member.id
      FROM public.delphi_panel_member AS member
     WHERE member.study_id = requested_study_id
     ORDER BY member.id
     FOR SHARE;
    SELECT pg_catalog.max(event.created_at)
      INTO latest_consent_change
      FROM kokonut_security.delphi_participant_consent_event AS event
     WHERE event.study_id = requested_study_id;

    FOR item_record IN
        SELECT item.id
          FROM public.delphi_item AS item
         WHERE item.study_id = requested_study_id
         ORDER BY item.id
    LOOP
        item_count := item_count + 1;
        SELECT pg_catalog.count(contribution.score)::INTEGER AS participant_count,
               pg_catalog.percentile_cont(0.5) WITHIN GROUP (ORDER BY contribution.score)::NUMERIC AS median,
               (pg_catalog.percentile_cont(0.75) WITHIN GROUP (ORDER BY contribution.score)
                - pg_catalog.percentile_cont(0.25) WITHIN GROUP (ORDER BY contribution.score))::NUMERIC AS iqr
          INTO distribution
          FROM public.delphi_contribution AS contribution
          JOIN public.delphi_panel_member AS member
            ON member.id = contribution.panel_member_id
           AND member.study_id = contribution.study_id
           AND member.consent_status = 'granted'
         WHERE contribution.study_id = requested_study_id
           AND contribution.item_id = item_record.id;

        current_median := distribution.median;
        current_iqr := distribution.iqr;
        participation_met := distribution.participant_count >= required_participants;
        consensus_met := participation_met AND current_iqr IS NOT NULL
            AND current_iqr <= iqr_threshold;
        stability_met := FALSE;
        previous_iqr := NULL;
        previous_median := NULL;
        stability_change := NULL;
        median_shift := NULL;
        SELECT evaluation.detail ->> 'median' AS median,
               evaluation.detail ->> 'iqr' AS iqr
          INTO prior_record
          FROM public.delphi_stopping_evaluation AS evaluation
         WHERE evaluation.study_id = requested_study_id
           AND evaluation.item_id = item_record.id
           AND evaluation.scope = 'item'
           AND evaluation.detail ->> 'kernel_consent_filtered' = 'true'
           AND (latest_consent_change IS NULL
                OR evaluation.evaluated_at >= latest_consent_change)
           AND evaluation.evaluated_at < now_value
         ORDER BY evaluation.evaluated_at DESC, evaluation.id DESC
         LIMIT 1;
        prior_evaluation_found := FOUND;
        IF prior_evaluation_found THEN
            previous_median := NULLIF(prior_record.median, '')::NUMERIC;
            previous_iqr := NULLIF(prior_record.iqr, '')::NUMERIC;
            IF previous_iqr IS NOT NULL AND current_iqr IS NOT NULL THEN
                IF previous_iqr < 0.000000001 AND current_iqr < 0.000000001 THEN
                    stability_change := 0;
                ELSIF previous_iqr < 0.000000001 THEN
                    stability_change := 100;
                ELSE
                    stability_change := pg_catalog.round(
                        pg_catalog.abs(current_iqr - previous_iqr) / previous_iqr * 100,
                        4
                    );
                END IF;
                IF current_median IS NOT NULL AND previous_median IS NOT NULL THEN
                    median_shift := pg_catalog.abs(current_median - previous_median);
                END IF;
                stability_met := participation_met
                    AND stability_change <= stability_threshold
                    AND median_shift IS NOT NULL
                    AND median_shift <= iqr_threshold * 0.1;
            END IF;
        ELSE
            has_missing_stability_history := TRUE;
        END IF;
        should_stop := consensus_met OR stability_met OR duration_exceeded;
        IF consensus_met AND duration_exceeded THEN
            item_outcome := 'time_limit_with_consensus';
        ELSIF consensus_met THEN
            item_outcome := 'consensus_reached';
        ELSIF duration_exceeded THEN
            item_outcome := 'time_limit_without_consensus';
        ELSIF stability_met THEN
            item_outcome := 'stable_without_consensus';
        ELSIF NOT participation_met THEN
            item_outcome := 'insufficient_participation';
        ELSIF NOT prior_evaluation_found THEN
            item_outcome := 'insufficient_stability_history';
        ELSE
            item_outcome := 'continue';
        END IF;
        IF should_stop THEN
            stopped_count := stopped_count + 1;
            stop_reasons := pg_catalog.array_append(stop_reasons, item_outcome);
        END IF;
        all_consensus := all_consensus AND consensus_met;
        all_participation := all_participation AND participation_met;
        all_stability := all_stability AND stability_met;
        INSERT INTO public.delphi_stopping_evaluation (
            study_id, item_id, scope, outcome, consensus_met, participation_met,
            stability_met, duration_exceeded, completion_met, normalized_iqr,
            median_shift, detail, evaluated_at
        ) VALUES (
            requested_study_id, item_record.id, 'item', item_outcome,
            consensus_met, participation_met, stability_met, duration_exceeded,
            should_stop, NULL, median_shift,
            pg_catalog.jsonb_build_object(
                'kernel_consent_filtered', TRUE,
                'median', current_median,
                'iqr', current_iqr,
                'stability_change_pct', stability_change
            ), now_value
        );
        item_results := item_results || pg_catalog.jsonb_build_array(
            pg_catalog.jsonb_build_object(
                'item_id', item_record.id,
                'should_stop', should_stop,
                'outcome', item_outcome
            )
        );
    END LOOP;

    IF item_count = 0 THEN
        study_outcome := 'incomplete_items';
    ELSIF stopped_count = item_count AND duration_exceeded AND all_consensus THEN
        study_outcome := 'time_limit_with_consensus';
    ELSIF stopped_count = item_count AND all_consensus THEN
        study_outcome := 'consensus_reached';
    ELSIF stopped_count = item_count AND duration_exceeded THEN
        study_outcome := 'time_limit_without_consensus';
    ELSIF stopped_count = item_count THEN
        study_outcome := 'stable_without_consensus';
    ELSIF NOT all_participation THEN
        study_outcome := 'insufficient_participation';
    ELSIF has_missing_stability_history THEN
        study_outcome := 'insufficient_stability_history';
    ELSE
        study_outcome := 'continue';
    END IF;
    IF item_count = 0 THEN
        all_consensus := FALSE;
        all_participation := FALSE;
        all_stability := FALSE;
    END IF;
    response := pg_catalog.jsonb_build_object(
        'study_id', requested_study_id,
        'location_id', requested_location_id,
        'should_stop', item_count > 0 AND stopped_count = item_count,
        'outcome', study_outcome,
        'items', item_results,
        'evaluated_at', now_value,
        'replayed', FALSE
    );
    INSERT INTO public.delphi_stopping_evaluation (
        study_id, item_id, scope, outcome, consensus_met, participation_met,
        stability_met, duration_exceeded, completion_met, detail, evaluated_at
    ) VALUES (
        requested_study_id, NULL, 'study', study_outcome, all_consensus,
        all_participation, all_stability, duration_exceeded,
        item_count > 0 AND stopped_count = item_count,
        pg_catalog.jsonb_build_object(
            'kernel_consent_filtered', TRUE,
            'item_count', item_count,
            'stopped_item_count', stopped_count,
            'stop_reasons', to_jsonb(stop_reasons)
        ), now_value
    );
    INSERT INTO kokonut_security.delphi_stopping_evaluation_request (
        operator_id, request_id, location_id, study_id,
        payload_digest, result, evaluated_at
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_study_id, payload_digest, response, now_value
    );
    RETURN response;
END;
$$;

ALTER TABLE kokonut_security.delphi_stopping_evaluation_request
    OWNER TO kokonut_delphi_stopping;
ALTER FUNCTION kokonut_security.prevent_delphi_stopping_request_mutation()
    OWNER TO kokonut_delphi_stopping;
ALTER FUNCTION kokonut_security.prevent_delphi_stopping_evaluation_mutation()
    OWNER TO kokonut_delphi_stopping;
ALTER FUNCTION kokonut_security.evaluate_location_delphi_stopping(UUID, UUID, UUID)
    OWNER TO kokonut_delphi_stopping;
REVOKE ALL ON TABLE kokonut_security.delphi_stopping_evaluation_request
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;
REVOKE ALL ON FUNCTION kokonut_security.evaluate_location_delphi_stopping(UUID, UUID, UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.evaluate_location_delphi_stopping(
            UUID, UUID, UUID
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.evaluate_location_delphi_stopping(
            UUID, UUID, UUID
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.evaluate_location_delphi_stopping(UUID, UUID, UUID)
IS 'Evaluates one exact-location Delphi study from current consented contributions, persists private append-only snapshots, and never changes study lifecycle state.';

COMMIT;
