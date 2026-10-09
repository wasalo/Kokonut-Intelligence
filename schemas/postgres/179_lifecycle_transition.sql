-- ============================================================
-- 179_lifecycle_transition.sql - Lifecycle transition ledger (VSM)
-- ============================================================
-- Generic, append-only ledger capturing every 5-state lifecycle
-- transition (draft -> submitted -> verified -> published -> rejected)
-- for governed pipeline entities. Enables value-stream lead time,
-- first-time-through yield, rework rate, and WIP analytics without
-- touching the ~50 call sites that update status.
--
-- Triggers fire AFTER UPDATE OF status (or review_status) and record
-- the transition only when the value actually changes. Actor is
-- enriched from the optional session variables kokonut.actor_id /
-- kokonut.actor_type when the application (or Directus hook) sets them.

CREATE TABLE IF NOT EXISTS lifecycle_transition (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    from_status VARCHAR(50),
    to_status VARCHAR(50) NOT NULL,
    transitioned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_id UUID,
    actor_type VARCHAR(50),
    source_event_id UUID,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lt_entity ON lifecycle_transition(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_lt_to_status ON lifecycle_transition(to_status);
CREATE INDEX IF NOT EXISTS idx_lt_transitioned_at ON lifecycle_transition(transitioned_at);

-- Status-column lifecycle trigger (data_stream_post, ai_summary, etc.)
CREATE OR REPLACE FUNCTION fn_record_lifecycle_transition()
RETURNS TRIGGER AS $$
DECLARE
    v_actor_id UUID;
    v_actor_type VARCHAR(50);
BEGIN
    IF OLD.status IS NOT DISTINCT FROM NEW.status THEN
        RETURN NEW;
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
        TG_TABLE_NAME, NEW.id, OLD.status, NEW.status, v_actor_id, v_actor_type
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Review-status trigger (agent_task.review_status is the 5-state axis)
CREATE OR REPLACE FUNCTION fn_record_review_transition()
RETURNS TRIGGER AS $$
DECLARE
    v_actor_id UUID;
    v_actor_type VARCHAR(50);
BEGIN
    IF OLD.review_status IS NOT DISTINCT FROM NEW.review_status THEN
        RETURN NEW;
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
        TG_TABLE_NAME, NEW.id, OLD.review_status, NEW.review_status, v_actor_id, v_actor_type
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_lt_data_stream_post ON data_stream_post;
CREATE TRIGGER trg_lt_data_stream_post
    AFTER UPDATE OF status ON data_stream_post
    FOR EACH ROW EXECUTE FUNCTION fn_record_lifecycle_transition();

DROP TRIGGER IF EXISTS trg_lt_ai_summary ON ai_summary;
CREATE TRIGGER trg_lt_ai_summary
    AFTER UPDATE OF status ON ai_summary
    FOR EACH ROW EXECUTE FUNCTION fn_record_lifecycle_transition();

DROP TRIGGER IF EXISTS trg_lt_impact_claim ON impact_claim;
CREATE TRIGGER trg_lt_impact_claim
    AFTER UPDATE OF status ON impact_claim
    FOR EACH ROW EXECUTE FUNCTION fn_record_lifecycle_transition();

DROP TRIGGER IF EXISTS trg_lt_report_snapshot ON report_snapshot;
CREATE TRIGGER trg_lt_report_snapshot
    AFTER UPDATE OF status ON report_snapshot
    FOR EACH ROW EXECUTE FUNCTION fn_record_lifecycle_transition();

DROP TRIGGER IF EXISTS trg_lt_stakeholder_feedback ON stakeholder_feedback;
CREATE TRIGGER trg_lt_stakeholder_feedback
    AFTER UPDATE OF status ON stakeholder_feedback
    FOR EACH ROW EXECUTE FUNCTION fn_record_lifecycle_transition();

DROP TRIGGER IF EXISTS trg_lt_farm_activity ON farm_activity;
CREATE TRIGGER trg_lt_farm_activity
    AFTER UPDATE OF status ON farm_activity
    FOR EACH ROW EXECUTE FUNCTION fn_record_lifecycle_transition();

DROP TRIGGER IF EXISTS trg_lt_harvest_event ON harvest_event;
CREATE TRIGGER trg_lt_harvest_event
    AFTER UPDATE OF status ON harvest_event
    FOR EACH ROW EXECUTE FUNCTION fn_record_lifecycle_transition();

DROP TRIGGER IF EXISTS trg_lt_agent_task ON agent_task;
CREATE TRIGGER trg_lt_agent_task
    AFTER UPDATE OF review_status ON agent_task
    FOR EACH ROW EXECUTE FUNCTION fn_record_review_transition();
