-- ============================================================
-- 248_governance_circle_links.sql
-- Explicit cross-circle representation and liaison mandates.
-- ============================================================

CREATE TABLE IF NOT EXISTS governance_circle_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_circle_id UUID NOT NULL REFERENCES governance_circle(id) ON DELETE RESTRICT,
    target_circle_id UUID NOT NULL REFERENCES governance_circle(id) ON DELETE RESTRICT,
    link_type VARCHAR(20) NOT NULL CHECK (link_type IN ('lead_link', 'representative_link', 'liaison', 'observer')),
    role_id UUID NOT NULL REFERENCES governance_role(id) ON DELETE RESTRICT,
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE RESTRICT,
    mandate TEXT NOT NULL,
    scope_type VARCHAR(30) NOT NULL DEFAULT 'network'
        CHECK (scope_type IN ('network', 'organization', 'location', 'farm', 'cooperative', 'value_stream', 'initiative', 'decision')),
    scope_id UUID,
    term_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    term_end TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'active', 'suspended', 'ended', 'rejected')),
    recusal_status VARCHAR(20) NOT NULL DEFAULT 'clear'
        CHECK (recusal_status IN ('clear', 'declared', 'recused')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (source_circle_id <> target_circle_id),
    CHECK (NULLIF(BTRIM(mandate), '') IS NOT NULL),
    CHECK (term_end IS NULL OR term_end >= term_start),
    CHECK (status <> 'active' OR approved_by_party_id IS NOT NULL),
    CHECK (status <> 'active' OR recusal_status = 'clear')
);

CREATE INDEX IF NOT EXISTS idx_governance_circle_link_source
    ON governance_circle_link(source_circle_id, status, link_type);
CREATE INDEX IF NOT EXISTS idx_governance_circle_link_target
    ON governance_circle_link(target_circle_id, status, link_type);
CREATE INDEX IF NOT EXISTS idx_governance_circle_link_party
    ON governance_circle_link(party_id, status, term_end);

CREATE OR REPLACE FUNCTION enforce_governance_circle_link()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'active' THEN
        IF NOT EXISTS (
            SELECT 1 FROM governance_circle
            WHERE id IN (NEW.source_circle_id, NEW.target_circle_id) AND status = 'active'
        ) OR NOT EXISTS (
            SELECT 1 FROM governance_role r
            JOIN governance_role_assignment a ON a.role_id = r.id
            WHERE r.id = NEW.role_id AND r.status = 'active'
              AND a.party_id = NEW.party_id AND a.status = 'active'
              AND a.recusal_status = 'clear'
              AND (a.effective_until IS NULL OR a.effective_until >= NOW())
        ) THEN
            RAISE EXCEPTION 'active circle link requires active circles, role, and assignment';
        END IF;
        IF NEW.approved_by_party_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM party WHERE id = NEW.approved_by_party_id AND party_type = 'person'
        ) THEN
            RAISE EXCEPTION 'active circle link requires an identified human approver';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_circle_link ON governance_circle_link;
CREATE TRIGGER trg_governance_circle_link
    BEFORE INSERT OR UPDATE ON governance_circle_link
    FOR EACH ROW EXECUTE FUNCTION enforce_governance_circle_link();

DROP TRIGGER IF EXISTS trg_governance_circle_link_updated_at ON governance_circle_link;
CREATE TRIGGER trg_governance_circle_link_updated_at
    BEFORE UPDATE ON governance_circle_link
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE VIEW v_governance_circle_links AS
SELECT
    l.id AS link_id,
    l.source_circle_id,
    source.circle_key AS source_circle_key,
    l.target_circle_id,
    target.circle_key AS target_circle_key,
    l.link_type,
    l.role_id,
    role.role_key,
    l.party_id,
    party.display_name AS party_name,
    l.mandate,
    l.scope_type,
    l.scope_id,
    l.term_start,
    l.term_end,
    l.status,
    l.recusal_status,
    l.approved_by_party_id,
    approver.display_name AS approved_by_name
FROM governance_circle_link l
JOIN governance_circle source ON source.id = l.source_circle_id
JOIN governance_circle target ON target.id = l.target_circle_id
JOIN governance_role role ON role.id = l.role_id
JOIN party party ON party.id = l.party_id
LEFT JOIN party approver ON approver.id = l.approved_by_party_id;

COMMENT ON TABLE governance_circle_link IS 'Term-bound representative or liaison link across bounded governance circles';
COMMENT ON VIEW v_governance_circle_links IS 'Internal cross-circle representation with mandate, term, recusal, and approval';
