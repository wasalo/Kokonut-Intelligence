-- Ecocredit Module Enhancements: Enrollment, Bridge, Batch Improvements

-- ============================================================
-- project_credit_class_enrollment (apply → approve/reject/terminate)
-- ============================================================
CREATE TABLE IF NOT EXISTS project_credit_class_enrollment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    credit_class_id UUID NOT NULL REFERENCES credit_class(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'applied',
    application_metadata TEXT,
    enrollment_metadata TEXT,
    applied_by VARCHAR(42),
    evaluated_by VARCHAR(42),
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    evaluated_at TIMESTAMPTZ,
    UNIQUE(location_id, credit_class_id),
    CONSTRAINT chk_enrollment_status CHECK (status IN (
        'applied', 'changes_requested', 'accepted', 'rejected', 'terminated'
    ))
);

CREATE INDEX idx_pce_location ON project_credit_class_enrollment(location_id);
CREATE INDEX idx_pce_class ON project_credit_class_enrollment(credit_class_id);
CREATE INDEX idx_pce_status ON project_credit_class_enrollment(status);

-- ============================================================
-- Batch improvements: open, jurisdiction, origin_tx
-- ============================================================
ALTER TABLE credit_batch ADD COLUMN IF NOT EXISTS is_open BOOLEAN DEFAULT FALSE;
ALTER TABLE credit_batch ADD COLUMN IF NOT EXISTS jurisdiction VARCHAR(50);
ALTER TABLE credit_batch ADD COLUMN IF NOT EXISTS origin_tx_id VARCHAR(255);
ALTER TABLE credit_batch ADD COLUMN IF NOT EXISTS origin_tx_source VARCHAR(100);
ALTER TABLE credit_batch ADD COLUMN IF NOT EXISTS origin_tx_contract VARCHAR(42);

-- ============================================================
-- credit_batch_contract (link batch to on-chain contract)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_batch_contract (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_batch_id UUID NOT NULL REFERENCES credit_batch(id) ON DELETE CASCADE,
    contract_address VARCHAR(42) NOT NULL,
    chain VARCHAR(50) NOT NULL,
    class_id UUID REFERENCES credit_class(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(credit_batch_id, chain)
);

CREATE INDEX idx_cbc_batch ON credit_batch_contract(credit_batch_id);
CREATE INDEX idx_cbc_contract ON credit_batch_contract(contract_address);

-- ============================================================
-- credit_bridge_transaction (cross-chain bridge tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_bridge_transaction (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    direction VARCHAR(10) NOT NULL,
    source_chain VARCHAR(50) NOT NULL,
    target_chain VARCHAR(50) NOT NULL,
    sender_address VARCHAR(42),
    recipient_address VARCHAR(42),
    credit_batch_id UUID REFERENCES credit_batch(id),
    quantity NUMERIC(14,4) NOT NULL,
    origin_tx_id VARCHAR(255),
    origin_tx_source VARCHAR(100),
    bridge_tx_hash VARCHAR(66),
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    CONSTRAINT chk_bridge_direction CHECK (direction IN ('outbound', 'inbound')),
    CONSTRAINT chk_bridge_status CHECK (status IN ('pending', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX idx_cbt_direction ON credit_bridge_transaction(direction);
CREATE INDEX idx_cbt_source ON credit_bridge_transaction(source_chain);
CREATE INDEX idx_cbt_target ON credit_bridge_transaction(target_chain);
CREATE INDEX idx_cbt_batch ON credit_bridge_transaction(credit_batch_id);
CREATE INDEX idx_cbt_status ON credit_bridge_transaction(status);
