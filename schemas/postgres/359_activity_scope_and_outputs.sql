-- ============================================================
-- 359_activity_scope_and_outputs.sql
-- Typed activity duration/scope, multi-valued links, and activity outputs.
-- ============================================================

ALTER TABLE farm_activity
    ADD COLUMN IF NOT EXISTS farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS farm_task_id UUID REFERENCES farm_task(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS duration_minutes INTEGER,
    ADD COLUMN IF NOT EXISTS activity_end_date DATE;

ALTER TABLE farm_activity
    DROP CONSTRAINT IF EXISTS chk_farm_activity_duration_minutes,
    ADD CONSTRAINT chk_farm_activity_duration_minutes
        CHECK (duration_minutes >= 0),
    DROP CONSTRAINT IF EXISTS chk_farm_activity_end_date,
    ADD CONSTRAINT chk_farm_activity_end_date
        CHECK (activity_end_date IS NULL OR activity_end_date >= activity_date);

CREATE INDEX IF NOT EXISTS idx_farm_activity_farm ON farm_activity(farm_id);
CREATE INDEX IF NOT EXISTS idx_farm_activity_task ON farm_activity(farm_task_id);
CREATE INDEX IF NOT EXISTS idx_farm_activity_end_date ON farm_activity(activity_end_date);

CREATE OR REPLACE FUNCTION validate_farm_activity_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    expected_location UUID;
    plot_farm_id UUID;
    task_farm_id UUID;
    task_location_id UUID;
BEGIN
    IF NEW.farm_id IS NOT NULL THEN
        SELECT f.location_id INTO expected_location
        FROM farm f
        WHERE f.id = NEW.farm_id;
        IF expected_location IS NULL OR expected_location <> NEW.location_id THEN
            RAISE EXCEPTION 'farm_activity % location does not match its farm', NEW.id;
        END IF;
    END IF;

    IF NEW.plot_id IS NOT NULL THEN
        SELECT p.farm_id, f.location_id INTO plot_farm_id, expected_location
        FROM plot p
        JOIN farm f ON f.id = p.farm_id
        WHERE p.id = NEW.plot_id;
        IF plot_farm_id IS NULL OR expected_location IS NULL
           OR expected_location <> NEW.location_id THEN
            RAISE EXCEPTION 'farm_activity % location does not match its plot', NEW.id;
        END IF;
        IF NEW.farm_id IS NOT NULL AND plot_farm_id <> NEW.farm_id THEN
            RAISE EXCEPTION 'farm_activity % farm does not match its plot', NEW.id;
        END IF;
    END IF;

    IF NEW.farm_task_id IS NOT NULL THEN
        SELECT t.farm_id, t.location_id INTO task_farm_id, task_location_id
        FROM farm_task t
        WHERE t.id = NEW.farm_task_id;
        IF task_location_id IS NULL OR task_location_id <> NEW.location_id THEN
            RAISE EXCEPTION 'farm_activity % location does not match its task', NEW.id;
        END IF;
        IF NEW.farm_id IS NOT NULL AND task_farm_id IS NOT NULL
           AND task_farm_id <> NEW.farm_id THEN
            RAISE EXCEPTION 'farm_activity % farm does not match its task', NEW.id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_farm_activity_scope ON farm_activity;
CREATE TRIGGER trg_farm_activity_scope
    BEFORE INSERT OR UPDATE OF farm_id, farm_task_id, plot_id, location_id
    ON farm_activity
    FOR EACH ROW
    EXECUTE FUNCTION validate_farm_activity_scope();

CREATE TABLE IF NOT EXISTS farm_activity_responsible_staff (
    activity_id UUID NOT NULL REFERENCES farm_activity(id) ON DELETE CASCADE,
    staff_id UUID NOT NULL REFERENCES staff(id) ON DELETE RESTRICT,
    source_system TEXT NOT NULL,
    source_database_id BIGINT NOT NULL,
    source_table_id BIGINT NOT NULL,
    source_field_id BIGINT NOT NULL,
    source_row_id BIGINT NOT NULL,
    source_related_table_id BIGINT NOT NULL,
    source_related_row_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (activity_id, staff_id),
    CONSTRAINT uq_farm_activity_responsible_source_edge UNIQUE (
        source_system, source_database_id, source_table_id, source_field_id,
        source_row_id, source_related_table_id, source_related_row_id
    )
);

CREATE INDEX IF NOT EXISTS idx_farm_activity_responsible_staff_staff
    ON farm_activity_responsible_staff(staff_id);

CREATE TABLE IF NOT EXISTS farm_activity_plot (
    activity_id UUID NOT NULL REFERENCES farm_activity(id) ON DELETE CASCADE,
    plot_id UUID NOT NULL REFERENCES plot(id) ON DELETE RESTRICT,
    source_system TEXT NOT NULL,
    source_database_id BIGINT NOT NULL,
    source_table_id BIGINT NOT NULL,
    source_field_id BIGINT NOT NULL,
    source_row_id BIGINT NOT NULL,
    source_related_table_id BIGINT NOT NULL,
    source_related_row_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (activity_id, plot_id),
    CONSTRAINT uq_farm_activity_plot_source_edge UNIQUE (
        source_system, source_database_id, source_table_id, source_field_id,
        source_row_id, source_related_table_id, source_related_row_id
    )
);

CREATE INDEX IF NOT EXISTS idx_farm_activity_plot_plot
    ON farm_activity_plot(plot_id);

CREATE OR REPLACE FUNCTION validate_farm_activity_plot_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    activity_farm_id UUID;
    activity_location_id UUID;
    plot_farm_id UUID;
    plot_location_id UUID;
BEGIN
    SELECT fa.farm_id, fa.location_id
      INTO activity_farm_id, activity_location_id
    FROM farm_activity fa
    WHERE fa.id = NEW.activity_id;

    SELECT p.farm_id, f.location_id
      INTO plot_farm_id, plot_location_id
    FROM plot p
    JOIN farm f ON f.id = p.farm_id
    WHERE p.id = NEW.plot_id;

    IF activity_location_id IS NULL OR plot_location_id IS NULL
       OR activity_location_id <> plot_location_id THEN
        RAISE EXCEPTION 'farm_activity_plot location does not match its activity';
    END IF;
    IF activity_farm_id IS NOT NULL AND plot_farm_id <> activity_farm_id THEN
        RAISE EXCEPTION 'farm_activity_plot farm does not match its activity';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_farm_activity_plot_scope ON farm_activity_plot;
CREATE TRIGGER trg_farm_activity_plot_scope
    BEFORE INSERT OR UPDATE OF activity_id, plot_id
    ON farm_activity_plot
    FOR EACH ROW
    EXECUTE FUNCTION validate_farm_activity_plot_scope();

CREATE TABLE IF NOT EXISTS farm_activity_output (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    output_name VARCHAR(255) NOT NULL CHECK (BTRIM(output_name) <> ''),
    description TEXT,
    proof_url TEXT,
    source_system TEXT NOT NULL,
    source_database_id BIGINT NOT NULL,
    source_table_id BIGINT NOT NULL,
    source_row_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_farm_activity_output_source_identity UNIQUE (
        source_system, source_database_id, source_table_id, source_row_id
    )
);

CREATE TABLE IF NOT EXISTS farm_activity_output_activity (
    output_id UUID NOT NULL REFERENCES farm_activity_output(id) ON DELETE CASCADE,
    activity_id UUID NOT NULL REFERENCES farm_activity(id) ON DELETE CASCADE,
    source_system TEXT NOT NULL,
    source_database_id BIGINT NOT NULL,
    source_table_id BIGINT NOT NULL,
    source_field_id BIGINT NOT NULL,
    source_row_id BIGINT NOT NULL,
    source_related_table_id BIGINT NOT NULL,
    source_related_row_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (output_id, activity_id),
    CONSTRAINT uq_farm_activity_output_source_edge UNIQUE (
        source_system, source_database_id, source_table_id, source_field_id,
        source_row_id, source_related_table_id, source_related_row_id
    )
);

CREATE INDEX IF NOT EXISTS idx_farm_activity_output_activity_activity
    ON farm_activity_output_activity(activity_id);

COMMENT ON COLUMN farm_activity.duration_minutes IS
    'Elapsed activity time in whole minutes; distinct from labor_hours.';
COMMENT ON TABLE farm_activity_responsible_staff IS
    'Staff accountable or assigned to an activity; this relation does not allocate labor hours.';
COMMENT ON TABLE farm_activity_plot IS
    'All plot links for an activity; farm_activity.plot_id is populated only for a single-plot association.';
COMMENT ON TABLE farm_activity_output IS
    'Activity outputs and proof URLs; not formal impact claims. File attachments require manual curation.';

INSERT INTO schema_version (version, description, applied_by)
VALUES (
    'activity-scope-outputs-v1',
    'Typed farm activity scope, duration, staff/plot/output relations (schema 359)',
    'schema 359'
)
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
