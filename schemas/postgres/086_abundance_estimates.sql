-- ============================================================
-- 086_abundance_estimates.sql — Impact Estimate Posts
-- ============================================================

-- 1. Impact estimate post
CREATE TABLE IF NOT EXISTS impact_estimate_post (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_hash VARCHAR(66) NOT NULL,
    project_id UUID,
    estimator_id UUID REFERENCES evaluator(id) ON DELETE SET NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    estimated_impact_score NUMERIC(12,4) NOT NULL,
    credibility_score NUMERIC(5,4),
    urgency VARCHAR(50) DEFAULT 'normal',
    effort_level VARCHAR(50) NOT NULL,
    validation_fee NUMERIC(12,4),
    comments TEXT,
    supporting_sources TEXT[],
    status VARCHAR(50) DEFAULT 'draft',
    waiting_list_position INTEGER,
    validation_started_at TIMESTAMPTZ,
    validated_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eep_project ON impact_estimate_post(project_hash);
CREATE INDEX IF NOT EXISTS idx_eep_estimator ON impact_estimate_post(estimator_id);
CREATE INDEX IF NOT EXISTS idx_eep_status ON impact_estimate_post(status);
CREATE INDEX IF NOT EXISTS idx_eep_waiting ON impact_estimate_post(waiting_list_position);

ALTER TABLE impact_estimate_post DROP CONSTRAINT IF EXISTS chk_eep_urgency;
ALTER TABLE impact_estimate_post ADD CONSTRAINT chk_eep_urgency CHECK (urgency IN ('normal', 'urgent'));

ALTER TABLE impact_estimate_post DROP CONSTRAINT IF EXISTS chk_eep_effort;
ALTER TABLE impact_estimate_post ADD CONSTRAINT chk_eep_effort CHECK (effort_level IN ('low', 'medium', 'high', 'very_high'));

ALTER TABLE impact_estimate_post DROP CONSTRAINT IF EXISTS chk_eep_status;
ALTER TABLE impact_estimate_post ADD CONSTRAINT chk_eep_status CHECK (status IN (
    'draft', 'submitted', 'waiting_list', 'validating', 'validated', 'disputed', 'finalized', 'rejected'
));

-- 2. Estimate category assignment
CREATE TABLE IF NOT EXISTS estimate_category_assignment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    estimate_id UUID NOT NULL REFERENCES impact_estimate_post(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES expertise_category(id) ON DELETE RESTRICT,
    relative_impact_score NUMERIC(8,4) NOT NULL,
    justification TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eca_estimate ON estimate_category_assignment(estimate_id);
CREATE INDEX IF NOT EXISTS idx_eca_category ON estimate_category_assignment(category_id);

-- 3. Waiting list entry
CREATE TABLE IF NOT EXISTS waiting_list_entry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    estimate_id UUID NOT NULL REFERENCES impact_estimate_post(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    sort_score NUMERIC(12,6) NOT NULL,
    credibility_component NUMERIC(8,4),
    impact_component NUMERIC(8,4),
    expertise_component NUMERIC(8,4),
    status VARCHAR(50) DEFAULT 'queued',
    entered_at TIMESTAMPTZ DEFAULT NOW(),
    dequeued_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_wle_position ON waiting_list_entry(position);
CREATE INDEX IF NOT EXISTS idx_wle_status ON waiting_list_entry(status);
CREATE INDEX IF NOT EXISTS idx_wle_sort ON waiting_list_entry(sort_score DESC);

ALTER TABLE waiting_list_entry DROP CONSTRAINT IF EXISTS chk_wle_status;
ALTER TABLE waiting_list_entry ADD CONSTRAINT chk_wle_status CHECK (status IN ('queued', 'processing', 'dequeued', 'cancelled'));

-- 4. Expertise category
CREATE TABLE IF NOT EXISTS expertise_category (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    parent_category_id UUID REFERENCES expertise_category(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_by UUID REFERENCES evaluator(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ec_parent ON expertise_category(parent_category_id);
CREATE INDEX IF NOT EXISTS idx_ec_active ON expertise_category(is_active);

-- 5. Category relatedness
CREATE TABLE IF NOT EXISTS category_relatedness (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_a_id UUID NOT NULL REFERENCES expertise_category(id) ON DELETE CASCADE,
    category_b_id UUID NOT NULL REFERENCES expertise_category(id) ON DELETE CASCADE,
    relatedness_coefficient NUMERIC(5,4) NOT NULL CHECK (relatedness_coefficient >= 0 AND relatedness_coefficient <= 1),
    co_occurrence_count INTEGER DEFAULT 0,
    avg_impact_weight NUMERIC(8,4),
    last_computed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(category_a_id, category_b_id)
);

CREATE INDEX IF NOT EXISTS idx_cr_cat_a ON category_relatedness(category_a_id);
CREATE INDEX IF NOT EXISTS idx_cr_cat_b ON category_relatedness(category_b_id);

-- 6. Category graft
CREATE TABLE IF NOT EXISTS category_graft (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    new_category_id UUID NOT NULL REFERENCES expertise_category(id) ON DELETE CASCADE,
    graft_initiated_by UUID REFERENCES evaluator(id) ON DELETE SET NULL,
    related_category_ids UUID[] NOT NULL,
    estimated_coefficients JSONB NOT NULL,
    validator_adjustments JSONB DEFAULT '{}',
    final_coefficients JSONB,
    status VARCHAR(50) DEFAULT 'proposed',
    graft_completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cg_status ON category_graft(status);

ALTER TABLE category_graft DROP CONSTRAINT IF EXISTS chk_cg_status;
ALTER TABLE category_graft ADD CONSTRAINT chk_cg_status CHECK (status IN ('proposed', 'validating', 'accepted', 'rejected'));
