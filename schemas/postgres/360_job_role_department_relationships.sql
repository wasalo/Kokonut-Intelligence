-- ============================================================
-- 360_job_role_department_relationships.sql
-- Preserve multi-department job-role links as a normalized relation.
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS job_role_department (
    job_role_id UUID NOT NULL REFERENCES job_role(id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES department(id) ON DELETE CASCADE,
    source_system TEXT,
    source_database_id BIGINT,
    source_table_id BIGINT,
    source_field_id BIGINT,
    source_row_id BIGINT,
    source_related_table_id BIGINT,
    source_related_row_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (job_role_id, department_id),
    CONSTRAINT chk_job_role_department_source_identity CHECK (
        (
            source_system IS NULL
            AND source_database_id IS NULL
            AND source_table_id IS NULL
            AND source_field_id IS NULL
            AND source_row_id IS NULL
            AND source_related_table_id IS NULL
            AND source_related_row_id IS NULL
        )
        OR
        (
            source_system IS NOT NULL
            AND btrim(source_system) <> ''
            AND source_database_id IS NOT NULL AND source_database_id > 0
            AND source_table_id IS NOT NULL AND source_table_id > 0
            AND source_field_id IS NOT NULL AND source_field_id > 0
            AND source_row_id IS NOT NULL AND source_row_id > 0
            AND source_related_table_id IS NOT NULL AND source_related_table_id > 0
            AND source_related_row_id IS NOT NULL AND source_related_row_id > 0
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_job_role_department_source_edge
    ON job_role_department (
        source_system,
        source_database_id,
        source_table_id,
        source_field_id,
        source_row_id,
        source_related_table_id,
        source_related_row_id
    )
    WHERE source_system IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_job_role_department_department
    ON job_role_department(department_id);

COMMENT ON TABLE job_role_department IS
    'Many-to-many job-role/department assignments; department_id on job_role remains a legacy single-link field.';
COMMENT ON COLUMN job_role_department.source_field_id IS
    'Optional source-link field provenance for the canonical relationship edge.';

COMMIT;
