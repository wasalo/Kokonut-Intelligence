-- ============================================================
-- 175_management_work_items.sql - Work / task management
-- ============================================================

DO $$ BEGIN
    CREATE TYPE work_item_status AS ENUM ('draft', 'assigned', 'in_progress', 'blocked', 'done', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE work_item_priority AS ENUM ('low', 'medium', 'high', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- A work item is a unit of assigned human/agent work, distinct from the
-- automation cron substrate (scheduled_task / task_run). It is lifecycle-
-- governed by the work_item workflow specification.
CREATE TABLE IF NOT EXISTS work_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status work_item_status NOT NULL DEFAULT 'draft',
    priority work_item_priority NOT NULL DEFAULT 'medium',
    assignee_type VARCHAR(20)
        CHECK (assignee_type IN ('staff', 'farmer', 'agent', 'team')),
    assignee_id UUID,
    created_by_type VARCHAR(20) NOT NULL
        CHECK (created_by_type IN ('staff', 'farmer', 'agent', 'system')),
    created_by_id UUID,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    parent_work_item_id UUID REFERENCES work_item(id) ON DELETE SET NULL,
    objective_id UUID,
    risk_id UUID,
    due_at TIMESTAMPTZ,
    sla_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Cannot leave draft (or be cancelled) without an assignee.
    CONSTRAINT work_item_assignee_required
        CHECK (status = 'draft' OR status = 'cancelled' OR assignee_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_work_item_org ON work_item(organization_id);
CREATE INDEX IF NOT EXISTS idx_work_item_assignee ON work_item(assignee_type, assignee_id, status);
CREATE INDEX IF NOT EXISTS idx_work_item_due ON work_item(due_at)
    WHERE status NOT IN ('done', 'cancelled');
CREATE INDEX IF NOT EXISTS idx_work_item_parent ON work_item(parent_work_item_id);

-- Append-only audit trail of work-item lifecycle transitions.
CREATE TABLE IF NOT EXISTS work_item_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id UUID NOT NULL REFERENCES work_item(id) ON DELETE CASCADE,
    actor_type VARCHAR(20) NOT NULL
        CHECK (actor_type IN ('staff', 'farmer', 'agent', 'system')),
    actor_id UUID,
    from_status work_item_status,
    to_status work_item_status,
    action VARCHAR(60),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_work_item_event_item ON work_item_event(work_item_id);

DROP TRIGGER IF EXISTS trg_work_item_updated_at ON work_item;
CREATE TRIGGER trg_work_item_updated_at
    BEFORE UPDATE ON work_item
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE work_item IS 'Assigned human/agent work items with a governed lifecycle';
COMMENT ON TABLE work_item_event IS 'Append-only audit trail of work-item lifecycle transitions';
