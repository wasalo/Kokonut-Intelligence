-- ============================================================
-- 361_farm_task_relationships.sql
-- Typed task dependencies and cross-domain task relationships.
-- ============================================================

BEGIN;

ALTER TABLE expense_event
    ADD COLUMN IF NOT EXISTS farm_task_id UUID REFERENCES farm_task(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_expense_event_farm_task
    ON expense_event(farm_task_id);

CREATE OR REPLACE FUNCTION validate_expense_event_farm_task_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    task_location_id UUID;
BEGIN
    IF NEW.farm_task_id IS NOT NULL THEN
        SELECT t.location_id INTO task_location_id
        FROM farm_task t
        WHERE t.id = NEW.farm_task_id;

        IF task_location_id IS NULL OR task_location_id <> NEW.location_id THEN
            RAISE EXCEPTION 'expense_event % location does not match its farm task', NEW.id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_expense_event_farm_task_scope ON expense_event;
CREATE TRIGGER trg_expense_event_farm_task_scope
    BEFORE INSERT OR UPDATE OF farm_task_id, location_id
    ON expense_event
    FOR EACH ROW
    EXECUTE FUNCTION validate_expense_event_farm_task_scope();

CREATE TABLE IF NOT EXISTS farm_task_dependency (
    task_id UUID NOT NULL REFERENCES farm_task(id) ON DELETE CASCADE,
    prerequisite_task_id UUID NOT NULL REFERENCES farm_task(id) ON DELETE CASCADE,
    source_system TEXT,
    source_database_id BIGINT,
    source_table_id BIGINT,
    source_field_id BIGINT,
    source_row_id BIGINT,
    source_related_table_id BIGINT,
    source_related_row_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (task_id, prerequisite_task_id),
    CONSTRAINT chk_farm_task_dependency_not_self CHECK (task_id <> prerequisite_task_id),
    CONSTRAINT chk_farm_task_dependency_source_identity CHECK (
        (
            source_system IS NULL AND source_database_id IS NULL
            AND source_table_id IS NULL AND source_field_id IS NULL
            AND source_row_id IS NULL AND source_related_table_id IS NULL
            AND source_related_row_id IS NULL
        )
        OR
        (
            source_system IS NOT NULL AND btrim(source_system) <> ''
            AND source_database_id IS NOT NULL AND source_database_id > 0
            AND source_table_id IS NOT NULL AND source_table_id > 0
            AND source_field_id IS NOT NULL AND source_field_id > 0
            AND source_row_id IS NOT NULL AND source_row_id > 0
            AND source_related_table_id IS NOT NULL AND source_related_table_id > 0
            AND source_related_row_id IS NOT NULL AND source_related_row_id > 0
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_farm_task_dependency_source_edge
    ON farm_task_dependency (
        source_system, source_database_id, source_table_id, source_field_id,
        source_row_id, source_related_table_id, source_related_row_id
    )
    WHERE source_system IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_farm_task_dependency_prerequisite
    ON farm_task_dependency(prerequisite_task_id);

CREATE TABLE IF NOT EXISTS farm_task_framework_step (
    task_id UUID NOT NULL REFERENCES farm_task(id) ON DELETE CASCADE,
    framework_step_id UUID NOT NULL REFERENCES framework_step(id) ON DELETE CASCADE,
    source_system TEXT,
    source_database_id BIGINT,
    source_table_id BIGINT,
    source_field_id BIGINT,
    source_row_id BIGINT,
    source_related_table_id BIGINT,
    source_related_row_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (task_id, framework_step_id),
    CONSTRAINT chk_farm_task_framework_step_source_identity CHECK (
        (
            source_system IS NULL AND source_database_id IS NULL
            AND source_table_id IS NULL AND source_field_id IS NULL
            AND source_row_id IS NULL AND source_related_table_id IS NULL
            AND source_related_row_id IS NULL
        )
        OR
        (
            source_system IS NOT NULL AND btrim(source_system) <> ''
            AND source_database_id IS NOT NULL AND source_database_id > 0
            AND source_table_id IS NOT NULL AND source_table_id > 0
            AND source_field_id IS NOT NULL AND source_field_id > 0
            AND source_row_id IS NOT NULL AND source_row_id > 0
            AND source_related_table_id IS NOT NULL AND source_related_table_id > 0
            AND source_related_row_id IS NOT NULL AND source_related_row_id > 0
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_farm_task_framework_step_source_edge
    ON farm_task_framework_step (
        source_system, source_database_id, source_table_id, source_field_id,
        source_row_id, source_related_table_id, source_related_row_id
    )
    WHERE source_system IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_farm_task_framework_step_step
    ON farm_task_framework_step(framework_step_id);

CREATE TABLE IF NOT EXISTS farm_task_weekly_plan (
    task_id UUID NOT NULL REFERENCES farm_task(id) ON DELETE CASCADE,
    weekly_plan_id UUID NOT NULL REFERENCES weekly_plan(id) ON DELETE CASCADE,
    source_system TEXT,
    source_database_id BIGINT,
    source_table_id BIGINT,
    source_field_id BIGINT,
    source_row_id BIGINT,
    source_related_table_id BIGINT,
    source_related_row_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (task_id, weekly_plan_id),
    CONSTRAINT chk_farm_task_weekly_plan_source_identity CHECK (
        (
            source_system IS NULL AND source_database_id IS NULL
            AND source_table_id IS NULL AND source_field_id IS NULL
            AND source_row_id IS NULL AND source_related_table_id IS NULL
            AND source_related_row_id IS NULL
        )
        OR
        (
            source_system IS NOT NULL AND btrim(source_system) <> ''
            AND source_database_id IS NOT NULL AND source_database_id > 0
            AND source_table_id IS NOT NULL AND source_table_id > 0
            AND source_field_id IS NOT NULL AND source_field_id > 0
            AND source_row_id IS NOT NULL AND source_row_id > 0
            AND source_related_table_id IS NOT NULL AND source_related_table_id > 0
            AND source_related_row_id IS NOT NULL AND source_related_row_id > 0
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_farm_task_weekly_plan_source_edge
    ON farm_task_weekly_plan (
        source_system, source_database_id, source_table_id, source_field_id,
        source_row_id, source_related_table_id, source_related_row_id
    )
    WHERE source_system IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_farm_task_weekly_plan_plan
    ON farm_task_weekly_plan(weekly_plan_id);

COMMENT ON COLUMN expense_event.farm_task_id IS
    'Optional task association; task and expense must share the same location.';
COMMENT ON TABLE farm_task_dependency IS
    'Directed task prerequisite edges: task_id depends on prerequisite_task_id.';
COMMENT ON TABLE farm_task_framework_step IS
    'Many-to-many associations between farm tasks and canonical framework steps.';
COMMENT ON TABLE farm_task_weekly_plan IS
    'Many-to-many associations between farm tasks and weekly plans.';

COMMIT;
