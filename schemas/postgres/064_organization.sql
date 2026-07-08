-- 064_organization.sql
-- Organization Entity: Multi-Org Grouping

BEGIN;

-- ============================================================================
-- ORGANIZATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS organization (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_key VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    org_type VARCHAR(100) NOT NULL DEFAULT 'cooperative'
        CHECK (org_type IN ('cooperative', 'nonprofit', 'dao', 'enterprise', 'collective', 'other')),
    description TEXT,
    logo_url TEXT,
    website VARCHAR(500),
    contact_email VARCHAR(255),
    legal_entity_name VARCHAR(255),
    jurisdiction VARCHAR(100),
    governance_model VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'dissolved')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE TRIGGER trg_organization_updated_at
    BEFORE UPDATE ON organization
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE organization IS 'Multi-organization grouping for farms, partners, and wallets';

-- ============================================================================
-- ORGANIZATION MEMBER
-- ============================================================================

CREATE TABLE IF NOT EXISTS organization_member (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    membership_type VARCHAR(100) NOT NULL DEFAULT 'owned'
        CHECK (membership_type IN ('owned', 'affiliated', 'sponsored', 'partner')),
    join_date DATE NOT NULL DEFAULT CURRENT_DATE,
    role VARCHAR(100) NOT NULL DEFAULT 'primary'
        CHECK (role IN ('primary', 'satellite', 'partner', 'incubated')),
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'suspended')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_org_member_org ON organization_member(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_member_location ON organization_member(location_id);

CREATE TRIGGER trg_org_member_updated_at
    BEFORE UPDATE ON organization_member
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE organization_member IS 'Links organizations to locations/farms with membership type and role';

-- ============================================================================
-- ORGANIZATION WALLET
-- ============================================================================

CREATE TABLE IF NOT EXISTS organization_wallet (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    wallet_id UUID NOT NULL,
    wallet_purpose VARCHAR(100) NOT NULL DEFAULT 'treasury'
        CHECK (wallet_purpose IN ('treasury', 'operations', 'rewards', 'donor_escrow')),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_org_wallet_org ON organization_wallet(organization_id);

CREATE TRIGGER trg_org_wallet_updated_at
    BEFORE UPDATE ON organization_wallet
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE organization_wallet IS 'Links organizations to wallets for treasury, operations, rewards, and donor escrow';

-- ============================================================================
-- FK ADDITIONS
-- ============================================================================

ALTER TABLE location ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organization(id);
ALTER TABLE partner ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organization(id);
ALTER TABLE staff ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organization(id);

CREATE INDEX IF NOT EXISTS idx_location_organization ON location(organization_id);
CREATE INDEX IF NOT EXISTS idx_partner_organization ON partner(organization_id);
CREATE INDEX IF NOT EXISTS idx_staff_organization ON staff(organization_id);

-- ============================================================================
-- VIEW
-- ============================================================================

CREATE OR REPLACE VIEW v_public_organization_summary AS
SELECT
    o.id,
    o.org_key,
    o.name,
    o.org_type,
    o.description,
    o.website,
    o.contact_email,
    o.legal_entity_name,
    o.jurisdiction,
    o.governance_model,
    o.status,
    (SELECT COUNT(*)::int FROM organization_member om WHERE om.organization_id = o.id AND om.status = 'active') AS farm_count,
    (SELECT COALESCE(SUM(f.total_area), 0) FROM organization_member om JOIN farm f ON om.farm_id = f.id WHERE om.organization_id = o.id AND om.status = 'active') AS total_area_ha,
    (SELECT COUNT(DISTINCT om.location_id) FROM organization_member om WHERE om.organization_id = o.id AND om.status = 'active') AS location_count,
    o.created_at
FROM organization o
WHERE o.status = 'active';

COMMIT;
