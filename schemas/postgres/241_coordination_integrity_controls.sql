-- ============================================================
-- 241_coordination_integrity_controls.sql
-- ============================================================
-- Enforce the coordination approval, consent, publication, and
-- market-cycle controls that cannot safely live only in Python.

ALTER TABLE coordination_alliance
    ADD COLUMN IF NOT EXISTS approval_quorum_required INTEGER NOT NULL DEFAULT 1
        CHECK (approval_quorum_required > 0),
    ADD COLUMN IF NOT EXISTS approval_quorum_met BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS reversible_until TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS shared_procurement_order_id UUID REFERENCES collective_market_order(id) ON DELETE SET NULL;

ALTER TABLE coordination_contribution
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255);
ALTER TABLE coordination_benefit
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255);

CREATE UNIQUE INDEX IF NOT EXISTS uq_coord_contribution_idempotency
    ON coordination_contribution(alliance_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_coord_benefit_idempotency
    ON coordination_benefit(alliance_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS coordination_approval (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    approval_status VARCHAR(20) NOT NULL DEFAULT 'approved'
        CHECK (approval_status IN ('approved', 'withdrawn')),
    basis TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (alliance_id, party_id)
);

CREATE TABLE IF NOT EXISTS coordination_partner_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    participant_id UUID REFERENCES coordination_participant(id) ON DELETE SET NULL,
    event_type VARCHAR(30) NOT NULL CHECK (event_type IN ('failure', 'recovery', 'substitution')),
    description TEXT NOT NULL,
    severity VARCHAR(20) CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    resolved_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coordination_market_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    market_order_id UUID REFERENCES market_order(id) ON DELETE SET NULL,
    outcome VARCHAR(30) NOT NULL CHECK (outcome IN ('on_time', 'late', 'fulfilled', 'disputed', 'cancelled')),
    performance_value NUMERIC,
    performance_unit VARCHAR(50),
    notes TEXT NOT NULL,
    observed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coord_approval_alliance
    ON coordination_approval(alliance_id, approval_status);
CREATE INDEX IF NOT EXISTS idx_coord_partner_event_alliance
    ON coordination_partner_event(alliance_id, event_type, resolved_at);
CREATE INDEX IF NOT EXISTS idx_coord_market_observation_alliance
    ON coordination_market_observation(alliance_id, outcome, observed_at DESC);

CREATE OR REPLACE FUNCTION enforce_coordination_alliance_integrity()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    approval_count INTEGER;
    proposal_status VARCHAR(20);
    proposal_meeting UUID;
BEGIN
    IF NEW.status IN ('approved', 'active') THEN
        SELECT COUNT(*) INTO approval_count
        FROM coordination_approval
        WHERE alliance_id = NEW.id AND approval_status = 'approved';

        IF approval_count < NEW.approval_quorum_required THEN
            RAISE EXCEPTION 'coordination approval quorum is not met (% of %)', approval_count, NEW.approval_quorum_required;
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM coordination_approval
            WHERE alliance_id = NEW.id AND party_id = NEW.approved_by_party_id AND approval_status = 'approved'
        ) THEN
            RAISE EXCEPTION 'recorded alliance approver must have an approved quorum record';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM coordination_conflict_declaration
            WHERE alliance_id = NEW.id AND status IN ('reviewed', 'managed', 'dismissed')
        ) THEN
            RAISE EXCEPTION 'conflict or no-conflict declaration must be reviewed before alliance approval';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM coordination_benefit_harm_analysis
            WHERE alliance_id = NEW.id AND status IN ('reviewed', 'accepted')
        ) THEN
            RAISE EXCEPTION 'benefit/harm analysis must be reviewed before alliance approval';
        END IF;
        IF EXISTS (
            SELECT 1 FROM coordination_conflict_declaration
            WHERE alliance_id = NEW.id
              AND party_id = NEW.approved_by_party_id
              AND recusal_required = TRUE
              AND status <> 'dismissed'
              AND (LOWER(COALESCE(recused_from, '')) LIKE '%approval%'
                   OR LOWER(COALESCE(recused_from, '')) LIKE '%alliance%')
        ) THEN
            RAISE EXCEPTION 'recused party cannot approve this alliance';
        END IF;
        IF NEW.cooperative_proposal_id IS NOT NULL THEN
            SELECT status, meeting_id INTO proposal_status, proposal_meeting
            FROM cooperative_proposal WHERE id = NEW.cooperative_proposal_id;
            IF proposal_status <> 'approved' THEN
                RAISE EXCEPTION 'cooperative proposal must be approved before alliance approval';
            END IF;
            IF proposal_meeting IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM cooperative_quorum
                WHERE meeting_id = proposal_meeting AND achieved = TRUE
            ) THEN
                RAISE EXCEPTION 'cooperative proposal meeting quorum must be achieved before alliance approval';
            END IF;
        END IF;
        IF NEW.market_cycle = 'slow' AND NEW.review_due_at IS NULL THEN
            RAISE EXCEPTION 'slow-cycle alliances require a stewardship review due date';
        END IF;
        IF NEW.market_cycle = 'fast' AND (
            jsonb_typeof(COALESCE(NEW.metadata -> 'reversible_pilot', 'null'::jsonb)) <> 'object'
            OR NULLIF(BTRIM(COALESCE(NEW.metadata #>> '{reversible_pilot,rollback_plan}', '')), '') IS NULL
            OR NEW.reversible_until IS NULL
        ) THEN
            RAISE EXCEPTION 'fast-cycle alliances require a reversible pilot and rollback deadline';
        END IF;
        NEW.approval_quorum_met := TRUE;
    END IF;

    IF NEW.publication_status = 'published' THEN
        IF NEW.public_summary IS NULL OR BTRIM(NEW.public_summary) = ''
           OR NEW.published_by_party_id IS NULL OR NEW.published_at IS NULL
           OR jsonb_typeof(NEW.public_evidence) <> 'array'
           OR NOT EXISTS (
               SELECT 1 FROM jsonb_array_elements(NEW.public_evidence) evidence
               WHERE evidence ->> 'verified' = 'true'
                  OR evidence ->> 'status' IN ('verified', 'published')
           ) THEN
            RAISE EXCEPTION 'published alliance output requires verified public evidence, summary, human publisher, and publication timestamp';
        END IF;
        IF NEW.status NOT IN ('active', 'completed') THEN
            RAISE EXCEPTION 'only active or completed alliances may be published';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_coordination_exchange_integrity()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    alliance_scope_type VARCHAR(30);
    alliance_scope_id UUID;
BEGIN
    IF NEW.status = 'completed' THEN
        SELECT scope_type, scope_id INTO alliance_scope_type, alliance_scope_id
        FROM coordination_alliance WHERE id = NEW.alliance_id;
        IF NEW.consent_event_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM v_effective_stakeholder_consent c
            WHERE c.consent_event_id = NEW.consent_event_id
              AND c.party_id = NEW.from_party_id
              AND c.event_type = 'grant'
              AND c.consented = TRUE
              AND c.data_category = 'coordination_knowledge_exchange'
              AND c.purpose = 'knowledge_exchange'
              AND (c.recipient_party_id IS NULL OR c.recipient_party_id = NEW.to_party_id)
              AND (NEW.consent_scope IS NULL OR c.scope_type = NEW.consent_scope)
              AND (
                  c.scope_type = 'network'
                  OR (c.scope_type = alliance_scope_type AND c.scope_id IS NOT DISTINCT FROM alliance_scope_id)
              )
        ) THEN
            RAISE EXCEPTION 'effective sender consent for this knowledge exchange is required';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_coordination_governance ON coordination_alliance;
CREATE TRIGGER trg_coordination_governance
    BEFORE INSERT OR UPDATE ON coordination_alliance
    FOR EACH ROW EXECUTE FUNCTION enforce_coordination_alliance_integrity();

DROP TRIGGER IF EXISTS trg_coordination_exchange_consent ON coordination_knowledge_exchange;
CREATE TRIGGER trg_coordination_exchange_consent
    BEFORE INSERT OR UPDATE ON coordination_knowledge_exchange
    FOR EACH ROW EXECUTE FUNCTION enforce_coordination_exchange_integrity();

CREATE OR REPLACE FUNCTION enforce_coordination_benefit_integrity()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.allocation_status = 'approved' AND EXISTS (
        SELECT 1 FROM coordination_conflict_declaration
        WHERE alliance_id = NEW.alliance_id
          AND party_id = NEW.approved_by_party_id
          AND recusal_required = TRUE
          AND status <> 'dismissed'
          AND (LOWER(COALESCE(recused_from, '')) LIKE '%benefit%'
               OR LOWER(COALESCE(recused_from, '')) LIKE '%distribution%')
    ) THEN
        RAISE EXCEPTION 'recused party cannot approve this benefit distribution';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_coordination_benefit_integrity ON coordination_benefit;
CREATE TRIGGER trg_coordination_benefit_integrity
    BEFORE INSERT OR UPDATE ON coordination_benefit
    FOR EACH ROW EXECUTE FUNCTION enforce_coordination_benefit_integrity();

COMMENT ON TABLE coordination_approval IS 'Distinct human approvals used to satisfy coordination alliance quorum; approval is not ownership or spending authorization';
COMMENT ON TABLE coordination_partner_event IS 'Governed partner failure, recovery, and substitution evidence used in alliance review';
COMMENT ON TABLE coordination_market_observation IS 'Governed marketplace performance evidence linked to alliance review';
