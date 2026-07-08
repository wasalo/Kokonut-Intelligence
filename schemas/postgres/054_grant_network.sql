-- ============================================================
-- 054_grant_network.sql — Grant application history, regional chapters, network diversity
-- ============================================================

-- Grant application history: tracks each grant application with cycle tracking
CREATE TABLE IF NOT EXISTS grant_application_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    grant_name VARCHAR(255) NOT NULL,
    grantor VARCHAR(255),
    application_date DATE NOT NULL,
    application_status VARCHAR(50) DEFAULT 'submitted',
    grant_cycle VARCHAR(100),
    grant_cycle_number INTEGER DEFAULT 1,
    previous_grant_id UUID REFERENCES grant_application_history(id) ON DELETE SET NULL,
    is_returning_applicant BOOLEAN DEFAULT FALSE,
    amount_requested NUMERIC(15,2),
    amount_awarded NUMERIC(15,2),
    currency VARCHAR(10) DEFAULT 'USD',
    grant_period_start DATE,
    grant_period_end DATE,
    funding_focus TEXT,
    ecological_metrics_submitted JSONB DEFAULT '{}',
    onchain_offchain_flow_description TEXT,
    community_partnerships TEXT[],
    geographic_region VARCHAR(100),
    notes TEXT,
    -- Governance
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'grant-network-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_grant_hist_location ON grant_application_history(location_id);
CREATE INDEX IF NOT EXISTS idx_grant_hist_date ON grant_application_history(application_date);
CREATE INDEX IF NOT EXISTS idx_grant_hist_status ON grant_application_history(application_status);
CREATE INDEX IF NOT EXISTS idx_grant_hist_cycle ON grant_application_history(grant_cycle);
CREATE INDEX IF NOT EXISTS idx_grant_hist_returning ON grant_application_history(is_returning_applicant);
CREATE INDEX IF NOT EXISTS idx_grant_hist_previous ON grant_application_history(previous_grant_id);

ALTER TABLE grant_application_history DROP CONSTRAINT IF EXISTS chk_grant_hist_status;
ALTER TABLE grant_application_history ADD CONSTRAINT chk_grant_hist_status CHECK (application_status IN (
    'draft', 'submitted', 'under_review', 'approved', 'rejected', 'funded', 'completed', 'expired'
));

-- Add returning_applicant flag to farm_registry_record
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS returning_applicant BOOLEAN DEFAULT FALSE;
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS grant_count INTEGER DEFAULT 0;
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS total_grants_received NUMERIC(15,2) DEFAULT 0;

-- Regional chapter: maps farms to regional chapters/networks
CREATE TABLE IF NOT EXISTS regional_chapter (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chapter_name VARCHAR(255) NOT NULL,
    chapter_key VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    geographic_region VARCHAR(100),
    country VARCHAR(100),
    region VARCHAR(100),
    sub_region VARCHAR(100),
    chapter_type VARCHAR(100),
    coordinator_name VARCHAR(255),
    coordinator_wallet VARCHAR(42),
    founding_date DATE,
    status VARCHAR(50) DEFAULT 'active',
    notes TEXT,
    -- Governance
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'grant-network-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_chapter_region ON regional_chapter(geographic_region);
CREATE INDEX IF NOT EXISTS idx_chapter_country ON regional_chapter(country);
CREATE INDEX IF NOT EXISTS idx_chapter_status ON regional_chapter(status);

ALTER TABLE regional_chapter DROP CONSTRAINT IF EXISTS chk_chapter_type;
ALTER TABLE regional_chapter ADD CONSTRAINT chk_chapter_type CHECK (
    chapter_type IS NULL OR chapter_type IN (
        'regional', 'national', 'continental', 'thematic', 'research', 'other'
    )
);

ALTER TABLE regional_chapter DROP CONSTRAINT IF EXISTS chk_chapter_status;
ALTER TABLE regional_chapter ADD CONSTRAINT chk_chapter_status CHECK (status IN (
    'active', 'inactive', 'dissolved', 'merging'
));

-- Network membership: links farms to regional chapters
CREATE TABLE IF NOT EXISTS network_membership (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    chapter_id UUID NOT NULL REFERENCES regional_chapter(id) ON DELETE CASCADE,
    membership_type VARCHAR(100) DEFAULT 'member',
    join_date DATE,
    role VARCHAR(100),
    contribution_focus TEXT,
    status VARCHAR(50) DEFAULT 'active',
    notes TEXT,
    -- Governance
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'grant-network-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_membership_location ON network_membership(location_id);
CREATE INDEX IF NOT EXISTS idx_membership_chapter ON network_membership(chapter_id);
CREATE INDEX IF NOT EXISTS idx_membership_status ON network_membership(status);

ALTER TABLE network_membership DROP CONSTRAINT IF EXISTS chk_membership_type;
ALTER TABLE network_membership ADD CONSTRAINT chk_membership_type CHECK (
    membership_type IN ('member', 'founding_member', 'affiliate', 'observer', 'partner')
);

ALTER TABLE network_membership DROP CONSTRAINT IF EXISTS chk_membership_status;
ALTER TABLE network_membership ADD CONSTRAINT chk_membership_status CHECK (status IN (
    'active', 'inactive', 'suspended', 'transferred'
));

-- ============================================================
-- Public-safe views
-- ============================================================

CREATE OR REPLACE VIEW v_public_grant_application_history AS
SELECT
    gah.id,
    gah.location_id,
    l.name AS location_name,
    gah.grant_name,
    gah.grantor,
    gah.application_date,
    gah.application_status,
    gah.grant_cycle,
    gah.grant_cycle_number,
    gah.is_returning_applicant,
    gah.amount_requested,
    gah.amount_awarded,
    gah.currency,
    gah.funding_focus,
    gah.community_partnerships,
    gah.geographic_region,
    gah.notes,
    gah.status
FROM grant_application_history gah
JOIN location l ON l.id = gah.location_id
WHERE l.status = 'active'
  AND gah.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_regional_chapters AS
SELECT
    rc.id,
    rc.chapter_name,
    rc.chapter_key,
    rc.description,
    rc.geographic_region,
    rc.country,
    rc.region,
    rc.chapter_type,
    rc.founding_date,
    rc.status,
    (SELECT COUNT(*) FROM network_membership nm WHERE nm.chapter_id = rc.id AND nm.status = 'active') AS member_count,
    (SELECT COUNT(DISTINCT nm.location_id) FROM network_membership nm WHERE nm.chapter_id = rc.id AND nm.status = 'active') AS farm_count
FROM regional_chapter rc
WHERE rc.status = 'active';

CREATE OR REPLACE VIEW v_network_diversity AS
SELECT
    rc.geographic_region,
    rc.country,
    rc.chapter_name,
    COUNT(DISTINCT nm.location_id) AS farm_count,
    COUNT(DISTINCT l.id) AS location_count,
    ARRAY_AGG(DISTINCT l.country) AS countries_represented,
    (SELECT COUNT(DISTINCT so.species_name)
     FROM species_observation so
     JOIN network_membership nm2 ON nm2.location_id = so.location_id
     WHERE nm2.chapter_id = rc.id
       AND so.status IN ('verified', 'published')
    ) AS unique_species_count,
    (SELECT AVG/ros.regenerative_score
     FROM regenerative_outcome_summary ros
     JOIN network_membership nm3 ON nm3.location_id = ros.location_id
     WHERE nm3.chapter_id = rc.id
       AND ros.status IN ('verified', 'published')
    ) AS avg_regenerative_score
FROM regional_chapter rc
JOIN network_membership nm ON nm.chapter_id = rc.id AND nm.status = 'active'
JOIN location l ON l.id = nm.location_id
WHERE rc.status = 'active'
GROUP BY rc.id, rc.geographic_region, rc.country, rc.chapter_name;

CREATE OR REPLACE VIEW v_public_farm_network_summary AS
SELECT
    fr.location_id,
    l.name AS location_name,
    l.country,
    fr.returning_applicant,
    fr.grant_count,
    fr.total_grants_received,
    (SELECT COUNT(*) FROM grant_application_history gah WHERE gah.location_id = fr.location_id AND gah.status IN ('verified', 'published')) AS total_applications,
    (SELECT COUNT(*) FROM grant_application_history gah WHERE gah.location_id = fr.location_id AND gah.application_status = 'funded') AS funded_applications,
    (SELECT STRING_AGG(DISTINCT nm.chapter_name, ', ')
     FROM network_membership mem
     JOIN regional_chapter nm ON nm.id = mem.chapter_id
     WHERE mem.location_id = fr.location_id AND mem.status = 'active'
    ) AS chapter_memberships
FROM farm_registry_record fr
JOIN location l ON l.id = fr.location_id
WHERE l.status = 'active'
  AND fr.status IN ('verified', 'published');

INSERT INTO schema_version (version, description, applied_by)
VALUES ('grant-network-v1', 'Grant application history, regional chapters, network membership, network diversity views', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
