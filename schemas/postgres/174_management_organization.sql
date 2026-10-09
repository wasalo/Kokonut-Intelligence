-- ============================================================
-- 174_management_organization.sql - Organizing & responsibility (RACI)
-- ============================================================

-- Teams within an organization (enables delegation and span of control).
CREATE TABLE IF NOT EXISTS org_team (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    description TEXT,
    team_lead_staff_id UUID REFERENCES staff(id) ON DELETE SET NULL,
    created_by_type VARCHAR(20) NOT NULL DEFAULT 'staff'
        CHECK (created_by_type IN ('staff', 'farmer', 'agent', 'system')),
    created_by_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_org_team_org ON org_team(organization_id);

-- Generic responsibility assignment (RACI) linking any governed entity to a
-- responsible party. Polymorphic references (party_id, entity_id) follow the
-- kokonut:{entity_type}:{entity_id} IRI convention and are intentionally not
-- foreign-key constrained, so a single table covers locations, work items,
-- objectives, risks, cooperatives, and other governed entities.
CREATE TABLE IF NOT EXISTS responsibility_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(60) NOT NULL,
    entity_id UUID NOT NULL,
    party_type VARCHAR(20) NOT NULL
        CHECK (party_type IN ('staff', 'farmer', 'agent', 'team')),
    party_id UUID NOT NULL,
    raci_role VARCHAR(20) NOT NULL
        CHECK (raci_role IN ('accountable', 'responsible', 'consulted', 'informed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_resp_entity ON responsibility_assignment(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_resp_party ON responsibility_assignment(party_type, party_id);

-- Exactly one accountable party per governed entity.
CREATE UNIQUE INDEX IF NOT EXISTS uq_one_accountable
    ON responsibility_assignment(entity_type, entity_id)
    WHERE raci_role = 'accountable';

-- Additive: associate organization members with a team (span of control).
ALTER TABLE organization_member
    ADD COLUMN IF NOT EXISTS team_id UUID REFERENCES org_team(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_org_member_team ON organization_member(team_id);

DROP TRIGGER IF EXISTS trg_org_team_updated_at ON org_team;
CREATE TRIGGER trg_org_team_updated_at
    BEFORE UPDATE ON org_team
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_resp_updated_at ON responsibility_assignment;
CREATE TRIGGER trg_resp_updated_at
    BEFORE UPDATE ON responsibility_assignment
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE org_team IS 'Teams within an organization for delegation and span of control';
COMMENT ON TABLE responsibility_assignment IS 'Generic RACI assignment linking governed entities to responsible parties';
