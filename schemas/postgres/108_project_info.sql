-- ProjectInfo parity: Generic links and reference IDs for projects

-- ============================================================
-- project_link (hasLinks)
-- ============================================================
CREATE TABLE IF NOT EXISTS project_link (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    link_name VARCHAR(255) NOT NULL,
    link_url TEXT NOT NULL,
    link_description TEXT,
    link_type VARCHAR(50) DEFAULT 'external',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pl_location ON project_link(location_id);
CREATE INDEX idx_pl_type ON project_link(link_type);

-- ============================================================
-- project_reference_id (hasReferenceId)
-- ============================================================
CREATE TABLE IF NOT EXISTS project_reference_id (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    identifier VARCHAR(255) NOT NULL,
    reference_type VARCHAR(100) NOT NULL,
    registry_name VARCHAR(255),
    url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pri_location ON project_reference_id(location_id);
CREATE INDEX idx_pri_type ON project_reference_id(reference_type);
