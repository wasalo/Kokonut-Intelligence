-- ============================================================
-- 259_strategy_coherence.sql
-- Explainable strategy coherence findings.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_coherence_finding (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    rule_key VARCHAR(100) NOT NULL,
    entity_type VARCHAR(60) NOT NULL,
    entity_id UUID NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'informational')),
    explanation TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}',
    remediation TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'accepted', 'resolved', 'waived')),
    resolved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    resolution_note TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (strategy_plan_id, rule_key, entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_strategy_coherence_plan
    ON strategy_coherence_finding(strategy_plan_id, status, severity);
CREATE INDEX IF NOT EXISTS idx_strategy_coherence_entity
    ON strategy_coherence_finding(entity_type, entity_id, status);

CREATE OR REPLACE VIEW v_strategy_coherence_summary AS
SELECT strategy_plan_id,
       COUNT(*) FILTER (WHERE status = 'open') AS open_finding_count,
       COUNT(*) FILTER (WHERE status = 'open' AND severity = 'critical') AS critical_count,
       COUNT(*) FILTER (WHERE status = 'open' AND severity = 'high') AS high_count,
       COUNT(*) FILTER (WHERE status = 'open' AND severity = 'medium') AS medium_count,
       MAX(last_seen_at) AS last_checked_at
FROM strategy_coherence_finding
GROUP BY strategy_plan_id;

COMMENT ON TABLE strategy_coherence_finding IS 'Explainable strategy integrity findings; advisory until human resolution or waiver';
