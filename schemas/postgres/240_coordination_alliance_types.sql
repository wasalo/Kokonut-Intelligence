-- ============================================================
-- 240_coordination_alliance_types.sql
-- ============================================================

ALTER TABLE coordination_alliance DROP CONSTRAINT IF EXISTS coordination_alliance_coordination_type_check;
ALTER TABLE coordination_alliance DROP CONSTRAINT IF EXISTS chk_coordination_type;
ALTER TABLE coordination_alliance ADD CONSTRAINT chk_coordination_type CHECK (
    coordination_type IN ('alliance', 'cooperative_network', 'knowledge_network', 'ecological_alliance',
                          'joint_venture', 'equity_alliance', 'nonequity_alliance')
);

COMMENT ON COLUMN coordination_alliance.coordination_type IS 'Coordination form distinction; equity or joint-venture labels do not automatically create ownership, financial rights, or reputation';
