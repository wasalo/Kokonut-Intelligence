-- 157_pest_trap_monitoring.sql
-- Trap monitoring, mode of action rotation tracking
-- Extends 149 and 156 pest management tables

BEGIN;

-- ============================================================
-- PEST MONITORING TRAPS
-- Pheromone traps, sticky traps, light traps, pitfall traps
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_trap (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id         UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id             UUID,

    trap_name           VARCHAR(200) NOT NULL,
    trap_type           VARCHAR(100) NOT NULL CHECK (trap_type IN (
        'pheromone', 'sticky', 'light', 'pitfall', 'sweep_net'
    )),
    target_pest         VARCHAR(200),
    lure_type           VARCHAR(200),
    install_date        DATE NOT NULL,
    lat                 NUMERIC(9,6),
    lon                 NUMERIC(9,6),

    status              VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pest_trap_location ON pest_trap (location_id, status);
CREATE INDEX IF NOT EXISTS idx_pest_trap_type ON pest_trap (trap_type);
CREATE INDEX IF NOT EXISTS idx_pest_trap_pest ON pest_trap (target_pest);

-- ============================================================
-- TRAP CATCH RECORDS
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_trap_catch (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trap_id             UUID NOT NULL REFERENCES pest_trap(id) ON DELETE CASCADE,

    check_date          DATE NOT NULL,
    pest_count          INTEGER NOT NULL DEFAULT 0,
    bycatch_count       INTEGER DEFAULT 0,
    beneficial_count    INTEGER DEFAULT 0,
    trap_condition      VARCHAR(50),
    notes               TEXT,
    scouting_record_id  UUID REFERENCES pest_scouting_record(id) ON DELETE SET NULL,

    status              VARCHAR(50) NOT NULL DEFAULT 'recorded',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trap_catch_trap ON pest_trap_catch (trap_id, check_date DESC);
CREATE INDEX IF NOT EXISTS idx_trap_catch_date ON pest_trap_catch (check_date DESC);

-- ============================================================
-- MODE OF ACTION REFERENCE
-- IRAC, FRAC, HRAC codes for resistance management
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_mode_of_action (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chemical_class          VARCHAR(100) NOT NULL UNIQUE,
    moa_code                VARCHAR(50) NOT NULL,
    irac_group              VARCHAR(200),
    frac_group              VARCHAR(200),
    hrac_group              VARCHAR(200),
    mode_of_action          TEXT NOT NULL,
    cross_resistance        JSONB DEFAULT '[]',
    rotation_compatibility  JSONB DEFAULT '[]',
    notes                   TEXT,
    status                  VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_moa_code ON pest_mode_of_action (moa_code);
CREATE INDEX IF NOT EXISTS idx_moa_class ON pest_mode_of_action (chemical_class);

-- ============================================================
-- ROTATION COMPLIANCE CHECKS
-- ============================================================

CREATE TABLE IF NOT EXISTS pest_rotation_check (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id             UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    check_date              DATE NOT NULL,
    chemical_class_used     VARCHAR(100),
    previous_class          VARCHAR(100),
    rotation_ok             BOOLEAN NOT NULL,
    days_since_last_class   INTEGER,
    recommendation          TEXT,
    pesticide_application_id UUID REFERENCES pesticide_application_log(id) ON DELETE SET NULL,
    status                  VARCHAR(50) NOT NULL DEFAULT 'recorded',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rotation_check_location ON pest_rotation_check (location_id, check_date DESC);

-- ============================================================
-- VIEWS
-- ============================================================

CREATE OR REPLACE VIEW v_trap_summary AS
SELECT
    pt.location_id,
    pt.trap_name,
    pt.trap_type,
    pt.target_pest,
    pt.install_date,
    COUNT(ptc.id) AS total_checks,
    SUM(ptc.pest_count) AS total_pest_catch,
    AVG(ptc.pest_count) AS avg_pest_per_check,
    MAX(ptc.check_date) AS last_checked
FROM pest_trap pt
LEFT JOIN pest_trap_catch ptc ON ptc.trap_id = pt.id
WHERE pt.status = 'active'
GROUP BY pt.id, pt.location_id, pt.trap_name, pt.trap_type, pt.target_pest, pt.install_date;

CREATE OR REPLACE VIEW v_rotation_compliance AS
SELECT
    prc.location_id,
    prc.check_date,
    prc.chemical_class_used,
    prc.previous_class,
    prc.rotation_ok,
    prc.days_since_last_class,
    prc.recommendation
FROM pest_rotation_check prc
ORDER BY prc.location_id, prc.check_date DESC;

-- ============================================================
-- Schema version
-- ============================================================

INSERT INTO schema_version (version, description, applied_by)
VALUES ('pest-trap-monitoring-v1', 'Trap monitoring, MoA rotation tracking, rotation compliance checks', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;

COMMIT;
