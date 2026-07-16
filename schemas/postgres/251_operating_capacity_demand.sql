-- ============================================================
-- 251_operating_capacity_demand.sql
-- Capacity signals for the internal and Adelphi operating scopes.
-- ============================================================

CREATE TABLE IF NOT EXISTS operating_capacity_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('internal', 'adelphi')),
    scope_id UUID NOT NULL,
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    available_hours NUMERIC(10,2) NOT NULL CHECK (available_hours >= 0),
    committed_hours NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (committed_hours >= 0),
    protected_hours NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (protected_hours >= 0),
    notes TEXT,
    source VARCHAR(30) NOT NULL DEFAULT 'self_reported'
        CHECK (source IN ('self_reported', 'manager_reviewed', 'system_derived', 'field_coordinator')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'approved', 'superseded')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (period_end >= period_start),
    CHECK (committed_hours + protected_hours <= available_hours)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_operating_capacity_profile_period
    ON operating_capacity_profile(scope_type, scope_id, party_id, period_start, period_end)
    WHERE status <> 'superseded';
CREATE INDEX IF NOT EXISTS idx_operating_capacity_scope
    ON operating_capacity_profile(scope_type, scope_id, period_start, status);

CREATE TABLE IF NOT EXISTS operating_demand_signal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('internal', 'adelphi')),
    scope_id UUID NOT NULL,
    work_type VARCHAR(50) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    required_hours NUMERIC(10,2) NOT NULL CHECK (required_hours >= 0),
    priority VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    source VARCHAR(30) NOT NULL DEFAULT 'planning'
        CHECK (source IN ('planning', 'work_queue', 'field_coordinator', 'stakeholder_request', 'system_derived')),
    source_ref UUID,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'approved', 'fulfilled', 'cancelled')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (period_end >= period_start)
);

CREATE INDEX IF NOT EXISTS idx_operating_demand_scope
    ON operating_demand_signal(scope_type, scope_id, period_start, status);
CREATE INDEX IF NOT EXISTS idx_operating_demand_type
    ON operating_demand_signal(work_type, period_start, status);

CREATE OR REPLACE VIEW v_operating_capacity_gap AS
WITH capacity AS (
    SELECT scope_type, scope_id, period_start, period_end,
           SUM(available_hours - committed_hours - protected_hours) AS available_hours
    FROM operating_capacity_profile
    WHERE status IN ('submitted', 'approved')
    GROUP BY scope_type, scope_id, period_start, period_end
), demand AS (
    SELECT scope_type, scope_id, work_type, period_start, period_end,
           SUM(required_hours) AS required_hours,
           MAX(CASE priority WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END) AS priority_rank
    FROM operating_demand_signal
    WHERE status IN ('submitted', 'approved')
    GROUP BY scope_type, scope_id, work_type, period_start, period_end
)
SELECT
    d.scope_type,
    d.scope_id,
    d.work_type,
    d.period_start,
    d.period_end,
    COALESCE(c.available_hours, 0) AS available_hours,
    d.required_hours,
    COALESCE(c.available_hours, 0) - d.required_hours AS net_hours,
    CASE
        WHEN COALESCE(c.available_hours, 0) - d.required_hours < 0 THEN 'gap'
        WHEN COALESCE(c.available_hours, 0) - d.required_hours < d.required_hours * 0.2 THEN 'thin'
        ELSE 'covered'
    END AS coverage_status,
    d.priority_rank
FROM demand d
LEFT JOIN capacity c USING (scope_type, scope_id, period_start, period_end);

DROP TRIGGER IF EXISTS trg_operating_capacity_updated_at ON operating_capacity_profile;
CREATE TRIGGER trg_operating_capacity_updated_at
    BEFORE UPDATE ON operating_capacity_profile
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_operating_demand_updated_at ON operating_demand_signal;
CREATE TRIGGER trg_operating_demand_updated_at
    BEFORE UPDATE ON operating_demand_signal
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE operating_capacity_profile IS 'Time-bounded available, committed, and protected capacity for internal or Adelphi participants';
COMMENT ON TABLE operating_demand_signal IS 'Governed demand signal used to expose staffing and field execution gaps';
