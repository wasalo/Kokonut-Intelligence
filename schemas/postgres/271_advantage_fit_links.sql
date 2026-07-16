-- ============================================================
-- 271_advantage_fit_links.sql
-- Link defensible advantages to the operating model and choices.
-- ============================================================

ALTER TABLE strategy_choice
    ADD COLUMN IF NOT EXISTS target_position_id UUID REFERENCES strategy_position(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS expected_advantage_id UUID REFERENCES strategy_advantage(id) ON DELETE SET NULL;

ALTER TABLE strategy_investment_case
    ADD COLUMN IF NOT EXISTS advantage_id UUID REFERENCES strategy_advantage(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS strategy_advantage_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    advantage_id UUID NOT NULL REFERENCES strategy_advantage(id) ON DELETE CASCADE,
    entity_type VARCHAR(30) NOT NULL CHECK (entity_type IN ('capability', 'process', 'service', 'value_stream', 'strategy_choice', 'investment')),
    entity_id UUID NOT NULL,
    relationship VARCHAR(20) NOT NULL CHECK (relationship IN ('required', 'supports', 'evidence', 'funded_by')),
    strength NUMERIC(5,2) NOT NULL DEFAULT 50 CHECK (strength BETWEEN 0 AND 100),
    rationale TEXT,
    evidence JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (advantage_id, entity_type, entity_id, relationship)
);

CREATE INDEX IF NOT EXISTS idx_strategy_advantage_link_advantage ON strategy_advantage_link(advantage_id, relationship);
CREATE INDEX IF NOT EXISTS idx_strategy_advantage_link_entity ON strategy_advantage_link(entity_type, entity_id);

CREATE OR REPLACE VIEW v_strategy_advantage_fit AS
SELECT sa.id AS advantage_id,
       sa.strategy_plan_id,
       sa.name,
       sa.defensibility_score,
       sa.status,
       COUNT(sal.id) AS link_count,
       COUNT(sal.id) FILTER (WHERE sal.entity_type = 'capability') AS capability_link_count,
       COUNT(sal.id) FILTER (WHERE sal.entity_type = 'strategy_choice') AS choice_link_count,
       COUNT(sal.id) FILTER (WHERE sal.entity_type = 'investment') AS investment_link_count,
       CASE WHEN COUNT(sal.id) FILTER (WHERE sal.entity_type = 'capability') > 0
             AND COUNT(sal.id) FILTER (WHERE sal.entity_type = 'investment') > 0 THEN 'fit'
            WHEN COUNT(sal.id) > 0 THEN 'partial' ELSE 'unlinked' END AS fit_status
FROM strategy_advantage sa
LEFT JOIN strategy_advantage_link sal ON sal.advantage_id = sa.id
GROUP BY sa.id, sa.strategy_plan_id, sa.name, sa.defensibility_score, sa.status;

COMMENT ON TABLE strategy_advantage_link IS 'Links claimed competitive advantages to capabilities, value chain, choices, evidence, and funded investments';
