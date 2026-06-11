-- ============================================================
-- Baserow Migration: New Tables DDL
-- Generated from field_analysis.json
-- ============================================================

-- ============================================================
-- 1. REFERENCE/LOOKUP TABLES
-- ============================================================

-- Department table
CREATE TABLE IF NOT EXISTS department (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Job Role table
CREATE TABLE IF NOT EXISTS job_role (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    department_id UUID REFERENCES department(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Impact Framework table
CREATE TABLE IF NOT EXISTS impact_framework (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    url VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- SDG table
CREATE TABLE IF NOT EXISTS sdg (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Form of Capital table
CREATE TABLE IF NOT EXISTS form_of_capital (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- 2. OPERATIONAL TABLES
-- ============================================================

-- Farm Task table
CREATE TABLE IF NOT EXISTS farm_task (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    start_date DATE,
    end_date DATE,
    duration_days INTEGER,
    category VARCHAR(100),
    quantity NUMERIC(15,2),
    cost_per_unit NUMERIC(15,2),
    status VARCHAR(50) DEFAULT 'pending',
    priority VARCHAR(50) DEFAULT 'medium',
    location_id UUID,
    farm_id UUID,
    plot_id UUID,
    crop_cycle_id UUID,
    assignee_id UUID,
    slug VARCHAR(255),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Resource Input table
CREATE TABLE IF NOT EXISTS resource_input (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    input_type VARCHAR(100),
    quantity NUMERIC(15,2),
    unit VARCHAR(50),
    cost NUMERIC(15,2),
    source VARCHAR(255),
    location_id UUID,
    farm_id UUID,
    plot_id UUID,
    crop_cycle_id UUID,
    slug VARCHAR(255),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Development Phase table
CREATE TABLE IF NOT EXISTS development_phase (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    phase_order INTEGER,
    start_date DATE,
    end_date DATE,
    status VARCHAR(50) DEFAULT 'pending',
    location_id UUID,
    farm_id UUID,
    plot_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Weekly Plan table
CREATE TABLE IF NOT EXISTS weekly_plan (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    week_start DATE,
    week_end DATE,
    budget_forecast NUMERIC(15,2),
    budget_actual NUMERIC(15,2),
    location_id UUID,
    farm_id UUID,
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- ============================================================
-- 3. IMPACT/GOVERNANCE TABLES
-- ============================================================

-- Impact Dimension table
CREATE TABLE IF NOT EXISTS impact_dimension (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    framework_id UUID REFERENCES impact_framework(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Objective table
CREATE TABLE IF NOT EXISTS objective (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    target_date DATE,
    target_value NUMERIC(15,2),
    current_value NUMERIC(15,2),
    unit VARCHAR(50),
    status VARCHAR(50) DEFAULT 'active',
    location_id UUID,
    farm_id UUID,
    parent_id UUID REFERENCES objective(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Funding table
CREATE TABLE IF NOT EXISTS funding (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    grant_amount NUMERIC(15,2),
    crowdfunding_amount NUMERIC(15,2),
    total_amount NUMERIC(15,2),
    funding_date DATE,
    organization_id UUID,
    status VARCHAR(50) DEFAULT 'active',
    slug VARCHAR(255),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Funding Milestone table
CREATE TABLE IF NOT EXISTS funding_milestone (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(50),
    start_date DATE,
    end_date DATE,
    achieved_date DATE,
    status VARCHAR(50) DEFAULT 'pending',
    funding_id UUID REFERENCES funding(id),
    slug VARCHAR(255),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Milestone Outcome table
CREATE TABLE IF NOT EXISTS milestone_outcome (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    proof_url VARCHAR(500),
    milestone_id UUID REFERENCES funding_milestone(id),
    objective_id UUID REFERENCES objective(id),
    status VARCHAR(50) DEFAULT 'pending',
    slug VARCHAR(255),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Impact Record table
CREATE TABLE IF NOT EXISTS impact_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    work_description TEXT,
    impact_description TEXT,
    work_start_date DATE,
    work_end_date DATE,
    evidence_url VARCHAR(500),
    impact_url VARCHAR(500),
    verification_notes TEXT,
    impact_level VARCHAR(50),
    impact_score NUMERIC(5,2),
    dimension_id UUID REFERENCES impact_dimension(id),
    framework_id UUID REFERENCES impact_framework(id),
    location_id UUID,
    farm_id UUID,
    status VARCHAR(50) DEFAULT 'draft',
    slug VARCHAR(255),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- EBF Record table
CREATE TABLE IF NOT EXISTS ebf_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    category VARCHAR(100),
    value NUMERIC(15,2),
    unit VARCHAR(50),
    location_id UUID,
    farm_id UUID,
    period_start DATE,
    period_end DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- ============================================================
-- 4. STRUCTURAL TABLES
-- ============================================================

-- Framework Step table
CREATE TABLE IF NOT EXISTS framework_step (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    duration_days INTEGER,
    step_order INTEGER,
    step_type VARCHAR(100),
    prerequisites JSONB DEFAULT '[]',
    location_id UUID,
    farm_id UUID,
    plot_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Dependency table
CREATE TABLE IF NOT EXISTS dependency (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    url VARCHAR(500),
    dependency_type VARCHAR(100),
    entity_type VARCHAR(100),
    entity_id UUID,
    required_by_entity_type VARCHAR(100),
    required_by_entity_id UUID,
    criticality VARCHAR(50) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ecosystem Branch table
CREATE TABLE IF NOT EXISTS ecosystem_branch (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    parent_id UUID REFERENCES ecosystem_branch(id),
    branch_type VARCHAR(100),
    location_id UUID REFERENCES location(id),
    farm_id UUID REFERENCES farm(id),
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ground Analytics Snapshot table
CREATE TABLE IF NOT EXISTS ground_analytics_snapshot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    snapshot_date DATE,
    metrics JSONB DEFAULT '{}',
    location_id UUID,
    farm_id UUID,
    plot_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- ============================================================
-- 5. ACTIVITY EXTENSION TABLES
-- ============================================================

-- Activity Output table
CREATE TABLE IF NOT EXISTS activity_output (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    proof_url VARCHAR(500),
    activity_id UUID,
    crop_cycle_id UUID,
    location_id UUID,
    farm_id UUID,
    plot_id UUID,
    status VARCHAR(50) DEFAULT 'completed',
    slug VARCHAR(255),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Activity Metric table
CREATE TABLE IF NOT EXISTS activity_metric (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    value NUMERIC(15,2),
    unit VARCHAR(50),
    proof_url VARCHAR(500),
    activity_id UUID,
    crop_cycle_id UUID,
    location_id UUID,
    farm_id UUID,
    plot_id UUID,
    slug VARCHAR(255),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Farm Task indexes
CREATE INDEX idx_farm_task_location ON farm_task(location_id);
CREATE INDEX idx_farm_task_farm ON farm_task(farm_id);
CREATE INDEX idx_farm_task_plot ON farm_task(plot_id);
CREATE INDEX idx_farm_task_crop_cycle ON farm_task(crop_cycle_id);
CREATE INDEX idx_farm_task_status ON farm_task(status);
CREATE INDEX idx_farm_task_start_date ON farm_task(start_date);

-- Resource Input indexes
CREATE INDEX idx_resource_input_location ON resource_input(location_id);
CREATE INDEX idx_resource_input_farm ON resource_input(farm_id);
CREATE INDEX idx_resource_input_plot ON resource_input(plot_id);
CREATE INDEX idx_resource_input_crop_cycle ON resource_input(crop_cycle_id);

-- Weekly Plan indexes
CREATE INDEX idx_weekly_plan_location ON weekly_plan(location_id);
CREATE INDEX idx_weekly_plan_farm ON weekly_plan(farm_id);
CREATE INDEX idx_weekly_plan_week_start ON weekly_plan(week_start);

-- Objective indexes
CREATE INDEX idx_objective_location ON objective(location_id);
CREATE INDEX idx_objective_farm ON objective(farm_id);
CREATE INDEX idx_objective_parent ON objective(parent_id);

-- Funding indexes
CREATE INDEX idx_funding_organization ON funding(organization_id);
CREATE INDEX idx_funding_date ON funding(funding_date);

-- Funding Milestone indexes
CREATE INDEX idx_funding_milestone_funding ON funding_milestone(funding_id);
CREATE INDEX idx_funding_milestone_status ON funding_milestone(status);

-- Milestone Outcome indexes
CREATE INDEX idx_milestone_outcome_milestone ON milestone_outcome(milestone_id);
CREATE INDEX idx_milestone_outcome_objective ON milestone_outcome(objective_id);

-- Impact Record indexes
CREATE INDEX idx_impact_record_dimension ON impact_record(dimension_id);
CREATE INDEX idx_impact_record_framework ON impact_record(framework_id);
CREATE INDEX idx_impact_record_location ON impact_record(location_id);
CREATE INDEX idx_impact_record_farm ON impact_record(farm_id);

-- Activity Output indexes
CREATE INDEX idx_activity_output_activity ON activity_output(activity_id);
CREATE INDEX idx_activity_output_crop_cycle ON activity_output(crop_cycle_id);

-- Activity Metric indexes
CREATE INDEX idx_activity_metric_activity ON activity_metric(activity_id);
CREATE INDEX idx_activity_metric_crop_cycle ON activity_metric(crop_cycle_id);

-- ============================================================
-- ============================================================
-- 7. PRD-REQUIRED TABLES
-- ============================================================

-- Inventory Event table (PRD 7.2)
CREATE TABLE IF NOT EXISTS inventory_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id),
    farm_id UUID REFERENCES farm(id),
    plot_id UUID REFERENCES plot(id),
    item_name VARCHAR(255) NOT NULL,
    item_category VARCHAR(100),
    event_type VARCHAR(50) NOT NULL, -- purchase, usage, transfer, adjustment
    quantity NUMERIC(12,4) NOT NULL,
    unit VARCHAR(50),
    unit_cost NUMERIC(15,2),
    total_cost NUMERIC(15,2),
    supplier VARCHAR(255),
    reference_number VARCHAR(100),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Maintenance Event table (PRD 7.2)
CREATE TABLE IF NOT EXISTS maintenance_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_id UUID REFERENCES infrastructure_asset(id),
    location_id UUID REFERENCES location(id),
    farm_id UUID REFERENCES farm(id),
    maintenance_type VARCHAR(100) NOT NULL, -- preventive, corrective, emergency
    description TEXT NOT NULL,
    scheduled_date DATE,
    completed_date DATE,
    performed_by UUID REFERENCES staff(id),
    cost NUMERIC(15,2),
    parts_used JSONB DEFAULT '[]',
    downtime_hours NUMERIC(8,2),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'scheduled',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Revenue Event table (PRD 7.3)
CREATE TABLE IF NOT EXISTS revenue_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id),
    farm_id UUID REFERENCES farm(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    revenue_type VARCHAR(100) NOT NULL, -- sales, grant, sponsorship, service, other
    description TEXT,
    amount NUMERIC(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    received_date DATE,
    reference_number VARCHAR(100),
    partner_id UUID REFERENCES partner(id),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- COMMENTS
-- ============================================================

COMMENT ON TABLE department IS 'Organizational departments from Baserow';
COMMENT ON TABLE job_role IS 'Job roles within departments from Baserow';
COMMENT ON TABLE impact_framework IS 'Impact measurement frameworks (IRIS+, GRI, etc.)';
COMMENT ON TABLE sdg IS 'UN Sustainable Development Goals reference data';
COMMENT ON TABLE form_of_capital IS 'Capital categories (social, natural, produced, human)';
COMMENT ON TABLE farm_task IS 'Discrete farm tasks with assignments and deadlines';
COMMENT ON TABLE resource_input IS 'Input resources (seeds, fertilizer, water, feed)';
COMMENT ON TABLE development_phase IS 'Farm/project lifecycle phases';
COMMENT ON TABLE weekly_plan IS 'Scheduled weekly work plans';
COMMENT ON TABLE impact_dimension IS 'Dimensions of impact measurement';
COMMENT ON TABLE objective IS 'Strategic goals and targets';
COMMENT ON TABLE funding IS 'Funding sources and grants';
COMMENT ON TABLE funding_milestone IS 'Milestone-based funding tranches';
COMMENT ON TABLE milestone_outcome IS 'Outcomes tied to funding milestones';
COMMENT ON TABLE impact_record IS 'Aggregated impact measurements';
COMMENT ON TABLE ebf_record IS 'Economic/Bio/Financial framework records';
COMMENT ON TABLE framework_step IS 'Process/methodology steps';
COMMENT ON TABLE dependency IS 'Dependency tracking between entities';
COMMENT ON TABLE ground_analytics_snapshot IS 'Composite ground analytics data';
COMMENT ON TABLE activity_output IS 'Outputs from farm activities';
COMMENT ON TABLE activity_metric IS 'Metrics from farm activities';
