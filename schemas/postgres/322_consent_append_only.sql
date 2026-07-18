-- ============================================================
-- 322_consent_append_only.sql
-- Protect canonical consent chronology and event history.
-- ============================================================

CREATE OR REPLACE FUNCTION prevent_stakeholder_consent_mutation()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'stakeholder_consent is append-only; record a new event';
END;
$$;

DROP TRIGGER IF EXISTS trg_stakeholder_consent_append_only ON stakeholder_consent;
CREATE TRIGGER trg_stakeholder_consent_append_only
    BEFORE UPDATE OR DELETE ON stakeholder_consent
    FOR EACH ROW EXECUTE FUNCTION prevent_stakeholder_consent_mutation();

CREATE OR REPLACE FUNCTION validate_stakeholder_consent_chronology()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.effective_at < NEW.created_at
       AND NEW.consent_method <> 'system_migration' THEN
        RAISE EXCEPTION
            'effective_at cannot precede created_at except for system migrations';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_stakeholder_consent_chronology ON stakeholder_consent;
CREATE TRIGGER trg_stakeholder_consent_chronology
    BEFORE INSERT ON stakeholder_consent
    FOR EACH ROW EXECUTE FUNCTION validate_stakeholder_consent_chronology();

COMMENT ON FUNCTION prevent_stakeholder_consent_mutation() IS
    'Canonical consent events cannot be updated or deleted; append a correction event.';
