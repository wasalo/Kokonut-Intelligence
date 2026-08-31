-- ============================================================
-- 356_safe_settlement.sql — SAFE settlement tracking (KI-14 D3)
-- ============================================================
-- Marketplace value moves are proposed to the Core Team SAFE (Gnosis)
-- instead of raw DB-only escrow updates. Track the SAFE proposal so the
-- order book reflects execution once humans confirm.

ALTER TABLE credit_sell_order
    ADD COLUMN IF NOT EXISTS safe_settlement_tx_hash VARCHAR(66);
ALTER TABLE credit_sell_order
    ADD COLUMN IF NOT EXISTS settlement_status VARCHAR(50) DEFAULT 'pending';

ALTER TABLE credit_buy_order
    ADD COLUMN IF NOT EXISTS safe_settlement_tx_hash VARCHAR(66);
ALTER TABLE credit_buy_order
    ADD COLUMN IF NOT EXISTS settlement_status VARCHAR(50) DEFAULT 'pending';

CREATE INDEX IF NOT EXISTS idx_credit_sell_order_settlement
    ON credit_sell_order(safe_settlement_tx_hash);
CREATE INDEX IF NOT EXISTS idx_credit_buy_order_settlement
    ON credit_buy_order(safe_settlement_tx_hash);

ALTER TABLE credit_sell_order DROP CONSTRAINT IF EXISTS chk_sell_order_settlement;
ALTER TABLE credit_sell_order ADD CONSTRAINT chk_sell_order_settlement CHECK (
    settlement_status IN ('pending', 'proposed', 'confirmed', 'executed', 'failed')
);

ALTER TABLE credit_buy_order DROP CONSTRAINT IF EXISTS chk_buy_order_settlement;
ALTER TABLE credit_buy_order ADD CONSTRAINT chk_buy_order_settlement CHECK (
    settlement_status IN ('pending', 'proposed', 'confirmed', 'executed', 'failed')
);

INSERT INTO schema_version (version, description, applied_by)
VALUES ('safe-settlement-v1', 'SAFE settlement tracking on marketplace orders (KI-14 D3)', 'schema 356')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
