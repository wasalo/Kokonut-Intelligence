-- ============================================================
-- 319_guild_integrity_controls.sql
-- Preserve canonical Guild facts while allowing projection reconciliation.
-- ============================================================

ALTER TABLE guild_domain
    DROP CONSTRAINT IF EXISTS uq_guild_domain_identity;
ALTER TABLE guild_domain
    ADD CONSTRAINT uq_guild_domain_identity UNIQUE (guild_id, id);

ALTER TABLE guild_task
    DROP CONSTRAINT IF EXISTS fk_guild_task_domain_guild;
ALTER TABLE guild_task
    ADD CONSTRAINT fk_guild_task_domain_guild
    FOREIGN KEY (guild_id, domain_id) REFERENCES guild_domain(guild_id, id);

ALTER TABLE guild_domain
    DROP CONSTRAINT IF EXISTS chk_guild_domain_chain_identity;
ALTER TABLE guild_domain
    ADD CONSTRAINT chk_guild_domain_chain_identity
    CHECK ((deployment_id IS NULL AND onchain_domain_id IS NULL)
        OR (deployment_id IS NOT NULL AND onchain_domain_id IS NOT NULL));

ALTER TABLE guild_task
    DROP CONSTRAINT IF EXISTS chk_guild_task_chain_identity;
ALTER TABLE guild_task
    ADD CONSTRAINT chk_guild_task_chain_identity
    CHECK ((deployment_id IS NULL AND onchain_task_id IS NULL)
        OR (deployment_id IS NOT NULL AND onchain_task_id IS NOT NULL));

ALTER TABLE guild_motion
    DROP CONSTRAINT IF EXISTS chk_guild_motion_chain_identity;
ALTER TABLE guild_motion
    ADD CONSTRAINT chk_guild_motion_chain_identity
    CHECK ((deployment_id IS NULL AND onchain_motion_id IS NULL)
        OR (deployment_id IS NOT NULL AND onchain_motion_id IS NOT NULL));

ALTER TABLE guild_motion
    ADD COLUMN IF NOT EXISTS requires_treasury_proposal BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE guild_motion
    DROP CONSTRAINT IF EXISTS chk_guild_motion_treasury_link;
ALTER TABLE guild_motion
    ADD CONSTRAINT chk_guild_motion_treasury_link
    CHECK (NOT requires_treasury_proposal OR dao_proposal_id IS NOT NULL);

ALTER TABLE kgp_chain_event
    ADD COLUMN IF NOT EXISTS is_canonical BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS orphaned_at TIMESTAMPTZ;

ALTER TABLE kgp_indexer_cursor
    ADD COLUMN IF NOT EXISTS last_block_number BIGINT;

ALTER TABLE guild_reputation_event
    ADD COLUMN IF NOT EXISTS reviewed_by UUID;

CREATE TABLE IF NOT EXISTS guild_evidence_review_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id UUID REFERENCES guild_evidence_review(id) ON DELETE SET NULL,
    task_id UUID NOT NULL REFERENCES guild_task(id) ON DELETE CASCADE,
    deployment_id UUID REFERENCES kgp_protocol_deployment(id),
    event_type VARCHAR(30) NOT NULL
        CHECK (event_type IN ('reviewed', 'disputed', 'resolved', 'revoked')),
    onchain_event_id VARCHAR(66),
    reviewer_wallet VARCHAR(42),
    evidence_hash VARCHAR(66),
    reason_hash VARCHAR(66),
    resolution_hash VARCHAR(66),
    transaction_hash VARCHAR(66),
    block_number BIGINT,
    log_index INTEGER,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (onchain_event_id IS NULL OR onchain_event_id ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (reviewer_wallet IS NULL OR reviewer_wallet ~ '^0x[0-9a-fA-F]{40}$'),
    CHECK (evidence_hash IS NULL OR evidence_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (reason_hash IS NULL OR reason_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (resolution_hash IS NULL OR resolution_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (transaction_hash IS NULL OR transaction_hash ~ '^0x[0-9a-fA-F]{64}$'),
    UNIQUE(deployment_id, transaction_hash, log_index)
);

CREATE INDEX IF NOT EXISTS idx_guild_evidence_review_event_task
    ON guild_evidence_review_event(task_id, created_at);

CREATE OR REPLACE FUNCTION enforce_guild_reputation_event_integrity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    original guild_reputation_event%ROWTYPE;
    reversal_total NUMERIC(30, 6);
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'guild_reputation_event is append-only';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF OLD.id IS DISTINCT FROM NEW.id
           OR OLD.guild_id IS DISTINCT FROM NEW.guild_id
           OR OLD.contributor_id IS DISTINCT FROM NEW.contributor_id
           OR OLD.contributor_wallet IS DISTINCT FROM NEW.contributor_wallet
           OR OLD.domain_id IS DISTINCT FROM NEW.domain_id
           OR OLD.event_type IS DISTINCT FROM NEW.event_type
           OR OLD.amount IS DISTINCT FROM NEW.amount
           OR OLD.epoch IS DISTINCT FROM NEW.epoch
           OR OLD.evidence_hash IS DISTINCT FROM NEW.evidence_hash
           OR OLD.evidence_cid IS DISTINCT FROM NEW.evidence_cid
           OR OLD.ledger_record_hash IS DISTINCT FROM NEW.ledger_record_hash
           OR OLD.calculation_version IS DISTINCT FROM NEW.calculation_version
           OR OLD.award_id IS DISTINCT FROM NEW.award_id
           OR OLD.reversal_id IS DISTINCT FROM NEW.reversal_id
           OR OLD.reversal_of_id IS DISTINCT FROM NEW.reversal_of_id
           OR OLD.reason_hash IS DISTINCT FROM NEW.reason_hash THEN
            RAISE EXCEPTION 'canonical reputation facts are immutable';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.event_type = 'reversal' THEN
        SELECT * INTO original
        FROM guild_reputation_event
        WHERE id = NEW.reversal_of_id
        FOR UPDATE;

        IF NOT FOUND OR original.event_type <> 'award' THEN
            RAISE EXCEPTION 'reversal must reference an award event';
        END IF;
        IF original.guild_id <> NEW.guild_id
           OR original.domain_id <> NEW.domain_id
           OR original.contributor_id IS DISTINCT FROM NEW.contributor_id
           OR LOWER(original.contributor_wallet) <> LOWER(NEW.contributor_wallet) THEN
            RAISE EXCEPTION 'reversal identity does not match original award';
        END IF;

        SELECT COALESCE(SUM(amount), 0) INTO reversal_total
        FROM guild_reputation_event
        WHERE reversal_of_id = NEW.reversal_of_id;
        IF reversal_total + NEW.amount > original.amount THEN
            RAISE EXCEPTION 'reversal amount exceeds original award';
        END IF;
    END IF;

    IF NEW.event_type = 'award' AND NEW.reversal_of_id IS NOT NULL THEN
        RAISE EXCEPTION 'award cannot reference a reversal source';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_guild_reputation_event_integrity ON guild_reputation_event;
CREATE TRIGGER trg_guild_reputation_event_integrity
BEFORE INSERT OR UPDATE OR DELETE ON guild_reputation_event
FOR EACH ROW EXECUTE FUNCTION enforce_guild_reputation_event_integrity();

CREATE OR REPLACE FUNCTION enforce_guild_task_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    contributor_wallet_value VARCHAR(42);
BEGIN
    IF NEW.contributor_id IS NOT NULL THEN
        SELECT wallet_address INTO contributor_wallet_value
        FROM guild_contributor
        WHERE id = NEW.contributor_id;
        IF NOT FOUND OR contributor_wallet_value IS NULL
           OR LOWER(contributor_wallet_value) <> LOWER(COALESCE(NEW.contributor_wallet, '')) THEN
            RAISE EXCEPTION 'task contributor identity does not match wallet';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_guild_task_identity ON guild_task;
CREATE TRIGGER trg_guild_task_identity
BEFORE INSERT OR UPDATE ON guild_task
FOR EACH ROW EXECUTE FUNCTION enforce_guild_task_identity();

CREATE OR REPLACE FUNCTION enforce_kgp_chain_event_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    deployment kgp_protocol_deployment%ROWTYPE;
BEGIN
    SELECT * INTO deployment
    FROM kgp_protocol_deployment
    WHERE id = NEW.deployment_id;
    IF NOT FOUND OR deployment.chain_id <> NEW.chain_id THEN
        RAISE EXCEPTION 'chain event chain does not match deployment';
    END IF;
    IF LOWER(NEW.contract_address) <> LOWER(deployment.proxy_address)
       AND LOWER(NEW.contract_address) <> LOWER(COALESCE(deployment.registry_address, ''))
       AND LOWER(NEW.contract_address) <> LOWER(COALESCE(deployment.domain_address, ''))
       AND LOWER(NEW.contract_address) <> LOWER(COALESCE(deployment.task_board_address, ''))
       AND LOWER(NEW.contract_address) <> LOWER(COALESCE(deployment.evidence_review_address, ''))
       AND LOWER(NEW.contract_address) <> LOWER(COALESCE(deployment.governance_address, '')) THEN
        RAISE EXCEPTION 'chain event contract does not match deployment';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_kgp_chain_event_identity ON kgp_chain_event;
CREATE TRIGGER trg_kgp_chain_event_identity
BEFORE INSERT OR UPDATE ON kgp_chain_event
FOR EACH ROW EXECUTE FUNCTION enforce_kgp_chain_event_identity();

CREATE OR REPLACE VIEW v_kgp_ledger_integrity_violations AS
SELECT guild_id, domain_id, contributor_wallet, SUM(
    CASE WHEN event_type = 'award' THEN amount ELSE -amount END
) AS computed_balance
FROM guild_reputation_event
GROUP BY guild_id, domain_id, contributor_wallet
HAVING SUM(CASE WHEN event_type = 'award' THEN amount ELSE -amount END) < 0;

COMMENT ON TABLE guild_evidence_review_event IS
    'Immutable history of review, dispute, resolution, and revocation events; guild_evidence_review is current state.';
COMMENT ON VIEW v_kgp_ledger_integrity_violations IS
    'Should remain empty; negative balances indicate rejected writes or ledger corruption.';
