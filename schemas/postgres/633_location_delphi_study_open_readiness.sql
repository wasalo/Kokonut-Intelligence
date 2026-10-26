-- Return only readiness booleans and fixed blocker codes for a location Delphi study.
-- Participant counts and panel identities are deliberately not exposed.

BEGIN;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_delphi_study_open_readiness(
    requested_location_id UUID,
    requested_study_id UUID
)
RETURNS TABLE (
    study_id UUID,
    location_id UUID,
    status TEXT,
    has_question BOOLEAN,
    minimum_policy_valid BOOLEAN,
    consent_minimum_met BOOLEAN,
    eligible_to_open BOOLEAN,
    blocker_codes TEXT[]
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    study_record RECORD;
    required_value NUMERIC;
    required_participants INTEGER;
    blocker_list TEXT[] := ARRAY[]::TEXT[];
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_study_id IS NULL THEN
        RAISE EXCEPTION 'Delphi readiness requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'open', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi readiness requires an active location open grant'
            USING ERRCODE = '42501';
    END IF;

    SELECT study.id, study.location_id, study.status, study.stopping_criteria
      INTO study_record
      FROM public.delphi_study AS study
     WHERE study.id = requested_study_id
       AND study.location_id = requested_location_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi study is unavailable for this location'
            USING ERRCODE = '42501';
    END IF;

    study_id := study_record.id;
    location_id := study_record.location_id;
    status := study_record.status;
    has_question := EXISTS (
        SELECT 1 FROM public.delphi_item AS item
         WHERE item.study_id = requested_study_id
    );

    minimum_policy_valid := FALSE;
    required_participants := NULL;
    IF pg_catalog.jsonb_typeof(study_record.stopping_criteria) = 'object'
       AND pg_catalog.jsonb_typeof(
           study_record.stopping_criteria -> 'min_participants'
       ) = 'number' THEN
        BEGIN
            required_value :=
                (study_record.stopping_criteria ->> 'min_participants')::NUMERIC;
            IF required_value >= -2147483648 AND required_value <= 2147483647 THEN
                -- Match migration 631's numeric-to-integer conversion exactly.
                required_participants := required_value::INTEGER;
                minimum_policy_valid := required_participants >= 3;
            END IF;
        EXCEPTION WHEN numeric_value_out_of_range OR invalid_text_representation THEN
            minimum_policy_valid := FALSE;
            required_participants := NULL;
        END;
    END IF;

    consent_minimum_met := FALSE;
    IF minimum_policy_valid THEN
        SELECT pg_catalog.count(*) >= required_participants
          INTO consent_minimum_met
          FROM public.delphi_panel_member AS member
         WHERE member.study_id = requested_study_id
           AND member.consent_status = 'granted';
    END IF;

    IF status IS DISTINCT FROM 'draft' THEN
        blocker_list := pg_catalog.array_append(blocker_list, 'study_not_draft');
    END IF;
    IF NOT has_question THEN
        blocker_list := pg_catalog.array_append(blocker_list, 'question_required');
    END IF;
    IF NOT minimum_policy_valid THEN
        blocker_list := pg_catalog.array_append(blocker_list, 'minimum_participants_invalid');
    ELSIF NOT consent_minimum_met THEN
        blocker_list := pg_catalog.array_append(blocker_list, 'consented_panel_below_minimum');
    END IF;

    eligible_to_open := pg_catalog.cardinality(blocker_list) = 0;
    blocker_codes := blocker_list;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.get_location_delphi_study_open_readiness(UUID, UUID)
    OWNER TO kokonut_delphi_study_lifecycle;
REVOKE ALL ON FUNCTION kokonut_security.get_location_delphi_study_open_readiness(UUID, UUID)
    FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.get_location_delphi_study_open_readiness(
            UUID, UUID
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.get_location_delphi_study_open_readiness(
            UUID, UUID
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.get_location_delphi_study_open_readiness(UUID, UUID)
IS 'Returns only private operator-facing readiness booleans and fixed blockers for opening one exact-location Delphi study; never returns panel counts or identities.';

COMMIT;
