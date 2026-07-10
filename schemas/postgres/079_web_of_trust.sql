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

-- ============================================================
-- 079_web_of_trust.sql — PR-2: Preferences, Rankings, Cascade
-- ============================================================

-- 5. Continuous preference signals
CREATE TABLE IF NOT EXISTS preference_signal (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evaluator_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    signal_type VARCHAR(50) NOT NULL,
    subject_type VARCHAR(100) NOT NULL,
    subject_id UUID NOT NULL,
    preference_value NUMERIC(5,4),
    preference_rank INTEGER,
    decay_rate NUMERIC(5,4) DEFAULT 0.0100,
    weight NUMERIC(5,4) DEFAULT 1.0000,
    expires_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pref_evaluator ON preference_signal(evaluator_id);
CREATE INDEX IF NOT EXISTS idx_pref_type ON preference_signal(signal_type);
CREATE INDEX IF NOT EXISTS idx_pref_subject ON preference_signal(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_pref_created ON preference_signal(created_at);

ALTER TABLE preference_signal DROP CONSTRAINT IF EXISTS chk_pref_type;
ALTER TABLE preference_signal ADD CONSTRAINT chk_pref_type CHECK (
    signal_type IN ('metric_preference', 'evaluator_trust', 'capital_allocation', 'methodology_preference')
);

-- 6. Ranking algorithms
CREATE TABLE IF NOT EXISTS ranking_algorithm (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    algorithm_key VARCHAR(100) NOT NULL UNIQUE,
    algorithm_name VARCHAR(255) NOT NULL,
    description TEXT,
    weighting_config JSONB NOT NULL,
    author_evaluator_id UUID REFERENCES evaluator(id) ON DELETE SET NULL,
    is_default BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rank_algo_key ON ranking_algorithm(algorithm_key);
CREATE INDEX IF NOT EXISTS idx_rank_algo_status ON ranking_algorithm(status);

ALTER TABLE ranking_algorithm DROP CONSTRAINT IF EXISTS chk_rank_algo_status;
ALTER TABLE ranking_algorithm ADD CONSTRAINT chk_rank_algo_status CHECK (
    status IN ('active', 'inactive', 'deprecated')
);

-- 7. Ranking results
CREATE TABLE IF NOT EXISTS ranking_result (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    algorithm_id UUID NOT NULL REFERENCES ranking_algorithm(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    ranking_period VARCHAR(20) NOT NULL,
    rank INTEGER NOT NULL,
    score NUMERIC(8,4) NOT NULL,
    dimension_scores JSONB,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(algorithm_id, location_id, ranking_period)
);

CREATE INDEX IF NOT EXISTS idx_rank_result_algo ON ranking_result(algorithm_id);
CREATE INDEX IF NOT EXISTS idx_rank_result_location ON ranking_result(location_id);
CREATE INDEX IF NOT EXISTS idx_rank_result_period ON ranking_result(ranking_period);
CREATE INDEX IF NOT EXISTS idx_rank_result_rank ON ranking_result(ranking_period, rank);

-- 8. Public ranking view
CREATE OR REPLACE VIEW v_public_ranking_comparison AS
SELECT
    ra.algorithm_key,
    ra.algorithm_name,
    rr.ranking_period,
    rr.rank,
    rr.score,
    rr.dimension_scores,
    l.name AS location_name,
    rr.location_id
FROM ranking_result rr
JOIN ranking_algorithm ra ON ra.id = rr.algorithm_id
JOIN location l ON l.id = rr.location_id
WHERE ra.status = 'active'
AND EXISTS (
    SELECT 1 FROM farm_registry_record fr
    WHERE fr.location_id = rr.location_id
    AND fr.status IN ('verified', 'published')
)
ORDER BY rr.ranking_period DESC, ra.algorithm_key, rr.rank;

-- ============================================================
-- 079_web_of_trust.sql — PR-3: Network Value + Trust Graph
-- ============================================================

-- 9. Network value view (Metcalfe's law)
CREATE OR REPLACE VIEW v_network_value AS
SELECT
    (SELECT COUNT(*) FROM location WHERE status = 'active') AS active_farms,
    (SELECT COUNT(*) FROM evaluator WHERE status = 'active') AS active_evaluators,
    (SELECT COUNT(*) FROM attestation_record WHERE status = 'published') AS published_attestations,
    (SELECT COUNT(*) FROM stakeholder_feedback WHERE consent_given = TRUE) AS consented_feedbacks,
    (SELECT COUNT(*) FROM carbon_credit WHERE status = 'published') AS published_credits,
    (SELECT COUNT(*) FROM evaluator WHERE status = 'active') *
    (GREATEST((SELECT COUNT(*) FROM evaluator WHERE status = 'active'), 1) - 1) / 2 AS evaluator_network_value,
    (SELECT COUNT(*) FROM attestation_record WHERE status = 'published') *
    (GREATEST((SELECT COUNT(*) FROM attestation_record WHERE status = 'published'), 1) - 1) / 2 AS attestation_network_value,
    (SELECT COUNT(*) FROM attestation_reference) AS total_cross_references,
    (SELECT COUNT(*) FROM preference_signal ps JOIN evaluator e ON e.id = ps.evaluator_id WHERE e.status = 'active') AS total_preferences;

-- 10. Evaluator trust graph view
CREATE OR REPLACE VIEW v_evaluator_trust_graph AS
SELECT
    ar.id AS reference_id,
    e1.id AS source_evaluator_id,
    e1.display_name AS source_name,
    e1.evaluator_type AS source_type,
    e1.trust_score AS source_trust,
    ar.reference_type AS edge_type,
    a1.attestation_uid AS source_attestation_uid,
    a2.attestation_uid AS target_attestation_uid,
    ar.strength AS edge_weight,
    ar.created_at
FROM attestation_reference ar
JOIN attestation_record a1 ON a1.id = ar.source_attestation_id
JOIN attestation_record a2 ON a2.id = ar.target_attestation_id
JOIN evaluator e1 ON e1.id = ar.evaluator_id
WHERE ar.evaluator_id IS NOT NULL
ORDER BY ar.created_at DESC;
