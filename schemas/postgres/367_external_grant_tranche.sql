-- ============================================================
-- 367_external_grant_tranche.sql
-- Model grant-round tranche metadata separately from cash transactions.
-- The source program date is not a cash-settlement date; amount fields
-- remain outside this model until their accounting relationship is approved.
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS external_grant_tranche (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    program_name TEXT NOT NULL CHECK (BTRIM(program_name) <> ''),
    program_date DATE NOT NULL,
    source_system TEXT NOT NULL CHECK (BTRIM(source_system) <> ''),
    source_database_id BIGINT NOT NULL CHECK (source_database_id > 0),
    source_table_id BIGINT NOT NULL CHECK (source_table_id > 0),
    source_row_id BIGINT NOT NULL CHECK (source_row_id > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_external_grant_tranche_source_identity UNIQUE (
        source_system, source_database_id, source_table_id, source_row_id
    )
);

CREATE INDEX IF NOT EXISTS idx_external_grant_tranche_location
    ON external_grant_tranche(location_id);

CREATE TABLE IF NOT EXISTS external_grant_tranche_funder (
    tranche_id UUID NOT NULL
        REFERENCES external_grant_tranche(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL
        REFERENCES organization(id) ON DELETE RESTRICT,
    source_system TEXT NOT NULL CHECK (BTRIM(source_system) <> ''),
    source_database_id BIGINT NOT NULL CHECK (source_database_id > 0),
    source_table_id BIGINT NOT NULL CHECK (source_table_id > 0),
    source_field_id BIGINT NOT NULL CHECK (source_field_id > 0),
    source_row_id BIGINT NOT NULL CHECK (source_row_id > 0),
    source_related_table_id BIGINT NOT NULL CHECK (source_related_table_id > 0),
    source_related_row_id BIGINT NOT NULL CHECK (source_related_row_id > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tranche_id, organization_id),
    CONSTRAINT fk_external_grant_tranche_funder_source_row
        FOREIGN KEY (source_system, source_database_id, source_table_id, source_row_id)
        REFERENCES external_grant_tranche
            (source_system, source_database_id, source_table_id, source_row_id)
        ON DELETE CASCADE,
    CONSTRAINT uq_external_grant_tranche_funder_source_edge UNIQUE (
        source_system, source_database_id, source_table_id, source_field_id,
        source_row_id, source_related_table_id, source_related_row_id
    )
);

CREATE INDEX IF NOT EXISTS idx_external_grant_tranche_funder_organization
    ON external_grant_tranche_funder(organization_id);

COMMENT ON TABLE external_grant_tranche IS
    'External grant-round tranche metadata; program_date is not a cash-settlement date. Reported amount fields are intentionally not represented here.';
COMMENT ON COLUMN external_grant_tranche.location_id IS
    'Required per-tranche location; source rows remain unprojectable until an owner-approved location mapping exists.';
COMMENT ON TABLE external_grant_tranche_funder IS
    'Many-to-many funder/source organizations for an external grant tranche, with source-edge identity for reconciliation.';

COMMIT;
