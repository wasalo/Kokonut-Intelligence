-- 061_impact_value_chain.sql
-- Impact Value Chain: Organizational Structure, Operational Planning, Framework Steps

BEGIN;

-- ============================================================================
-- 1. DEPARTMENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS department (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE TRIGGER trg_department_updated_at
    BEFORE UPDATE ON department
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE department IS 'Organizational departments (Operations, Ecology, Finance, Community, Governance)';

-- ============================================================================
-- 2. JOB ROLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS job_role (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    department_id UUID REFERENCES department(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_job_role_department ON job_role(department_id);

CREATE TRIGGER trg_job_role_updated_at
    BEFORE UPDATE ON job_role
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE job_role IS 'Job role definitions with department linkage';

-- ============================================================================
-- 3. FARM TASK
-- ============================================================================

CREATE TABLE IF NOT EXISTS farm_task (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    crop_cycle_id UUID REFERENCES crop_cycle(id) ON DELETE SET NULL,
    assignee_id UUID REFERENCES staff(id) ON DELETE SET NULL,
    task_name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL DEFAULT 'other'
        CHECK (category IN ('planting', 'weeding', 'irrigation', 'spraying', 'harvesting', 'maintenance', 'training', 'reporting', 'other')),
    start_date DATE,
    end_date DATE,
    duration_days INT,
    priority VARCHAR(50) NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    estimated_cost_usd NUMERIC(10,2),
    actual_cost_usd NUMERIC(10,2),
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_farm_task_location ON farm_task(location_id);
CREATE INDEX IF NOT EXISTS idx_farm_task_farm ON farm_task(farm_id);
CREATE INDEX IF NOT EXISTS idx_farm_task_status ON farm_task(status);
CREATE INDEX IF NOT EXISTS idx_farm_task_assignee ON farm_task(assignee_id);
CREATE INDEX IF NOT EXISTS idx_farm_task_dates ON farm_task(start_date, end_date);

CREATE TRIGGER trg_farm_task_updated_at
    BEFORE UPDATE ON farm_task
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE farm_task IS 'Planned farm tasks with scheduling, priorities, and assignees';

-- ============================================================================
-- 4. WEEKLY PLAN
-- ============================================================================

CREATE TABLE IF NOT EXISTS weekly_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    plan_name VARCHAR(255) NOT NULL,
    description TEXT,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    budget_forecast_usd NUMERIC(10,2),
    budget_actual_usd NUMERIC(10,2),
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'completed', 'archived')),
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_weekly_plan_location ON weekly_plan(location_id);
CREATE INDEX IF NOT EXISTS idx_weekly_plan_week ON weekly_plan(week_start, week_end);
CREATE INDEX IF NOT EXISTS idx_weekly_plan_status ON weekly_plan(status);

CREATE TRIGGER trg_weekly_plan_updated_at
    BEFORE UPDATE ON weekly_plan
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE weekly_plan IS 'Weekly action planning with budget tracking';

-- ============================================================================
-- 5. DEVELOPMENT PHASE
-- ============================================================================

CREATE TABLE IF NOT EXISTS development_phase (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    phase_name VARCHAR(255) NOT NULL,
    description TEXT,
    phase_order INT NOT NULL,
    start_date DATE,
    end_date DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'active', 'completed', 'paused')),
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_dev_phase_location ON development_phase(location_id);
CREATE INDEX IF NOT EXISTS idx_dev_phase_order ON development_phase(phase_order);
CREATE INDEX IF NOT EXISTS idx_dev_phase_status ON development_phase(status);

CREATE TRIGGER trg_dev_phase_updated_at
    BEFORE UPDATE ON development_phase
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE development_phase IS 'Farm lifecycle phases with sequencing and progress tracking';

-- ============================================================================
-- 6. FRAMEWORK STEP
-- ============================================================================

CREATE TABLE IF NOT EXISTS framework_step (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    step_name VARCHAR(255) NOT NULL,
    description TEXT,
    step_order INT NOT NULL,
    step_type VARCHAR(100) NOT NULL DEFAULT 'implementation'
        CHECK (step_type IN ('preparation', 'implementation', 'monitoring', 'verification', 'publication', 'other')),
    duration_days INT,
    prerequisites JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'skipped')),
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_framework_step_location ON framework_step(location_id);
CREATE INDEX IF NOT EXISTS idx_framework_step_order ON framework_step(step_order);
CREATE INDEX IF NOT EXISTS idx_framework_step_status ON framework_step(status);

CREATE TRIGGER trg_framework_step_updated_at
    BEFORE UPDATE ON framework_step
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE framework_step IS 'Sequenced methodology steps with prerequisites and progress tracking';

-- ============================================================================
-- 7. EXTEND STAFF TABLE
-- ============================================================================

ALTER TABLE staff ADD COLUMN IF NOT EXISTS job_role_id UUID REFERENCES job_role(id);
ALTER TABLE staff ADD COLUMN IF NOT EXISTS department_id UUID REFERENCES department(id);
ALTER TABLE staff ADD COLUMN IF NOT EXISTS hire_date DATE;
ALTER TABLE staff ADD COLUMN IF NOT EXISTS employment_status VARCHAR(50) DEFAULT 'active'
    CHECK (employment_status IN ('active', 'inactive', 'terminated', 'on_leave'));

CREATE INDEX IF NOT EXISTS idx_staff_job_role ON staff(job_role_id);
CREATE INDEX IF NOT EXISTS idx_staff_department ON staff(department_id);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- 1. Public farm tasks (gated: registry + status filter + PII stripped)
CREATE OR REPLACE VIEW v_public_farm_tasks AS
SELECT
    ft.id,
    ft.location_id,
    l.name AS location_name,
    ft.farm_id,
    f.name AS farm_name,
    ft.plot_id,
    p.name AS plot_name,
    ft.task_name,
    ft.category,
    ft.start_date,
    ft.end_date,
    ft.duration_days,
    ft.priority,
    ft.status,
    ft.estimated_cost_usd,
    ft.actual_cost_usd,
    CASE
        WHEN ft.status = 'completed' THEN 100
        WHEN ft.start_date IS NOT NULL AND ft.end_date IS NOT NULL AND CURRENT_DATE BETWEEN ft.start_date AND ft.end_date
        THEN ROUND(((CURRENT_DATE - ft.start_date)::numeric / (ft.end_date - ft.start_date)) * 100, 1)
        WHEN ft.start_date IS NOT NULL AND CURRENT_DATE > ft.end_date THEN 0
        ELSE 0
    END AS progress_pct,
    ft.created_at
FROM farm_task ft
JOIN location l ON ft.location_id = l.id
LEFT JOIN farm f ON ft.farm_id = f.id
LEFT JOIN plot p ON ft.plot_id = p.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND ft.status IN ('completed', 'in_progress')
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

-- 2. Public weekly plans
CREATE OR REPLACE VIEW v_public_weekly_plans AS
SELECT
    wp.id,
    wp.location_id,
    l.name AS location_name,
    wp.farm_id,
    f.name AS farm_name,
    wp.plan_name,
    wp.description,
    wp.week_start,
    wp.week_end,
    wp.budget_forecast_usd,
    wp.budget_actual_usd,
    CASE
        WHEN wp.budget_forecast_usd > 0 AND wp.budget_actual_usd IS NOT NULL
        THEN ROUND((wp.budget_actual_usd / wp.budget_forecast_usd * 100)::numeric, 1)
        ELSE NULL
    END AS budget_adherence_pct,
    (SELECT COUNT(*)::int FROM farm_task ft
     WHERE ft.location_id = wp.location_id
       AND ft.start_date >= wp.week_start AND ft.end_date <= wp.week_end) AS total_tasks,
    (SELECT COUNT(*)::int FROM farm_task ft
     WHERE ft.location_id = wp.location_id
       AND ft.start_date >= wp.week_start AND ft.end_date <= wp.week_end
       AND ft.status = 'completed') AS completed_tasks,
    wp.status,
    wp.notes,
    wp.created_at
FROM weekly_plan wp
JOIN location l ON wp.location_id = l.id
LEFT JOIN farm f ON wp.farm_id = f.id
WHERE l.status IN ('active', 'verified', 'published');

-- 3. Public development phases
CREATE OR REPLACE VIEW v_public_development_phases AS
SELECT
    dp.id,
    dp.location_id,
    l.name AS location_name,
    dp.farm_id,
    f.name AS farm_name,
    dp.phase_name,
    dp.description,
    dp.phase_order,
    dp.start_date,
    dp.end_date,
    dp.status,
    CASE
        WHEN dp.start_date IS NOT NULL AND dp.end_date IS NOT NULL AND CURRENT_DATE BETWEEN dp.start_date AND dp.end_date
        THEN ROUND(((CURRENT_DATE - dp.start_date)::numeric / (dp.end_date - dp.start_date)) * 100, 1)
        WHEN dp.status = 'completed' THEN 100
        WHEN dp.status = 'pending' THEN 0
        ELSE NULL
    END AS progress_pct,
    dp.notes,
    dp.created_at
FROM development_phase dp
JOIN location l ON dp.location_id = l.id
LEFT JOIN farm f ON dp.farm_id = f.id
WHERE l.status IN ('active', 'verified', 'published')
ORDER BY dp.phase_order;

-- 4. Public framework steps
CREATE OR REPLACE VIEW v_public_framework_steps AS
SELECT
    fs.id,
    fs.location_id,
    l.name AS location_name,
    fs.farm_id,
    f.name AS farm_name,
    fs.step_name,
    fs.description,
    fs.step_order,
    fs.step_type,
    fs.duration_days,
    fs.prerequisites,
    fs.status,
    fs.notes,
    fs.created_at
FROM framework_step fs
JOIN location l ON fs.location_id = l.id
LEFT JOIN farm f ON fs.farm_id = f.id
WHERE l.status IN ('active', 'verified', 'published')
ORDER BY fs.step_order;

COMMIT;
