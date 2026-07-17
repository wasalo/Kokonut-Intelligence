-- ============================================================
-- 298_consent_privacy_p0.sql
-- ============================================================
-- P0 privacy corrections. Keep public projections fail-closed when
-- legacy records have no explicit public-safe designation.

-- A failed early attempt could have left an ambiguous seven-argument
-- overload behind. Remove only that exact signature before recreating it.
DROP VIEW IF EXISTS v_public_stakeholder_feedback_summary;
DROP FUNCTION IF EXISTS stakeholder_has_effective_consent(UUID, TEXT, TEXT, TEXT, UUID, TEXT, UUID);

CREATE OR REPLACE FUNCTION stakeholder_has_effective_consent_for_recipient(
    requested_party_id UUID,
    requested_category TEXT,
    requested_purpose TEXT,
    requested_scope_type TEXT,
    requested_scope_id UUID,
    requested_recipient_type TEXT,
    requested_recipient_party_id UUID
) RETURNS BOOLEAN
LANGUAGE SQL STABLE AS $$
    SELECT EXISTS (
        SELECT 1
        FROM v_effective_stakeholder_consent c
        WHERE c.party_id = requested_party_id
          AND c.data_category = requested_category
          AND c.purpose = requested_purpose
          AND c.recipient_type = requested_recipient_type
          AND c.recipient_party_id IS NOT DISTINCT FROM requested_recipient_party_id
          AND c.consented = TRUE
          AND (
              (c.scope_type = requested_scope_type AND c.scope_id IS NOT DISTINCT FROM requested_scope_id)
              OR c.scope_type = 'network'
          )
    );
$$;

-- Preserve the original call signature used by existing triggers and views.
CREATE OR REPLACE FUNCTION stakeholder_has_effective_consent(
    requested_party_id UUID,
    requested_category TEXT,
    requested_purpose TEXT,
    requested_scope_type TEXT,
    requested_scope_id UUID,
    requested_recipient_type TEXT DEFAULT 'system'
) RETURNS BOOLEAN
LANGUAGE SQL STABLE AS $$
    SELECT stakeholder_has_effective_consent_for_recipient(
        requested_party_id,
        requested_category,
        requested_purpose,
        requested_scope_type,
        requested_scope_id,
        requested_recipient_type,
        NULL::UUID
    );
$$;

CREATE OR REPLACE FUNCTION enforce_stakeholder_consent_transition()
RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    plan_record RECORD;
    new_status TEXT := to_jsonb(NEW)->>'status';
    new_is_public BOOLEAN := COALESCE((to_jsonb(NEW)->>'is_public')::BOOLEAN, FALSE);
BEGIN
    IF TG_TABLE_NAME = 'stakeholder_feedback'
       AND (new_status = 'published' OR new_is_public = TRUE) THEN
        IF NEW.party_id IS NULL
            OR NOT stakeholder_has_effective_consent_for_recipient(
               NEW.party_id, 'stakeholder_feedback',
               CASE WHEN new_is_public THEN 'public_summary' ELSE 'stakeholder_feedback_review' END,
               'location', NEW.location_id, 'system', NULL
           ) THEN
            RAISE EXCEPTION 'canonical consent is required before publishing stakeholder feedback';
        END IF;
        NEW.canonical_consent_event_id := COALESCE(
            NEW.canonical_consent_event_id,
            (SELECT c.consent_event_id
             FROM v_effective_stakeholder_consent c
             WHERE c.party_id = NEW.party_id
               AND c.data_category = 'stakeholder_feedback'
               AND c.purpose = CASE WHEN new_is_public THEN 'public_summary' ELSE 'stakeholder_feedback_review' END
               AND c.scope_type = 'location'
               AND c.scope_id IS NOT DISTINCT FROM NEW.location_id
               AND c.recipient_type = 'system'
               AND c.recipient_party_id IS NULL
               AND c.consented = TRUE
             ORDER BY c.effective_at DESC LIMIT 1)
        );
    ELSIF TG_TABLE_NAME = 'stakeholder_touchpoint' AND new_status = 'completed' THEN
        SELECT p.* INTO plan_record
        FROM stakeholder_engagement_plan p
        WHERE p.id = NEW.plan_id;
        IF plan_record.stakeholder_party_id IS NULL
            OR NOT stakeholder_has_effective_consent_for_recipient(
               plan_record.stakeholder_party_id, 'stakeholder_engagement', NEW.purpose,
               plan_record.scope_type, plan_record.scope_id, 'system', NULL
           ) THEN
            RAISE EXCEPTION 'canonical consent is required before completing stakeholder touchpoint';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE VIEW v_public_stakeholder_feedback_summary AS
SELECT
    sf.id,
    sf.location_id,
    sf.farm_id,
    sf.feedback_type,
    sf.stakeholder_group,
    sf.feedback_date,
    sf.sentiment,
    sf.themes,
    sf.public_summary,
    sf.evidence_maturity,
    em.label AS evidence_maturity_label
FROM stakeholder_feedback sf
LEFT JOIN evidence_maturity_level em ON em.level = sf.evidence_maturity
WHERE sf.party_id IS NOT NULL
  AND sf.is_public = TRUE
  AND sf.consent_given = TRUE
  AND sf.status = 'published'
  AND NULLIF(TRIM(COALESCE(sf.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = sf.location_id
        AND fr.status IN ('verified', 'published')
  )
   AND stakeholder_has_effective_consent_for_recipient(
      sf.party_id, 'stakeholder_feedback', 'public_summary',
      'location', sf.location_id, 'system', NULL
  );

CREATE OR REPLACE VIEW v_project_data_stream AS
SELECT
    dsp.id,
    dsp.location_id,
    dsp.post_type,
    dsp.title,
    dsp.content,
    dsp.media_type,
    dsp.evidence_urls,
    dsp.file_ids,
    dsp.visibility,
    dsp.status,
    dsp.is_anchored,
    dsp.attestation_uid,
    dsp.chain,
    dsp.anchored_at,
    dsp.created_at,
    dsp.created_by,
    dsp.metadata,
    l.name AS location_name,
    fm.name AS farm_name,
    (SELECT COUNT(*) FROM data_stream_post_comment dsc WHERE dsc.post_id = dsp.id) AS comment_count
FROM data_stream_post dsp
JOIN location l ON l.id = dsp.location_id
LEFT JOIN farm_registry_record fr ON fr.location_id = dsp.location_id AND fr.status IN ('verified', 'published')
LEFT JOIN farm fm ON fm.id = fr.farm_id
WHERE l.status = 'active'
  AND dsp.status IN ('published', 'verified')
  AND dsp.visibility = 'public'
  AND dsp.metadata->>'privacy' = 'public_summary'
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr2
      WHERE fr2.location_id = dsp.location_id
        AND fr2.status IN ('verified', 'published')
  )
ORDER BY dsp.created_at DESC;

CREATE OR REPLACE VIEW v_data_stream_search AS
SELECT
    dsp.id,
    dsp.location_id,
    dsp.post_type,
    dsp.title,
    dsp.content,
    dsp.visibility,
    dsp.status,
    dsp.created_at,
    l.name AS location_name,
    ts_rank(dsp.content_search, plainto_tsquery('english', COALESCE(dsp.title, '') || ' ' || COALESCE(dsp.content, ''))) AS search_rank
FROM data_stream_post dsp
JOIN location l ON l.id = dsp.location_id
WHERE dsp.status IN ('published', 'verified')
  AND dsp.visibility = 'public'
  AND dsp.metadata->>'privacy' = 'public_summary'
  AND dsp.content_search IS NOT NULL
  AND l.status = 'active'
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = dsp.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_emergency_incidents AS
SELECT
    e.id,
    e.location_id,
    l.name AS location_name,
    l.latitude,
    l.longitude,
    fr.id AS farm_registry_id,
    fr.status AS farm_status,
    e.incident_type,
    e.severity,
    e.detection_date,
    e.detection_method,
    e.description,
    e.affected_area_pct,
    e.affected_plant_count,
    e.response_actions,
    e.emergency_support_provided,
    e.response_deadline,
    e.recovery_date,
    CASE WHEN e.recovery_date IS NOT NULL AND e.detection_date IS NOT NULL
         THEN (e.recovery_date - e.detection_date) ELSE NULL END AS response_time_days,
    CASE WHEN e.response_deadline IS NOT NULL AND e.recovery_date IS NOT NULL
         THEN e.recovery_date <= e.response_deadline ELSE NULL END AS met_deadline,
    e.recovery_actions,
    e.financial_impact_usd,
    e.ecological_impact_notes,
    e.lessons_learned,
    e.status,
    e.created_at
FROM emergency_incident e
JOIN location l ON e.location_id = l.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND e.status = 'resolved'
  AND e.metadata->>'privacy' = 'public_summary'
  AND fr.status IN ('verified', 'published');

CREATE OR REPLACE VIEW v_public_water_sample_summary AS
SELECT
    ws.id,
    ws.sample_date,
    ws.sample_type,
    ws.collection_method,
    ws.depth_m,
    ws.gps_latitude,
    ws.gps_longitude,
    ws.water_temperature_c,
    ws.collector_name,
    ws.lab_name,
    ws.status,
    l.name AS location_name,
    wa.source_type AS water_source_type,
    wa.source_name AS water_source_name
FROM water_sample ws
JOIN location l ON l.id = ws.location_id
LEFT JOIN water_access wa ON wa.id = ws.water_access_id
WHERE ws.status = 'published'
  AND ws.evidence_maturity >= 4
  AND ws.metadata->>'privacy' = 'public_summary'
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = ws.location_id
        AND fr.status IN ('verified', 'published')
  );

COMMENT ON FUNCTION stakeholder_has_effective_consent_for_recipient IS 'Canonical consent check with exact recipient-party matching';

CREATE OR REPLACE FUNCTION enforce_coordination_exchange_integrity()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    alliance_scope_type VARCHAR(30);
    alliance_scope_id UUID;
BEGIN
    IF NEW.status = 'completed' THEN
        SELECT scope_type, scope_id INTO alliance_scope_type, alliance_scope_id
        FROM coordination_alliance WHERE id = NEW.alliance_id;
        IF NEW.consent_event_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM v_effective_stakeholder_consent c
            WHERE c.consent_event_id = NEW.consent_event_id
              AND c.party_id = NEW.from_party_id
              AND c.event_type = 'grant'
              AND c.consented = TRUE
              AND c.data_category = 'coordination_knowledge_exchange'
              AND c.purpose = 'knowledge_exchange'
               AND c.recipient_party_id = NEW.to_party_id
              AND (NEW.consent_scope IS NULL OR c.scope_type = NEW.consent_scope)
              AND (
                  c.scope_type = 'network'
                  OR (c.scope_type = alliance_scope_type AND c.scope_id IS NOT DISTINCT FROM alliance_scope_id)
              )
        ) THEN
            RAISE EXCEPTION 'effective sender consent for this knowledge exchange is required';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
