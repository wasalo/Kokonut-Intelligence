-- ============================================================
-- 238_coordination_governance_cockpit.sql
-- ============================================================

ALTER TABLE coordination_alliance
    ADD COLUMN IF NOT EXISTS market_cycle VARCHAR(20) NOT NULL DEFAULT 'standard'
        CHECK (market_cycle IN ('slow', 'standard', 'fast')),
    ADD COLUMN IF NOT EXISTS work_item_id UUID REFERENCES work_item(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS proxy_authority_id UUID REFERENCES stewardship_proxy_authority(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS review_due_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS public_summary TEXT,
    ADD COLUMN IF NOT EXISTS public_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS public_limitations TEXT,
    ADD COLUMN IF NOT EXISTS publication_status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (publication_status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    ADD COLUMN IF NOT EXISTS published_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;

ALTER TABLE coordination_knowledge_exchange
    ADD COLUMN IF NOT EXISTS consent_event_id UUID REFERENCES stakeholder_consent(id) ON DELETE SET NULL;

ALTER TABLE coordination_alliance DROP CONSTRAINT IF EXISTS coordination_alliance_coordination_type_check;
ALTER TABLE coordination_alliance DROP CONSTRAINT IF EXISTS chk_coordination_type;
ALTER TABLE coordination_alliance ADD CONSTRAINT chk_coordination_type CHECK (
    coordination_type IN ('alliance', 'cooperative_network', 'knowledge_network', 'ecological_alliance')
);

CREATE TABLE IF NOT EXISTS coordination_conflict_declaration (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    declaration_type VARCHAR(20) NOT NULL CHECK (declaration_type IN ('conflict', 'no_conflict')),
    description TEXT NOT NULL,
    recusal_required BOOLEAN NOT NULL DEFAULT FALSE,
    recused_from TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'declared' CHECK (status IN ('declared', 'reviewed', 'managed', 'dismissed')),
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coordination_benefit_harm_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    analysis_type VARCHAR(20) NOT NULL CHECK (analysis_type IN ('benefit', 'harm')),
    description TEXT NOT NULL,
    severity VARCHAR(20) CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    mitigation TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'reviewed', 'accepted', 'rejected')),
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coordination_minority_view (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    review_id UUID REFERENCES coordination_review(id) ON DELETE SET NULL,
    party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    anonymous_group VARCHAR(255),
    view_text TEXT NOT NULL,
    consent_checked BOOLEAN NOT NULL DEFAULT FALSE,
    preservation_status VARCHAR(20) NOT NULL DEFAULT 'preserved' CHECK (preservation_status IN ('preserved', 'reviewed', 'resolved')),
    response_text TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (party_id IS NOT NULL OR NULLIF(TRIM(COALESCE(anonymous_group, '')), '') IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS coordination_appeal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    target_type VARCHAR(30) NOT NULL CHECK (target_type IN ('alliance', 'participant', 'contribution', 'benefit', 'risk', 'exchange', 'review', 'remedy')),
    target_id UUID NOT NULL,
    appealed_by_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    correction_requested BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'resolved', 'rejected')),
    resolution TEXT,
    resolved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coordination_remedy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    harm_analysis_id UUID REFERENCES coordination_benefit_harm_analysis(id) ON DELETE SET NULL,
    benefit_id UUID REFERENCES coordination_benefit(id) ON DELETE SET NULL,
    remedy_type VARCHAR(30) NOT NULL CHECK (remedy_type IN ('explanation', 'correction', 'restoration', 'access', 'benefit_reallocation', 'other')),
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'approved', 'in_progress', 'completed', 'rejected')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    completed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    completed_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status <> 'approved' OR approved_by_party_id IS NOT NULL),
    CHECK (status <> 'approved' OR approved_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_coord_conflict_alliance ON coordination_conflict_declaration(alliance_id, status);
CREATE INDEX IF NOT EXISTS idx_coord_harm_alliance ON coordination_benefit_harm_analysis(alliance_id, analysis_type, status);
CREATE INDEX IF NOT EXISTS idx_coord_minority_alliance ON coordination_minority_view(alliance_id, preservation_status);
CREATE INDEX IF NOT EXISTS idx_coord_appeal_alliance ON coordination_appeal(alliance_id, status);
CREATE INDEX IF NOT EXISTS idx_coord_remedy_alliance ON coordination_remedy(alliance_id, status);

CREATE OR REPLACE FUNCTION enforce_coordination_governance()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'coordination_alliance' AND NEW.status IN ('approved', 'active') THEN
        IF NEW.approved_by_party_id IS NULL OR NEW.approved_at IS NULL THEN
            RAISE EXCEPTION 'human approval is required before alliance approval or activation';
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
        IF NEW.coordination_type = 'ecological_alliance' AND NOT EXISTS (
            SELECT 1 FROM stewardship_proxy_authority
            WHERE id = NEW.proxy_authority_id AND status = 'active'
        ) THEN
            RAISE EXCEPTION 'active proxy authority is required for ecological alliance approval';
        END IF;
    ELSIF TG_TABLE_NAME = 'coordination_knowledge_exchange' AND NEW.status = 'completed' THEN
        IF NEW.consent_event_id IS NULL THEN
            RAISE EXCEPTION 'consent is required before completing knowledge exchange';
        END IF;
    ELSIF TG_TABLE_NAME = 'coordination_alliance' AND NEW.publication_status = 'published' THEN
        IF NEW.public_summary IS NULL OR BTRIM(NEW.public_summary) = '' OR NEW.published_by_party_id IS NULL OR NEW.published_at IS NULL THEN
            RAISE EXCEPTION 'published alliance output requires summary, human publisher, and publication timestamp';
        END IF;
        IF NEW.status NOT IN ('active', 'completed') THEN
            RAISE EXCEPTION 'only active or completed alliances may be published';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_coordination_governance ON coordination_alliance;
CREATE TRIGGER trg_coordination_governance
    BEFORE INSERT OR UPDATE ON coordination_alliance
    FOR EACH ROW EXECUTE FUNCTION enforce_coordination_governance();

DROP TRIGGER IF EXISTS trg_coordination_exchange_consent ON coordination_knowledge_exchange;
CREATE TRIGGER trg_coordination_exchange_consent
    BEFORE INSERT OR UPDATE ON coordination_knowledge_exchange
    FOR EACH ROW EXECUTE FUNCTION enforce_coordination_governance();

CREATE OR REPLACE VIEW v_coordination_cockpit_internal AS
SELECT ca.id AS alliance_id, ca.name, ca.coordination_type, ca.market_cycle, ca.status,
       ca.review_due_at, ca.ends_at, ca.work_item_id, ca.proxy_authority_id,
       COUNT(DISTINCT cp.id) FILTER (WHERE cp.status = 'active') AS active_participant_count,
       COUNT(DISTINCT co.id) FILTER (WHERE co.status IN ('active', 'achieved')) AS shared_objective_count,
       COUNT(DISTINCT cc.id) FILTER (WHERE cc.status IN ('committed', 'delivered')) AS contribution_count,
       COUNT(DISTINCT cb.id) FILTER (WHERE cb.allocation_status IN ('approved', 'delivered')) AS verified_benefit_count,
       COUNT(DISTINCT bha.id) FILTER (WHERE bha.analysis_type = 'harm' AND bha.status IN ('proposed', 'reviewed')) AS open_harm_count,
       COUNT(DISTINCT ke.id) FILTER (WHERE ke.status IN ('proposed', 'scheduled')) AS open_knowledge_exchange_count,
       COUNT(DISTINCT cfd.id) FILTER (WHERE cfd.status IN ('declared', 'reviewed')) AS open_conflict_count,
       COUNT(DISTINCT rri.id) FILTER (WHERE rri.status IN ('open', 'monitoring')) AS trust_risk_count,
       COUNT(DISTINCT cr.id) FILTER (WHERE cr.status IN ('open', 'monitoring')) AS open_coordination_risk_count,
       COUNT(DISTINCT rem.id) FILTER (WHERE rem.status IN ('proposed', 'approved', 'in_progress')) AS open_remedy_count,
       COUNT(DISTINCT mv.id) FILTER (WHERE mv.preservation_status = 'preserved') AS preserved_minority_view_count,
       COUNT(DISTINCT cl.id) FILTER (WHERE cl.link_type = 'stakeholder_outcome' AND cl.status = 'verified') AS verified_outcome_change_count,
       COUNT(DISTINCT nso.id) FILTER (WHERE nso.status IN ('proposed', 'in_progress', 'breached')) AS ecological_obligation_count
FROM coordination_alliance ca
LEFT JOIN coordination_participant cp ON cp.alliance_id = ca.id
LEFT JOIN coordination_objective co ON co.alliance_id = ca.id
LEFT JOIN coordination_contribution cc ON cc.alliance_id = ca.id
LEFT JOIN coordination_benefit cb ON cb.alliance_id = ca.id
LEFT JOIN coordination_benefit_harm_analysis bha ON bha.alliance_id = ca.id
LEFT JOIN coordination_knowledge_exchange ke ON ke.alliance_id = ca.id
LEFT JOIN coordination_conflict_declaration cfd ON cfd.alliance_id = ca.id
LEFT JOIN relationship_risk_indicator rri ON rri.subject_party_id = ca.steward_party_id
LEFT JOIN coordination_risk cr ON cr.alliance_id = ca.id
LEFT JOIN coordination_remedy rem ON rem.alliance_id = ca.id
LEFT JOIN coordination_minority_view mv ON mv.alliance_id = ca.id
LEFT JOIN coordination_learning_link cl ON cl.alliance_id = ca.id
LEFT JOIN nature_stewardship_obligation nso ON nso.scope_id = ca.scope_id
GROUP BY ca.id, ca.name, ca.coordination_type, ca.market_cycle, ca.status,
         ca.review_due_at, ca.ends_at, ca.work_item_id, ca.proxy_authority_id;

CREATE OR REPLACE VIEW v_public_coordination_alliance AS
SELECT ca.id AS alliance_id, ca.name, ca.coordination_type, ca.market_cycle,
       ca.public_summary, ca.public_evidence, ca.public_limitations,
       ca.review_due_at, COUNT(DISTINCT cb.id) FILTER (WHERE cb.allocation_status = 'delivered') AS verified_benefit_count,
       COUNT(DISTINCT ke.id) FILTER (WHERE ke.status = 'completed') AS published_knowledge_count,
       COUNT(DISTINCT cl.id) FILTER (WHERE cl.link_type = 'stakeholder_outcome' AND cl.status = 'verified') AS verified_outcome_change_count,
       'Public output excludes participants, private evidence, unresolved conflicts, private trust evidence, and unverified harms.' AS privacy_limitation,
       'Published summaries are governed aggregates and do not prove alliance success, equity, or absence of harm.' AS uncertainty_limitation
FROM coordination_alliance ca
LEFT JOIN coordination_benefit cb ON cb.alliance_id = ca.id
LEFT JOIN coordination_knowledge_exchange ke ON ke.alliance_id = ca.id
LEFT JOIN coordination_learning_link cl ON cl.alliance_id = ca.id
WHERE ca.status IN ('active', 'completed')
  AND ca.publication_status = 'published'
  AND NULLIF(BTRIM(COALESCE(ca.public_summary, '')), '') IS NOT NULL
GROUP BY ca.id, ca.name, ca.coordination_type, ca.market_cycle,
         ca.public_summary, ca.public_evidence, ca.public_limitations, ca.review_due_at;

CREATE OR REPLACE VIEW v_stakeholder_cockpit_internal AS
SELECT
    (SELECT COUNT(*) FROM party WHERE status = 'active') AS active_party_count,
    (SELECT COUNT(*) FROM party_relationship WHERE status = 'active') AS active_relationship_count,
    (SELECT COUNT(*) FROM stakeholder_interest WHERE status NOT IN ('met', 'retired')) AS open_interest_count,
    (SELECT COUNT(*) FROM stakeholder_engagement_plan WHERE status IN ('draft', 'active')) AS active_engagement_plan_count,
    (SELECT COUNT(*) FROM v_stakeholder_commitment_health WHERE is_overdue) AS overdue_commitment_count,
    (SELECT COUNT(*) FROM stakeholder_grievance_case WHERE status NOT IN ('closed', 'rejected')) AS open_grievance_count,
    (SELECT COUNT(*) FROM stakeholder_decision WHERE status IN ('submitted', 'approved', 'in_execution')) AS active_decision_count,
    (SELECT COUNT(*) FROM stakeholder_decision_tradeoff WHERE direction IN ('harm', 'risk') AND NOT accepted) AS unresolved_harm_count,
    (SELECT COUNT(*) FROM relationship_risk_indicator WHERE status IN ('open', 'monitoring')) AS open_relationship_risk_count,
    (SELECT COUNT(*) FROM buyer_verification WHERE status = 'pending') AS pending_buyer_verification_count,
    (SELECT COUNT(*) FROM party_trust_evidence WHERE correction_status = 'requested' OR appeal_status = 'open') AS contested_trust_evidence_count,
    (SELECT COUNT(*) FROM nature_stewardship_obligation WHERE status IN ('proposed', 'in_progress', 'breached')) AS stewardship_action_count,
    (SELECT COUNT(*) FROM value_stream_stakeholder_outcome WHERE status IN ('draft', 'active')) AS unverified_value_stream_outcome_count,
    NOW() AS generated_at,
    (SELECT COUNT(*) FROM coordination_alliance WHERE status = 'active') AS active_alliance_count,
    (SELECT COUNT(*) FROM coordination_alliance WHERE status = 'active' AND market_cycle = 'slow') AS slow_cycle_alliance_count,
    (SELECT COUNT(*) FROM coordination_alliance WHERE status = 'active' AND market_cycle = 'fast') AS fast_cycle_alliance_count,
    (SELECT COUNT(*) FROM coordination_conflict_declaration WHERE status IN ('declared', 'reviewed')) AS open_coordination_conflict_count,
    (SELECT COUNT(*) FROM coordination_remedy WHERE status IN ('proposed', 'approved', 'in_progress')) AS open_coordination_remedy_count,
    (SELECT COUNT(*) FROM coordination_alliance WHERE review_due_at IS NOT NULL AND review_due_at <= NOW() AND status IN ('active', 'paused')) AS overdue_alliance_review_count;

CREATE OR REPLACE VIEW v_public_stakeholder_cockpit AS
SELECT
    (SELECT COUNT(*) FROM party WHERE status = 'active' AND privacy_level = 'public') AS public_party_count,
    (SELECT COUNT(*) FROM v_public_stakeholder_representation) AS representation_summary_count,
    (SELECT COUNT(*) FROM stakeholder_outcome WHERE status IN ('verified', 'published') AND evidence_maturity >= 4) AS verified_outcome_count,
    (SELECT COUNT(*) FROM impact_claim WHERE status = 'published' AND evidence_maturity >= 4) AS verified_impact_claim_count,
    (SELECT COUNT(*) FROM stakeholder_distribution WHERE status IN ('verified', 'published')) AS verified_distribution_count,
    (SELECT COUNT(*) FROM v_public_ecological_stewardship) AS ecological_stewardship_count,
    (SELECT COUNT(*) FROM stakeholder_feedback WHERE status = 'published' AND consent_given = TRUE AND is_public = TRUE) AS published_feedback_count,
    'Public cockpit excludes private consent, protected grievances, unresolved decision lineage, contested trust evidence, and small-group participation.' AS privacy_limitation,
    'Counts indicate governed records, not absence of impact or stakeholder satisfaction.' AS uncertainty_limitation,
    NOW() AS generated_at,
    (SELECT COUNT(*) FROM v_public_coordination_alliance) AS published_alliance_count,
    (SELECT COUNT(*) FROM v_public_coordination_alliance WHERE verified_benefit_count > 0) AS verified_alliance_benefit_count,
    (SELECT COUNT(*) FROM v_public_coordination_alliance WHERE published_knowledge_count > 0) AS published_alliance_knowledge_count;
