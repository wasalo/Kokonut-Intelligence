-- ============================================================
-- 079_web_of_trust.sql — Impact Web of Trust
-- ============================================================
-- Evaluator registry, attester reputation, and cross-attestation
-- linking for the Impact Web of Trust.
-- ============================================================

-- 1. Evaluator registry (supports wallet, DID, and ENS)
CREATE TABLE IF NOT EXISTS evaluator (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_address VARCHAR(42),
    did VARCHAR(255),
    ens_name VARCHAR(255),
    evaluator_type VARCHAR(50) NOT NULL,
    display_name VARCHAR(255),
    domain_expertise TEXT[] DEFAULT '{}',
    specialization VARCHAR(255),
    organization VARCHAR(255),
    credentials TEXT,
    total_attestations INTEGER DEFAULT 0,
    revoked_attestations INTEGER DEFAULT 0,
    accuracy_score NUMERIC(5,4) DEFAULT 0.5000,
    trust_score NUMERIC(5,4) DEFAULT 0.5000,
    last_active_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CHECK (wallet_address IS NOT NULL OR did IS NOT NULL OR ens_name IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_evaluator_wallet ON evaluator(wallet_address) WHERE wallet_address IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_evaluator_did ON evaluator(did) WHERE did IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_evaluator_ens ON evaluator(ens_name) WHERE ens_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_evaluator_type ON evaluator(evaluator_type);
CREATE INDEX IF NOT EXISTS idx_evaluator_status ON evaluator(status);
CREATE INDEX IF NOT EXISTS idx_evaluator_trust ON evaluator(trust_score DESC);

ALTER TABLE evaluator DROP CONSTRAINT IF EXISTS chk_evaluator_type;
ALTER TABLE evaluator ADD CONSTRAINT chk_evaluator_type CHECK (
    evaluator_type IN ('citizen', 'professional', 'expert', 'funder', 'self')
);

ALTER TABLE evaluator DROP CONSTRAINT IF EXISTS chk_evaluator_status;
ALTER TABLE evaluator ADD CONSTRAINT chk_evaluator_status CHECK (
    status IN ('active', 'inactive', 'suspended', 'revoked')
);

ALTER TABLE evaluator DROP CONSTRAINT IF EXISTS chk_evaluator_accuracy;
ALTER TABLE evaluator ADD CONSTRAINT chk_evaluator_accuracy CHECK (
    accuracy_score >= 0 AND accuracy_score <= 1
);

ALTER TABLE evaluator DROP CONSTRAINT IF EXISTS chk_evaluator_trust;
ALTER TABLE evaluator ADD CONSTRAINT chk_evaluator_trust CHECK (
    trust_score >= 0 AND trust_score <= 1
);

-- 2. Attester reputation event log
CREATE TABLE IF NOT EXISTS attester_reputation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evaluator_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    attestation_id UUID,
    score_delta NUMERIC(5,4),
    reason TEXT,
    computed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reputation_evaluator ON attester_reputation(evaluator_id);
CREATE INDEX IF NOT EXISTS idx_reputation_event ON attester_reputation(event_type);
CREATE INDEX IF NOT EXISTS idx_reputation_computed ON attester_reputation(computed_at);

ALTER TABLE attester_reputation DROP CONSTRAINT IF EXISTS chk_reputation_event;
ALTER TABLE attester_reputation ADD CONSTRAINT chk_reputation_event CHECK (
    event_type IN (
        'attestation_made', 'attestation_verified', 'attestation_revoked',
        'review_completed', 'accuracy_confirmed', 'accuracy_disputed',
        'evaluator_registered', 'evaluator_suspended', 'evaluator_reactivated'
    )
);

-- 3. Cross-attestation linking
CREATE TABLE IF NOT EXISTS attestation_reference (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_attestation_id UUID NOT NULL REFERENCES attestation_record(id) ON DELETE CASCADE,
    target_attestation_id UUID NOT NULL REFERENCES attestation_record(id) ON DELETE CASCADE,
    reference_type VARCHAR(50) NOT NULL,
    strength NUMERIC(3,2) DEFAULT 1.00,
    evaluator_id UUID REFERENCES evaluator(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_attestation_id, target_attestation_id, reference_type)
);

CREATE INDEX IF NOT EXISTS idx_attref_source ON attestation_reference(source_attestation_id);
CREATE INDEX IF NOT EXISTS idx_attref_target ON attestation_reference(target_attestation_id);
CREATE INDEX IF NOT EXISTS idx_attref_type ON attestation_reference(reference_type);
CREATE INDEX IF NOT EXISTS idx_attref_evaluator ON attestation_reference(evaluator_id);

ALTER TABLE attestation_reference DROP CONSTRAINT IF EXISTS chk_attref_type;
ALTER TABLE attestation_reference ADD CONSTRAINT chk_attref_type CHECK (
    reference_type IN ('supports', 'contradicts', 'supersedes', 'extends', 'validates')
);

ALTER TABLE attestation_reference DROP CONSTRAINT IF EXISTS chk_attref_strength;
ALTER TABLE attestation_reference ADD CONSTRAINT chk_attref_strength CHECK (
    strength >= 0 AND strength <= 1
);

-- 4. Public evaluator view
CREATE OR REPLACE VIEW v_public_evaluator_directory AS
SELECT
    id,
    evaluator_type,
    display_name,
    domain_expertise,
    specialization,
    organization,
    total_attestations,
    accuracy_score,
    trust_score,
    last_active_at,
    status
FROM evaluator
WHERE status = 'active'
AND trust_score >= 0.3
ORDER BY trust_score DESC;
