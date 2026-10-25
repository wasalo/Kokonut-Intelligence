-- Bounded location-scoped invite inventory for operator console management.

BEGIN;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_delphi_participant_invites(
    requested_location_id UUID,
    requested_study_id UUID,
    requested_limit INTEGER DEFAULT 50,
    requested_offset INTEGER DEFAULT 0
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    invite_values JSONB := '[]'::JSONB;
    has_more BOOLEAN := FALSE;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_study_id IS NULL THEN
        RAISE EXCEPTION 'Delphi invite inventory requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'invite', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi invite inventory requires a current location invite grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Delphi invite inventory page is invalid'
            USING ERRCODE = '22023';
    END IF;

    WITH selected_page AS (
        SELECT invite.id,
               invite.study_id,
               invite.consent_notice_version,
               CASE WHEN invite.status = 'pending'
                          AND invite.expires_at <= pg_catalog.statement_timestamp()
                    THEN 'expired' ELSE invite.status END AS visible_status,
               invite.created_at,
               invite.expires_at
          FROM kokonut_security.delphi_participant_invite AS invite
         WHERE invite.location_id = requested_location_id
           AND invite.study_id = requested_study_id
         ORDER BY invite.created_at DESC, invite.id DESC
         OFFSET requested_offset
         LIMIT requested_limit + 1
    ), page AS (
        SELECT selected_page.*,
               pg_catalog.row_number() OVER (
                   ORDER BY selected_page.created_at DESC, selected_page.id DESC
               ) AS ordinal
          FROM selected_page
    )
    SELECT COALESCE(
               pg_catalog.jsonb_agg(
                   pg_catalog.jsonb_build_object(
                       'invite_id', page.id,
                       'study_id', page.study_id,
                       'notice_version', page.consent_notice_version,
                       'status', page.visible_status,
                       'created_at', page.created_at,
                       'expires_at', page.expires_at
                   ) ORDER BY page.ordinal
               ) FILTER (WHERE page.ordinal <= requested_limit),
               '[]'::JSONB
           ),
           pg_catalog.count(*) > requested_limit
      INTO invite_values, has_more
      FROM page;

    RETURN pg_catalog.jsonb_build_object(
        'location_id', requested_location_id,
        'study_id', requested_study_id,
        'invites', invite_values,
        'has_more', has_more,
        'limit', requested_limit,
        'offset', requested_offset
    );
END;
$$;

ALTER FUNCTION kokonut_security.list_location_delphi_participant_invites(
    UUID, UUID, INTEGER, INTEGER
) OWNER TO kokonut_delphi_invite;
REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_participant_invites(
    UUID, UUID, INTEGER, INTEGER
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_delphi_participant_invites(
            UUID, UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_participant_invites(
            UUID, UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_delphi_participant_invites(
    UUID, UUID, INTEGER, INTEGER
) IS 'Returns bounded invite lifecycle metadata for one signed operator location and study; never exposes tokens or participant identity.';

COMMIT;
