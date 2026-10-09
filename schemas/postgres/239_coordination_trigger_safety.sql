-- ============================================================
-- 239_coordination_trigger_safety.sql
-- ============================================================
-- Keep table-specific trigger records separate: PostgreSQL NEW records
-- do not expose columns from another table to a shared trigger function.

CREATE OR REPLACE FUNCTION enforce_coordination_alliance_governance()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IN ('approved', 'active') THEN
        IF NEW.approved_by_party_id IS NULL OR NEW.approved_at IS NULL THEN
            RAISE EXCEPTION 'human approval is required before alliance approval or activation';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM coordination_conflict_declaration
            WHERE alliance_id = NEW.id AND status IN ('reviewed', 'managed', 'dismissed')
        ) THEN
            RAISE EXCEPTION 'conflict or no-conflict declaration must be reviewed before alliance approval';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM coordination_benefit_harm_analysis
            WHERE alliance_id = NEW.id AND status IN ('reviewed', 'accepted')
        ) THEN
            RAISE EXCEPTION 'benefit/harm analysis must be reviewed before alliance approval';
        END IF;
        IF NEW.coordination_type = 'ecological_alliance' AND NOT EXISTS (
            SELECT 1 FROM stewardship_proxy_authority
            WHERE id = NEW.proxy_authority_id AND status = 'active'
        ) THEN
            RAISE EXCEPTION 'active proxy authority is required for ecological alliance approval';
        END IF;
    END IF;
    IF NEW.publication_status = 'published' THEN
        IF NEW.public_summary IS NULL OR BTRIM(NEW.public_summary) = '' OR NEW.published_by_party_id IS NULL OR NEW.published_at IS NULL THEN
            RAISE EXCEPTION 'published alliance output requires summary, human publisher, and publication timestamp';
        END IF;
        IF NEW.status NOT IN ('active', 'completed') THEN
            RAISE EXCEPTION 'only active or completed alliances may be published';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_coordination_exchange_consent()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'completed' AND NEW.consent_event_id IS NULL THEN
        RAISE EXCEPTION 'consent is required before completing knowledge exchange';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_coordination_governance ON coordination_alliance;
CREATE TRIGGER trg_coordination_governance
    BEFORE INSERT OR UPDATE ON coordination_alliance
    FOR EACH ROW EXECUTE FUNCTION enforce_coordination_alliance_governance();

DROP TRIGGER IF EXISTS trg_coordination_exchange_consent ON coordination_knowledge_exchange;
CREATE TRIGGER trg_coordination_exchange_consent
    BEFORE INSERT OR UPDATE ON coordination_knowledge_exchange
    FOR EACH ROW EXECUTE FUNCTION enforce_coordination_exchange_consent();
