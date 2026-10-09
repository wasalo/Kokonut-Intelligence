-- ============================================================
-- 187_state_model_triggers.sql - Instrument 4 more governed tables
-- ============================================================
-- Extends the lifecycle_transition ledger (179) to four high-value governed
-- tables so they participate in process mining, predictive BPM, the
-- process-health board, and auto-escalation:
--   * work_item            (workflow_spec state machine)
--   * market_order         (trade fulfillment; vocabulary enforced by CHECK)
--   * credit_retirement    (already 5-state; only needs a trigger)
--   * metric_value         (no status column; verified boolean mapped to draft/verified)

-- market_order: enforce vocabulary at the DB to keep the ledger clean.
ALTER TABLE market_order DROP CONSTRAINT IF EXISTS chk_market_order_status;
ALTER TABLE market_order ADD CONSTRAINT chk_market_order_status
    CHECK (status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled'));

DROP TRIGGER IF EXISTS trg_lt_work_item ON work_item;
CREATE TRIGGER trg_lt_work_item
    AFTER UPDATE OF status ON work_item
    FOR EACH ROW EXECUTE FUNCTION fn_record_lifecycle_transition();

DROP TRIGGER IF EXISTS trg_lt_market_order ON market_order;
CREATE TRIGGER trg_lt_market_order
    AFTER UPDATE OF status ON market_order
    FOR EACH ROW EXECUTE FUNCTION fn_record_lifecycle_transition();

DROP TRIGGER IF EXISTS trg_lt_credit_retirement ON credit_retirement;
CREATE TRIGGER trg_lt_credit_retirement
    AFTER UPDATE OF status ON credit_retirement
    FOR EACH ROW EXECUTE FUNCTION fn_record_lifecycle_transition();

-- metric_value has no status column; map the verified boolean to draft/verified.
CREATE OR REPLACE FUNCTION fn_record_metric_lifecycle()
RETURNS TRIGGER AS $$
DECLARE
    v_actor_id UUID;
    v_actor_type VARCHAR(50);
    from_s VARCHAR(50);
    to_s VARCHAR(50);
BEGIN
    IF TG_OP = 'INSERT' THEN
        from_s := NULL;
        to_s := 'draft';
    ELSE
        IF OLD.verified IS NOT DISTINCT FROM NEW.verified THEN
            RETURN NEW;
        END IF;
        from_s := CASE WHEN OLD.verified THEN 'verified' ELSE 'draft' END;
        to_s := CASE WHEN NEW.verified THEN 'verified' ELSE 'draft' END;
    END IF;
    BEGIN
        v_actor_id := NULLIF(current_setting('kokonut.actor_id', true), '')::UUID;
    EXCEPTION WHEN OTHERS THEN
        v_actor_id := NULL;
    END;
    BEGIN
        v_actor_type := NULLIF(current_setting('kokonut.actor_type', true), '');
    EXCEPTION WHEN OTHERS THEN
        v_actor_type := NULL;
    END;
    INSERT INTO lifecycle_transition (
        entity_type, entity_id, from_status, to_status, actor_id, actor_type
    ) VALUES (
        'metric_value', NEW.id, from_s, to_s, v_actor_id, v_actor_type
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_lt_metric_value ON metric_value;
CREATE TRIGGER trg_lt_metric_value
    AFTER INSERT OR UPDATE OF verified ON metric_value
    FOR EACH ROW EXECUTE FUNCTION fn_record_metric_lifecycle();
