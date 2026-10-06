-- ============================================================
-- 362_farm_staff_membership.sql
-- Typed farm/team membership edges without inferring staff roles or dates.
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS farm_staff_member (
    farm_id UUID NOT NULL REFERENCES farm(id) ON DELETE CASCADE,
    staff_id UUID NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    source_system TEXT,
    source_database_id BIGINT,
    source_table_id BIGINT,
    source_field_id BIGINT,
    source_row_id BIGINT,
    source_related_table_id BIGINT,
    source_related_row_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (farm_id, staff_id),
    CONSTRAINT chk_farm_staff_member_source_identity CHECK (
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

CREATE INDEX IF NOT EXISTS idx_farm_staff_member_staff
    ON farm_staff_member(staff_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_farm_staff_member_source_edge
    ON farm_staff_member(
        source_system,
        source_database_id,
        source_table_id,
        source_field_id,
        source_row_id,
        source_related_table_id,
        source_related_row_id
    )
    WHERE source_system IS NOT NULL;

COMMENT ON TABLE farm_staff_member IS
    'Farm team membership; source link does not imply employment status, role, or dates.';
COMMENT ON COLUMN farm_staff_member.source_field_id IS
    'For the reviewed source map, the canonical edge is emitted from Staff.Projects - Team; validate the reciprocal farm.Team field without duplicating edges.';

COMMIT;
