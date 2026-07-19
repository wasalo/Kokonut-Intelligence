-- ============================================================
-- 323_guild_projection_reorg_recovery.sql
-- Track chain-owned projections so reorg recovery can rebuild them safely.
-- ============================================================

ALTER TABLE kokonut_guild
    ADD COLUMN IF NOT EXISTS chain_projection BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS source_chain_event_id UUID REFERENCES kgp_chain_event(id),
    ADD COLUMN IF NOT EXISTS orphaned_at TIMESTAMPTZ;

ALTER TABLE guild_domain
    ADD COLUMN IF NOT EXISTS chain_projection BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS source_chain_event_id UUID REFERENCES kgp_chain_event(id),
    ADD COLUMN IF NOT EXISTS orphaned_at TIMESTAMPTZ;

ALTER TABLE guild_task
    ADD COLUMN IF NOT EXISTS chain_projection BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS source_chain_event_id UUID REFERENCES kgp_chain_event(id),
    ADD COLUMN IF NOT EXISTS orphaned_at TIMESTAMPTZ;

ALTER TABLE guild_evidence_review
    ADD COLUMN IF NOT EXISTS chain_projection BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS source_chain_event_id UUID REFERENCES kgp_chain_event(id),
    ADD COLUMN IF NOT EXISTS orphaned_at TIMESTAMPTZ;

ALTER TABLE guild_evidence_review_event
    ADD COLUMN IF NOT EXISTS is_canonical BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS orphaned_at TIMESTAMPTZ;

ALTER TABLE guild_evidence_review_event
    ALTER COLUMN task_id DROP NOT NULL,
    DROP CONSTRAINT IF EXISTS guild_evidence_review_event_task_id_fkey;
ALTER TABLE guild_evidence_review_event
    ADD CONSTRAINT guild_evidence_review_event_task_id_fkey
    FOREIGN KEY (task_id) REFERENCES guild_task(id) ON DELETE SET NULL;

ALTER TABLE guild_motion
    ADD COLUMN IF NOT EXISTS chain_projection BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS source_chain_event_id UUID REFERENCES kgp_chain_event(id),
    ADD COLUMN IF NOT EXISTS orphaned_at TIMESTAMPTZ;

ALTER TABLE guild_reputation_event
    ADD COLUMN IF NOT EXISTS source_chain_event_id UUID REFERENCES kgp_chain_event(id),
    ADD COLUMN IF NOT EXISTS orphaned_at TIMESTAMPTZ;

ALTER TABLE kgp_claim
    ADD COLUMN IF NOT EXISTS source_chain_event_id UUID REFERENCES kgp_chain_event(id),
    ADD COLUMN IF NOT EXISTS orphaned_at TIMESTAMPTZ;

ALTER TABLE guild_domain
    DROP CONSTRAINT IF EXISTS chk_guild_domain_chain_projection_identity,
    ADD CONSTRAINT chk_guild_domain_chain_projection_identity
    CHECK (NOT chain_projection OR (deployment_id IS NOT NULL AND onchain_domain_id IS NOT NULL));
ALTER TABLE guild_task
    DROP CONSTRAINT IF EXISTS chk_guild_task_chain_projection_identity,
    ADD CONSTRAINT chk_guild_task_chain_projection_identity
    CHECK (NOT chain_projection OR (deployment_id IS NOT NULL AND onchain_task_id IS NOT NULL));
ALTER TABLE guild_evidence_review
    DROP CONSTRAINT IF EXISTS chk_guild_review_chain_projection_identity,
    ADD CONSTRAINT chk_guild_review_chain_projection_identity
    CHECK (NOT chain_projection OR (deployment_id IS NOT NULL AND onchain_review_id IS NOT NULL));
ALTER TABLE guild_motion
    DROP CONSTRAINT IF EXISTS chk_guild_motion_chain_projection_identity,
    ADD CONSTRAINT chk_guild_motion_chain_projection_identity
    CHECK (NOT chain_projection OR (deployment_id IS NOT NULL AND onchain_motion_id IS NOT NULL));

CREATE INDEX IF NOT EXISTS idx_guild_projection_source_event
    ON guild_domain(source_chain_event_id)
    WHERE source_chain_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_guild_task_projection_source_event
    ON guild_task(source_chain_event_id)
    WHERE source_chain_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_guild_review_projection_source_event
    ON guild_evidence_review(source_chain_event_id)
    WHERE source_chain_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_guild_motion_projection_source_event
    ON guild_motion(source_chain_event_id)
    WHERE source_chain_event_id IS NOT NULL;

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
  AND review.lifecycle_status IN ('verified', 'published')
  AND (task.deadline IS NULL OR NOW() <= task.deadline + INTERVAL '7 days');
