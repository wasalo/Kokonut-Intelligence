-- ============================================================
-- 178_program_portfolio.sql - Program / project portfolio (PPM)
-- ============================================================

DO $$ BEGIN
    CREATE TYPE portfolio_status AS ENUM ('draft', 'active', 'on_hold', 'done', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- A program groups projects toward an objective and (optionally) a budget.
CREATE TABLE IF NOT EXISTS program (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    objective_id UUID REFERENCES objective(id) ON DELETE SET NULL,
    budget_id UUID REFERENCES financial_plan(id) ON DELETE SET NULL,
    status portfolio_status NOT NULL DEFAULT 'draft',
    created_by_type VARCHAR(20) NOT NULL DEFAULT 'system'
        CHECK (created_by_type IN ('staff', 'farmer', 'agent', 'system')),
    created_by_id UUID,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_program_org ON program(organization_id);
CREATE INDEX IF NOT EXISTS idx_program_objective ON program(objective_id);

-- A project is a unit of delivery that groups work items and links budget + objective.
CREATE TABLE IF NOT EXISTS project (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID REFERENCES program(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    objective_id UUID REFERENCES objective(id) ON DELETE SET NULL,
    budget_id UUID REFERENCES financial_plan(id) ON DELETE SET NULL,
    status portfolio_status NOT NULL DEFAULT 'draft',
    due_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_program ON project(program_id);
CREATE INDEX IF NOT EXISTS idx_project_org ON project(organization_id);

-- Tie work items to projects (additive; work_item already exists in 175).
ALTER TABLE work_item
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES project(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_work_item_project ON work_item(project_id);

DROP TRIGGER IF EXISTS trg_program_updated_at ON program;
CREATE TRIGGER trg_program_updated_at
    BEFORE UPDATE ON program
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_project_updated_at ON project;
CREATE TRIGGER trg_project_updated_at
    BEFORE UPDATE ON project
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE program IS 'Program grouping projects toward an objective and budget';
COMMENT ON TABLE project IS 'Project grouping work items and linking budget + objective';
