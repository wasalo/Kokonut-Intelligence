-- ============================================================
-- 207_capability_map.sql — Business Architecture Capability Map
-- ============================================================
-- Core business architecture artifact: maps Guild strategy →
-- capabilities → processes → services with maturity tracking.

CREATE TABLE IF NOT EXISTS business_capability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    capability_type VARCHAR(30) NOT NULL DEFAULT 'core'
        CHECK (capability_type IN ('strategic', 'core', 'support')),
    parent_id UUID REFERENCES business_capability(id) ON DELETE SET NULL,
    guild_key VARCHAR(50),
    maturity_level SMALLINT CHECK (maturity_level BETWEEN 1 AND 5),
    owner_role VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'deprecated', 'planned')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bcap_parent ON business_capability(parent_id);
CREATE INDEX IF NOT EXISTS idx_bcap_guild ON business_capability(guild_key);
CREATE INDEX IF NOT EXISTS idx_bcap_type ON business_capability(capability_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bcap_name_guild ON business_capability(name, guild_key);

DROP TRIGGER IF EXISTS trg_bcap_updated_at ON business_capability;
CREATE TRIGGER trg_bcap_updated_at
    BEFORE UPDATE ON business_capability
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- Capability → Process mapping
-- ============================================================
CREATE TABLE IF NOT EXISTS capability_process_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capability_id UUID NOT NULL REFERENCES business_capability(id) ON DELETE CASCADE,
    process_key VARCHAR(100) NOT NULL REFERENCES process_map(process_key) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (capability_id, process_key)
);

CREATE INDEX IF NOT EXISTS idx_cpm_capability ON capability_process_map(capability_id);
CREATE INDEX IF NOT EXISTS idx_cpm_process ON capability_process_map(process_key);

-- ============================================================
-- Capability → Service mapping
-- ============================================================
CREATE TABLE IF NOT EXISTS capability_service_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capability_id UUID NOT NULL REFERENCES business_capability(id) ON DELETE CASCADE,
    service_name VARCHAR(100) NOT NULL REFERENCES service_registry(name) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (capability_id, service_name)
);

CREATE INDEX IF NOT EXISTS idx_csm_capability ON capability_service_map(capability_id);
CREATE INDEX IF NOT EXISTS idx_csm_service ON capability_service_map(service_name);

-- ============================================================
-- Maturity assessments
-- ============================================================
CREATE TABLE IF NOT EXISTS capability_maturity_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capability_id UUID NOT NULL REFERENCES business_capability(id) ON DELETE CASCADE,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    maturity_level SMALLINT NOT NULL CHECK (maturity_level BETWEEN 1 AND 5),
    assessed_by VARCHAR(100),
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_cma_capability ON capability_maturity_assessment(capability_id);
CREATE INDEX IF NOT EXISTS idx_cma_assessed_at ON capability_maturity_assessment(assessed_at);

-- ============================================================
-- View: Capability dashboard
-- ============================================================
CREATE OR REPLACE VIEW v_capability_dashboard AS
SELECT
    bc.id AS capability_id,
    bc.name AS capability_name,
    bc.capability_type,
    bc.guild_key,
    bc.maturity_level,
    bc.owner_role,
    bc.status,
    bc.parent_id,
    parent.name AS parent_name,
    (SELECT COUNT(*) FROM capability_process_map cpm WHERE cpm.capability_id = bc.id) AS process_count,
    (SELECT COUNT(*) FROM capability_service_map csm WHERE csm.capability_id = bc.id) AS service_count,
    (SELECT COUNT(*) FROM business_capability child WHERE child.parent_id = bc.id) AS child_count,
    (SELECT ROUND(AVG(cma.maturity_level), 1)
     FROM capability_maturity_assessment cma
     WHERE cma.capability_id = bc.id
       AND cma.assessed_at = (
           SELECT MAX(cma2.assessed_at)
           FROM capability_maturity_assessment cma2
           WHERE cma2.capability_id = bc.id
       )) AS latest_maturity_score,
    bc.created_at,
    bc.updated_at
FROM business_capability bc
LEFT JOIN business_capability parent ON bc.parent_id = parent.id;

COMMENT ON TABLE business_capability IS 'Business architecture capability map: Guild → capability → process → service hierarchy';
COMMENT ON TABLE capability_process_map IS 'Links capabilities to governed processes in the process_map taxonomy';
COMMENT ON TABLE capability_service_map IS 'Links capabilities to registered services in the service_registry';
COMMENT ON TABLE capability_maturity_assessment IS 'Historical maturity assessments per capability (CMMI 1-5 scale)';
COMMENT ON VIEW v_capability_dashboard IS 'Aggregated capability view with process/service counts and latest maturity';
