-- ============================================================
-- 228_stakeholder_consent_enforcement.sql
-- ============================================================

ALTER TABLE stakeholder_feedback ADD COLUMN IF NOT EXISTS party_id UUID REFERENCES party(id) ON DELETE SET NULL;
ALTER TABLE stakeholder_feedback ADD COLUMN IF NOT EXISTS canonical_consent_event_id UUID REFERENCES stakeholder_consent(id) ON DELETE SET NULL;
ALTER TABLE stakeholder_touchpoint ADD COLUMN IF NOT EXISTS consent_event_id UUID REFERENCES stakeholder_consent(id) ON DELETE SET NULL;
ALTER TABLE stakeholder_participation ADD COLUMN IF NOT EXISTS consent_event_id UUID REFERENCES stakeholder_consent(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_feedback_party ON stakeholder_feedback(party_id);
CREATE INDEX IF NOT EXISTS idx_feedback_consent ON stakeholder_feedback(canonical_consent_event_id);
CREATE INDEX IF NOT EXISTS idx_touchpoint_consent ON stakeholder_touchpoint(consent_event_id);
CREATE INDEX IF NOT EXISTS idx_participation_consent ON stakeholder_participation(consent_event_id);

CREATE OR REPLACE FUNCTION stakeholder_has_effective_consent(
    requested_party_id UUID,
    requested_category TEXT,
    requested_purpose TEXT,
    requested_scope_type TEXT,
    requested_scope_id UUID,
    requested_recipient_type TEXT DEFAULT 'system'
) RETURNS BOOLEAN
LANGUAGE SQL STABLE AS $$
    SELECT EXISTS (
        SELECT 1
        FROM v_effective_stakeholder_consent c
        WHERE c.party_id = requested_party_id
          AND c.data_category = requested_category
          AND c.purpose = requested_purpose
          AND c.recipient_type = requested_recipient_type
          AND c.consented = TRUE
          AND (
              (c.scope_type = requested_scope_type AND c.scope_id IS NOT DISTINCT FROM requested_scope_id)
              OR (c.scope_type = 'network')
          )
    );
$$;

CREATE OR REPLACE FUNCTION enforce_stakeholder_consent_transition()
RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    plan_record RECORD;
BEGIN
    IF TG_TABLE_NAME = 'stakeholder_feedback'
       AND (NEW.status = 'published' OR NEW.is_public = TRUE) THEN
        IF NEW.party_id IS NULL
           OR NOT stakeholder_has_effective_consent(
               NEW.party_id, 'stakeholder_feedback',
               CASE WHEN NEW.is_public THEN 'public_summary' ELSE 'stakeholder_feedback_review' END,
               'location', NEW.location_id, 'system'
           ) THEN
            RAISE EXCEPTION 'canonical consent is required before publishing stakeholder feedback';
        END IF;
        NEW.canonical_consent_event_id := COALESCE(
            NEW.canonical_consent_event_id,
            (SELECT c.consent_event_id
             FROM v_effective_stakeholder_consent c
             WHERE c.party_id = NEW.party_id
               AND c.data_category = 'stakeholder_feedback'
               AND c.purpose = CASE WHEN NEW.is_public THEN 'public_summary' ELSE 'stakeholder_feedback_review' END
               AND c.consented = TRUE
             ORDER BY c.effective_at DESC LIMIT 1)
        );
    ELSIF TG_TABLE_NAME = 'stakeholder_touchpoint' AND NEW.status = 'completed' THEN
        SELECT p.* INTO plan_record
        FROM stakeholder_engagement_plan p
        WHERE p.id = NEW.plan_id;
        IF plan_record.stakeholder_party_id IS NULL
           OR NOT stakeholder_has_effective_consent(
               plan_record.stakeholder_party_id, 'stakeholder_engagement', NEW.purpose,
               plan_record.scope_type, plan_record.scope_id, 'system'
           ) THEN
            RAISE EXCEPTION 'canonical consent is required before completing stakeholder touchpoint';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_feedback_canonical_consent ON stakeholder_feedback;
CREATE TRIGGER trg_feedback_canonical_consent
BEFORE INSERT OR UPDATE ON stakeholder_feedback
FOR EACH ROW EXECUTE FUNCTION enforce_stakeholder_consent_transition();

DROP TRIGGER IF EXISTS trg_touchpoint_canonical_consent ON stakeholder_touchpoint;
CREATE TRIGGER trg_touchpoint_canonical_consent
BEFORE INSERT OR UPDATE ON stakeholder_touchpoint
FOR EACH ROW EXECUTE FUNCTION enforce_stakeholder_consent_transition();

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
WHERE sf.is_public = TRUE
  AND sf.consent_given = TRUE
  AND sf.status = 'published'
  AND NULLIF(TRIM(COALESCE(sf.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = sf.location_id
        AND fr.status IN ('verified', 'published')
  )
  AND (sf.party_id IS NULL OR stakeholder_has_effective_consent(
      sf.party_id, 'stakeholder_feedback', 'public_summary', 'location', sf.location_id, 'system'
  ));

COMMENT ON FUNCTION stakeholder_has_effective_consent IS 'Canonical consent check used by stakeholder workflow transitions';
