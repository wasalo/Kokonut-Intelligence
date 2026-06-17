-- ============================================================
-- 017_fr_gaps.sql — FR gap fixes: FKs, schema_version, agent logging, high_risk
-- ============================================================

-- FR7: Add direct FK from treasury_event to capital_source
ALTER TABLE treasury_event
    ADD COLUMN IF NOT EXISTS capital_source_id UUID REFERENCES capital_source(id);

CREATE INDEX IF NOT EXISTS idx_treasury_capital_source ON treasury_event(capital_source_id);

-- FR7: Add user_id to digital_lego_usage for direct user linkage
ALTER TABLE digital_lego_usage
    ADD COLUMN IF NOT EXISTS user_id UUID;
ALTER TABLE digital_lego_usage
    ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_dlego_user ON digital_lego_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_dlego_verified ON digital_lego_usage(verified);

-- FR1: Add schema_version to master tables that lack it
ALTER TABLE location ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50) DEFAULT 'common-data-schema-v1';
ALTER TABLE farm ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50) DEFAULT 'common-data-schema-v1';
ALTER TABLE plot ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50) DEFAULT 'common-data-schema-v1';
ALTER TABLE partner ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50) DEFAULT 'common-data-schema-v1';
ALTER TABLE infrastructure_asset ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50) DEFAULT 'common-data-schema-v1';
ALTER TABLE staff ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50) DEFAULT 'common-data-schema-v1';
ALTER TABLE crop ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50) DEFAULT 'common-data-schema-v1';
ALTER TABLE expense_category ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50) DEFAULT 'common-data-schema-v1';
ALTER TABLE capital_source ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50) DEFAULT 'common-data-schema-v1';

ALTER TABLE location ALTER COLUMN schema_version TYPE VARCHAR(50);
ALTER TABLE farm ALTER COLUMN schema_version TYPE VARCHAR(50);
ALTER TABLE plot ALTER COLUMN schema_version TYPE VARCHAR(50);
ALTER TABLE partner ALTER COLUMN schema_version TYPE VARCHAR(50);
ALTER TABLE infrastructure_asset ALTER COLUMN schema_version TYPE VARCHAR(50);
ALTER TABLE staff ALTER COLUMN schema_version TYPE VARCHAR(50);
ALTER TABLE crop ALTER COLUMN schema_version TYPE VARCHAR(50);
ALTER TABLE expense_category ALTER COLUMN schema_version TYPE VARCHAR(50);
ALTER TABLE capital_source ALTER COLUMN schema_version TYPE VARCHAR(50);

-- FR10: Add high_risk flag and action initiator to agent tables
ALTER TABLE agent_task ADD COLUMN IF NOT EXISTS high_risk BOOLEAN DEFAULT FALSE;
ALTER TABLE agent_task ADD COLUMN IF NOT EXISTS initiator_type VARCHAR(50) DEFAULT 'agent';
ALTER TABLE agent_task ADD COLUMN IF NOT EXISTS initiator_id UUID;

ALTER TABLE agent_action_log ADD COLUMN IF NOT EXISTS high_risk BOOLEAN DEFAULT FALSE;
ALTER TABLE agent_action_log ADD COLUMN IF NOT EXISTS requires_human_approval BOOLEAN DEFAULT FALSE;

-- FR9: Add immutability marker to report_snapshot
ALTER TABLE report_snapshot ADD COLUMN IF NOT EXISTS frozen BOOLEAN DEFAULT FALSE;
ALTER TABLE report_snapshot ADD COLUMN IF NOT EXISTS frozen_at TIMESTAMPTZ;
ALTER TABLE report_snapshot ADD COLUMN IF NOT EXISTS frozen_by UUID;

-- Prevent updates to frozen snapshots via trigger
CREATE OR REPLACE FUNCTION prevent_frozen_update()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.frozen = TRUE THEN
        RAISE EXCEPTION 'Cannot modify frozen snapshot %', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_frozen_update ON report_snapshot;
CREATE TRIGGER trg_prevent_frozen_update
    BEFORE UPDATE ON report_snapshot
    FOR EACH ROW
    EXECUTE FUNCTION prevent_frozen_update();
