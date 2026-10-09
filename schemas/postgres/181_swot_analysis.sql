-- ============================================================
-- 181_swot_analysis.sql - SWOT analysis (business plan section)
-- ============================================================
-- Structured Strengths / Weaknesses / Opportunities / Threats
-- framework for an organization or a single location. Supports the
-- business-plan assembler (services/export/business_plan.py). Threats and
-- opportunities can be auto-suggested from threatcasting + CRISP; the
-- arrays remain human-editable and follow the governed lifecycle.

CREATE TABLE IF NOT EXISTS swot_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organization(id) ON DELETE CASCADE,
    location_id UUID REFERENCES location(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN ('organization', 'location')),
    entity_id UUID NOT NULL,
    strengths TEXT[],
    weaknesses TEXT[],
    opportunities TEXT[],
    threats TEXT[],
    generated_from TEXT[],
    status VARCHAR(50) DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    created_by UUID,
    updated_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_swot_organization ON swot_analysis(organization_id);
CREATE INDEX IF NOT EXISTS idx_swot_location ON swot_analysis(location_id);
CREATE INDEX IF NOT EXISTS idx_swot_entity ON swot_analysis(entity_type, entity_id);
