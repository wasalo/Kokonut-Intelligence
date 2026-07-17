-- ============================================================
-- 318_guild_protocol_projection.sql
-- PostgreSQL projections for the self-hosted Kokonut Guild protocol.
-- ============================================================

ALTER TABLE kgp_protocol_deployment
    ADD COLUMN IF NOT EXISTS registry_address VARCHAR(42),
    ADD COLUMN IF NOT EXISTS domain_address VARCHAR(42),
    ADD COLUMN IF NOT EXISTS task_board_address VARCHAR(42),
    ADD COLUMN IF NOT EXISTS evidence_review_address VARCHAR(42),
    ADD COLUMN IF NOT EXISTS governance_address VARCHAR(42);

ALTER TABLE kgp_protocol_deployment
    DROP CONSTRAINT IF EXISTS chk_kgp_deployment_component_addresses;
ALTER TABLE kgp_protocol_deployment
    ADD CONSTRAINT chk_kgp_deployment_component_addresses CHECK (
        (registry_address IS NULL OR registry_address ~ '^0x[0-9a-fA-F]{40}$') AND
        (domain_address IS NULL OR domain_address ~ '^0x[0-9a-fA-F]{40}$') AND
        (task_board_address IS NULL OR task_board_address ~ '^0x[0-9a-fA-F]{40}$') AND
        (evidence_review_address IS NULL OR evidence_review_address ~ '^0x[0-9a-fA-F]{40}$') AND
        (governance_address IS NULL OR governance_address ~ '^0x[0-9a-fA-F]{40}$')
    );

ALTER TABLE guild_reputation_event
    ADD COLUMN IF NOT EXISTS task_id UUID,
    ADD COLUMN IF NOT EXISTS evidence_review_id UUID;

CREATE TABLE IF NOT EXISTS guild_domain (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id UUID NOT NULL REFERENCES kokonut_guild(id) ON DELETE CASCADE,
    deployment_id UUID REFERENCES kgp_protocol_deployment(id),
    onchain_domain_id BIGINT NOT NULL CHECK (onchain_domain_id > 0),
    parent_onchain_domain_id BIGINT CHECK (parent_onchain_domain_id IS NULL OR parent_onchain_domain_id > 0),
    domain_key VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    purpose TEXT,
    metadata_uri TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'deprecated')),
    lifecycle_status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (lifecycle_status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(guild_id, domain_key),
    UNIQUE(deployment_id, onchain_domain_id)
);

CREATE INDEX IF NOT EXISTS idx_guild_domain_guild
    ON guild_domain(guild_id, status);

CREATE TABLE IF NOT EXISTS guild_task (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id UUID NOT NULL REFERENCES kokonut_guild(id) ON DELETE CASCADE,
    domain_id UUID NOT NULL REFERENCES guild_domain(id),
    deployment_id UUID REFERENCES kgp_protocol_deployment(id),
    onchain_task_id BIGINT,
    task_key VARCHAR(255) NOT NULL,
    task_type VARCHAR(100) NOT NULL DEFAULT 'contribution',
    contributor_id UUID REFERENCES guild_contributor(id),
    contributor_wallet VARCHAR(42),
    reward_amount NUMERIC(30, 6) NOT NULL DEFAULT 0 CHECK (reward_amount >= 0),
    reward_token VARCHAR(42),
    deadline TIMESTAMPTZ,
    evidence_requirement_hash VARCHAR(66),
    submitted_evidence_hash VARCHAR(66),
    metadata_uri TEXT,
    task_status VARCHAR(50) NOT NULL DEFAULT 'open'
        CHECK (task_status IN ('open', 'assigned', 'submitted', 'accepted', 'rejected', 'disputed', 'cancelled', 'paid')),
    lifecycle_status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (lifecycle_status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    transaction_hash VARCHAR(66),
    block_number BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (contributor_wallet IS NULL OR contributor_wallet ~ '^0x[0-9a-fA-F]{40}$'),
    CHECK (reward_token IS NULL OR reward_token ~ '^0x[0-9a-fA-F]{40}$'),
    CHECK (evidence_requirement_hash IS NULL OR evidence_requirement_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (submitted_evidence_hash IS NULL OR submitted_evidence_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (transaction_hash IS NULL OR transaction_hash ~ '^0x[0-9a-fA-F]{64}$'),
    UNIQUE(guild_id, task_key),
    UNIQUE(deployment_id, onchain_task_id)
);

CREATE INDEX IF NOT EXISTS idx_guild_task_domain_status
    ON guild_task(domain_id, task_status, lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_guild_task_contributor
    ON guild_task(contributor_id, contributor_wallet);

CREATE TABLE IF NOT EXISTS guild_evidence_review (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES guild_task(id) ON DELETE CASCADE,
    deployment_id UUID REFERENCES kgp_protocol_deployment(id),
    onchain_review_id VARCHAR(66),
    reviewer_id UUID,
    reviewer_wallet VARCHAR(42),
    evidence_hash VARCHAR(66) NOT NULL,
    evidence_cid TEXT,
    notes_hash VARCHAR(66),
    decision VARCHAR(30) NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    review_status VARCHAR(30) NOT NULL DEFAULT 'accepted'
        CHECK (review_status IN ('accepted', 'rejected', 'disputed', 'revoked')),
    dispute_reason_hash VARCHAR(66),
    resolution_hash VARCHAR(66),
    lifecycle_status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (lifecycle_status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    transaction_hash VARCHAR(66),
    block_number BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (onchain_review_id IS NULL OR onchain_review_id ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (reviewer_wallet IS NULL OR reviewer_wallet ~ '^0x[0-9a-fA-F]{40}$'),
    CHECK (evidence_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (notes_hash IS NULL OR notes_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (dispute_reason_hash IS NULL OR dispute_reason_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (resolution_hash IS NULL OR resolution_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (transaction_hash IS NULL OR transaction_hash ~ '^0x[0-9a-fA-F]{64}$'),
    UNIQUE(task_id)
);

CREATE INDEX IF NOT EXISTS idx_guild_evidence_review_status
    ON guild_evidence_review(review_status, lifecycle_status);

ALTER TABLE guild_reputation_event
    DROP CONSTRAINT IF EXISTS fk_guild_reputation_task,
    DROP CONSTRAINT IF EXISTS fk_guild_reputation_review;
ALTER TABLE guild_reputation_event
    ADD CONSTRAINT fk_guild_reputation_task FOREIGN KEY (task_id) REFERENCES guild_task(id),
    ADD CONSTRAINT fk_guild_reputation_review FOREIGN KEY (evidence_review_id) REFERENCES guild_evidence_review(id);

ALTER TABLE guild_contribution
    ADD COLUMN IF NOT EXISTS task_id UUID REFERENCES guild_task(id);
CREATE INDEX IF NOT EXISTS idx_guild_contribution_task
    ON guild_contribution(task_id);

CREATE TABLE IF NOT EXISTS guild_motion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id UUID NOT NULL REFERENCES kokonut_guild(id) ON DELETE CASCADE,
    deployment_id UUID REFERENCES kgp_protocol_deployment(id),
    dao_proposal_id UUID REFERENCES dao_proposal(id) ON DELETE SET NULL,
    onchain_motion_id BIGINT,
    title TEXT NOT NULL,
    purpose TEXT,
    target_address VARCHAR(42),
    data_hash VARCHAR(66),
    objection_deadline TIMESTAMPTZ,
    objection_count INTEGER NOT NULL DEFAULT 0 CHECK (objection_count >= 0),
    motion_status VARCHAR(30) NOT NULL DEFAULT 'open'
        CHECK (motion_status IN ('open', 'passed', 'rejected', 'executed', 'cancelled')),
    lifecycle_status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (lifecycle_status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    transaction_hash VARCHAR(66),
    block_number BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (target_address IS NULL OR target_address ~ '^0x[0-9a-fA-F]{40}$'),
    CHECK (data_hash IS NULL OR data_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (transaction_hash IS NULL OR transaction_hash ~ '^0x[0-9a-fA-F]{64}$'),
    UNIQUE(deployment_id, onchain_motion_id)
);

CREATE INDEX IF NOT EXISTS idx_guild_motion_status
    ON guild_motion(guild_id, motion_status, lifecycle_status);

CREATE OR REPLACE VIEW v_guild_reputation_candidates AS
SELECT
    task.id AS task_id,
    task.guild_id,
    task.domain_id,
    task.contributor_id,
    task.contributor_wallet,
    review.id AS evidence_review_id,
    review.evidence_hash,
    review.evidence_cid,
    task.reward_amount,
    task.task_status,
    review.review_status,
    task.lifecycle_status,
    GREATEST(task.updated_at, review.updated_at) AS last_updated_at
FROM guild_task task
JOIN guild_evidence_review review ON review.task_id = task.id
WHERE task.task_status = 'accepted'
  AND review.review_status = 'accepted'
  AND task.lifecycle_status IN ('verified', 'published')
  AND review.lifecycle_status IN ('verified', 'published');

COMMENT ON TABLE guild_task IS
    'PostgreSQL projection of a Kokonut Guild operational task; treasury payment remains external Moloch execution.';
COMMENT ON TABLE guild_evidence_review IS
    'Governed evidence review projection linked to a Guild task and eligible for KGP settlement.';
COMMENT ON TABLE guild_motion IS
    'Guild operational motion projection; it must not be used to bypass Moloch treasury proposals.';
COMMENT ON VIEW v_guild_reputation_candidates IS
    'Accepted, governed task evidence candidates that may be converted into canonical KGP events.';
